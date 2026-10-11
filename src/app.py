from utils import db_connect
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "housing.csv"
OUTPUT_PATH = ROOT / "data" / "processed"
MODELS_PATH = ROOT / "models"
DATA_URL = "https://raw.githubusercontent.com/4GeeksAcademy/k-means-project-tutorial/main/housing.csv"
FEATURES = ["Latitude", "Longitude", "MedInc"]
N_CLUSTERS = 6
RANDOM_STATE = 42


def load_data():
	if not DATA_PATH.exists():
		DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
		response = requests.get(DATA_URL, timeout=30)
		response.raise_for_status()
		DATA_PATH.write_bytes(response.content)

	data = pd.read_csv(DATA_PATH)
	missing_columns = set(FEATURES) - set(data.columns)
	if missing_columns:
		raise ValueError(f"El dataset no contiene las columnas requeridas: {sorted(missing_columns)}")

	data = data.dropna(subset=FEATURES).reset_index(drop=True)
	if len(data) < N_CLUSTERS:
		raise ValueError(f"Se necesitan al menos {N_CLUSTERS} filas válidas para entrenar K-Means.")
	return data


def main():
	data = load_data()
	features = data[FEATURES]
	train_indices, test_indices = train_test_split(
		features.index, test_size=0.2, random_state=RANDOM_STATE
	)
	train_features = features.loc[train_indices]
	test_features = features.loc[test_indices]

	kmeans_pipeline = Pipeline(
		[
			("scaler", StandardScaler()),
			("kmeans", KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10)),
		]
	)
	train_clusters = kmeans_pipeline.fit_predict(train_features)
	test_clusters = kmeans_pipeline.predict(test_features)

	classifier = RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1)
	classifier.fit(train_features, train_clusters)
	classifier_predictions = classifier.predict(test_features)

	assignments = data.copy()
	assignments["cluster"] = -1
	assignments["split"] = "train"
	assignments.loc[train_indices, "cluster"] = train_clusters
	assignments.loc[test_indices, "cluster"] = test_clusters
	assignments.loc[test_indices, "split"] = "test"

	OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
	MODELS_PATH.mkdir(parents=True, exist_ok=True)
	assignments.to_csv(OUTPUT_PATH / "housing_clusters.csv", index=False)
	joblib.dump(kmeans_pipeline, MODELS_PATH / "kmeans_pipeline.joblib")
	joblib.dump(classifier, MODELS_PATH / "cluster_classifier.joblib")

	cluster_summary = assignments.groupby("cluster")[FEATURES].median().round(2)
	print(f"Filas analizadas: {len(assignments)} ({len(train_indices)} train, {len(test_indices)} test)")
	print("Medianas por cluster (latitud, longitud e ingreso medio):")
	print(cluster_summary.to_string())
	print("\nRandom Forest frente a las etiquetas K-Means del conjunto test:")
	print(f"Accuracy: {accuracy_score(test_clusters, classifier_predictions):.4f}")
	print(f"Balanced accuracy: {balanced_accuracy_score(test_clusters, classifier_predictions):.4f}")
	print(classification_report(test_clusters, classifier_predictions, zero_division=0))
	print(
		"Nota: estas métricas miden cuánto reproduce el clasificador las etiquetas "
		"K-Means; no son una evaluación frente a regiones reales etiquetadas."
	)

	color_map = plt.get_cmap("tab10", N_CLUSTERS)
	figure, axis = plt.subplots(figsize=(11, 7))
	axis.scatter(
		train_features["Longitude"],
		train_features["Latitude"],
		c=train_clusters,
		cmap=color_map,
		vmin=-0.5,
		vmax=N_CLUSTERS - 0.5,
		s=10,
		alpha=0.45,
		label="Train",
	)
	axis.scatter(
		test_features["Longitude"],
		test_features["Latitude"],
		c=test_clusters,
		cmap=color_map,
		vmin=-0.5,
		vmax=N_CLUSTERS - 0.5,
		marker="x",
		s=22,
		alpha=0.8,
		label="Test (predicción K-Means)",
	)
	colorbar = figure.colorbar(
		plt.cm.ScalarMappable(cmap=color_map, norm=plt.Normalize(-0.5, N_CLUSTERS - 0.5)),
		ax=axis,
		ticks=np.arange(N_CLUSTERS),
	)
	colorbar.set_label("Cluster")
	axis.set(title="California Housing: clusters geográficos y de ingreso", xlabel="Longitud", ylabel="Latitud")
	axis.legend(loc="best")
	axis.grid(alpha=0.2)
	figure.tight_layout()
	figure.savefig(OUTPUT_PATH / "housing_clusters.png", dpi=160)
	plt.close(figure)

	print(f"\nGráfico: {OUTPUT_PATH / 'housing_clusters.png'}")
	print(f"Datos etiquetados: {OUTPUT_PATH / 'housing_clusters.csv'}")
	print(f"Modelos guardados en: {MODELS_PATH}")


if __name__ == "__main__":
	main()
