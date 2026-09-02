import asyncio
import csv
from pathlib import Path
from typing import Dict, List, Tuple
import sys
# Ajouter la racine du service au PYTHONPATH
SERVICE_DIR = Path(__file__).resolve().parents[2]

if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.field_sensitivity_repository import load_field_sensitivity
# ============================================================
# CONFIGURATION
# ============================================================

# IMPORTANT :
# Le seuil a été calibré puis validé.
# Il est maintenant FIGÉ pour le TEST FINAL.
TEST_THRESHOLD = 0.70

# Seuil ARX utilisé pour définir le label de référence.
ARX_THRESHOLD = 0.09


# ============================================================
# CHEMINS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATASET_FILE = (
    BASE_DIR
    / "data"
    / "validation"
    / "uci_adult"
    / "processed"
    / "adult_prepared.csv"
)

# Jeu de TEST indépendant
ARX_TEST_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "test"
    / "arx_test_labels.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "test"
    / "fuzzy_test_results.csv"
)

SUMMARY_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "test"
    / "fuzzy_test_summary.csv"
)


# ============================================================
# CHARGEMENT DATASET
# ============================================================

def load_dataset() -> List[Dict]:

    print()
    print("=" * 70)
    print("       CHARGEMENT DU DATASET UCI ADULT")
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

        fieldnames = reader.fieldnames or []

    print(f"Nombre de records : {len(records)}")
    print(f"Nombre de colonnes : {len(fieldnames)}")

    return records


# ============================================================
# CHARGEMENT TEST
# ============================================================

def load_test_labels() -> List[Dict]:

    print()
    print("=" * 70)
    print("       CHARGEMENT DU JEU DE TEST")
    print("=" * 70)

    print(f"Fichier : {ARX_TEST_FILE}")

    if not ARX_TEST_FILE.exists():
        raise FileNotFoundError(
            f"Fichier TEST introuvable : {ARX_TEST_FILE}"
        )

    rows = []

    with open(
        ARX_TEST_FILE,
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        required_columns = {
            "id",
            "combination",
            "num_qi",
            "num_records",
            "average_risk",
            "label",
        }

        missing = (
            required_columns
            - set(reader.fieldnames or [])
        )

        if missing:
            raise ValueError(
                "Colonnes manquantes dans le jeu de test : "
                f"{sorted(missing)}"
            )

        for row in reader:

            fields = tuple(
                field.strip()
                for field in row["combination"].split("+")
            )

            average_risk = float(
                row["average_risk"]
            )

            arx_label = int(
                row["label"]
            )

            # ------------------------------------------------
            # Vérification du label ARX
            # ------------------------------------------------

            expected_label = int(
                average_risk >= ARX_THRESHOLD
            )

            if arx_label != expected_label:
                raise ValueError(
                    "Label ARX incohérent : "
                    f"id={row['id']}, "
                    f"average_risk={average_risk}, "
                    f"label={arx_label}, "
                    f"attendu={expected_label}"
                )

            rows.append(
                {
                    "id": row["id"],
                    "combination": row["combination"],
                    "fields": fields,
                    "num_qi": int(row["num_qi"]),
                    "num_records": int(row["num_records"]),
                    "average_risk": average_risk,
                    "arx_label": arx_label,
                }
            )

    print(
        f"Combinaisons TEST : {len(rows)}"
    )

    if len(rows) != 6:
        raise ValueError(
            "Le jeu de test doit contenir exactement "
            f"6 combinaisons. Nombre trouvé : {len(rows)}"
        )

    print()
    print("Combinaisons utilisées pour le TEST :")

    for row in rows:
        print(
            f"  {row['id']} | "
            f"{row['combination']} | "
            f"ARX={row['average_risk']:.6f} | "
            f"label={row['arx_label']}"
        )

    return rows


# ============================================================
# METRIQUES
# ============================================================

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


# ============================================================
# CALCUL FUZZY SUR LE TEST
# ============================================================

async def compute_test_scores(
    test_rows: List[Dict],
    records: List[Dict],
) -> List[Dict]:

    print()
    print("=" * 70)
    print("       CALCUL DES SCORES FUZZY - TEST FINAL")
    print("=" * 70)

    # --------------------------------------------------------
    # Chargement des sensibilités
    # --------------------------------------------------------

    field_sensitivity = await load_field_sensitivity(
        force_refresh=True
    )

    print(
        f"Sensibilités chargées depuis MongoDB : "
        f"{len(field_sensitivity)}"
    )

    # --------------------------------------------------------
    # Chargement du modèle fuzzy
    # --------------------------------------------------------

    scorer = FuzzyRiskScorer(
        threshold=TEST_THRESHOLD,
        field_sensitivity=field_sensitivity,
        min_sample_size=0,
    )

    await scorer.load_fuzzy_configuration()

    print(
        f"Règles fuzzy chargées : "
        f"{len(scorer.fuzzy_rules)}"
    )

    results = []

    for row in test_rows:

        fields: Tuple[str, ...] = row["fields"]

        result = scorer.score(
            records,
            fields,
        )

        fuzzy_score = result.score

        # ----------------------------------------------------
        # IMPORTANT :
        # seuil FIGÉ = 0.70
        # aucun recalibrage
        # ----------------------------------------------------

        fuzzy_label = int(
            fuzzy_score >= TEST_THRESHOLD
        )

        results.append(
            {
                "id": row["id"],
                "combination": row["combination"],
                "num_qi": row["num_qi"],
                "num_records": row["num_records"],
                "arx_average_risk": row["average_risk"],
                "arx_label": row["arx_label"],
                "k": result.k,
                "uniqueness": result.uniqueness,
                "avg_sensitivity": result.avg_sensitivity,
                "fuzzy_score": fuzzy_score,
                "fuzzy_label": fuzzy_label,
                "sample_size": result.sample_size,
            }
        )

        print(
            f"{row['id']} | "
            f"{row['combination']:<55} | "
            f"ARX={row['average_risk']:.6f} | "
            f"ARX_LABEL={row['arx_label']} | "
            f"k={result.k} | "
            f"U={result.uniqueness:.4f} | "
            f"S={result.avg_sensitivity:.4f} | "
            f"Fuzzy={fuzzy_score:.4f} | "
            f"Fuzzy_LABEL={fuzzy_label}"
        )

    return results


# ============================================================
# EVALUATION FINALE
# ============================================================

def evaluate_test(
    results: List[Dict],
) -> Dict:

    print()
    print("=" * 70)
    print("       EVALUATION FINALE SUR LE TEST")
    print("=" * 70)

    print()
    print(
        f"Seuil Fuzzy FIGÉ : "
        f"{TEST_THRESHOLD:.2f}"
    )

    print(
        f"Seuil ARX de référence : "
        f"{ARX_THRESHOLD:.2f}"
    )

    y_true = [
        row["arx_label"]
        for row in results
    ]

    y_pred = [
        row["fuzzy_label"]
        for row in results
    ]

    metrics = compute_metrics(
        y_true,
        y_pred,
    )

    print()
    print("RESULTATS TEST")
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

    print()

    print(
        f"TP={metrics['tp']} | "
        f"FP={metrics['fp']} | "
        f"FN={metrics['fn']} | "
        f"TN={metrics['tn']}"
    )

    return metrics


# ============================================================
# ANALYSE DES ERREURS
# ============================================================

def analyze_errors(
    results: List[Dict],
) -> None:

    print()
    print("=" * 70)
    print("       ANALYSE DES ERREURS TEST")
    print("=" * 70)

    false_positives = [
        row
        for row in results
        if row["arx_label"] == 0
        and row["fuzzy_label"] == 1
    ]

    false_negatives = [
        row
        for row in results
        if row["arx_label"] == 1
        and row["fuzzy_label"] == 0
    ]

    print()
    print(
        f"Faux positifs : {len(false_positives)}"
    )

    for row in false_positives:

        print(
            f"  FP | {row['id']} | "
            f"{row['combination']} | "
            f"ARX={row['arx_average_risk']:.6f} | "
            f"Fuzzy={row['fuzzy_score']:.4f}"
        )

    print()
    print(
        f"Faux négatifs : {len(false_negatives)}"
    )

    for row in false_negatives:

        print(
            f"  FN | {row['id']} | "
            f"{row['combination']} | "
            f"ARX={row['arx_average_risk']:.6f} | "
            f"Fuzzy={row['fuzzy_score']:.4f}"
        )


# ============================================================
# SAUVEGARDE
# ============================================================

def save_results(
    results: List[Dict],
    metrics: Dict,
) -> None:

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        "fuzzy_label",
        "sample_size",
    ]

    with open(
        OUTPUT_FILE,
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

    summary_fields = [
        "threshold",
        "arx_threshold",
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
        "num_combinations",
    ]

    summary_row = {
        "threshold": TEST_THRESHOLD,
        "arx_threshold": ARX_THRESHOLD,
        "accuracy": metrics["accuracy"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "specificity": metrics["specificity"],
        "f1": metrics["f1"],
        "youden_j": metrics["youden_j"],
        "tp": metrics["tp"],
        "tn": metrics["tn"],
        "fp": metrics["fp"],
        "fn": metrics["fn"],
        "num_combinations": len(results),
    }

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=summary_fields,
        )

        writer.writeheader()
        writer.writerow(summary_row)

    print()
    print("=" * 70)
    print("       SAUVEGARDE DES RESULTATS TEST")
    print("=" * 70)

    print()
    print(
        f"Résultats détaillés : {OUTPUT_FILE}"
    )

    print(
        f"Résumé : {SUMMARY_FILE}"
    )


# ============================================================
# CONCLUSION
# ============================================================

def print_conclusion(
    metrics: Dict,
) -> None:

    print()
    print("=" * 70)
    print("       CONCLUSION DU TEST FINAL")
    print("=" * 70)

    print()
    print(
        "Le seuil utilisé pour cette évaluation est "
        "le seuil final fixé à 0.70."
    )

    print(
        "Aucun recalibrage n'a été effectué sur le jeu de test."
    )

    print()

    print(
        f"Recall TEST      : "
        f"{metrics['recall']:.4f}"
    )

    print(
        f"Specificity TEST : "
        f"{metrics['specificity']:.4f}"
    )

    print(
        f"F1 TEST          : "
        f"{metrics['f1']:.4f}"
    )

    print()

    print(
        "Le jeu de TEST a été utilisé uniquement "
        "pour l'évaluation finale des performances."
    )

    print(
        "Le seuil 0.70 reste inchangé."
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("=" * 70)
    print("       STREAMSHIELD - TEST FINAL")
    print("=" * 70)

    print()
    print(
        "Objectif : évaluer définitivement le modèle "
        "avec le seuil fixé à 0.70."
    )

    print()
    print(
        f"SEUIL FIGÉ = {TEST_THRESHOLD:.2f}"
    )

    print(
        "IMPORTANT : aucun recalibrage sur le TEST."
    )

    # --------------------------------------------------------
    # 1. Dataset UCI Adult
    # --------------------------------------------------------

    records = load_dataset()

    # --------------------------------------------------------
    # 2. Labels ARX du TEST
    # --------------------------------------------------------

    test_rows = load_test_labels()

    # --------------------------------------------------------
    # 3. Calcul des scores Fuzzy
    # --------------------------------------------------------

    results = await compute_test_scores(
        test_rows,
        records,
    )

    # --------------------------------------------------------
    # 4. Evaluation finale
    # --------------------------------------------------------

    metrics = evaluate_test(
        results
    )

    # --------------------------------------------------------
    # 5. Analyse des erreurs
    # --------------------------------------------------------

    analyze_errors(
        results
    )

    # --------------------------------------------------------
    # 6. Sauvegarde
    # --------------------------------------------------------

    save_results(
        results,
        metrics,
    )

    # --------------------------------------------------------
    # 7. Conclusion
    # --------------------------------------------------------

    print_conclusion(
        metrics
    )


if __name__ == "__main__":
    asyncio.run(main())
