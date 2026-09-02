import csv
from pathlib import Path
from typing import Dict, List


# ============================================================
# STREAMSHIELD - BASELINE ARX
# ============================================================
#
# Objectif :
#   Évaluer une baseline utilisant directement le risque ARX.
#
# Principe :
#
#       average_risk >= ARX_THRESHOLD
#                    |
#                    v
#              ARX_LABEL = 1
#
#       average_risk < ARX_THRESHOLD
#                    |
#                    v
#              ARX_LABEL = 0
#
# Protocole :
#
#       TRAIN       -> vérification
#       VALIDATION  -> évaluation
#       TEST        -> évaluation finale
#
# IMPORTANT :
#   Le seuil ARX = 0.09 est défini par le protocole de référence.
#   Il n'est PAS recalibré sur le TEST.
#
# Cette baseline ne dépend PAS du modèle fuzzy.
# ============================================================


# ============================================================
# CONFIGURATION
# ============================================================

# Seuil ARX utilisé comme référence.
ARX_THRESHOLD = 0.09

# Nombre attendu de combinaisons
TRAIN_SIZE = 18
VALIDATION_SIZE = 6
TEST_SIZE = 6
TOTAL_SIZE = 30


# ============================================================
# CHEMINS
# ============================================================

# validation/arx/baselines/arx_baseline.py
#
# parents[1] = validation/arx
#
BASE_DIR = Path(__file__).resolve().parents[1]

DATASET_FILE = (
    BASE_DIR
    / ".."
    / ".."
    / "data"
    / "validation"
    / "uci_adult"
    / "processed"
    / "adult_prepared.csv"
).resolve()
# DATASET_FILE = (
#     BASE_DIR
#     / "data"
#     / "validation"
#     / "uci_adult"
#     / "processed"
#     / "adult_prepared.csv"
# )

TRAIN_FILE = (
    BASE_DIR
    / "train"
    / "arx_train_labels.csv"
)

VALIDATION_FILE = (
    BASE_DIR
    / "validation"
    / "arx_validation_labels.csv"
)

TEST_FILE = (
    BASE_DIR
    / "test"
    / "arx_test_labels.csv"
)


OUTPUT_DIR = (
    BASE_DIR
    / "baselines"
)


TRAIN_OUTPUT = (
    OUTPUT_DIR
    / "arx_baseline_train.csv"
)

VALIDATION_OUTPUT = (
    OUTPUT_DIR
    / "arx_baseline_validation.csv"
)

TEST_OUTPUT = (
    OUTPUT_DIR
    / "arx_baseline_test.csv"
)

SUMMARY_OUTPUT = (
    OUTPUT_DIR
    / "arx_baseline_summary.csv"
)


# ============================================================
# AFFICHAGE
# ============================================================

def print_header(title: str) -> None:

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# CHARGEMENT DATASET
# ============================================================

def load_dataset() -> List[Dict]:

    print_header(
        "       CHARGEMENT DU DATASET UCI ADULT"
    )

    print(
        f"Fichier : {DATASET_FILE}"
    )

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

    print(
        f"Nombre de records : {len(records)}"
    )

    print(
        f"Nombre de colonnes : {len(fieldnames)}"
    )

    return records


# ============================================================
# CHARGEMENT DES COMBINAISONS
# ============================================================

def load_combinations(
    filepath: Path,
    dataset_name: str,
) -> List[Dict]:

    print_header(
        f"       CHARGEMENT {dataset_name}"
    )

    print(
        f"Fichier : {filepath}"
    )

    if not filepath.exists():

        raise FileNotFoundError(
            f"Fichier introuvable : {filepath}"
        )

    rows = []

    with open(
        filepath,
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
                f"Colonnes manquantes dans {filepath}: "
                f"{sorted(missing)}"
            )

        for row in reader:

            average_risk = float(
                row["average_risk"]
            )

            reference_label = int(
                row["label"]
            )

            # ------------------------------------------------
            # Prédiction de la baseline ARX
            # ------------------------------------------------

            arx_prediction = int(
                average_risk >= ARX_THRESHOLD
            )

            rows.append(
                {
                    "id": row["id"],
                    "combination": row["combination"],
                    "num_qi": int(row["num_qi"]),
                    "num_records": int(row["num_records"]),
                    "average_risk": average_risk,
                    "reference_label": reference_label,
                    "arx_prediction": arx_prediction,
                }
            )

    print(
        f"Combinaisons chargées : {len(rows)}"
    )

    return rows


# ============================================================
# VERIFICATION DES LABELS
# ============================================================

def verify_labels(
    rows: List[Dict],
    dataset_name: str,
) -> None:

    print()
    print(
        f"Vérification des labels ARX - {dataset_name}"
    )

    errors = []

    for row in rows:

        expected_label = int(
            row["average_risk"] >= ARX_THRESHOLD
        )

        if row["reference_label"] != expected_label:

            errors.append(
                {
                    "id": row["id"],
                    "average_risk": row["average_risk"],
                    "reference_label": row["reference_label"],
                    "expected_label": expected_label,
                }
            )

    if errors:

        print(
            f"ERREUR : {len(errors)} labels incohérents."
        )

        for error in errors:

            print(
                f"  {error['id']} | "
                f"ARX={error['average_risk']:.6f} | "
                f"label={error['reference_label']} | "
                f"attendu={error['expected_label']}"
            )

        raise ValueError(
            f"Labels ARX incohérents dans {dataset_name}."
        )

    print(
        "OK : tous les labels correspondent "
        f"au seuil ARX = {ARX_THRESHOLD:.2f}"
    )


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

    total = (
        tp
        + tn
        + fp
        + fn
    )

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
        recall
        + specificity
        - 1.0
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
# AFFICHAGE DES RESULTATS
# ============================================================

def print_results(
    rows: List[Dict],
    dataset_name: str,
) -> Dict:

    print_header(
        f"       RESULTATS {dataset_name}"
    )

    print(
        f"Seuil ARX : {ARX_THRESHOLD:.2f}"
    )

    print()

    for row in rows:

        print(
            f"{row['id']} | "
            f"{row['combination']:<55} | "
            f"ARX={row['average_risk']:.6f} | "
            f"REFERENCE={row['reference_label']} | "
            f"ARX_LABEL={row['arx_prediction']}"
        )

    y_true = [
        row["reference_label"]
        for row in rows
    ]

    y_pred = [
        row["arx_prediction"]
        for row in rows
    ]

    metrics = compute_metrics(
        y_true,
        y_pred,
    )

    print()
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
    rows: List[Dict],
    dataset_name: str,
) -> None:

    print()
    print(
        f"Analyse des erreurs - {dataset_name}"
    )

    false_positives = [
        row
        for row in rows
        if (
            row["reference_label"] == 0
            and row["arx_prediction"] == 1
        )
    ]

    false_negatives = [
        row
        for row in rows
        if (
            row["reference_label"] == 1
            and row["arx_prediction"] == 0
        )
    ]

    print()
    print(
        f"Faux positifs : {len(false_positives)}"
    )

    for row in false_positives:

        print(
            f"  FP | {row['id']} | "
            f"{row['combination']} | "
            f"ARX={row['average_risk']:.6f}"
        )

    print()
    print(
        f"Faux négatifs : {len(false_negatives)}"
    )

    for row in false_negatives:

        print(
            f"  FN | {row['id']} | "
            f"{row['combination']} | "
            f"ARX={row['average_risk']:.6f}"
        )


# ============================================================
# SAUVEGARDE
# ============================================================

def save_results(
    rows: List[Dict],
    filepath: Path,
) -> None:

    filepath.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "id",
        "combination",
        "num_qi",
        "num_records",
        "average_risk",
        "reference_label",
        "arx_prediction",
    ]

    with open(
        filepath,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(rows)

    print(
        f"Résultats sauvegardés : {filepath}"
    )


# ============================================================
# RESUME
# ============================================================

def save_summary(
    train_metrics: Dict,
    validation_metrics: Dict,
    test_metrics: Dict,
) -> None:

    SUMMARY_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "dataset",
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
        "num_combinations",
    ]

    rows = [
        {
            "dataset": "train",
            "threshold": ARX_THRESHOLD,
            **train_metrics,
            "num_combinations": TRAIN_SIZE,
        },
        {
            "dataset": "validation",
            "threshold": ARX_THRESHOLD,
            **validation_metrics,
            "num_combinations": VALIDATION_SIZE,
        },
        {
            "dataset": "test",
            "threshold": ARX_THRESHOLD,
            **test_metrics,
            "num_combinations": TEST_SIZE,
        },
    ]

    with open(
        SUMMARY_OUTPUT,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(rows)

    print(
        f"Résumé sauvegardé : {SUMMARY_OUTPUT}"
    )


# ============================================================
# VERIFICATION DES TAILLES
# ============================================================

def verify_sizes(
    train_rows: List[Dict],
    validation_rows: List[Dict],
    test_rows: List[Dict],
) -> None:

    print()
    print_header(
        "       VERIFICATION DES TAILLES"
    )

    print(
        f"TRAIN       : {len(train_rows)}"
    )

    print(
        f"VALIDATION  : {len(validation_rows)}"
    )

    print(
        f"TEST        : {len(test_rows)}"
    )

    total = (
        len(train_rows)
        + len(validation_rows)
        + len(test_rows)
    )

    print(
        f"TOTAL       : {total}"
    )

    if len(train_rows) != TRAIN_SIZE:

        raise ValueError(
            f"TRAIN incorrect : "
            f"{len(train_rows)} au lieu de {TRAIN_SIZE}"
        )

    if len(validation_rows) != VALIDATION_SIZE:

        raise ValueError(
            f"VALIDATION incorrecte : "
            f"{len(validation_rows)} au lieu de "
            f"{VALIDATION_SIZE}"
        )

    if len(test_rows) != TEST_SIZE:

        raise ValueError(
            f"TEST incorrect : "
            f"{len(test_rows)} au lieu de {TEST_SIZE}"
        )

    if total != TOTAL_SIZE:

        raise ValueError(
            f"TOTAL incorrect : "
            f"{total} au lieu de {TOTAL_SIZE}"
        )

    print()
    print(
        "OK : tailles TRAIN / VALIDATION / TEST correctes."
    )


# ============================================================
# VERIFICATION DES IDS
# ============================================================

def verify_ids(
    train_rows: List[Dict],
    validation_rows: List[Dict],
    test_rows: List[Dict],
) -> None:

    train_ids = {
        row["id"]
        for row in train_rows
    }

    validation_ids = {
        row["id"]
        for row in validation_rows
    }

    test_ids = {
        row["id"]
        for row in test_rows
    }

    print()
    print(
        "Vérification des IDs..."
    )

    if train_ids & validation_ids:

        raise RuntimeError(
            "Chevauchement TRAIN / VALIDATION."
        )

    if train_ids & test_ids:

        raise RuntimeError(
            "Chevauchement TRAIN / TEST."
        )

    if validation_ids & test_ids:

        raise RuntimeError(
            "Chevauchement VALIDATION / TEST."
        )

    all_ids = (
        train_ids
        | validation_ids
        | test_ids
    )

    if len(all_ids) != TOTAL_SIZE:

        raise RuntimeError(
            "Les 30 combinaisons ne sont pas "
            "réparties correctement."
        )

    print(
        "OK : aucun chevauchement entre les ensembles."
    )


# ============================================================
# CONCLUSION
# ============================================================

def print_conclusion(
    test_metrics: Dict,
) -> None:

    print_header(
        "       CONCLUSION BASELINE ARX"
    )

    print()

    print(
        f"Seuil ARX utilisé : "
        f"{ARX_THRESHOLD:.2f}"
    )

    print()

    print(
        f"TEST Accuracy     : "
        f"{test_metrics['accuracy']:.4f}"
    )

    print(
        f"TEST Precision    : "
        f"{test_metrics['precision']:.4f}"
    )

    print(
        f"TEST Recall       : "
        f"{test_metrics['recall']:.4f}"
    )

    print(
        f"TEST Specificity  : "
        f"{test_metrics['specificity']:.4f}"
    )

    print(
        f"TEST F1           : "
        f"{test_metrics['f1']:.4f}"
    )

    print(
        f"TEST Youden J     : "
        f"{test_metrics['youden_j']:.4f}"
    )

    print()

    print(
        "La baseline ARX utilise directement "
        "le risque ARX avec le seuil de référence "
        f"{ARX_THRESHOLD:.2f}."
    )

    print(
        "Aucun recalibrage n'a été effectué sur le TEST."
    )

    print(
        "Cette baseline est indépendante du "
        "FuzzyRiskScorer."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("       STREAMSHIELD - BASELINE ARX")
    print("=" * 70)

    print()

    print(
        "Objectif : utiliser directement le risque ARX "
        "comme baseline de classification."
    )

    print()

    print(
        f"SEUIL ARX = {ARX_THRESHOLD:.2f}"
    )

    print()

    # --------------------------------------------------------
    # 1. Dataset
    # --------------------------------------------------------

    load_dataset()

    # --------------------------------------------------------
    # 2. Chargement TRAIN / VALIDATION / TEST
    # --------------------------------------------------------

    train_rows = load_combinations(
        TRAIN_FILE,
        "TRAIN",
    )

    validation_rows = load_combinations(
        VALIDATION_FILE,
        "VALIDATION",
    )

    test_rows = load_combinations(
        TEST_FILE,
        "TEST",
    )

    # --------------------------------------------------------
    # 3. Vérification des tailles
    # --------------------------------------------------------

    verify_sizes(
        train_rows,
        validation_rows,
        test_rows,
    )

    # --------------------------------------------------------
    # 4. Vérification des IDs
    # --------------------------------------------------------

    verify_ids(
        train_rows,
        validation_rows,
        test_rows,
    )

    # --------------------------------------------------------
    # 5. Vérification des labels
    # --------------------------------------------------------

    verify_labels(
        train_rows,
        "TRAIN",
    )

    verify_labels(
        validation_rows,
        "VALIDATION",
    )

    verify_labels(
        test_rows,
        "TEST",
    )

    # --------------------------------------------------------
    # 6. TRAIN
    # --------------------------------------------------------

    train_metrics = print_results(
        train_rows,
        "TRAIN",
    )

    analyze_errors(
        train_rows,
        "TRAIN",
    )

    # --------------------------------------------------------
    # 7. VALIDATION
    # --------------------------------------------------------

    validation_metrics = print_results(
        validation_rows,
        "VALIDATION",
    )

    analyze_errors(
        validation_rows,
        "VALIDATION",
    )

    # --------------------------------------------------------
    # 8. TEST FINAL
    # --------------------------------------------------------

    print_header(
        "       TEST FINAL - BASELINE ARX"
    )

    print()

    print(
        f"Seuil ARX FIGÉ : "
        f"{ARX_THRESHOLD:.2f}"
    )

    print(
        "IMPORTANT : aucun recalibrage sur le TEST."
    )

    test_metrics = print_results(
        test_rows,
        "TEST",
    )

    analyze_errors(
        test_rows,
        "TEST",
    )

    # --------------------------------------------------------
    # 9. Sauvegarde
    # --------------------------------------------------------

    print_header(
        "       SAUVEGARDE DES RESULTATS"
    )

    save_results(
        train_rows,
        TRAIN_OUTPUT,
    )

    save_results(
        validation_rows,
        VALIDATION_OUTPUT,
    )

    save_results(
        test_rows,
        TEST_OUTPUT,
    )

    save_summary(
        train_metrics,
        validation_metrics,
        test_metrics,
    )

    # --------------------------------------------------------
    # 10. Conclusion
    # --------------------------------------------------------

    print_conclusion(
        test_metrics
    )

    print()

    print("=" * 70)
    print("       BASELINE ARX TERMINEE")
    print("=" * 70)


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    main()