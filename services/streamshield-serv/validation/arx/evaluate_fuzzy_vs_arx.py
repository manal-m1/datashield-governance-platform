"""
StreamShield - Validation Fuzzy vs ARX

Objectif
--------
Comparer le FuzzyRiskScorer de StreamShield aux labels de référence
obtenus avec ARX sur les 30 combinaisons UCI Adult.

Référence ARX :
    average_risk < 0.09  -> label 0
    average_risk >= 0.09 -> label 1

Validation fuzzy :
    fuzzy_score >= threshold -> prediction 1
    fuzzy_score < threshold  -> prediction 0

Le script teste plusieurs seuils fuzzy afin de déterminer
objectivement le seuil offrant le meilleur compromis.
"""

import asyncio
import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import sys
# Ajouter services/streamshield-serv au PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.field_sensitivity_repository import load_field_sensitivity
from detection.fuzzy_config_repository import load_fuzzy_config


# ============================================================================
# CONFIGURATION
# ============================================================================

CURRENT_FUZZY_THRESHOLD = 0.70

THRESHOLDS = [
    0.10,
    0.15,
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
    0.85,
    0.90,
]

ARX_THRESHOLD = 0.09

BASE_DIR = Path(__file__).resolve().parent

ARX_LABELS_FILE = (
    BASE_DIR
    / "java"
    / "arx_30_labels.csv"
)

DATASET_FILE = (
    BASE_DIR.parent.parent
    / "data"
    / "validation"
    / "uci_adult"
    / "processed"
    / "adult_prepared.csv"
)

DETAIL_RESULTS_FILE = (
    BASE_DIR
    / "fuzzy_vs_arx_results.csv"
)

THRESHOLD_RESULTS_FILE = (
    BASE_DIR
    / "fuzzy_threshold_evaluation.csv"
)


# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s - %(message)s",
)


# ============================================================================
# CHARGEMENT DES LABELS ARX
# ============================================================================

def load_arx_labels() -> List[Dict]:
    """
    Charge les 30 combinaisons et leurs labels ARX.
    """

    print()
    print("=" * 70)
    print("       CHARGEMENT DES LABELS ARX")
    print("=" * 70)

    print(f"Fichier : {ARX_LABELS_FILE}")

    if not ARX_LABELS_FILE.exists():
        raise FileNotFoundError(
            f"Fichier ARX introuvable : {ARX_LABELS_FILE}"
        )

    rows = []

    with open(
        ARX_LABELS_FILE,
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            combination = row["combination"]

            fields = tuple(
                field.strip()
                for field in combination.split("+")
            )

            average_risk = float(
                row["average_risk"]
            )

            label = int(row["label"])

            rows.append(
                {
                    "id": row["id"],
                    "combination": combination,
                    "fields": fields,
                    "num_qi": int(row["num_qi"]),
                    "num_records": int(row["num_records"]),
                    "average_risk": average_risk,
                    "arx_label": label,
                }
            )

    print(
        f"Combinaisons chargées : {len(rows)}"
    )

    return rows


# ============================================================================
# CHARGEMENT DU DATASET
# ============================================================================

def load_dataset() -> List[Dict]:
    """
    Charge le dataset UCI Adult préparé.
    """

    print()
    print("=" * 70)
    print("       CHARGEMENT DU DATASET")
    print("=" * 70)

    print(f"Fichier : {DATASET_FILE}")

    if not DATASET_FILE.exists():
        raise FileNotFoundError(
            f"Dataset introuvable : {DATASET_FILE}"
        )

    with open(
        DATASET_FILE,
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        records = list(reader)

    print(
        f"Nombre de records : {len(records)}"
    )

    print(
        f"Nombre de colonnes : "
        f"{len(reader.fieldnames or [])}"
    )

    return records


# ============================================================================
# METRIQUES
# ============================================================================

def compute_metrics(
    y_true: List[int],
    y_pred: List[int],
) -> Dict[str, float]:

    tp = sum(
        1
        for true, pred in zip(y_true, y_pred)
        if true == 1 and pred == 1
    )

    tn = sum(
        1
        for true, pred in zip(y_true, y_pred)
        if true == 0 and pred == 0
    )

    fp = sum(
        1
        for true, pred in zip(y_true, y_pred)
        if true == 0 and pred == 1
    )

    fn = sum(
        1
        for true, pred in zip(y_true, y_pred)
        if true == 1 and pred == 0
    )

    total = tp + tn + fp + fn

    accuracy = (
        (tp + tn) / total
        if total
        else 0.0
    )

    precision = (
        tp / (tp + fp)
        if (tp + fp)
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn)
        else 0.0
    )

    specificity = (
        tn / (tn + fp)
        if (tn + fp)
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    youden_j = (
        recall + specificity - 1.0
    )

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "youden_j": youden_j,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


# ============================================================================
# SCORE FUZZY DES 30 COMBINAISONS
# ============================================================================

async def compute_fuzzy_scores(
    arx_rows: List[Dict],
    records: List[Dict],
) -> List[Dict]:

    print()
    print("=" * 70)
    print("       CALCUL DES SCORES FUZZY")
    print("=" * 70)

    # ------------------------------------------------------------------------
    # Chargement des sensibilités depuis MongoDB
    # ------------------------------------------------------------------------

    print()
    print("Chargement des sensibilités depuis MongoDB...")

    field_sensitivity = await load_field_sensitivity(
        force_refresh=True
    )

    print(
        f"Sensibilités chargées : "
        f"{len(field_sensitivity)}"
    )

    # ------------------------------------------------------------------------
    # Création du scorer
    # ------------------------------------------------------------------------

    scorer = FuzzyRiskScorer(
        threshold=CURRENT_FUZZY_THRESHOLD,
        field_sensitivity=field_sensitivity,
    )

    # ------------------------------------------------------------------------
    # Configuration + règles fuzzy depuis MongoDB
    # ------------------------------------------------------------------------

    print(
        "Chargement de la configuration fuzzy..."
    )

    await scorer.load_fuzzy_configuration()

    print(
        f"Règles fuzzy chargées : "
        f"{len(scorer.fuzzy_rules)}"
    )

    # ------------------------------------------------------------------------
    # Calcul
    # ------------------------------------------------------------------------

    results = []

    for index, row in enumerate(
        arx_rows,
        start=1,
    ):

        fields: Tuple[str, ...] = row["fields"]

        result = scorer.score(
            records,
            fields,
        )

        results.append(
            {
                "id": row["id"],
                "combination": row["combination"],
                "num_qi": row["num_qi"],
                "num_records": row["num_records"],

                "arx_average_risk":
                    row["average_risk"],

                "arx_label":
                    row["arx_label"],

                "k":
                    result.k,

                "uniqueness":
                    result.uniqueness,

                "avg_sensitivity":
                    result.avg_sensitivity,

                "fuzzy_score":
                    result.score,

                "fuzzy_prediction_at_current_threshold":
                    int(result.score >= CURRENT_FUZZY_THRESHOLD),

                "sample_size":
                    result.sample_size,
            }
        )

        print(
            f"{row['id']} | "
            f"{row['combination']:<55} | "
            f"ARX={row['average_risk']:.6f} | "
            f"label={row['arx_label']} | "
            f"k={result.k} | "
            f"U={result.uniqueness:.4f} | "
            f"S={result.avg_sensitivity:.4f} | "
            f"Fuzzy={result.score:.4f}"
        )

    return results


# ============================================================================
# SAUVEGARDE DES RESULTATS DETAILLES
# ============================================================================

def save_detail_results(
    results: List[Dict],
) -> None:

    fieldnames = [
        "id",
        "combination",
        "num_qi",
        "num_records",
        "arx_average_risk",
        "arx_label",
        "k",
        "uniqueness",
        "avg_sensitivity",
        "fuzzy_score",
        "fuzzy_prediction_at_current_threshold",
        "sample_size",
    ]

    with open(
        DETAIL_RESULTS_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(results)

    print()
    print(
        f"Résultats détaillés sauvegardés : "
        f"{DETAIL_RESULTS_FILE}"
    )


# ============================================================================
# EVALUATION DES SEUILS
# ============================================================================

def evaluate_thresholds(
    results: List[Dict],
) -> List[Dict]:

    print()
    print("=" * 70)
    print("       EVALUATION DES SEUILS FUZZY")
    print("=" * 70)

    y_true = [
        row["arx_label"]
        for row in results
    ]

    evaluations = []

    print()
    print(
        "SEUIL | ACCURACY | PRECISION | RECALL | "
        "SPECIFICITY | F1 | YOUDEN | TP | FP | FN | TN"
    )

    print("-" * 110)

    for threshold in THRESHOLDS:

        y_pred = [
            int(
                row["fuzzy_score"]
                >= threshold
            )
            for row in results
        ]

        metrics = compute_metrics(
            y_true,
            y_pred,
        )

        evaluation = {
            "threshold": threshold,
            **metrics,
        }

        evaluations.append(
            evaluation
        )

        print(
            f"{threshold:5.2f} | "
            f"{metrics['accuracy']:.4f} | "
            f"{metrics['precision']:.4f} | "
            f"{metrics['recall']:.4f} | "
            f"{metrics['specificity']:.4f} | "
            f"{metrics['f1']:.4f} | "
            f"{metrics['youden_j']:.4f} | "
            f"{metrics['tp']:2d} | "
            f"{metrics['fp']:2d} | "
            f"{metrics['fn']:2d} | "
            f"{metrics['tn']:2d}"
        )

    return evaluations


# ============================================================================
# SELECTION DU SEUIL
# ============================================================================

def select_best_threshold(
    evaluations: List[Dict],
) -> Tuple[Dict, Dict]:

    # ------------------------------------------------------------------------
    # Meilleur seuil selon F1
    #
    # En cas d'égalité :
    # 1. meilleur recall
    # 2. meilleure précision
    # ------------------------------------------------------------------------

    best_f1 = max(
        evaluations,
        key=lambda x: (
            x["f1"],
            x["recall"],
            x["precision"],
        ),
    )

    # ------------------------------------------------------------------------
    # Meilleur seuil selon Youden J
    # ------------------------------------------------------------------------

    best_youden = max(
        evaluations,
        key=lambda x: (
            x["youden_j"],
            x["recall"],
        ),
    )

    return best_f1, best_youden


# ============================================================================
# AFFICHAGE DU SEUIL ACTUEL
# ============================================================================

def show_current_threshold(
    results: List[Dict],
) -> Dict:

    y_true = [
        row["arx_label"]
        for row in results
    ]

    y_pred = [
        int(
            row["fuzzy_score"]
            >= CURRENT_FUZZY_THRESHOLD
        )
        for row in results
    ]

    metrics = compute_metrics(
        y_true,
        y_pred,
    )

    print()
    print("=" * 70)
    print("       PERFORMANCE DU SEUIL ACTUEL")
    print("=" * 70)

    print(
        f"Seuil actuel : {CURRENT_FUZZY_THRESHOLD}"
    )

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
        f"F1-score     : {metrics['f1']:.4f}"
    )

    print(
        f"Youden J     : {metrics['youden_j']:.4f}"
    )

    print()
    print(
        "Matrice de confusion :"
    )

    print(
        f"TP = {metrics['tp']} | "
        f"FP = {metrics['fp']} | "
        f"FN = {metrics['fn']} | "
        f"TN = {metrics['tn']}"
    )

    return metrics


# ============================================================================
# SAUVEGARDE DES EVALUATIONS
# ============================================================================

def save_threshold_results(
    evaluations: List[Dict],
) -> None:

    fieldnames = [
        "threshold",
        "accuracy",
        "precision",
        "recall",
        "specificity",
        "f1",
        "youden_j",
        "tp",
        "tn",
        "fp",
        "fn",
    ]

    with open(
        THRESHOLD_RESULTS_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            evaluations
        )

    print()
    print(
        f"Evaluation des seuils sauvegardée : "
        f"{THRESHOLD_RESULTS_FILE}"
    )


# ============================================================================
# ANALYSE DES COMBINAISONS
# ============================================================================

def show_predictions_at_best_threshold(
    results: List[Dict],
    threshold: float,
) -> None:

    print()
    print("=" * 70)
    print(
        f"       PREDICTIONS AU SEUIL {threshold:.2f}"
    )
    print("=" * 70)

    print(
        "ID   ARX   FUZZY   RESULTAT   COMBINAISON"
    )

    print("-" * 90)

    for row in results:

        fuzzy_prediction = int(
            row["fuzzy_score"]
            >= threshold
        )

        if fuzzy_prediction == row["arx_label"]:
            status = "OK"
        elif fuzzy_prediction == 1:
            status = "FP"
        else:
            status = "FN"

        print(
            f"{row['id']:3s}  "
            f"{row['arx_label']}     "
            f"{fuzzy_prediction}       "
            f"{status:>2s}       "
            f"{row['combination']}"
        )


# ============================================================================
# MAIN
# ============================================================================

async def main():

    print()
    print("=" * 70)
    print("       STREAMSHIELD : FUZZY VS ARX")
    print("=" * 70)

    print()
    print(
        f"Seuil ARX : {ARX_THRESHOLD}"
    )

    print(
        "Règle ARX : "
        "average_risk < 0.09 -> 0 ; "
        "average_risk >= 0.09 -> 1"
    )

    print(
        f"Seuil fuzzy actuel : "
        f"{CURRENT_FUZZY_THRESHOLD}"
    )

    # ------------------------------------------------------------------------
    # 1. ARX
    # ------------------------------------------------------------------------

    arx_rows = load_arx_labels()

    # ------------------------------------------------------------------------
    # 2. Dataset
    # ------------------------------------------------------------------------

    records = load_dataset()

    # ------------------------------------------------------------------------
    # 3. Fuzzy scores
    # ------------------------------------------------------------------------

    results = await compute_fuzzy_scores(
        arx_rows,
        records,
    )

    # ------------------------------------------------------------------------
    # 4. Sauvegarde détaillée
    # ------------------------------------------------------------------------

    save_detail_results(results)

    # ------------------------------------------------------------------------
    # 5. Performance seuil actuel
    # ------------------------------------------------------------------------

    show_current_threshold(
        results
    )

    # ------------------------------------------------------------------------
    # 6. Evaluation de plusieurs seuils
    # ------------------------------------------------------------------------

    evaluations = evaluate_thresholds(
        results
    )

    save_threshold_results(
        evaluations
    )

    # ------------------------------------------------------------------------
    # 7. Meilleurs seuils
    # ------------------------------------------------------------------------

    best_f1, best_youden = (
        select_best_threshold(
            evaluations
        )
    )

    print()
    print("=" * 70)
    print("       SEUILS OPTIMAUX")
    print("=" * 70)

    print()
    print(">>> Meilleur seuil selon F1-score")

    print(
        f"Seuil       : "
        f"{best_f1['threshold']:.2f}"
    )

    print(
        f"Accuracy    : "
        f"{best_f1['accuracy']:.4f}"
    )

    print(
        f"Precision   : "
        f"{best_f1['precision']:.4f}"
    )

    print(
        f"Recall      : "
        f"{best_f1['recall']:.4f}"
    )

    print(
        f"Specificity : "
        f"{best_f1['specificity']:.4f}"
    )

    print(
        f"F1          : "
        f"{best_f1['f1']:.4f}"
    )

    print(
        f"Youden J    : "
        f"{best_f1['youden_j']:.4f}"
    )

    print()
    print(">>> Meilleur seuil selon Youden J")

    print(
        f"Seuil       : "
        f"{best_youden['threshold']:.2f}"
    )

    print(
        f"Accuracy    : "
        f"{best_youden['accuracy']:.4f}"
    )

    print(
        f"Precision   : "
        f"{best_youden['precision']:.4f}"
    )

    print(
        f"Recall      : "
        f"{best_youden['recall']:.4f}"
    )

    print(
        f"Specificity : "
        f"{best_youden['specificity']:.4f}"
    )

    print(
        f"F1          : "
        f"{best_youden['f1']:.4f}"
    )

    print(
        f"Youden J    : "
        f"{best_youden['youden_j']:.4f}"
    )

    # ------------------------------------------------------------------------
    # 8. Détails avec meilleur seuil F1
    # ------------------------------------------------------------------------

    show_predictions_at_best_threshold(
        results,
        best_f1["threshold"],
    )

    # ------------------------------------------------------------------------
    # 9. Conclusion automatique
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("       CONCLUSION")
    print("=" * 70)

    if (
        best_f1["threshold"]
        == CURRENT_FUZZY_THRESHOLD
    ):

        print(
            f"Le seuil actuel {CURRENT_FUZZY_THRESHOLD:.2f} "
            "correspond au meilleur seuil selon F1."
        )

    else:

        print(
            f"Le seuil actuel "
            f"{CURRENT_FUZZY_THRESHOLD:.2f} "
            f"n'est pas le meilleur seuil selon F1."
        )

        print(
            f"Seuil F1 recommandé sur cet "
            f"ensemble de validation : "
            f"{best_f1['threshold']:.2f}"
        )

    print()
    print(
        "IMPORTANT : le seuil recommandé est "
        "calibré sur les 30 combinaisons ARX "
        "de cette validation."
    )

    print(
        "Il ne doit pas être considéré comme "
        "un seuil universel sans validation "
        "complémentaire."
    )

    print()
    print("=" * 70)
    print("       VALIDATION TERMINEE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())