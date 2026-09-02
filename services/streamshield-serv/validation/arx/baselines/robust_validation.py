from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd

from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
from lightgbm import LGBMClassifier


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = PROJECT_ROOT / "validation" / "arx" / "baselines"

FEATURE_FILES = [
    BASE_DIR / "ml_features_train.csv",
    BASE_DIR / "ml_features_validation.csv",
    BASE_DIR / "ml_features_test.csv",
]

FUZZY_FILE = PROJECT_ROOT / "validation" / "arx" / "fuzzy_vs_arx_results.csv"

OUTPUT_CSV = BASE_DIR / "robust_validation_results.csv"
OUTPUT_SUMMARY = BASE_DIR / "robust_validation_summary.json"


# ============================================================
# CONFIGURATION
# ============================================================

FUZZY_THRESHOLD = 0.7
N_SPLITS = 5
RANDOM_STATE = 42

FEATURE_COLUMNS = [
    "num_qi",
    "k",
    "uniqueness",
    "avg_sensitivity",
    "sample_size",
]


# ============================================================
# METRICS
# ============================================================

def compute_metrics(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))

    specificity = (
        tn / (tn + fp)
        if (tn + fp) > 0
        else 0.0
    )

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(
                y_true,
                y_pred,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_true,
                y_pred,
                zero_division=0,
            )
        ),
        "specificity": float(specificity),
        "f1": float(
            f1_score(
                y_true,
                y_pred,
                zero_division=0,
            )
        ),
        "youden_j": float(
            recall_score(
                y_true,
                y_pred,
                zero_division=0,
            )
            + specificity
            - 1.0
        ),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


# ============================================================
# K-ANONYMITY
# ============================================================

def select_k_threshold(train_df):
    """
    Sélectionne le seuil k uniquement sur le TRAIN.

    Règle :
        k < threshold -> risque
        k >= threshold -> non-risque
    """

    candidates = sorted(
        train_df["k"].dropna().unique()
    )

    best_threshold = candidates[0]
    best_f1 = -1.0

    for threshold in candidates:
        y_true = train_df["label"].values

        y_pred = (
            train_df["k"].values < threshold
        ).astype(int)

        score = f1_score(
            y_true,
            y_pred,
            zero_division=0,
        )

        if score > best_f1:
            best_f1 = score
            best_threshold = threshold

    return best_threshold


# ============================================================
# LIGHTGBM
# ============================================================

def train_lightgbm(train_df):
    model = LGBMClassifier(
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
        random_state=RANDOM_STATE,
        verbosity=-1,
    )

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df["label"]

    model.fit(X_train, y_train)

    return model


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("       STREAMSHIELD - VALIDATION ROBUSTE")
    print("=" * 70)

    print("\nChargement des features...")

    dfs = [
        pd.read_csv(path)
        for path in FEATURE_FILES
    ]

    features_df = pd.concat(
        dfs,
        ignore_index=True,
    )

    print(
        f"Nombre total de combinaisons : "
        f"{len(features_df)}"
    )

    # --------------------------------------------------------
    # Vérification
    # --------------------------------------------------------

    if len(features_df) != 30:
        raise ValueError(
            f"Nombre inattendu de combinaisons : "
            f"{len(features_df)}"
        )

    print(
        "\nRépartition des labels ARX :"
    )

    print(
        features_df["label"]
        .value_counts()
        .sort_index()
    )

    # --------------------------------------------------------
    # Chargement Fuzzy
    # --------------------------------------------------------

    print("\nChargement des résultats Fuzzy...")

    fuzzy_df = pd.read_csv(FUZZY_FILE)

    print(
        f"Combinaisons Fuzzy : "
        f"{len(fuzzy_df)}"
    )

    if len(fuzzy_df) != 30:
        raise ValueError(
            "Le fichier Fuzzy doit contenir "
            "30 combinaisons."
        )

    # --------------------------------------------------------
    # Fusion
    # --------------------------------------------------------

    columns_fuzzy = [
        "id",
        "fuzzy_score",
    ]

    fuzzy_df = fuzzy_df[columns_fuzzy]

    df = features_df.merge(
        fuzzy_df,
        on="id",
        how="inner",
    )

    if len(df) != 30:
        raise ValueError(
            "La fusion features/Fuzzy "
            "ne contient pas 30 combinaisons."
        )

    # --------------------------------------------------------
    # Stratified K-Fold
    # --------------------------------------------------------

    X = df[FEATURE_COLUMNS]
    y = df["label"]

    skf = StratifiedKFold(
        n_splits=N_SPLITS,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    all_results = []

    print("\n" + "=" * 70)
    print("DÉBUT VALIDATION CROISÉE")
    print("=" * 70)

    for fold, (train_idx, test_idx) in enumerate(
        skf.split(X, y),
        start=1,
    ):

        train_df = df.iloc[train_idx].copy()
        test_df = df.iloc[test_idx].copy()

        print(
            f"\n{'-' * 70}"
        )

        print(
            f"FOLD {fold}"
        )

        print(
            f"TRAIN : {len(train_df)} "
            f"combinaisons"
        )

        print(
            f"TEST  : {len(test_df)} "
            f"combinaisons"
        )

        # ====================================================
        # FUZZY
        # ====================================================

        fuzzy_pred = (
            test_df["fuzzy_score"].values
            >= FUZZY_THRESHOLD
        ).astype(int)

        fuzzy_metrics = compute_metrics(
            test_df["label"].values,
            fuzzy_pred,
        )

        # ====================================================
        # K-ANONYMITY
        # ====================================================

        k_threshold = select_k_threshold(
            train_df
        )

        k_pred = (
            test_df["k"].values
            < k_threshold
        ).astype(int)

        k_metrics = compute_metrics(
            test_df["label"].values,
            k_pred,
        )

        # ====================================================
        # LIGHTGBM
        # ====================================================

        model = train_lightgbm(
            train_df
        )

        lightgbm_proba = model.predict_proba(
            test_df[FEATURE_COLUMNS]
        )[:, 1]

        lightgbm_pred = (
            lightgbm_proba >= 0.5
        ).astype(int)

        lightgbm_metrics = compute_metrics(
            test_df["label"].values,
            lightgbm_pred,
        )

        # ====================================================
        # STOCKAGE
        # ====================================================

        for method, metrics in [
            ("Fuzzy Risk Score", fuzzy_metrics),
            ("K-anonymity", k_metrics),
            ("LightGBM", lightgbm_metrics),
        ]:

            row = {
                "fold": fold,
                "method": method,
                "k_threshold": (
                    k_threshold
                    if method == "K-anonymity"
                    else np.nan
                ),
            }

            row.update(metrics)

            all_results.append(row)

        print(
            f"Fuzzy      F1={fuzzy_metrics['f1']:.4f} "
            f"Recall={fuzzy_metrics['recall']:.4f}"
        )

        print(
            f"K-anon     F1={k_metrics['f1']:.4f} "
            f"Recall={k_metrics['recall']:.4f} "
            f"(k={k_threshold})"
        )

        print(
            f"LightGBM   F1={lightgbm_metrics['f1']:.4f} "
            f"Recall={lightgbm_metrics['recall']:.4f}"
        )

    # ========================================================
    # RÉSULTATS
    # ========================================================

    results_df = pd.DataFrame(
        all_results
    )

    results_df.to_csv(
        OUTPUT_CSV,
        index=False,
    )

    # ========================================================
    # MOYENNES + ÉCARTS-TYPES
    # ========================================================

    metric_columns = [
        "accuracy",
        "precision",
        "recall",
        "specificity",
        "f1",
        "youden_j",
    ]

    summary = []

    for method in [
        "Fuzzy Risk Score",
        "K-anonymity",
        "LightGBM",
    ]:

        method_df = results_df[
            results_df["method"] == method
        ]

        row = {
            "method": method
        }

        for metric in metric_columns:

            row[
                f"{metric}_mean"
            ] = float(
                method_df[metric].mean()
            )

            row[
                f"{metric}_std"
            ] = float(
                method_df[metric].std(
                    ddof=1
                )
            )

        summary.append(row)

    summary_df = pd.DataFrame(
        summary
    )

    # ========================================================
    # AFFICHAGE
    # ========================================================

    print("\n" + "=" * 70)
    print("RÉSULTATS MOYENS")
    print("=" * 70)

    for _, row in summary_df.iterrows():

        print(
            f"\n{row['method']}"
        )

        for metric in metric_columns:

            print(
                f"  {metric:15s}: "
                f"{row[f'{metric}_mean']:.4f} "
                f"+/- "
                f"{row[f'{metric}_std']:.4f}"
            )

    # ========================================================
    # JSON
    # ========================================================

    output = {
        "configuration": {
            "n_combinations": 30,
            "n_splits": N_SPLITS,
            "random_state": RANDOM_STATE,
            "fuzzy_threshold": FUZZY_THRESHOLD,
            "lightgbm_threshold": 0.5,
            "k_threshold_selection": (
                "selected on training fold"
            ),
        },
        "summary": summary,
        "fold_results": all_results,
    }

    with open(
        OUTPUT_SUMMARY,
        "w",
        encoding="utf-8",
    ) as f:
        def make_json_serializable(obj):
            if isinstance(obj, dict):
                return {
                    str(k): make_json_serializable(v)
                    for k, v in obj.items()
                }

            if isinstance(obj, list):
                return [
                    make_json_serializable(v)
                    for v in obj
                ]

            if isinstance(obj, (np.integer,)):
                return int(obj)

            if isinstance(obj, (np.floating,)):
                return float(obj)

            if isinstance(obj, np.ndarray):
                return obj.tolist()

            return obj


        output = make_json_serializable(output)

        with open(
            OUTPUT_SUMMARY,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                output,
                f,
                indent=2,
            )

    print("\n" + "=" * 70)
    print("FICHIERS SAUVEGARDÉS")
    print("=" * 70)

    print(
        f"CSV  : {OUTPUT_CSV}"
    )

    print(
        f"JSON : {OUTPUT_SUMMARY}"
    )

    print("\n" + "=" * 70)
    print("VALIDATION ROBUSTE TERMINÉE")
    print("=" * 70)


if __name__ == "__main__":
    main()