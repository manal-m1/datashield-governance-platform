from pathlib import Path
import json

import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = PROJECT_ROOT

FEATURES_DIR = (
    BASE_DIR
    / "validation"
    / "arx"
    / "baselines"
)

TRAIN_FILE = FEATURES_DIR / "ml_features_train.csv"
VALIDATION_FILE = FEATURES_DIR / "ml_features_validation.csv"
TEST_FILE = FEATURES_DIR / "ml_features_test.csv"

TRAIN_RESULTS_FILE = FEATURES_DIR / "k_anonymity_train_results.csv"
VALIDATION_RESULTS_FILE = FEATURES_DIR / "k_anonymity_validation_results.csv"
TEST_RESULTS_FILE = FEATURES_DIR / "k_anonymity_test_results.csv"

METRICS_FILE = FEATURES_DIR / "k_anonymity_metrics.json"


TARGET_COLUMN = "label"
K_COLUMN = "k"


# ============================================================================
# CHARGEMENT
# ============================================================================

def load_features(path: Path) -> pd.DataFrame:

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    df = pd.read_csv(path)

    required = [
        K_COLUMN,
        TARGET_COLUMN,
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {path}: {missing}"
        )

    return df


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
# EVALUATION
# ============================================================================

def evaluate_split(
    df: pd.DataFrame,
    k_threshold: int,
):

    # ------------------------------------------------------------------------
    # Baseline K-anonymity
    #
    # k < threshold => risque
    # k >= threshold => non-risque
    # ------------------------------------------------------------------------

    prediction = (
        df[K_COLUMN] < k_threshold
    ).astype(int)

    metrics = calculate_metrics(
        df[TARGET_COLUMN],
        prediction,
    )

    result = df.copy()

    result["k_threshold"] = k_threshold
    result["prediction"] = prediction

    return result, metrics


# ============================================================================
# RECHERCHE DU SEUIL SUR TRAIN
# ============================================================================

def find_best_k_threshold(
    train_df: pd.DataFrame,
):

    possible_thresholds = sorted(
        train_df[K_COLUMN]
        .dropna()
        .astype(int)
        .unique()
    )

    # Ajouter quelques seuils autour des valeurs observées.
    possible_thresholds = sorted(
        set(
            possible_thresholds
            + [1, 2, 3, 4, 5]
        )
    )

    best_threshold = None
    best_metrics = None

    for threshold in possible_thresholds:

        _, metrics = evaluate_split(
            train_df,
            threshold,
        )

        # Critère principal : Youden J.
        # En cas d'égalité : F1.
        score = (
            metrics["youden_j"],
            metrics["f1"],
        )

        if (
            best_metrics is None
            or score
            > (
                best_metrics["youden_j"],
                best_metrics["f1"],
            )
        ):
            best_threshold = threshold
            best_metrics = metrics

    return best_threshold, best_metrics


# ============================================================================
# AFFICHAGE
# ============================================================================

def print_metrics(
    name,
    metrics,
):

    print()
    print("-" * 70)
    print(f"RESULTATS {name}")
    print("-" * 70)

    print(
        f"Accuracy     : "
        f"{metrics['accuracy']:.4f}"
    )

    print(
        f"Precision    : "
        f"{metrics['precision']:.4f}"
    )

    print(
        f"Recall       : "
        f"{metrics['recall']:.4f}"
    )

    print(
        f"Specificity  : "
        f"{metrics['specificity']:.4f}"
    )

    print(
        f"F1           : "
        f"{metrics['f1']:.4f}"
    )

    print(
        f"Youden J     : "
        f"{metrics['youden_j']:.4f}"
    )

    print()

    print(
        f"TP={metrics['tp']} | "
        f"FP={metrics['fp']} | "
        f"FN={metrics['fn']} | "
        f"TN={metrics['tn']}"
    )


# ============================================================================
# MAIN
# ============================================================================

def main():

    print("=" * 70)
    print("       STREAMSHIELD - BASELINE K-ANONYMITY")
    print("=" * 70)

    print()
    print(
        "Objectif : évaluer une baseline K-anonymity "
        "basée uniquement sur k."
    )

    print()
    print(
        "Règle : k < seuil => risque ; "
        "k >= seuil => non-risque."
    )

    print()
    print(
        "IMPORTANT : le seuil est déterminé sur TRAIN."
    )

    print(
        "IMPORTANT : le TEST n'est jamais utilisé "
        "pour déterminer le seuil."
    )

    # ------------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("CHARGEMENT DES FEATURES")
    print("=" * 70)

    train_df = load_features(
        TRAIN_FILE
    )

    validation_df = load_features(
        VALIDATION_FILE
    )

    test_df = load_features(
        TEST_FILE
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
    # Recherche seuil TRAIN
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("CALIBRATION DU SEUIL K SUR TRAIN")
    print("=" * 70)

    k_threshold, train_calibration_metrics = (
        find_best_k_threshold(train_df)
    )

    print()
    print(
        f"Seuil K sélectionné : "
        f"{k_threshold}"
    )

    print_metrics(
        "TRAIN - CALIBRATION",
        train_calibration_metrics,
    )

    # ------------------------------------------------------------------------
    # TRAIN
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("EVALUATION TRAIN")
    print("=" * 70)

    train_results, train_metrics = evaluate_split(
        train_df,
        k_threshold,
    )

    print_metrics(
        "TRAIN",
        train_metrics,
    )

    train_results.to_csv(
        TRAIN_RESULTS_FILE,
        index=False,
    )

    # ------------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("EVALUATION VALIDATION")
    print("=" * 70)

    validation_results, validation_metrics = (
        evaluate_split(
            validation_df,
            k_threshold,
        )
    )

    print_metrics(
        "VALIDATION",
        validation_metrics,
    )

    validation_results.to_csv(
        VALIDATION_RESULTS_FILE,
        index=False,
    )

    # ------------------------------------------------------------------------
    # TEST
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("TEST FINAL K-ANONYMITY")
    print("=" * 70)

    print()
    print(
        f"Seuil K FIGE : {k_threshold}"
    )

    print(
        "IMPORTANT : aucun recalibrage sur TEST."
    )

    test_results, test_metrics = evaluate_split(
        test_df,
        k_threshold,
    )

    print_metrics(
        "TEST",
        test_metrics,
    )

    test_results.to_csv(
        TEST_RESULTS_FILE,
        index=False,
    )

    # ------------------------------------------------------------------------
    # Sauvegarde métriques
    # ------------------------------------------------------------------------

    all_metrics = {
        "model": "K-anonymity",
        "feature": "k",
        "rule": "k < threshold => risk",
        "threshold": int(k_threshold),
        "train_size": len(train_df),
        "validation_size": len(validation_df),
        "test_size": len(test_df),
        "train": train_metrics,
        "validation": validation_metrics,
        "test": test_metrics,
    }

    with open(
        METRICS_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            all_metrics,
            f,
            indent=2,
        )

    # ------------------------------------------------------------------------
    # Sauvegarde
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("SAUVEGARDE")
    print("=" * 70)

    print(
        f"Seuil K : {k_threshold}"
    )

    print(
        f"Train : {TRAIN_RESULTS_FILE}"
    )

    print(
        f"Validation : {VALIDATION_RESULTS_FILE}"
    )

    print(
        f"Test : {TEST_RESULTS_FILE}"
    )

    print(
        f"Métriques : {METRICS_FILE}"
    )

    print()
    print("=" * 70)
    print("       BASELINE K-ANONYMITY TERMINEE")
    print("=" * 70)


if __name__ == "__main__":
    main()