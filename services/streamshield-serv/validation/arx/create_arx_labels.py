import pandas as pd
from pathlib import Path


# ============================================================
# ETAPE 3 — CREATION DES LABELS A PARTIR DU RISQUE ARX
# ============================================================

# Seuil méthodologique de risque ARX
ARX_THRESHOLD = 0.09


# ------------------------------------------------------------
# Chemins
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "java" / "arx_30_results_step2.csv"
OUTPUT_FILE = BASE_DIR / "java" / "arx_30_labels.csv"


# ------------------------------------------------------------
# Chargement des résultats ARX
# ------------------------------------------------------------

print("=" * 60)
print("       ETAPE 3 : LABELISATION ARX")
print("=" * 60)

print(f"Fichier source : {INPUT_FILE}")

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Fichier introuvable : {INPUT_FILE}"
    )

df = pd.read_csv(INPUT_FILE)

print(f"Nombre de combinaisons chargées : {len(df)}")


# ------------------------------------------------------------
# Vérification des colonnes nécessaires
# ------------------------------------------------------------

required_columns = [
    "id",
    "combination",
    "num_qi",
    "num_records",
    "average_risk",
]

missing = [
    column for column in required_columns
    if column not in df.columns
]

if missing:
    raise ValueError(
        f"Colonnes manquantes dans le fichier ARX : {missing}"
    )


# ------------------------------------------------------------
# Création du label
# ------------------------------------------------------------

df["label"] = (
    df["average_risk"] >= ARX_THRESHOLD
).astype(int)


# ------------------------------------------------------------
# Sélection des colonnes du dataset de labels
# ------------------------------------------------------------

labels = df[
    [
        "id",
        "combination",
        "num_qi",
        "num_records",
        "average_risk",
        "label",
    ]
].copy()


# ------------------------------------------------------------
# Sauvegarde
# ------------------------------------------------------------

labels.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8"
)


# ------------------------------------------------------------
# Statistiques
# ------------------------------------------------------------

num_positive = int((labels["label"] == 1).sum())
num_negative = int((labels["label"] == 0).sum())
total = len(labels)

print()
print("=== PARAMETRE DE LABELISATION ===")
print(f"Seuil ARX : {ARX_THRESHOLD}")
print()
print("Règle :")
print("  average_risk <  0.09 -> label 0")
print("  average_risk >= 0.09 -> label 1")

print()
print("=== DISTRIBUTION DES LABELS ===")
print(f"Label 0 : {num_negative}")
print(f"Label 1 : {num_positive}")
print(f"Total   : {total}")

print()
print("Pourcentages :")
print(f"Label 0 : {100 * num_negative / total:.2f}%")
print(f"Label 1 : {100 * num_positive / total:.2f}%")

print()
print("=== COMBINAISONS LABELISEES 1 ===")

for _, row in labels[labels["label"] == 1].iterrows():
    print(
        f"{row['id']} : "
        f"{row['combination']} "
        f"-> risk={row['average_risk']:.6f}"
    )

print()
print("=== VERIFICATION ===")

invalid = labels[
    (
        (labels["average_risk"] < ARX_THRESHOLD)
        & (labels["label"] != 0)
    )
    |
    (
        (labels["average_risk"] >= ARX_THRESHOLD)
        & (labels["label"] != 1)
    )
]

if len(invalid) == 0:
    print("OK : tous les labels respectent le seuil ARX.")
else:
    print("ERREUR : labels incohérents !")
    print(invalid)

print()
print(f"Dataset sauvegardé dans : {OUTPUT_FILE}")
print("=" * 60)

