
import asyncio
import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import sys
SERVICE_DIR = Path(__file__).resolve().parents[3]

if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))
from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.field_sensitivity_repository import load_field_sensitivity
# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[3]

DATASET_FILE = (
    BASE_DIR
    / "data"
    / "validation"
    / "uci_adult"
    / "processed"
    / "adult_prepared.csv"
)

TRAIN_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "train"
    / "arx_train_labels.csv"
)

VALIDATION_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "validation"
    / "arx_validation_labels.csv"
)

TEST_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "test"
    / "arx_test_labels.csv"
)

OUTPUT_DIR = (
    BASE_DIR
    / "validation"
    / "arx"
    / "test"
)

TRAIN_OUTPUT = OUTPUT_DIR / "fuzzy_test_train.csv"
VALIDATION_OUTPUT = OUTPUT_DIR / "fuzzy_test_validation.csv"
TEST_OUTPUT = OUTPUT_DIR / "fuzzy_test_test.csv"
SUMMARY_OUTPUT = OUTPUT_DIR / "fuzzy_test_summary.csv"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s - %(message)s",
)

logger = logging.getLogger("streamshield.fuzzy_validation")


# ============================================================
# UTILITAIRES
# ============================================================

def load_csv(path: Path) -> List[Dict]:
    """
    Charge un fichier CSV et retourne une liste de dictionnaires.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        return list(csv.DictReader(file))

def find_column(
    row: Dict,
    candidates: List[str],
) -> str:

    for candidate in candidates:

        if candidate in row:
            return candidate

    raise ValueError(
        f"Aucune des colonnes {candidates} "
        f"n'existe dans le fichier."
    )
def parse_fields(value: str) -> Tuple[str, ...]:
    """
    Transforme une représentation de combinaison en tuple de champs.

    Exemples acceptés :

        age + sex

        age,sex

        age;sex
    """

    if not value:
        return tuple()

    value = value.strip()

    if "+" in value:
        fields = value.split("+")

    elif "," in value:
        fields = value.split(",")

    elif ";" in value:
        fields = value.split(";")

    else:
        fields = [value]

    return tuple(
        field.strip()
        for field in fields
        if field.strip()
    )


def normalize_label(value) -> int:
    """
    Convertit un label en 0/1.
    """

    if isinstance(value, bool):
        return int(value)

    text = str(value).strip().lower()

    if text in {
        "1",
        "true",
        "yes",
        "oui",
        "positive",
    }:
        return 1

    if text in {
        "0",
        "false",
        "no",
        "non",
        "negative",
    }:
        return 0

    raise ValueError(
        f"Label inconnu : {value}"
    )


# ============================================================
# DATASET
# ============================================================

def load_dataset() -> List[Dict]:

    print()
    print("=" * 70)
    print("       CHARGEMENT DU DATASET UCI ADULT")
    print("=" * 70)

    print(
        f"Fichier : {DATASET_FILE}"
    )

    rows = load_csv(DATASET_FILE)

    if not rows:
        raise ValueError(
            "Le dataset UCI Adult est vide."
        )

    print(
        f"Nombre de records : {len(rows)}"
    )

    print(
        f"Nombre de colonnes : {len(rows[0])}"
    )

    return rows


# ============================================================
# LABELS
# ============================================================

def load_labels(
    path: Path,
    name: str,
) -> List[Dict]:

    print()
    print("=" * 70)
    print(
        f"       CHARGEMENT {name.upper()}"
    )
    print("=" * 70)

    print(
        f"Fichier : {path}"
    )

    rows = load_csv(path)

    if not rows:
        raise ValueError(
            f"Le fichier {name} est vide."
        )

    print(
        f"Combinaisons chargées : {len(rows)}"
    )

    return rows


# ============================================================
# CONSTRUCTION DES COMBINAISONS
# ============================================================

def extract_reference_label(
    row: Dict,
) -> int:
    """
    Extrait le label de référence ARX.
    """

    label_column = find_column(
        row,
        [
            "label",
            "arx_label",
            "reference",
            "reference_label",
            "risk_label",
        ],
    )

    return normalize_label(
        row[label_column]
    )
def extract_combination(row: Dict) -> Tuple[str, Tuple[str, ...]]:
    """
    Extrait l'identifiant et les champs de la combinaison
    depuis une ligne du fichier de labels ARX.

    Format actuel des CSV :

        id
        combination
        num_qi
        num_records
        average_risk
        label

    Exemple :

        C01 | age + sex | 2 | ... | 0.004422 | 0
    """

    # ============================================================
    # IDENTIFIANT
    # ============================================================

    id_column = find_column(
        row,
        [
            "id",
            "combination_id",
            "combination",
        ],
    )

    combination_id = str(
        row[id_column]
    ).strip()

    # ============================================================
    # COMBINAISON
    # ============================================================

    fields_column = find_column(
        row,
        [
            "combination",
            "fields",
            "qi_fields",
            "quasi_identifiers",
            "combination_fields",
        ],
    )

    combination_value = str(
        row[fields_column]
    ).strip()

    # ============================================================
    # CONVERSION :
    #
    # "age + sex"
    #
    # devient :
    #
    # ("age", "sex")
    # ============================================================

    if "+" in combination_value:

        fields = tuple(
            field.strip()
            for field in combination_value.split("+")
            if field.strip()
        )

    elif "," in combination_value:

        fields = tuple(
            field.strip()
            for field in combination_value.split(",")
            if field.strip()
        )

    else:

        fields = (
            combination_value,
        )

    if not fields:
        raise ValueError(
            f"Combinaison vide pour {combination_id}"
        )

    return combination_id, fields

# ============================================================
# METRIQUES
# ============================================================

def compute_metrics(
    y_true: List[int],
    y_pred: List[int],
) -> Dict:

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

    total = len(y_true)

    accuracy = (
        (tp + tn) / total
        if total > 0
        else 0.0
    )

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0
        else 0.0
    )

    specificity = (
        tn / (tn + fp)
        if (tn + fp) > 0
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    youden_j = (
        recall + specificity - 1
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
# EVALUATION D'UN ENSEMBLE
# ============================================================

async def evaluate_split(
    name: str,
    rows: List[Dict],
    dataset: List[Dict],
    scorer: FuzzyRiskScorer,
    output_file: Path,
) -> Dict:

    print()
    print("=" * 70)
    print(
        f"       RESULTATS FUZZY - {name.upper()}"
    )
    print("=" * 70)

    print()

    print(
        f"Seuil Fuzzy : {scorer.threshold}"
    )

    results = []

    y_true = []
    y_pred = []

    for row in rows:

        combination_id, fields = extract_combination(
            row
        )

        reference_label = extract_reference_label(
            row
        )

        # ----------------------------------------------------
        # Calcul du risque Fuzzy
        # ----------------------------------------------------

        risk = scorer.score(
            dataset,
            fields,
        )

        prediction = int(
            risk.triggered
        )

        y_true.append(
            reference_label
        )

        y_pred.append(
            prediction
        )

        results.append(
            {
                "combination_id": combination_id,
                "fields": " + ".join(fields),
                "k": risk.k,
                "uniqueness": risk.uniqueness,
                "avg_sensitivity": risk.avg_sensitivity,
                "fuzzy_score": risk.score,
                "threshold": scorer.threshold,
                "reference_label": reference_label,
                "fuzzy_label": prediction,
                "sample_size": risk.sample_size,
            }
        )

        print(
            f"{combination_id:<4} | "
            f"{' + '.join(fields):<55} | "
            f"k={risk.k:<5} | "
            f"U={risk.uniqueness:.4f} | "
            f"S={risk.avg_sensitivity:.4f} | "
            f"Fuzzy={risk.score:.6f} | "
            f"REF={reference_label} | "
            f"PRED={prediction}"
        )

    metrics = compute_metrics(
        y_true,
        y_pred,
    )

    print()
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

    # --------------------------------------------------------
    # Analyse erreurs
    # --------------------------------------------------------

    false_positives = [
        result
        for result in results
        if (
            result["reference_label"] == 0
            and result["fuzzy_label"] == 1
        )
    ]

    false_negatives = [
        result
        for result in results
        if (
            result["reference_label"] == 1
            and result["fuzzy_label"] == 0
        )
    ]

    print()
    print(
        f"Analyse des erreurs - {name.upper()}"
    )

    print()

    print(
        f"Faux positifs : "
        f"{len(false_positives)}"
    )

    for result in false_positives:

        print(
            f"  FP : {result['combination_id']} "
            f"| score={result['fuzzy_score']:.6f}"
        )

    print()

    print(
        f"Faux négatifs : "
        f"{len(false_negatives)}"
    )

    for result in false_negatives:

        print(
            f"  FN : {result['combination_id']} "
            f"| score={result['fuzzy_score']:.6f}"
        )

    # --------------------------------------------------------
    # Sauvegarde détaillée
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "combination_id",
        "fields",
        "k",
        "uniqueness",
        "avg_sensitivity",
        "fuzzy_score",
        "threshold",
        "reference_label",
        "fuzzy_label",
        "sample_size",
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

        writer.writerows(
            results
        )

    print()
    print(
        f"Résultats sauvegardés : "
        f"{output_file}"
    )

    return metrics


# ============================================================
# RESUME
# ============================================================

def save_summary(
    threshold: float,
    test_metrics: Dict,
    num_combinations: int,
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    row = {
        "threshold": threshold,
        "accuracy": test_metrics["accuracy"],
        "precision": test_metrics["precision"],
        "recall": test_metrics["recall"],
        "specificity": test_metrics["specificity"],
        "f1": test_metrics["f1"],
        "youden_j": test_metrics["youden_j"],
        "tp": test_metrics["tp"],
        "tn": test_metrics["tn"],
        "fp": test_metrics["fp"],
        "fn": test_metrics["fn"],
        "num_combinations": num_combinations,
    }

    fieldnames = list(
        row.keys()
    )

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
        writer.writerow(row)

    print()
    print(
        f"Résumé sauvegardé : "
        f"{SUMMARY_OUTPUT}"
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("=" * 70)
    print("       STREAMSHIELD - VALIDATION FUZZYRISKSCORER")
    print("=" * 70)

    print()
    print(
        "Objectif : évaluer le FuzzyRiskScorer "
        "sur TRAIN / VALIDATION / TEST."
    )

    print()
    print(
        "IMPORTANT : le seuil Fuzzy est chargé "
        "depuis la configuration MongoDB."
    )

    print(
        "IMPORTANT : aucun recalibrage n'est effectué "
        "sur le TEST."
    )

    # --------------------------------------------------------
    # 1. Dataset
    # --------------------------------------------------------

    dataset = load_dataset()

    # --------------------------------------------------------
    # 2. Labels
    # --------------------------------------------------------

    train_rows = load_labels(
        TRAIN_FILE,
        "TRAIN",
    )

    validation_rows = load_labels(
        VALIDATION_FILE,
        "VALIDATION",
    )

    test_rows = load_labels(
        TEST_FILE,
        "TEST",
    )

    # --------------------------------------------------------
    # 3. Vérification
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       VERIFICATION")
    print("=" * 70)

    total = (
        len(train_rows)
        + len(validation_rows)
        + len(test_rows)
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

    print(
        f"TOTAL       : {total}"
    )

    if total != 30:

        raise ValueError(
            f"Le nombre total de combinaisons "
            f"doit être 30, trouvé : {total}"
        )

    print()
    print(
        "OK : 30 combinaisons."
    )

    # --------------------------------------------------------
    # 4. Sensibilité MongoDB
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       CHARGEMENT SENSIBILITE")
    print("=" * 70)

    field_sensitivity = await load_field_sensitivity()

    print(
        f"Champs de sensibilité chargés : "
        f"{len(field_sensitivity)}"
    )

    # --------------------------------------------------------
    # 5. FuzzyRiskScorer
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       INITIALISATION FUZZYRISKSCORER")
    print("=" * 70)

    scorer = FuzzyRiskScorer(
        threshold=0.5,
        field_sensitivity=field_sensitivity,
    )

    await scorer.load_fuzzy_configuration()

    print()
    print(
        f"Threshold Fuzzy : "
        f"{scorer.threshold}"
    )

    print(
        f"Min sample size : "
        f"{scorer.min_sample_size}"
    )

    print(
        f"Nombre de règles : "
        f"{len(scorer.fuzzy_rules)}"
    )

    # --------------------------------------------------------
    # 6. TRAIN
    # --------------------------------------------------------

    train_metrics = await evaluate_split(
        "TRAIN",
        train_rows,
        dataset,
        scorer,
        TRAIN_OUTPUT,
    )

    # --------------------------------------------------------
    # 7. VALIDATION
    # --------------------------------------------------------

    validation_metrics = await evaluate_split(
        "VALIDATION",
        validation_rows,
        dataset,
        scorer,
        VALIDATION_OUTPUT,
    )

    # --------------------------------------------------------
    # 8. TEST FINAL
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       TEST FINAL - FUZZYRISKSCORER")
    print("=" * 70)

    print()
    print(
        f"Seuil Fuzzy FIGE : "
        f"{scorer.threshold}"
    )

    print(
        "IMPORTANT : aucun recalibrage sur le TEST."
    )

    test_metrics = await evaluate_split(
        "TEST",
        test_rows,
        dataset,
        scorer,
        TEST_OUTPUT,
    )

    # --------------------------------------------------------
    # 9. Résumé final
    # --------------------------------------------------------

    save_summary(
        scorer.threshold,
        test_metrics,
        len(test_rows),
    )

    # --------------------------------------------------------
    # 10. Conclusion
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       CONCLUSION FUZZYRISKSCORER")
    print("=" * 70)

    print()

    print(
        f"Seuil Fuzzy utilisé : "
        f"{scorer.threshold:.4f}"
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
        "Le FuzzyRiskScorer a été évalué "
        "sans recalibrage sur le TEST."
    )

    print(
        "Les labels de référence proviennent "
        "du protocole ARX."
    )

    print()
    print("=" * 70)
    print("       VALIDATION FUZZYRISKSCORER TERMINEE")
    print("=" * 70)


if __name__ == "__main__":

    asyncio.run(main())

