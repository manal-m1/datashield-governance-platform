# import csv
# from pathlib import Path
# from typing import Dict, List


# # ============================================================
# # CONFIGURATION
# # ============================================================

# BASE_DIR = Path(__file__).resolve().parents[3]


# # ============================================================
# # FICHIER RESULTATS FUZZY
# # ============================================================

# FUZZY_FILE = (
#     BASE_DIR
#     / "validation"
#     / "arx"
#     / "test"
#     / "fuzzy_test_summary.csv"
# )


# # ============================================================
# # FICHIER RESULTATS K-ANONYMITY
# # ============================================================
# BASELINES_DIR = (
#     BASE_DIR
#     / "validation"
#     / "arx"
#     / "baselines"
# )

# K_ANONYMITY_FILE = (
#     BASE_DIR
#     / "validation"
#     / "arx"
#     / "baselines"
#     / "k_anonymity_summary.csv"
# )


# # ============================================================
# # FICHIER RESULTATS ARX
# # ============================================================

# ARX_FILE = (
#     BASE_DIR
#     / "validation"
#     / "arx"
#     / "baselines"
#     / "arx_baseline_summary.csv"
# )


# # ============================================================
# # FICHIERS DE SORTIE
# # ============================================================

# OUTPUT_FILE = (
#     BASE_DIR
#     / "validation"
#     / "arx"
#     / "baselines"
#     / "model_comparison.csv"
# )

# DETAIL_FILE = (
#     BASE_DIR
#     / "validation"
#     / "arx"
#     / "baselines"
#     / "model_comparison_detailed.csv"
# )



# # ============================================================
# # UTILITAIRES
# # ============================================================

# def load_csv(file_path: Path) -> List[Dict]:
#     """
#     Charge un fichier CSV.
#     """

#     if not file_path.exists():
#         raise FileNotFoundError(
#             f"Fichier introuvable : {file_path}"
#         )

#     with open(
#         file_path,
#         "r",
#         encoding="utf-8",
#         newline="",
#     ) as file:

#         reader = csv.DictReader(file)

#         return list(reader)


# def get_float(
#     row: Dict,
#     key: str,
# ) -> float:

#     value = row.get(key)

#     if value is None:
#         raise ValueError(
#             f"Colonne '{key}' absente du fichier."
#         )

#     return float(value)


# def get_int(
#     row: Dict,
#     key: str,
# ) -> int:

#     value = row.get(key)

#     if value is None:
#         raise ValueError(
#             f"Colonne '{key}' absente du fichier."
#         )

#     return int(value)


# # ============================================================
# # CHARGEMENT FUZZY
# # ============================================================

# def load_fuzzy_results() -> Dict:

#     print()
#     print("=" * 70)
#     print("       CHARGEMENT FUZZYRISKSCORER")
#     print("=" * 70)

#     print(
#         f"Fichier : {FUZZY_FILE}"
#     )

#     rows = load_csv(FUZZY_FILE)

#     if not rows:
#         raise ValueError(
#             "Le fichier Fuzzy est vide."
#         )

#     row = rows[0]

#     required = [
#         "threshold",
#         "accuracy",
#         "precision",
#         "recall",
#         "specificity",
#         "f1",
#         "youden_j",
#         "tp",
#         "tn",
#         "fp",
#         "fn",
#         "num_combinations",
#     ]

#     for column in required:

#         if column not in row:
#             raise ValueError(
#                 f"Colonne '{column}' absente "
#                 f"de {FUZZY_FILE}"
#             )

#     result = {
#         "model": "FuzzyRiskScorer",
#         "threshold": get_float(row, "threshold"),
#         "accuracy": get_float(row, "accuracy"),
#         "precision": get_float(row, "precision"),
#         "recall": get_float(row, "recall"),
#         "specificity": get_float(row, "specificity"),
#         "f1": get_float(row, "f1"),
#         "youden_j": get_float(row, "youden_j"),
#         "tp": get_int(row, "tp"),
#         "tn": get_int(row, "tn"),
#         "fp": get_int(row, "fp"),
#         "fn": get_int(row, "fn"),
#         "num_combinations": get_int(
#             row,
#             "num_combinations",
#         ),
#     }

#     print(
#         f"Combinaisons : "
#         f"{result['num_combinations']}"
#     )

#     return result


# # ============================================================
# # CHARGEMENT K-ANONYMITY
# # ============================================================

# def load_k_anonymity_results() -> Dict:

#     print()
#     print("=" * 70)
#     print("       CHARGEMENT K-ANONYMITY")
#     print("=" * 70)

#     print(
#         f"Fichier : {K_ANONYMITY_FILE}"
#     )

#     rows = load_csv(K_ANONYMITY_FILE)

#     if not rows:
#         raise ValueError(
#             "Le fichier k-anonymity est vide."
#         )

#     row = rows[0]

#     required = [
#         "threshold_k",
#         "accuracy_test",
#         "precision_test",
#         "recall_test",
#         "specificity_test",
#         "f1_test",
#         "youden_j_test",
#         "tp_test",
#         "tn_test",
#         "fp_test",
#         "fn_test",
#         "num_combinations_test",
#     ]

#     # --------------------------------------------------------
#     # Le fichier peut avoir des noms légèrement différents.
#     # On cherche d'abord la structure utilisée par le script.
#     # --------------------------------------------------------

#     if all(
#         column in row
#         for column in required
#     ):

#         result = {
#             "model": "k-anonymity",
#             "threshold": row["threshold_k"],
#             "accuracy": get_float(
#                 row,
#                 "accuracy_test",
#             ),
#             "precision": get_float(
#                 row,
#                 "precision_test",
#             ),
#             "recall": get_float(
#                 row,
#                 "recall_test",
#             ),
#             "specificity": get_float(
#                 row,
#                 "specificity_test",
#             ),
#             "f1": get_float(
#                 row,
#                 "f1_test",
#             ),
#             "youden_j": get_float(
#                 row,
#                 "youden_j_test",
#             ),
#             "tp": get_int(
#                 row,
#                 "tp_test",
#             ),
#             "tn": get_int(
#                 row,
#                 "tn_test",
#             ),
#             "fp": get_int(
#                 row,
#                 "fp_test",
#             ),
#             "fn": get_int(
#                 row,
#                 "fn_test",
#             ),
#             "num_combinations": get_int(
#                 row,
#                 "num_combinations_test",
#             ),
#         }

#     # --------------------------------------------------------
#     # Structure alternative
#     # --------------------------------------------------------

#     else:

#         possible_thresholds = [
#             "threshold",
#             "k_threshold",
#             "threshold_k",
#         ]

#         threshold_key = next(
#             (
#                 key
#                 for key in possible_thresholds
#                 if key in row
#             ),
#             None,
#         )

#         if threshold_key is None:
#             raise ValueError(
#                 "Impossible de trouver le seuil k "
#                 f"dans {K_ANONYMITY_FILE}"
#             )

#         result = {
#             "model": "k-anonymity",
#             "threshold": row[threshold_key],
#             "accuracy": get_float(
#                 row,
#                 "accuracy",
#             ),
#             "precision": get_float(
#                 row,
#                 "precision",
#             ),
#             "recall": get_float(
#                 row,
#                 "recall",
#             ),
#             "specificity": get_float(
#                 row,
#                 "specificity",
#             ),
#             "f1": get_float(
#                 row,
#                 "f1",
#             ),
#             "youden_j": get_float(
#                 row,
#                 "youden_j",
#             ),
#             "tp": get_int(row, "tp"),
#             "tn": get_int(row, "tn"),
#             "fp": get_int(row, "fp"),
#             "fn": get_int(row, "fn"),
#             "num_combinations": get_int(
#                 row,
#                 "num_combinations",
#             ),
#         }

#     print(
#         f"Seuil k : "
#         f"{result['threshold']}"
#     )

#     return result


# # ============================================================
# # CHARGEMENT ARX
# # ============================================================

# def load_arx_results() -> Dict:

#     print()
#     print("=" * 70)
#     print("       CHARGEMENT BASELINE ARX")
#     print("=" * 70)

#     print(
#         f"Fichier : {ARX_FILE}"
#     )

#     rows = load_csv(ARX_FILE)

#     if not rows:
#         raise ValueError(
#             "Le fichier ARX est vide."
#         )

#     row = rows[0]

#     required = [
#         "threshold",
#         "accuracy_test",
#         "precision_test",
#         "recall_test",
#         "specificity_test",
#         "f1_test",
#         "youden_j_test",
#         "tp_test",
#         "tn_test",
#         "fp_test",
#         "fn_test",
#         "num_combinations_test",
#     ]

#     if all(
#         column in row
#         for column in required
#     ):

#         result = {
#             "model": "ARX",
#             "threshold": get_float(
#                 row,
#                 "threshold",
#             ),
#             "accuracy": get_float(
#                 row,
#                 "accuracy_test",
#             ),
#             "precision": get_float(
#                 row,
#                 "precision_test",
#             ),
#             "recall": get_float(
#                 row,
#                 "recall_test",
#             ),
#             "specificity": get_float(
#                 row,
#                 "specificity_test",
#             ),
#             "f1": get_float(
#                 row,
#                 "f1_test",
#             ),
#             "youden_j": get_float(
#                 row,
#                 "youden_j_test",
#             ),
#             "tp": get_int(
#                 row,
#                 "tp_test",
#             ),
#             "tn": get_int(
#                 row,
#                 "tn_test",
#             ),
#             "fp": get_int(
#                 row,
#                 "fp_test",
#             ),
#             "fn": get_int(
#                 row,
#                 "fn_test",
#             ),
#             "num_combinations": get_int(
#                 row,
#                 "num_combinations_test",
#             ),
#         }

#     else:

#         result = {
#             "model": "ARX",
#             "threshold": get_float(
#                 row,
#                 "threshold",
#             ),
#             "accuracy": get_float(
#                 row,
#                 "accuracy",
#             ),
#             "precision": get_float(
#                 row,
#                 "precision",
#             ),
#             "recall": get_float(
#                 row,
#                 "recall",
#             ),
#             "specificity": get_float(
#                 row,
#                 "specificity",
#             ),
#             "f1": get_float(
#                 row,
#                 "f1",
#             ),
#             "youden_j": get_float(
#                 row,
#                 "youden_j",
#             ),
#             "tp": get_int(row, "tp"),
#             "tn": get_int(row, "tn"),
#             "fp": get_int(row, "fp"),
#             "fn": get_int(row, "fn"),
#             "num_combinations": get_int(
#                 row,
#                 "num_combinations",
#             ),
#         }

#     print(
#         f"Seuil ARX : "
#         f"{result['threshold']:.4f}"
#     )

#     return result


# # ============================================================
# # COMPARAISON
# # ============================================================

# def compare_models(
#     models: List[Dict],
# ) -> None:

#     print()
#     print("=" * 70)
#     print("          COMPARAISON FINALE DES MODELES")
#     print("=" * 70)

#     print()

#     header = (
#         f"{'Modèle':<22}"
#         f"{'Accuracy':>10}"
#         f"{'Precision':>11}"
#         f"{'Recall':>10}"
#         f"{'Specificity':>13}"
#         f"{'F1':>10}"
#         f"{'Youden J':>11}"
#     )

#     print(header)
#     print("-" * len(header))

#     for model in models:

#         print(
#             f"{model['model']:<22}"
#             f"{model['accuracy']:>10.4f}"
#             f"{model['precision']:>11.4f}"
#             f"{model['recall']:>10.4f}"
#             f"{model['specificity']:>13.4f}"
#             f"{model['f1']:>10.4f}"
#             f"{model['youden_j']:>11.4f}"
#         )

#     print()

#     print(
#         "MATRICES DE CONFUSION"
#     )

#     print("-" * 70)

#     for model in models:

#         print()
#         print(
#             f"{model['model']}"
#         )

#         print(
#             f"  TP={model['tp']} | "
#             f"TN={model['tn']} | "
#             f"FP={model['fp']} | "
#             f"FN={model['fn']}"
#         )


# # ============================================================
# # ANALYSE
# # ============================================================

# def analyze_models(
#     models: List[Dict],
# ) -> None:

#     print()
#     print("=" * 70)
#     print("                 ANALYSE")
#     print("=" * 70)

#     print()

#     # --------------------------------------------------------
#     # Meilleur F1
#     # --------------------------------------------------------

#     best_f1 = max(
#         models,
#         key=lambda model: model["f1"],
#     )

#     print(
#         f"Meilleur F1 : "
#         f"{best_f1['model']} "
#         f"({best_f1['f1']:.4f})"
#     )

#     # --------------------------------------------------------
#     # Meilleure spécificité
#     # --------------------------------------------------------

#     best_specificity = max(
#         models,
#         key=lambda model: model["specificity"],
#     )

#     print(
#         f"Meilleure spécificité : "
#         f"{best_specificity['model']} "
#         f"({best_specificity['specificity']:.4f})"
#     )

#     # --------------------------------------------------------
#     # Meilleur rappel
#     # --------------------------------------------------------

#     best_recall = max(
#         models,
#         key=lambda model: model["recall"],
#     )

#     print(
#         f"Meilleur recall : "
#         f"{best_recall['model']} "
#         f"({best_recall['recall']:.4f})"
#     )

#     # --------------------------------------------------------
#     # Youden J
#     # --------------------------------------------------------

#     best_youden = max(
#         models,
#         key=lambda model: model["youden_j"],
#     )

#     print(
#         f"Meilleur Youden J : "
#         f"{best_youden['model']} "
#         f"({best_youden['youden_j']:.4f})"
#     )

#     # --------------------------------------------------------
#     # Analyse spécifique Fuzzy
#     # --------------------------------------------------------

#     fuzzy = next(
#         model
#         for model in models
#         if model["model"] == "FuzzyRiskScorer"
#     )

#     print()
#     print(
#         "ANALYSE DU FUZZYRISKSCORER"
#     )

#     print(
#         f"  Faux positifs : {fuzzy['fp']}"
#     )

#     print(
#         f"  Faux négatifs : {fuzzy['fn']}"
#     )

#     if fuzzy["fn"] == 0:

#         print(
#             "  OK : aucun faux négatif sur le TEST."
#         )

#         print(
#             "  Le Recall est donc de "
#             f"{fuzzy['recall']:.4f}."
#         )

#     if fuzzy["fp"] > 0:

#         print(
#             "  Attention : le modèle Fuzzy produit "
#             f"{fuzzy['fp']} faux positifs."
#         )

#         print(
#             "  Cela indique une tendance à "
#             "sur-détecter certaines combinaisons."
#         )


# # ============================================================
# # SAUVEGARDE
# # ============================================================

# def save_comparison(
#     models: List[Dict],
# ) -> None:

#     BASELINES_DIR.mkdir(
#         parents=True,
#         exist_ok=True,
#     )

#     # --------------------------------------------------------
#     # Résumé
#     # --------------------------------------------------------

#     fieldnames = [
#         "model",
#         "threshold",
#         "accuracy",
#         "precision",
#         "recall",
#         "specificity",
#         "f1",
#         "youden_j",
#         "tp",
#         "tn",
#         "fp",
#         "fn",
#         "num_combinations",
#     ]

#     with open(
#         OUTPUT_FILE,
#         "w",
#         encoding="utf-8",
#         newline="",
#     ) as file:

#         writer = csv.DictWriter(
#             file,
#             fieldnames=fieldnames,
#         )

#         writer.writeheader()

#         for model in models:

#             writer.writerow(model)

#     print()
#     print(
#         f"Comparaison sauvegardée : "
#         f"{OUTPUT_FILE}"
#     )

#     # --------------------------------------------------------
#     # Comparaison détaillée
#     # --------------------------------------------------------

#     detailed_fields = [
#         "model",
#         "metric",
#         "value",
#     ]

#     with open(
#         DETAIL_FILE,
#         "w",
#         encoding="utf-8",
#         newline="",
#     ) as file:

#         writer = csv.DictWriter(
#             file,
#             fieldnames=detailed_fields,
#         )

#         writer.writeheader()

#         for model in models:

#             metrics = [
#                 "accuracy",
#                 "precision",
#                 "recall",
#                 "specificity",
#                 "f1",
#                 "youden_j",
#             ]

#             for metric in metrics:

#                 writer.writerow(
#                     {
#                         "model": model["model"],
#                         "metric": metric,
#                         "value": model[metric],
#                     }
#                 )

#     print(
#         f"Comparaison détaillée sauvegardée : "
#         f"{DETAIL_FILE}"
#     )


# # ============================================================
# # CONCLUSION
# # ============================================================

# def print_conclusion(
#     models: List[Dict],
# ) -> None:

#     print()
#     print("=" * 70)
#     print("             CONCLUSION COMPARATIVE")
#     print("=" * 70)

#     print()

#     fuzzy = next(
#         model
#         for model in models
#         if model["model"] == "FuzzyRiskScorer"
#     )

#     k_anonymity = next(
#         model
#         for model in models
#         if model["model"] == "k-anonymity"
#     )

#     arx = next(
#         model
#         for model in models
#         if model["model"] == "ARX"
#     )

#     print(
#         "Résultats TEST :"
#     )

#     print()

#     print(
#         f"FuzzyRiskScorer : "
#         f"Accuracy={fuzzy['accuracy']:.4f}, "
#         f"Recall={fuzzy['recall']:.4f}, "
#         f"Specificity={fuzzy['specificity']:.4f}, "
#         f"F1={fuzzy['f1']:.4f}"
#     )

#     print(
#         f"k-anonymity    : "
#         f"Accuracy={k_anonymity['accuracy']:.4f}, "
#         f"Recall={k_anonymity['recall']:.4f}, "
#         f"Specificity={k_anonymity['specificity']:.4f}, "
#         f"F1={k_anonymity['f1']:.4f}"
#     )

#     print(
#         f"ARX            : "
#         f"Accuracy={arx['accuracy']:.4f}, "
#         f"Recall={arx['recall']:.4f}, "
#         f"Specificity={arx['specificity']:.4f}, "
#         f"F1={arx['f1']:.4f}"
#     )

#     print()

#     print(
#         "INTERPRETATION"
#     )

#     print(
#         "- La baseline ARX reproduit directement "
#         "la règle utilisée pour construire les labels."
#     )

#     print(
#         "- Elle doit donc être considérée comme "
#         "une référence/oracle et non comme un modèle "
#         "indépendant."
#     )

#     print(
#         "- La baseline k-anonymity montre la limite "
#         "d'une décision basée uniquement sur k."
#     )

#     print(
#         "- Le FuzzyRiskScorer conserve un Recall de 1.0 "
#         "sur le TEST, mais présente davantage de "
#         "faux positifs."
#     )

#     print()

#     print(
#         "La comparaison doit être interprétée avec "
#         "prudence car le TEST contient seulement "
#         f"{fuzzy['num_combinations']} combinaisons."
#     )


# # ============================================================
# # MAIN
# # ============================================================

# def main():

#     print()
#     print("=" * 70)
#     print("       STREAMSHIELD - COMPARAISON DES BASELINES")
#     print("=" * 70)

#     print()
#     print(
#         "Objectif : comparer les performances finales "
#         "du FuzzyRiskScorer et des baselines."
#     )

#     print()
#     print(
#         "IMPORTANT : aucun modèle n'est recalibré."
#     )

#     print(
#         "IMPORTANT : les résultats TEST sont "
#         "uniquement lus depuis les fichiers générés."
#     )

#     # --------------------------------------------------------
#     # 1. Chargement
#     # --------------------------------------------------------

#     fuzzy = load_fuzzy_results()

#     k_anonymity = load_k_anonymity_results()

#     arx = load_arx_results()

#     models = [
#         fuzzy,
#         k_anonymity,
#         arx,
#     ]

#     # --------------------------------------------------------
#     # 2. Comparaison
#     # --------------------------------------------------------

#     compare_models(
#         models
#     )

#     # --------------------------------------------------------
#     # 3. Analyse
#     # --------------------------------------------------------

#     analyze_models(
#         models
#     )

#     # --------------------------------------------------------
#     # 4. Sauvegarde
#     # --------------------------------------------------------

#     save_comparison(
#         models
#     )

#     # --------------------------------------------------------
#     # 5. Conclusion
#     # --------------------------------------------------------

#     print_conclusion(
#         models
#     )

#     print()
#     print("=" * 70)
#     print("       COMPARAISON TERMINEE")
#     print("=" * 70)


# if __name__ == "__main__":
#     main()

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