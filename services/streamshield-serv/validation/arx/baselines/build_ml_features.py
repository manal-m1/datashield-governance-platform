"""
STREAMSHIELD - Construction des features pour LightGBM

Objectif :
    Construire les jeux de données TRAIN / VALIDATION / TEST
    utilisés ensuite par LightGBM.

IMPORTANT :
    - Les labels proviennent du protocole ARX existant.
    - Aucun label n'est recalculé ici.
    - average_risk n'est PAS utilisé comme feature afin d'éviter
      une fuite d'information.
    - k et uniqueness sont calculés avec CombinationAnalyzer,
      exactement comme dans FuzzyRiskScorer.
    - avg_sensitivity est calculée avec la même configuration
      de sensibilité que FuzzyRiskScorer.
"""

from pathlib import Path
import sys
import asyncio
# ============================================================================
# CONFIGURATION DU PATH PYTHON
# ============================================================================

# Racine du projet
# /app/validation/arx/baselines/build_ml_features.py
#                    ↑
# parents[0] = baselines
# parents[1] = arx
# parents[2] = validation
# parents[3] = /app

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# IMPORTS
# ============================================================================

import csv
import logging
from typing import Dict, List, Tuple

import pandas as pd

from detection.frequency_counter import CombinationAnalyzer

from detection.field_sensitivity_repository import load_field_sensitivity
from detection.risk_scorer import SENSITIVITY_ENCODING
logger = logging.getLogger("streamshield.build_ml_features")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)


# ============================================================================
# FICHIERS
# ============================================================================

DATASET_PATH = (
    BASE_DIR
    / "data"
    / "validation"
    / "uci_adult"
    / "processed"
    / "adult_prepared.csv"
)

TRAIN_LABELS = (
    BASE_DIR
    / "validation"
    / "arx"
    / "train"
    / "arx_train_labels.csv"
)

VALIDATION_LABELS = (
    BASE_DIR
    / "validation"
    / "arx"
    / "validation"
    / "arx_validation_labels.csv"
)

TEST_LABELS = (
    BASE_DIR
    / "validation"
    / "arx"
    / "test"
    / "arx_test_labels.csv"
)

OUTPUT_DIR = (
    BASE_DIR
    / "validation"
    / "arx"
    / "baselines"
)

# ============================================================================
# UTILITAIRES
# ============================================================================

def normalize_field_name(field: str) -> str:
    """
    Normalise légèrement le nom d'un champ.

    Le dataset et les fichiers de combinaisons doivent normalement
    utiliser les mêmes noms.
    """

    return field.strip()


def parse_combination(combination: str) -> Tuple[str, ...]:
    """
    Transforme :

        'age + sex + education'

    en :

        ('age', 'sex', 'education')
    """

    if not combination:
        return tuple()

    fields = [
        normalize_field_name(field)
        for field in combination.split("+")
    ]

    fields = [
        field
        for field in fields
        if field
    ]

    return tuple(fields)


def calculate_average_sensitivity(
    fields: Tuple[str, ...],
    field_sensitivity: Dict[str, str],
) -> float:
    """
    Calcule la sensibilité moyenne exactement selon le principe
    utilisé dans FuzzyRiskScorer.
    """

    if not fields:
        return 0.0

    values = []

    for field in fields:

        sensitivity_level = field_sensitivity.get(field)

        if sensitivity_level is None:
            logger.warning(
                "Champ '%s' absent de la configuration de sensibilité. "
                "Valeur par défaut utilisée : '%s'.",
                field,
                DEFAULT_SENSITIVITY,
            )

            sensitivity_level = DEFAULT_SENSITIVITY

        if sensitivity_level not in SENSITIVITY_ENCODING:

            logger.warning(
                "Niveau de sensibilité invalide pour '%s' : '%s'. "
                "Valeur par défaut utilisée : '%s'.",
                field,
                sensitivity_level,
                DEFAULT_SENSITIVITY,
            )

            sensitivity_level = DEFAULT_SENSITIVITY

        values.append(
            SENSITIVITY_ENCODING[sensitivity_level]
        )

    return sum(values) / len(values)


# ============================================================================
# CHARGEMENT DES LABELS
# ============================================================================

def load_labels(path: Path) -> pd.DataFrame:
    """
    Charge un fichier de labels ARX.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    df = pd.read_csv(path)

    required_columns = {
        "id",
        "combination",
        "num_qi",
        "num_records",
        "average_risk",
        "label",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {path}: {sorted(missing)}"
        )

    return df


# ============================================================================
# CALCUL DES FEATURES
# ============================================================================

def build_features(
    labels_df: pd.DataFrame,
    records: List[dict],
    field_sensitivity: Dict[str, str],
) -> pd.DataFrame:
    """
    Construit les features ML pour un split.

    Features retenues :

        num_qi
        k
        uniqueness
        avg_sensitivity

    Target :

        label

    L'identifiant et la combinaison sont conservés uniquement
    pour permettre l'analyse des résultats.
    """

    rows = []

    for _, row in labels_df.iterrows():

        combination_id = str(row["id"])
        combination = str(row["combination"])

        fields = parse_combination(combination)

        if not fields:
            raise ValueError(
                f"Combinaison vide pour {combination_id}"
            )

        # ------------------------------------------------------------
        # Vérification des champs
        # ------------------------------------------------------------

        missing_fields = [
            field
            for field in fields
            if field not in records[0]
        ]

        if missing_fields:
            raise ValueError(
                f"{combination_id} : champs absents du dataset : "
                f"{missing_fields}"
            )

        # ------------------------------------------------------------
        # Analyse de la combinaison
        # ------------------------------------------------------------

        analysis = CombinationAnalyzer.analyze(
            records,
            fields,
        )

        k = analysis["k"]

        uniqueness = analysis["uniqueness"]

        sample_size = analysis["sample_size"]

        # ------------------------------------------------------------
        # Sensibilité
        # ------------------------------------------------------------

        avg_sensitivity = calculate_average_sensitivity(
            fields,
            field_sensitivity,
        )

        # ------------------------------------------------------------
        # Label de référence
        # ------------------------------------------------------------

        label = int(row["label"])

        # ------------------------------------------------------------
        # Features finales
        # ------------------------------------------------------------

        rows.append(
            {
                "id": combination_id,
                "combination": combination,
                "num_qi": int(row["num_qi"]),
                "k": int(k),
                "uniqueness": float(uniqueness),
                "avg_sensitivity": float(avg_sensitivity),
                "sample_size": int(sample_size),
                "label": label,
            }
        )

    return pd.DataFrame(rows)


# ============================================================================
# VERIFICATION
# ============================================================================

def verify_features(
    df: pd.DataFrame,
    split_name: str,
) -> None:

    print()
    print("=" * 70)
    print(f"VERIFICATION FEATURES - {split_name}")
    print("=" * 70)

    print(
        f"Nombre de combinaisons : {len(df)}"
    )

    print(
        f"Nombre de positives : "
        f"{int((df['label'] == 1).sum())}"
    )

    print(
        f"Nombre de négatives : "
        f"{int((df['label'] == 0).sum())}"
    )

    print()

    print("Features utilisées :")

    feature_columns = [
        "num_qi",
        "k",
        "uniqueness",
        "avg_sensitivity",
        "sample_size",
    ]

    for column in feature_columns:

        print(
            f"  {column:20s} | "
            f"min={df[column].min():.4f} | "
            f"max={df[column].max():.4f}"
        )

    print()

    print("Répartition des labels :")

    print(
        df["label"]
        .value_counts()
        .sort_index()
        .to_string()
    )


# ============================================================================
# SAUVEGARDE
# ============================================================================

def save_features(
    df: pd.DataFrame,
    path: Path,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        path,
        index=False,
        encoding="utf-8",
    )

    print(
        f"\nFeatures sauvegardées : {path}"
    )


# ============================================================================
# MAIN
# ============================================================================

async def main():

    print("=" * 70)
    print("       STREAMSHIELD - BUILD ML FEATURES")
    print("=" * 70)

    # ------------------------------------------------------------------------
    # Dataset
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("CHARGEMENT DU DATASET UCI ADULT")
    print("=" * 70)

    print(f"Fichier : {DATASET_PATH}")

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset introuvable : {DATASET_PATH}"
        )

    dataset_df = pd.read_csv(
        DATASET_PATH
    )

    print(
        f"Nombre de records : {len(dataset_df)}"
    )

    print(
        f"Nombre de colonnes : {len(dataset_df.columns)}"
    )

    records = dataset_df.to_dict(
        orient="records"
    )

    if not records:
        raise ValueError(
            "Le dataset est vide."
        )

    # ------------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("CHARGEMENT DES LABELS ARX")
    print("=" * 70)

    train_df = load_labels(
        TRAIN_LABELS
    )

    validation_df = load_labels(
        VALIDATION_LABELS
    )

    test_df = load_labels(
        TEST_LABELS
    )

    print(
        f"TRAIN       : {len(train_df)}"
    )

    print(
        f"VALIDATION  : {len(validation_df)}"
    )

    print(
        f"TEST        : {len(test_df)}"
    )

    # ------------------------------------------------------------------------
    # Sensibilité
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("CHARGEMENT DE LA SENSIBILITE")
    print("=" * 70)

    field_sensitivity = await load_field_sensitivity()

    print(
        f"Champs de sensibilité chargés : "
        f"{len(field_sensitivity)}"
    )

    # ------------------------------------------------------------------------
    # TRAIN
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("CONSTRUCTION FEATURES - TRAIN")
    print("=" * 70)

    features_train = build_features(
        train_df,
        records,
        field_sensitivity,
    )

    verify_features(
        features_train,
        "TRAIN",
    )

    # ------------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("CONSTRUCTION FEATURES - VALIDATION")
    print("=" * 70)

    features_validation = build_features(
        validation_df,
        records,
        field_sensitivity,
    )

    verify_features(
        features_validation,
        "VALIDATION",
    )

    # ------------------------------------------------------------------------
    # TEST
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("CONSTRUCTION FEATURES - TEST")
    print("=" * 70)

    features_test = build_features(
        test_df,
        records,
        field_sensitivity,
    )

    verify_features(
        features_test,
        "TEST",
    )

    # ------------------------------------------------------------------------
    # Sauvegarde
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("SAUVEGARDE")
    print("=" * 70)

    save_features(
        features_train,
        OUTPUT_DIR / "ml_features_train.csv",
    )

    save_features(
        features_validation,
        OUTPUT_DIR / "ml_features_validation.csv",
    )

    save_features(
        features_test,
        OUTPUT_DIR / "ml_features_test.csv",
    )

    # ------------------------------------------------------------------------
    # Aperçu
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("APERÇU DES FEATURES")
    print("=" * 70)

    print(
        features_train.to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("BUILD ML FEATURES TERMINE")
    print("=" * 70)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    asyncio.run(main())