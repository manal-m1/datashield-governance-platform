#ce sript Il conserve les données originales (adult.data)intact les valeurs inconnues:? transforme en:NaN
from pathlib import Path
import pandas as pd


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

RAW_FILE = (
    BASE_DIR
    / "data"
    / "validation"
    / "uci_adult"
    / "raw"
    / "adult.data"
)

OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "validation"
    / "uci_adult"
    / "processed"
)

OUTPUT_FILE = OUTPUT_DIR / "adult_prepared.csv"


# ============================================================
# Colonnes officielles UCI Adult
# ============================================================

COLUMNS = [
    "age",
    "workclass",
    "fnlwgt",
    "education",
    "education-num",
    "marital-status",
    "occupation",
    "relationship",
    "race",
    "sex",
    "capital-gain",
    "capital-loss",
    "hours-per-week",
    "native-country",
    "income",
]


# ============================================================
# Lecture du fichier original
# ============================================================

df = pd.read_csv(
    RAW_FILE,
    names=COLUMNS,
    sep=",",
    skipinitialspace=True,
    na_values="?",
)


# ============================================================
# Nettoyage des espaces résiduels
# ============================================================

for column in df.select_dtypes(include="object").columns:
    df[column] = df[column].str.strip()


# ============================================================
# Vérifications
# ============================================================

print("=== UCI ADULT ===")
print(f"Fichier source : {RAW_FILE}")
print(f"Nombre de lignes : {len(df)}")
print(f"Nombre de colonnes : {len(df.columns)}")

print("\nColonnes :")
print(df.columns.tolist())

print("\nValeurs manquantes :")
print(df.isna().sum())

print("\nPremières lignes :")
print(df.head())


# ============================================================
# Sauvegarde
# ============================================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8",
)

print(f"\nFichier créé : {OUTPUT_FILE}")