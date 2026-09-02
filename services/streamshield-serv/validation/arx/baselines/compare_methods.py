from pathlib import Path
import json

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).resolve().parents[3]

BASELINES_DIR = (
    BASE_DIR
    / "validation"
    / "arx"
    / "baselines"
)

FUZZY_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "test"
    / "fuzzy_test_summary.csv"
)

K_ANON_METRICS = (
    BASELINES_DIR
    / "k_anonymity_metrics.json"
)

LIGHTGBM_METRICS = (
    BASELINES_DIR
    / "lightgbm_metrics.json"
)

OUTPUT_FILE = (
    BASELINES_DIR
    / "final_comparison.csv"
)

OUTPUT_JSON = (
    BASELINES_DIR
    / "final_comparison.json"
)


# ============================================================================
# METRIQUES
# ============================================================================

def calculate_metrics(y_true, y_pred):

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1],
    ).ravel()

    accuracy = accuracy_score(
        y_true,
        y_pred,
    )

    precision = precision_score(
        y_true,
        y_pred,
        zero_division=0,
    )

    recall = recall_score(
        y_true,
        y_pred,
        zero_division=0,
    )

    specificity = (
        tn / (tn + fp)
        if (tn + fp) > 0
        else 0.0
    )

    f1 = f1_score(
        y_true,
        y_pred,
        zero_division=0,
    )

    youden_j = (
        recall
        + specificity
        - 1.0
    )

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "specificity": float(specificity),
        "f1": float(f1),
        "youden_j": float(youden_j),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }


# ============================================================================
# CHARGEMENT JSON
# ============================================================================

def load_json(path):

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
# AFFICHAGE
# ============================================================================

def print_result(
    method,
    dataset,
    metrics,
):

    print()
    print("-" * 70)
    print(
        f"{method} - {dataset}"
    )
    print("-" * 70)

    print(
        f"Accuracy     : {metrics['accuracy']:.4f}"
    )

    print(
        f"Precision    : {metrics['precision']:.4f}"
    )

    print(
        f"Recall       : {metrics['recall']:.4f}"
    )

    print(
        f"Specificity  : {metrics['specificity']:.4f}"
    )

    print(
        f"F1           : {metrics['f1']:.4f}"
    )

    print(
        f"Youden J     : {metrics['youden_j']:.4f}"
    )

    print(
        f"TP={metrics['tp']} | "
        f"TN={metrics['tn']} | "
        f"FP={metrics['fp']} | "
        f"FN={metrics['fn']}"
    )


# ============================================================================
# MAIN
# ============================================================================

def main():

    print("=" * 70)
    print("       STREAMSHIELD - COMPARAISON FINALE")
    print("=" * 70)

    print()
    print(
        "Comparaison : Fuzzy Risk Score vs "
        "K-anonymity vs LightGBM"
    )

    print()
    print(
        "Le TEST est utilisé uniquement pour "
        "l'évaluation finale."
    )

    # ========================================================================
    # CHARGEMENT K-ANONYMITY
    # ========================================================================

    print()
    print("=" * 70)
    print("CHARGEMENT K-ANONYMITY")
    print("=" * 70)

    k_metrics = load_json(
        K_ANON_METRICS
    )

    k_threshold = k_metrics.get(
        "threshold",
        2,
    )

    print(
        f"Seuil K utilisé : {k_threshold}"
    )

    # ========================================================================
    # CHARGEMENT LIGHTGBM
    # ========================================================================

    print()
    print("=" * 70)
    print("CHARGEMENT LIGHTGBM")
    print("=" * 70)

    lgb_metrics = load_json(
        LIGHTGBM_METRICS
    )

    print(
        f"Seuil LightGBM : "
        f"{lgb_metrics.get('threshold', 0.5)}"
    )

    # ========================================================================
    # CHARGEMENT FUZZY
    # ========================================================================

    print()
    print("=" * 70)
    print("CHARGEMENT FUZZY RISK SCORE")
    print("=" * 70)

    if not FUZZY_FILE.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {FUZZY_FILE}"
        )

    fuzzy_df = pd.read_csv(
        FUZZY_FILE
    )

    print(
        f"Nombre de combinaisons : "
        f"{len(fuzzy_df)}"
    )

    print(
        f"Seuil Fuzzy : "
        f"{fuzzy_df['threshold'].iloc[0]}"
    )

    # ========================================================================
    # RESULTATS DEPUIS LES FICHIERS EXISTANTS
    # ========================================================================

    results = []

    # ------------------------------------------------------------------------
    # Fuzzy
    # ------------------------------------------------------------------------

    fuzzy_metrics = {
        "accuracy": float(
            fuzzy_df["accuracy"].iloc[0]
        ),
        "precision": float(
            fuzzy_df["precision"].iloc[0]
        ),
        "recall": float(
            fuzzy_df["recall"].iloc[0]
        ),
        "specificity": float(
            fuzzy_df["specificity"].iloc[0]
        ),
        "f1": float(
            fuzzy_df["f1"].iloc[0]
        ),
        "youden_j": float(
            fuzzy_df["youden_j"].iloc[0]
        ),
        "tp": int(
            fuzzy_df["tp"].iloc[0]
        ),
        "tn": int(
            fuzzy_df["tn"].iloc[0]
        ),
        "fp": int(
            fuzzy_df["fp"].iloc[0]
        ),
        "fn": int(
            fuzzy_df["fn"].iloc[0]
        ),
    }

    print_result(
        "FUZZY RISK SCORE",
        "TEST",
        fuzzy_metrics,
    )

    results.append({
        "method": "Fuzzy Risk Score",
        "dataset": "TEST",
        **fuzzy_metrics,
    })

    # ------------------------------------------------------------------------
    # K-anonymity
    # ------------------------------------------------------------------------

    k_test = k_metrics["test"]

    print_result(
        "K-ANONYMITY",
        "TEST",
        k_test,
    )

    results.append({
        "method": "K-anonymity",
        "dataset": "TEST",
        **k_test,
    })

    # ------------------------------------------------------------------------
    # LightGBM
    # ------------------------------------------------------------------------

    lgb_test = lgb_metrics["test"]

    print_result(
        "LIGHTGBM",
        "TEST",
        lgb_test,
    )

    results.append({
        "method": "LightGBM",
        "dataset": "TEST",
        **lgb_test,
    })

    # ========================================================================
    # COMPARAISON
    # ========================================================================

    comparison = pd.DataFrame(
        results
    )

    # ========================================================================
    # SAUVEGARDE CSV
    # ========================================================================

    comparison.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # ========================================================================
    # SAUVEGARDE JSON
    # ========================================================================

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            {
                "comparison": results,
                "fuzzy_threshold": float(
                    fuzzy_df["threshold"].iloc[0]
                ),
                "k_anonymity_threshold": k_threshold,
                "lightgbm_threshold": float(
                    lgb_metrics.get(
                        "threshold",
                        0.5,
                    )
                ),
            },
            f,
            indent=2,
        )

    # ========================================================================
    # TABLEAU FINAL
    # ========================================================================

    print()
    print("=" * 70)
    print("TABLEAU COMPARATIF FINAL - TEST")
    print("=" * 70)

    display_columns = [
        "method",
        "accuracy",
        "precision",
        "recall",
        "specificity",
        "f1",
        "youden_j",
    ]

    print(
        comparison[
            display_columns
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    # ========================================================================
    # MEILLEURE METHODE
    # ========================================================================

    best_f1 = comparison.loc[
        comparison["f1"].idxmax()
    ]

    best_youden = comparison.loc[
        comparison["youden_j"].idxmax()
    ]

    print()
    print("=" * 70)
    print("ANALYSE")
    print("=" * 70)

    print(
        f"Meilleur F1       : "
        f"{best_f1['method']} "
        f"({best_f1['f1']:.4f})"
    )

    print(
        f"Meilleur Youden J : "
        f"{best_youden['method']} "
        f"({best_youden['youden_j']:.4f})"
    )

    print()
    print("Fichiers sauvegardés :")
    print(
        f"  CSV  : {OUTPUT_FILE}"
    )
    print(
        f"  JSON : {OUTPUT_JSON}"
    )

    print()
    print("=" * 70)
    print("       COMPARAISON TERMINEE")
    print("=" * 70)


if __name__ == "__main__":
    main()

