from pathlib import Path
import sys

# ============================================================================
# CONFIGURATION DU PATH
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# IMPORTS
# ============================================================================

import json
import logging

import lightgbm as lgb
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
)


logger = logging.getLogger("streamshield.train_lightgbm")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)


# ============================================================================
# FICHIERS
# ============================================================================

FEATURES_DIR = (
    BASE_DIR
    / "validation"
    / "arx"
    / "baselines"
)

TRAIN_FILE = FEATURES_DIR / "ml_features_train.csv"
VALIDATION_FILE = FEATURES_DIR / "ml_features_validation.csv"
TEST_FILE = FEATURES_DIR / "ml_features_test.csv"

MODEL_FILE = FEATURES_DIR / "lightgbm_model.txt"
VALIDATION_RESULTS_FILE = FEATURES_DIR / "lightgbm_validation_results.csv"
TEST_RESULTS_FILE = FEATURES_DIR / "lightgbm_test_results.csv"
METRICS_FILE = FEATURES_DIR / "lightgbm_metrics.json"


# ============================================================================
# FEATURES
# ============================================================================

FEATURE_COLUMNS = [
    "num_qi",
    "k",
    "uniqueness",
    "avg_sensitivity",
    "sample_size",
]

TARGET_COLUMN = "label"


# ============================================================================
# CHARGEMENT
# ============================================================================

def load_features(path: Path) -> pd.DataFrame:

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    df = pd.read_csv(path)

    required_columns = (
        FEATURE_COLUMNS
        + [TARGET_COLUMN]
    )

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {path}: {missing}"
        )

    return df


# ============================================================================
# VERIFICATION
# ============================================================================

def verify_dataset(
    df: pd.DataFrame,
    name: str,
) -> None:

    print()
    print("=" * 70)
    print(f"VERIFICATION {name}")
    print("=" * 70)

    print(f"Nombre de combinaisons : {len(df)}")
    print(
        f"Positives : {(df[TARGET_COLUMN] == 1).sum()}"
    )
    print(
        f"Negatives : {(df[TARGET_COLUMN] == 0).sum()}"
    )

    print()
    print("Features :")

    for column in FEATURE_COLUMNS:

        print(
            f"  {column:<20} | "
            f"min={df[column].min():.6f} | "
            f"max={df[column].max():.6f}"
        )


# ============================================================================
# METRIQUES
# ============================================================================

def calculate_metrics(
    y_true,
    y_pred,
    y_probability=None,
) -> dict:

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

    result = {
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

    if (
        y_probability is not None
        and len(set(y_true)) > 1
    ):
        result["roc_auc"] = float(
            roc_auc_score(
                y_true,
                y_probability,
            )
        )

    return result


# ============================================================================
# AFFICHAGE
# ============================================================================

def print_metrics(
    name: str,
    metrics: dict,
) -> None:

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

    if "roc_auc" in metrics:

        print(
            f"ROC-AUC      : "
            f"{metrics['roc_auc']:.4f}"
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
    print("       STREAMSHIELD - LIGHTGBM")
    print("=" * 70)

    print()
    print(
        "Objectif : entraîner LightGBM sur TRAIN, "
        "évaluer sur VALIDATION puis TEST."
    )

    print()
    print(
        "IMPORTANT : le TEST n'est jamais utilisé "
        "pour l'entraînement."
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
    # Verification
    # ------------------------------------------------------------------------

    verify_dataset(
        train_df,
        "TRAIN",
    )

    verify_dataset(
        validation_df,
        "VALIDATION",
    )

    verify_dataset(
        test_df,
        "TEST",
    )

    # ------------------------------------------------------------------------
    # Séparation X / y
    # ------------------------------------------------------------------------

    X_train = train_df[
        FEATURE_COLUMNS
    ]

    y_train = train_df[
        TARGET_COLUMN
    ]

    X_validation = validation_df[
        FEATURE_COLUMNS
    ]

    y_validation = validation_df[
        TARGET_COLUMN
    ]

    X_test = test_df[
        FEATURE_COLUMNS
    ]

    y_test = test_df[
        TARGET_COLUMN
    ]

    # ------------------------------------------------------------------------
    # Entraînement
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("ENTRAINEMENT LIGHTGBM")
    print("=" * 70)

    print()
    print(
        "Features utilisées :"
    )

    for feature in FEATURE_COLUMNS:
        print(f"  - {feature}")

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=7,
        max_depth=3,
        min_child_samples=3,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=42,
        verbosity=-1,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[
            (X_validation, y_validation)
        ],
        callbacks=[
            lgb.early_stopping(
                stopping_rounds=20,
                verbose=False,
            )
        ],
    )

    print()
    print(
        f"Nombre d'arbres utilisé : "
        f"{model.best_iteration_}"
    )

    # ------------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("EVALUATION VALIDATION")
    print("=" * 70)

    validation_probability = model.predict_proba(
        X_validation
    )[:, 1]

    validation_prediction = (
        validation_probability >= 0.5
    ).astype(int)

    validation_metrics = calculate_metrics(
        y_validation,
        validation_prediction,
        validation_probability,
    )

    print_metrics(
        "VALIDATION",
        validation_metrics,
    )

    validation_output = validation_df.copy()

    validation_output[
        "prediction_probability"
    ] = validation_probability

    validation_output[
        "prediction"
    ] = validation_prediction

    validation_output.to_csv(
        VALIDATION_RESULTS_FILE,
        index=False,
    )

    # ------------------------------------------------------------------------
    # TEST FINAL
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("TEST FINAL LIGHTGBM")
    print("=" * 70)

    print()
    print(
        "IMPORTANT : le TEST est utilisé "
        "uniquement pour l'évaluation finale."
    )

    test_probability = model.predict_proba(
        X_test
    )[:, 1]

    test_prediction = (
        test_probability >= 0.5
    ).astype(int)

    test_metrics = calculate_metrics(
        y_test,
        test_prediction,
        test_probability,
    )

    print_metrics(
        "TEST",
        test_metrics,
    )

    # ------------------------------------------------------------------------
    # Sauvegarde résultats TEST
    # ------------------------------------------------------------------------

    test_output = test_df.copy()

    test_output[
        "prediction_probability"
    ] = test_probability

    test_output[
        "prediction"
    ] = test_prediction

    test_output.to_csv(
        TEST_RESULTS_FILE,
        index=False,
    )

    # ------------------------------------------------------------------------
    # Sauvegarde modèle
    # ------------------------------------------------------------------------

    model.booster_.save_model(
        str(MODEL_FILE)
    )

    # ------------------------------------------------------------------------
    # Sauvegarde métriques
    # ------------------------------------------------------------------------

    all_metrics = {
        "model": "LightGBM",
        "features": FEATURE_COLUMNS,
        "threshold": 0.5,
        "train_size": len(train_df),
        "validation_size": len(validation_df),
        "test_size": len(test_df),
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
    # Fin
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("SAUVEGARDE")
    print("=" * 70)

    print(
        f"Modèle : {MODEL_FILE}"
    )

    print(
        f"Validation : "
        f"{VALIDATION_RESULTS_FILE}"
    )

    print(
        f"Test : "
        f"{TEST_RESULTS_FILE}"
    )

    print(
        f"Métriques : "
        f"{METRICS_FILE}"
    )

    print()
    print("=" * 70)
    print("       LIGHTGBM TERMINE")
    print("=" * 70)


if __name__ == "__main__":
    main()