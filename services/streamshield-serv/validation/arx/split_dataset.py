import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split


# ============================================================
# STREAMSHIELD - SPLIT TRAIN / VALIDATION / TEST
# ============================================================
#
# Objectif :
#   Séparer les 30 combinaisons ARX existantes en :
#
#       TRAIN       = 18 combinaisons
#       VALIDATION  =  6 combinaisons
#       TEST        =  6 combinaisons
#
# Le fichier arx_30_labels.csv EXISTE DEJA.
# Ce script ne crée PAS les labels ARX.
#
# Le split est reproductible grâce à random_state=42.
# ============================================================


# ------------------------------------------------------------
# 1. CHEMINS
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "java" / "arx_30_labels.csv"

TRAIN_DIR = BASE_DIR / "train"
VALIDATION_DIR = BASE_DIR / "validation"
TEST_DIR = BASE_DIR / "test"

TRAIN_FILE = TRAIN_DIR / "arx_train_labels.csv"
VALIDATION_FILE = VALIDATION_DIR / "arx_validation_labels.csv"
TEST_FILE = TEST_DIR / "arx_test_labels.csv"


# ------------------------------------------------------------
# 2. PARAMETRES
# ------------------------------------------------------------

RANDOM_STATE = 42

TRAIN_SIZE = 18
VALIDATION_SIZE = 6
TEST_SIZE = 6


# ------------------------------------------------------------
# 3. AFFICHAGE
# ------------------------------------------------------------

print("=" * 70)
print("       STREAMSHIELD - SPLIT TRAIN / VALIDATION / TEST")
print("=" * 70)

print()
print(f"Fichier source : {INPUT_FILE}")
print(f"Random state   : {RANDOM_STATE}")
print()
print("Répartition prévue :")
print(f"  TRAIN       : {TRAIN_SIZE}")
print(f"  VALIDATION  : {VALIDATION_SIZE}")
print(f"  TEST        : {TEST_SIZE}")
print(f"  TOTAL       : {TRAIN_SIZE + VALIDATION_SIZE + TEST_SIZE}")


# ------------------------------------------------------------
# 4. VERIFICATION DU FICHIER
# ------------------------------------------------------------

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Fichier ARX introuvable : {INPUT_FILE}"
    )


# ------------------------------------------------------------
# 5. CHARGEMENT
# ------------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print()
print("=== DATASET SOURCE ===")
print(f"Nombre de lignes : {len(df)}")
print(f"Colonnes         : {list(df.columns)}")


# ------------------------------------------------------------
# 6. VERIFICATION DES COLONNES
# ------------------------------------------------------------

required_columns = [
    "id",
    "combination",
    "num_qi",
    "num_records",
    "average_risk",
    "label",
]

missing = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing:
    raise ValueError(
        f"Colonnes manquantes : {missing}"
    )


# ------------------------------------------------------------
# 7. VERIFICATION DU NOMBRE DE COMBINAISONS
# ------------------------------------------------------------

if len(df) != 30:
    raise ValueError(
        f"Le fichier doit contenir exactement 30 combinaisons. "
        f"Nombre trouvé : {len(df)}"
    )


# ------------------------------------------------------------
# 8. CREATION DE LA STRATIFICATION
# ------------------------------------------------------------
#
# On conserve simultanément :
#
#   - le label ARX
#   - le nombre de QI
#
# Exemple :
#
#   2 QI + label 0
#   2 QI + label 1
#   3 QI + label 0
#   3 QI + label 1
#   4 QI + label 0
#   4 QI + label 1
#
# ------------------------------------------------------------

# ------------------------------------------------------------
# 8. DISTRIBUTION INITIALE
# ------------------------------------------------------------

print()
print("=== DISTRIBUTION INITIALE ===")

print(
    df.groupby(["num_qi", "label"])
      .size()
      .to_string()
)
# ------------------------------------------------------------
# 10. PREMIER SPLIT
# ------------------------------------------------------------
#
# 18 TRAIN
# 12 TEMPORARY
#
# Le temporary sera ensuite séparé en :
#
#   6 VALIDATION
#   6 TEST
#
# ------------------------------------------------------------

train_df, temp_df = train_test_split(
    df,
    train_size=TRAIN_SIZE,
    test_size=VALIDATION_SIZE + TEST_SIZE,
    random_state=RANDOM_STATE,
    stratify=df["label"],
)


# ------------------------------------------------------------
# 11. DEUXIEME SPLIT
# ------------------------------------------------------------
#
# 12 TEMPORARY
#
#       6 VALIDATION
#       6 TEST
#
# ------------------------------------------------------------

validation_df, test_df = train_test_split(
    temp_df,
    train_size=VALIDATION_SIZE,
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE,
    stratify=temp_df["label"],
)


# ------------------------------------------------------------
# 12. SUPPRESSION DE LA COLONNE TECHNIQUE
# ------------------------------------------------------------

# ------------------------------------------------------------
# 13. TRI PAR ID
# ------------------------------------------------------------

train_df = train_df.sort_values("id").reset_index(drop=True)
validation_df = validation_df.sort_values("id").reset_index(drop=True)
test_df = test_df.sort_values("id").reset_index(drop=True)


# ------------------------------------------------------------
# 14. CREATION DES DOSSIERS
# ------------------------------------------------------------

TRAIN_DIR.mkdir(parents=True, exist_ok=True)
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
TEST_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# 15. SAUVEGARDE
# ------------------------------------------------------------

train_df.to_csv(
    TRAIN_FILE,
    index=False,
    encoding="utf-8",
)

validation_df.to_csv(
    VALIDATION_FILE,
    index=False,
    encoding="utf-8",
)

test_df.to_csv(
    TEST_FILE,
    index=False,
    encoding="utf-8",
)


# ------------------------------------------------------------
# 16. FONCTION D'AFFICHAGE DES STATISTIQUES
# ------------------------------------------------------------

def print_statistics(name, data):
    print()
    print("=" * 70)
    print(f"{name}")
    print("=" * 70)

    print(f"Nombre de combinaisons : {len(data)}")

    print()
    print("Distribution par nombre de QI et label :")

    print(
        data.groupby(["num_qi", "label"])
            .size()
            .to_string()
    )

    print()
    print("Distribution des labels :")

    counts = data["label"].value_counts().sort_index()

    for label in [0, 1]:
        count = int(counts.get(label, 0))

        print(
            f"  Label {label} : "
            f"{count} "
            f"({100 * count / len(data):.2f}%)"
        )

    print()
    print("Combinaisons :")

    for _, row in data.iterrows():

        print(
            f"  {row['id']} | "
            f"{row['combination']} | "
            f"QI={row['num_qi']} | "
            f"ARX={row['average_risk']:.6f} | "
            f"label={row['label']}"
        )


# ------------------------------------------------------------
# 17. AFFICHAGE
# ------------------------------------------------------------

print_statistics("TRAIN", train_df)
print_statistics("VALIDATION", validation_df)
print_statistics("TEST", test_df)


# ------------------------------------------------------------
# 18. VERIFICATION FINALE
# ------------------------------------------------------------

print()
print("=" * 70)
print("                 VERIFICATION FINALE")
print("=" * 70)

total = (
    len(train_df)
    + len(validation_df)
    + len(test_df)
)

print(f"TRAIN       : {len(train_df)}")
print(f"VALIDATION  : {len(validation_df)}")
print(f"TEST        : {len(test_df)}")
print(f"TOTAL       : {total}")


# Vérification des IDs uniques

train_ids = set(train_df["id"])
validation_ids = set(validation_df["id"])
test_ids = set(test_df["id"])

if train_ids & validation_ids:
    raise RuntimeError(
        "ERREUR : chevauchement TRAIN / VALIDATION"
    )

if train_ids & test_ids:
    raise RuntimeError(
        "ERREUR : chevauchement TRAIN / TEST"
    )

if validation_ids & test_ids:
    raise RuntimeError(
        "ERREUR : chevauchement VALIDATION / TEST"
    )

all_ids = train_ids | validation_ids | test_ids

if len(all_ids) != 30:
    raise RuntimeError(
        "ERREUR : les 30 combinaisons ne sont pas réparties correctement."
    )


# Vérification des tailles

if len(train_df) != TRAIN_SIZE:
    raise RuntimeError("Taille TRAIN incorrecte.")

if len(validation_df) != VALIDATION_SIZE:
    raise RuntimeError("Taille VALIDATION incorrecte.")

if len(test_df) != TEST_SIZE:
    raise RuntimeError("Taille TEST incorrecte.")


print()
print("OK : 30 combinaisons réparties.")
print("OK : aucune combinaison dupliquée entre les ensembles.")
print("OK : TRAIN = 18.")
print("OK : VALIDATION = 6.")
print("OK : TEST = 6.")


# ------------------------------------------------------------
# 19. FICHIERS CREES
# ------------------------------------------------------------

print()
print("=" * 70)
print("                 FICHIERS CREES")
print("=" * 70)

print(f"TRAIN      : {TRAIN_FILE}")
print(f"VALIDATION : {VALIDATION_FILE}")
print(f"TEST       : {TEST_FILE}")

print()
print("Split terminé avec succès.")
print("=" * 70)

