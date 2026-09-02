
from pathlib import Path
import sys
import json

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

import lightgbm as lgb
import pandas as pd
import shap


# ============================================================================
# CONFIGURATION
# ============================================================================

FEATURES_DIR = (
    BASE_DIR
    / "validation"
    / "arx"
    / "baselines"
)

MODEL_FILE = FEATURES_DIR / "lightgbm_model.txt"

TRAIN_FILE = FEATURES_DIR / "ml_features_train.csv"
VALIDATION_FILE = FEATURES_DIR / "ml_features_validation.csv"
TEST_FILE = FEATURES_DIR / "ml_features_test.csv"

SHAP_VALUES_FILE = (
    FEATURES_DIR
    / "lightgbm_shap_test.csv"
)

SHAP_IMPORTANCE_FILE = (
    FEATURES_DIR
    / "lightgbm_shap_feature_importance.csv"
)

SHAP_SUMMARY_FILE = (
    FEATURES_DIR
    / "lightgbm_shap_summary.json"
)


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
# CHARGEMENT MODELE
# ============================================================================

def load_model():

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Modèle introuvable : {MODEL_FILE}"
        )

    print()
    print("=" * 70)
    print("CHARGEMENT DU MODELE LIGHTGBM")
    print("=" * 70)

    print(
        f"Fichier : {MODEL_FILE}"
    )

    model = lgb.Booster(
        model_file=str(MODEL_FILE)
    )

    print("Modèle chargé avec succès.")

    return model


# ============================================================================
# CHARGEMENT FEATURES
# ============================================================================

def load_features(path: Path) -> pd.DataFrame:

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    df = pd.read_csv(path)

    missing = [
        column
        for column in FEATURE_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Features manquantes dans {path}: {missing}"
        )

    return df


# ============================================================================
# VERIFICATION MODELE / FEATURES
# ============================================================================

def verify_model_features(model):

    print()
    print("=" * 70)
    print("VERIFICATION MODELE / FEATURES")
    print("=" * 70)

    model_features = model.feature_name()

    print()
    print("Features du modèle :")

    for feature in model_features:
        print(f"  - {feature}")

    print()
    print("Features attendues :")

    for feature in FEATURE_COLUMNS:
        print(f"  - {feature}")

    if set(model_features) != set(FEATURE_COLUMNS):
        raise ValueError(
            "Les features du modèle ne correspondent pas "
            "aux features utilisées pour la validation."
        )

    print()
    print("OK : features cohérentes.")


# ============================================================================
# CALCUL SHAP
# ============================================================================

def calculate_shap_values(
    model,
    X: pd.DataFrame,
):

    print()
    print("=" * 70)
    print("CALCUL DES VALEURS SHAP")
    print("=" * 70)

    print(
        f"Nombre de combinaisons : {len(X)}"
    )

    print()
    print(
        "Calcul SHAP en cours..."
    )

    # TreeExplainer est adapté aux modèles LightGBM
    explainer = shap.TreeExplainer(model)

    shap_values = explainer.shap_values(X)

    # Selon la version de SHAP,
    # un modèle binaire peut retourner :
    # - un tableau directement
    # - une liste de deux tableaux
    if isinstance(shap_values, list):

        if len(shap_values) == 2:
            shap_values = shap_values[1]
        else:
            shap_values = shap_values[0]

    shap_values = pd.DataFrame(
        shap_values,
        columns=FEATURE_COLUMNS,
        index=X.index,
    )

    print("Calcul SHAP terminé.")

    return shap_values, explainer


# ============================================================================
# IMPORTANCE GLOBALE
# ============================================================================

def calculate_global_importance(
    shap_values: pd.DataFrame,
) -> pd.DataFrame:

    importance = (
        shap_values.abs()
        .mean()
        .sort_values(
            ascending=False
        )
    )

    result = pd.DataFrame({
        "feature": importance.index,
        "mean_abs_shap": importance.values,
    })

    return result


# ============================================================================
# AFFICHAGE IMPORTANCE
# ============================================================================

def print_global_importance(
    importance: pd.DataFrame,
):

    print()
    print("=" * 70)
    print("IMPORTANCE GLOBALE SHAP")
    print("=" * 70)

    print()

    for rank, row in enumerate(
        importance.itertuples(index=False),
        start=1,
    ):

        print(
            f"{rank}. "
            f"{row.feature:<20} | "
            f"mean(|SHAP|) = "
            f"{row.mean_abs_shap:.6f}"
        )


# ============================================================================
# CREATION DATASET SHAP
# ============================================================================

def build_shap_output(
    original_df: pd.DataFrame,
    shap_values: pd.DataFrame,
) -> pd.DataFrame:

    output = original_df[
        [
            "id",
            "combination",
            *FEATURE_COLUMNS,
            TARGET_COLUMN,
        ]
    ].copy()

    # ------------------------------------------------------------------------
    # Valeurs SHAP
    # ------------------------------------------------------------------------

    for feature in FEATURE_COLUMNS:

        output[
            f"shap_{feature}"
        ] = shap_values[feature].values

    # ------------------------------------------------------------------------
    # Somme absolue des contributions
    # ------------------------------------------------------------------------

    output[
        "shap_total_abs"
    ] = shap_values.abs().sum(axis=1).values

    # ------------------------------------------------------------------------
    # Feature dominante
    # ------------------------------------------------------------------------

    output[
        "dominant_feature"
    ] = shap_values.abs().idxmax(axis=1).values

    # ------------------------------------------------------------------------
    # Contribution dominante
    # ------------------------------------------------------------------------

    output[
        "dominant_shap"
    ] = [
        shap_values.loc[index, feature]
        for index, feature
        in zip(
            shap_values.index,
            output["dominant_feature"],
        )
    ]

    return output


# ============================================================================
# RESUME SHAP
# ============================================================================

def build_summary(
    importance: pd.DataFrame,
    shap_values: pd.DataFrame,
    test_df: pd.DataFrame,
) -> dict:

    ranking = []

    for rank, row in enumerate(
        importance.itertuples(index=False),
        start=1,
    ):

        ranking.append({
            "rank": rank,
            "feature": row.feature,
            "mean_absolute_shap": float(
                row.mean_abs_shap
            ),
        })

    # Feature dominante par combinaison
    dominant_counts = (
        shap_values.abs()
        .idxmax(axis=1)
        .value_counts()
        .to_dict()
    )

    summary = {
        "model": "LightGBM",
        "analysis": "SHAP",
        "dataset": "UCI Adult",
        "dataset_split": "TEST",
        "test_size": int(len(test_df)),
        "features": FEATURE_COLUMNS,
        "global_feature_importance": ranking,
        "dominant_feature_counts": {
            str(k): int(v)
            for k, v in dominant_counts.items()
        },
    }

    return summary


# ============================================================================
# MAIN
# ============================================================================

def main():

    print("=" * 70)
    print("       STREAMSHIELD - SHAP LIGHTGBM")
    print("=" * 70)

    print()
    print(
        "Objectif : expliquer les décisions du modèle LightGBM."
    )

    print()
    print(
        "IMPORTANT : le modèle est déjà entraîné."
    )

    print(
        "IMPORTANT : SHAP n'effectue aucun réentraînement."
    )

    print(
        "IMPORTANT : le TEST est utilisé uniquement "
        "pour l'explication finale."
    )

    # ------------------------------------------------------------------------
    # Chargement modèle
    # ------------------------------------------------------------------------

    model = load_model()

    verify_model_features(
        model
    )

    # ------------------------------------------------------------------------
    # Chargement TRAIN / VALIDATION / TEST
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
    # TEST uniquement pour SHAP final
    # ------------------------------------------------------------------------

    X_test = test_df[
        FEATURE_COLUMNS
    ]

    # ------------------------------------------------------------------------
    # Calcul SHAP
    # ------------------------------------------------------------------------

    shap_values, explainer = calculate_shap_values(
        model,
        X_test,
    )

    # ------------------------------------------------------------------------
    # Importance globale
    # ------------------------------------------------------------------------

    importance = calculate_global_importance(
        shap_values
    )

    print_global_importance(
        importance
    )

    # ------------------------------------------------------------------------
    # Dataset SHAP
    # ------------------------------------------------------------------------

    shap_output = build_shap_output(
        test_df,
        shap_values,
    )

    # ------------------------------------------------------------------------
    # Sauvegarde valeurs SHAP
    # ------------------------------------------------------------------------

    shap_output.to_csv(
        SHAP_VALUES_FILE,
        index=False,
    )

    print()
    print(
        f"Valeurs SHAP sauvegardées : "
        f"{SHAP_VALUES_FILE}"
    )

    # ------------------------------------------------------------------------
    # Sauvegarde importance globale
    # ------------------------------------------------------------------------

    importance.to_csv(
        SHAP_IMPORTANCE_FILE,
        index=False,
    )

    print(
        f"Importance SHAP sauvegardée : "
        f"{SHAP_IMPORTANCE_FILE}"
    )

    # ------------------------------------------------------------------------
    # Résumé JSON
    # ------------------------------------------------------------------------

    summary = build_summary(
        importance,
        shap_values,
        test_df,
    )

    with open(
        SHAP_SUMMARY_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"Résumé SHAP sauvegardé : "
        f"{SHAP_SUMMARY_FILE}"
    )

    # ------------------------------------------------------------------------
    # Aperçu
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("APERÇU DES EXPLICATIONS SHAP")
    print("=" * 70)

    display_columns = [
        "id",
        "combination",
        "label",
        "dominant_feature",
        "dominant_shap",
    ]

    print()

    print(
        shap_output[
            display_columns
        ].to_string(index=False)
    )

    # ------------------------------------------------------------------------
    # Fin
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("       SHAP LIGHTGBM TERMINE")
    print("=" * 70)


if __name__ == "__main__":
    main()

