import csv
from pathlib import Path
from typing import Dict, List


# ============================================================
# STREAMSHIELD - BASELINE K-ANONYMITY
# ============================================================
#
# Objectif :
#
#   Évaluer une baseline simple basée uniquement sur k-anonymity.
#
# Protocole :
#
#   TRAIN       -> choix du seuil k
#   VALIDATION  -> vérification du seuil
#   TEST        -> évaluation finale
#
# IMPORTANT :
#
#   Cette baseline n'utilise PAS :
#
#       - l'unicité
#       - la sensibilité
#       - les règles fuzzy
#       - le score Fuzzy
#
#   Elle utilise uniquement la valeur k calculée à partir
#   des données UCI Adult pour chaque combinaison de QI.
#
# ============================================================


# ============================================================
# CHEMINS
# ============================================================

SERVICE_DIR = Path(__file__).resolve().parents[3]

TRAIN_FILE = (
    SERVICE_DIR
    / "validation"
    / "arx"
    / "train"
    / "arx_train_labels.csv"
)

VALIDATION_FILE = (
    SERVICE_DIR
    / "validation"
    / "arx"
    / "validation"
    / "arx_validation_labels.csv"
)

TEST_FILE = (
    SERVICE_DIR
    / "validation"
    / "arx"
    / "test"
    / "arx_test_labels.csv"
)

DATASET_FILE = (
    SERVICE_DIR
    / "data"
    / "validation"
    / "uci_adult"
    / "processed"
    / "adult_prepared.csv"
)

OUTPUT_DIR = (
    SERVICE_DIR
    / "validation"
    / "arx"
    / "baselines"
)

VALIDATION_OUTPUT = (
    OUTPUT_DIR
    / "k_anonymity_validation.csv"
)

TEST_OUTPUT = (
    OUTPUT_DIR
    / "k_anonymity_test.csv"
)

SUMMARY_OUTPUT = (
    OUTPUT_DIR
    / "k_anonymity_summary.csv"
)


# ============================================================
# CONFIGURATION
# ============================================================

ARX_THRESHOLD = 0.09

# Critère utilisé pour choisir le seuil de la baseline.
#
# Priorité :
#   1. Recall
#   2. F1
#   3. Specificity
#
# Le Recall est prioritaire car StreamShield doit éviter
# de manquer les combinaisons présentant un risque.
#
# Le seuil sera recherché automatiquement sur TRAIN.
# ============================================================


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
    filename: Path,
    name: str,
) -> List[Dict]:

    print()
    print("=" * 70)
    print(f"       CHARGEMENT {name}")
    print("=" * 70)

    print(f"Fichier : {filename}")

    if not filename.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {filename}"
        )

    rows = []

    with open(
        filename,
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
                f"Colonnes manquantes dans {filename}: "
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

            # Vérification du label ARX
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
        f"Combinaisons chargées : {len(rows)}"
    )

    return rows


# ============================================================
# CALCUL DE K
# ============================================================

def compute_k(
    records: List[Dict],
    fields: tuple,
) -> int:

    if not records:
        return 0

    # --------------------------------------------------------
    # Construction des classes d'équivalence.
    #
    # Deux records appartiennent à la même classe si leurs
    # valeurs sont identiques pour tous les QI de la combinaison.
    # --------------------------------------------------------

    groups = {}

    for record in records:

        key = tuple(
            record.get(field, "")
            for field in fields
        )

        groups[key] = (
            groups.get(key, 0) + 1
        )

    if not groups:
        return 0

    # --------------------------------------------------------
    # k-anonymity :
    #
    # k = taille de la plus petite classe d'équivalence.
    # --------------------------------------------------------

    return min(groups.values())


# ============================================================
# CALCUL DES METRIQUES
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
        tp + tn + fp + fn
    )

    accuracy = (
        (tp + tn) / total
        if total
        else 0.0
    )

    precision = (
        tp / (tp + fp)
        if tp + fp
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if tp + fn
        else 0.0
    )

    specificity = (
        tn / (tn + fp)
        if tn + fp
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
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
# CALCUL DES K POUR UN ENSEMBLE
# ============================================================

def compute_k_values(
    combinations: List[Dict],
    records: List[Dict],
) -> List[Dict]:

    results = []

    for row in combinations:

        k = compute_k(
            records,
            row["fields"],
        )

        results.append(
            {
                **row,
                "k": k,
            }
        )

    return results


# ============================================================
# EVALUATION D'UN SEUIL K
# ============================================================

def evaluate_k_threshold(
    rows: List[Dict],
    k_threshold: int,
) -> Dict:

    y_true = [
        row["arx_label"]
        for row in rows
    ]

    # --------------------------------------------------------
    # Une combinaison est considérée comme risquée si :
    #
    #       k <= seuil_k
    #
    # Plus k est petit, plus l'anonymat est faible.
    # --------------------------------------------------------

    y_pred = [
        int(row["k"] <= k_threshold)
        for row in rows
    ]

    metrics = compute_metrics(
        y_true,
        y_pred,
    )

    return metrics


# ============================================================
# RECHERCHE DU SEUIL SUR TRAIN
# ============================================================

def find_best_k_threshold(
    train_rows: List[Dict],
) -> int:

    print()
    print("=" * 70)
    print("       RECHERCHE DU SEUIL K SUR TRAIN")
    print("=" * 70)

    k_values = sorted(
        set(
            row["k"]
            for row in train_rows
        )
    )

    if not k_values:
        raise ValueError(
            "Aucune valeur k disponible."
        )

    print()
    print(
        f"Valeurs k observées : {k_values}"
    )

    candidates = []

    # Tester chaque valeur observée.
    for threshold in k_values:

        metrics = evaluate_k_threshold(
            train_rows,
            threshold,
        )

        candidates.append(
            {
                "threshold": threshold,
                **metrics,
            }
        )

        print(
            f"k <= {threshold:>4} | "
            f"Recall={metrics['recall']:.4f} | "
            f"F1={metrics['f1']:.4f} | "
            f"Specificity={metrics['specificity']:.4f} | "
            f"Accuracy={metrics['accuracy']:.4f}"
        )

    # --------------------------------------------------------
    # Sélection :
    #
    # 1. Recall maximum
    # 2. F1 maximum
    # 3. Specificity maximum
    # 4. seuil k le plus petit
    # --------------------------------------------------------

    best = max(
        candidates,
        key=lambda row: (
            row["recall"],
            row["f1"],
            row["specificity"],
            -row["threshold"],
        ),
    )

    best_threshold = int(
        best["threshold"]
    )

    print()
    print(
        f"SEUIL K RETENU SUR TRAIN : "
        f"k <= {best_threshold}"
    )

    print(
        f"Recall TRAIN      : "
        f"{best['recall']:.4f}"
    )

    print(
        f"F1 TRAIN          : "
        f"{best['f1']:.4f}"
    )

    print(
        f"Specificity TRAIN : "
        f"{best['specificity']:.4f}"
    )

    return best_threshold


# ============================================================
# AFFICHAGE DES RESULTATS
# ============================================================

def print_results(
    name: str,
    rows: List[Dict],
    k_threshold: int,
) -> Dict:

    print()
    print("=" * 70)
    print(f"       RESULTATS {name}")
    print("=" * 70)

    print()
    print(
        f"Seuil baseline k : k <= {k_threshold}"
    )

    for row in rows:

        prediction = int(
            row["k"] <= k_threshold
        )

        print(
            f"{row['id']} | "
            f"{row['combination']:<55} | "
            f"k={row['k']} | "
            f"ARX={row['average_risk']:.6f} | "
            f"ARX_LABEL={row['arx_label']} | "
            f"K_LABEL={prediction}"
        )

    y_true = [
        row["arx_label"]
        for row in rows
    ]

    y_pred = [
        int(row["k"] <= k_threshold)
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
# SAUVEGARDE
# ============================================================

def save_results(
    rows: List[Dict],
    metrics: Dict,
    threshold: int,
    output_file: Path,
) -> None:

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "id",
        "combination",
        "num_qi",
        "num_records",
        "average_risk",
        "arx_label",
        "k",
        "k_threshold",
        "k_label",
    ]

    with open(
        output_file,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in rows:

            writer.writerow(
                {
                    "id": row["id"],
                    "combination": row["combination"],
                    "num_qi": row["num_qi"],
                    "num_records": row["num_records"],
                    "average_risk": row["average_risk"],
                    "arx_label": row["arx_label"],
                    "k": row["k"],
                    "k_threshold": threshold,
                    "k_label": int(
                        row["k"] <= threshold
                    ),
                }
            )


# ============================================================
# SAUVEGARDE DU RESUME
# ============================================================

def save_summary(
    threshold: int,
    train_metrics: Dict,
    validation_metrics: Dict,
    test_metrics: Dict,
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "split",
        "k_threshold",
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

    rows = []

    for split, metrics, num in [
        (
            "TRAIN",
            train_metrics,
            18,
        ),
        (
            "VALIDATION",
            validation_metrics,
            6,
        ),
        (
            "TEST",
            test_metrics,
            6,
        ),
    ]:

        rows.append(
            {
                "split": split,
                "k_threshold": threshold,
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
                "num_combinations": num,
            }
        )

    with open(
        SUMMARY_OUTPUT,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("       STREAMSHIELD - BASELINE K-ANONYMITY")
    print("=" * 70)

    print()
    print(
        "Objectif : comparer une baseline k-anonymity "
        "au modèle FuzzyRiskScorer."
    )

    print()
    print(
        "Protocole : TRAIN -> VALIDATION -> TEST"
    )

    print(
        "Le seuil k est choisi uniquement sur TRAIN."
    )

    # --------------------------------------------------------
    # 1. Dataset
    # --------------------------------------------------------

    records = load_dataset()

    # --------------------------------------------------------
    # 2. Chargement des splits
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
    # 3. Calcul de k
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       CALCUL DE K")
    print("=" * 70)

    train_rows = compute_k_values(
        train_rows,
        records,
    )

    validation_rows = compute_k_values(
        validation_rows,
        records,
    )

    test_rows = compute_k_values(
        test_rows,
        records,
    )

    # --------------------------------------------------------
    # 4. Choix du seuil sur TRAIN
    # --------------------------------------------------------

    k_threshold = find_best_k_threshold(
        train_rows
    )

    # --------------------------------------------------------
    # 5. Evaluation TRAIN
    # --------------------------------------------------------

    train_metrics = print_results(
        "TRAIN",
        train_rows,
        k_threshold,
    )

    # --------------------------------------------------------
    # 6. Evaluation VALIDATION
    #
    # IMPORTANT :
    # Aucun changement du seuil.
    # --------------------------------------------------------

    validation_metrics = print_results(
        "VALIDATION",
        validation_rows,
        k_threshold,
    )

    # --------------------------------------------------------
    # 7. Evaluation TEST
    #
    # IMPORTANT :
    # Le seuil est celui choisi sur TRAIN.
    # Aucun recalibrage sur TEST.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       TEST FINAL - BASELINE K-ANONYMITY")
    print("=" * 70)

    print()
    print(
        f"Seuil k FIGÉ : k <= {k_threshold}"
    )

    print(
        "IMPORTANT : aucun recalibrage sur le TEST."
    )

    test_metrics = print_results(
        "TEST",
        test_rows,
        k_threshold,
    )

    # --------------------------------------------------------
    # 8. Sauvegarde
    # --------------------------------------------------------

    save_results(
        validation_rows,
        validation_metrics,
        k_threshold,
        VALIDATION_OUTPUT,
    )

    save_results(
        test_rows,
        test_metrics,
        k_threshold,
        TEST_OUTPUT,
    )

    save_summary(
        k_threshold,
        train_metrics,
        validation_metrics,
        test_metrics,
    )

    # --------------------------------------------------------
    # 9. Conclusion
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       CONCLUSION BASELINE K-ANONYMITY")
    print("=" * 70)

    print()
    print(
        f"Seuil k choisi sur TRAIN : "
        f"k <= {k_threshold}"
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

    print()
    print(
        "La baseline k-anonymity a été évaluée "
        "sans utiliser le modèle fuzzy."
    )

    print()
    print(
        f"Résultats validation : {VALIDATION_OUTPUT}"
    )

    print(
        f"Résultats test       : {TEST_OUTPUT}"
    )

    print(
        f"Résumé               : {SUMMARY_OUTPUT}"
    )


if __name__ == "__main__":
    main()

