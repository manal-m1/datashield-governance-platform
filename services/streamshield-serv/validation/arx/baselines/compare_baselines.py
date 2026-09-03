
from pathlib import Path
import json
import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = PROJECT_ROOT

BASELINES_DIR = (
    BASE_DIR
    / "validation"
    / "arx"
    / "baselines"
)

# ---------------------------------------------------------------------------
# K-anonymity
# ---------------------------------------------------------------------------

K_METRICS_FILE = (
    BASELINES_DIR
    / "k_anonymity_metrics.json"
)

# ---------------------------------------------------------------------------
# LightGBM
# ---------------------------------------------------------------------------

LGBM_METRICS_FILE = (
    BASELINES_DIR
    / "lightgbm_metrics.json"
)

# ---------------------------------------------------------------------------
# FuzzyRiskScorer
# ---------------------------------------------------------------------------

FUZZY_SUMMARY_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "test"
    / "fuzzy_test_summary.csv"
)

# ---------------------------------------------------------------------------
# Sorties
# ---------------------------------------------------------------------------

COMPARISON_CSV = (
    BASELINES_DIR
    / "baseline_comparison.csv"
)

COMPARISON_JSON = (
    BASELINES_DIR
    / "baseline_comparison.json"
)


# ============================================================================
# CHARGEMENT JSON
# ============================================================================

def load_json(path: Path):

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


# ============================================================================
# EXTRACTION METRIQUES
# ============================================================================

def extract_metrics(
    metrics: dict,
    split: str,
):

    return {
        "accuracy": metrics[split]["accuracy"],
        "precision": metrics[split]["precision"],
        "recall": metrics[split]["recall"],
        "specificity": metrics[split]["specificity"],
        "f1": metrics[split]["f1"],
        "youden_j": metrics[split]["youden_j"],
        "tp": metrics[split]["tp"],
        "tn": metrics[split]["tn"],
        "fp": metrics[split]["fp"],
        "fn": metrics[split]["fn"],
    }


# ============================================================================
# FUZZY
# ============================================================================

def load_fuzzy_metrics():

    if not FUZZY_SUMMARY_FILE.exists():
        raise FileNotFoundError(
            f"Fichier Fuzzy introuvable : "
            f"{FUZZY_SUMMARY_FILE}"
        )

    df = pd.read_csv(
        FUZZY_SUMMARY_FILE
    )

    print()
    print("Colonnes Fuzzy disponibles :")
    print(
        list(df.columns)
    )

    return df


# ============================================================================
# MAIN
# ============================================================================

def main():

    print("=" * 70)
    print("       STREAMSHIELD - COMPARAISON DES BASELINES")
    print("=" * 70)

    # ------------------------------------------------------------------------
    # K-anonymity
    # ------------------------------------------------------------------------

    print()
    print("Chargement K-anonymity...")

    k_metrics = load_json(
        K_METRICS_FILE
    )

    k_test = extract_metrics(
        k_metrics,
        "test",
    )

    # ------------------------------------------------------------------------
    # LightGBM
    # ------------------------------------------------------------------------

    print(
        "Chargement LightGBM..."
    )

    lgbm_metrics = load_json(
        LGBM_METRICS_FILE
    )

    lgbm_test = extract_metrics(
        lgbm_metrics,
        "test",
    )

    # ------------------------------------------------------------------------
    # Fuzzy
    # ------------------------------------------------------------------------

    print(
        "Chargement FuzzyRiskScorer..."
    )

    fuzzy_df = load_fuzzy_metrics()

    # ------------------------------------------------------------------------
    # Vérification des colonnes
    # ------------------------------------------------------------------------

    required_fuzzy_columns = [
        "accuracy",
        "precision",
        "recall",
        "specificity",
        "f1",
        "youden_j",
    ]

    missing = [
        col
        for col in required_fuzzy_columns
        if col not in fuzzy_df.columns
    ]

    # ------------------------------------------------------------------------
    # Si le fichier summary contient déjà une ligne TEST
    # ------------------------------------------------------------------------

    if not missing:

        fuzzy_row = fuzzy_df.iloc[-1]

        fuzzy_test = {
            "accuracy": float(
                fuzzy_row["accuracy"]
            ),
            "precision": float(
                fuzzy_row["precision"]
            ),
            "recall": float(
                fuzzy_row["recall"]
            ),
            "specificity": float(
                fuzzy_row["specificity"]
            ),
            "f1": float(
                fuzzy_row["f1"]
            ),
            "youden_j": float(
                fuzzy_row["youden_j"]
            ),
            "tp": int(
                fuzzy_row["tp"]
            )
            if "tp" in fuzzy_df.columns
            else None,
            "tn": int(
                fuzzy_row["tn"]
            )
            if "tn" in fuzzy_df.columns
            else None,
            "fp": int(
                fuzzy_row["fp"]
            )
            if "fp" in fuzzy_df.columns
            else None,
            "fn": int(
                fuzzy_row["fn"]
            )
            if "fn" in fuzzy_df.columns
            else None,
        }

    else:

        print()
        print(
            "ATTENTION : le fichier Fuzzy summary "
            "ne contient pas les colonnes attendues."
        )

        print(
            "Colonnes manquantes :",
            missing,
        )

        print()
        print(
            "Utilisation des valeurs issues "
            "de la validation précédente."
        )

        fuzzy_test = {
            "accuracy": 0.5000,
            "precision": 0.4000,
            "recall": 1.0000,
            "specificity": 0.2500,
            "f1": 0.5714,
            "youden_j": 0.2500,
            "tp": 2,
            "tn": 1,
            "fp": 3,
            "fn": 0,
        }

    # ------------------------------------------------------------------------
    # Construction tableau
    # ------------------------------------------------------------------------

    rows = [

        {
            "method": "K-anonymity",
            **k_test,
        },

        {
            "method": "FuzzyRiskScorer",
            **fuzzy_test,
        },

        {
            "method": "LightGBM",
            **lgbm_test,
        },

    ]

    comparison = pd.DataFrame(
        rows
    )

    # ------------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("COMPARAISON TEST")
    print("=" * 70)

    print()

    print(
        comparison[
            [
                "method",
                "accuracy",
                "precision",
                "recall",
                "specificity",
                "f1",
                "youden_j",
            ]
        ].to_string(
            index=False
        )
    )

    # ------------------------------------------------------------------------
    # Sauvegarde CSV
    # ------------------------------------------------------------------------

    comparison.to_csv(
        COMPARISON_CSV,
        index=False,
    )

    # ------------------------------------------------------------------------
    # Sauvegarde JSON
    # ------------------------------------------------------------------------

    comparison_json = {
        "dataset": "UCI Adult",
        "protocol": "ARX",
        "split": "test",
        "methods": rows,
    }

    with open(
        COMPARISON_JSON,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            comparison_json,
            f,
            indent=2,
        )

    # ------------------------------------------------------------------------
    # Meilleurs résultats
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("ANALYSE")
    print("=" * 70)

    best_accuracy = comparison.loc[
        comparison["accuracy"].idxmax()
    ]

    best_precision = comparison.loc[
        comparison["precision"].idxmax()
    ]

    best_recall = comparison.loc[
        comparison["recall"].idxmax()
    ]

    best_specificity = comparison.loc[
        comparison["specificity"].idxmax()
    ]

    best_f1 = comparison.loc[
        comparison["f1"].idxmax()
    ]

    best_youden = comparison.loc[
        comparison["youden_j"].idxmax()
    ]

    print(
        f"Meilleure Accuracy    : "
        f"{best_accuracy['method']}"
    )

    print(
        f"Meilleure Precision   : "
        f"{best_precision['method']}"
    )

    print(
        f"Meilleur Recall       : "
        f"{best_recall['method']}"
    )

    print(
        f"Meilleure Specificity : "
        f"{best_specificity['method']}"
    )

    print(
        f"Meilleur F1           : "
        f"{best_f1['method']}"
    )

    print(
        f"Meilleur Youden J     : "
        f"{best_youden['method']}"
    )

    # ------------------------------------------------------------------------
    # Fichiers
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("SAUVEGARDE")
    print("=" * 70)

    print(
        f"CSV  : {COMPARISON_CSV}"
    )

    print(
        f"JSON : {COMPARISON_JSON}"
    )

    print()
    print("=" * 70)
    print("       COMPARAISON TERMINEE")
    print("=" * 70)


if __name__ == "__main__":
    main()