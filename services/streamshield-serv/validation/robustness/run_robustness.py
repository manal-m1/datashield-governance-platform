from __future__ import annotations

import asyncio
import csv
import copy
import random
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv


# ============================================================================
# PROJECT PATH
# ============================================================================

SERVICE_DIR = Path(__file__).resolve().parents[2]

PROJECT_ROOT = SERVICE_DIR.parents[1]

ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
    print(f"[OK] .env loaded from: {ENV_FILE}")
else:
    print(f"[WARNING] .env not found: {ENV_FILE}")

print(
    "[DEBUG] MONGODB_URI loaded:",
    bool(os.getenv("MONGODB_URI"))
)


# Make imports such as "from detection..." work
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))


from detection.frequency_counter import CombinationAnalyzer
from detection.fuzzy_risk_scorer import (
    FuzzyRiskScorer,
    fuzzify_k_risk,
    fuzzify_uniqueness,
    fuzzify_sensitivity,
    _apply_rules,
    _defuzzify,
)
from detection.fuzzy_config_repository import load_fuzzy_config
from detection.fuzzy_rule_repository import load_fuzzy_rules
from detection.field_sensitivity_repository import (
    load_field_sensitivity,
    DEFAULT_SENSITIVITY,
)
from detection.risk_scorer import SENSITIVITY_ENCODING

# ============================================================================
# CONFIGURATION
# ============================================================================

FUZZY_THRESHOLD = 0.70
ARX_THRESHOLD = 0.09

RANDOM_SEED = 42

# Validation files
ARX_LABELS_FILE = (
    SERVICE_DIR
    / "validation"
    / "arx"
    / "java"
    / "arx_30_labels.csv"
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
    / "robustness"
)

# ============================================================================
# DATA LOADING
# ============================================================================

def load_arx_labels() -> List[Dict[str, Any]]:
    """Load the 30 ARX combinations and labels."""

    rows = []

    with open(ARX_LABELS_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            combination = row["combination"].strip()

            fields = tuple(
                field.strip()
                for field in combination.split("+")
                if field.strip()
            )

            rows.append(
                {
                    "id": row["id"],
                    "combination": combination,
                    "fields": fields,
                    "num_qi": int(row["num_qi"]),
                    "num_records": int(row["num_records"]),
                    "arx_average_risk": float(row["average_risk"]),
                    "arx_label": int(row["label"]),
                }
            )

    return rows


def load_dataset() -> List[Dict[str, Any]]:
    """Load the UCI Adult validation dataset."""

    with open(DATASET_FILE, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ============================================================================
# METRICS
# ============================================================================

def compute_metrics(
    y_true: List[int],
    y_pred: List[int],
) -> Dict[str, Any]:

    tp = sum(
        1 for t, p in zip(y_true, y_pred)
        if t == 1 and p == 1
    )

    tn = sum(
        1 for t, p in zip(y_true, y_pred)
        if t == 0 and p == 0
    )

    fp = sum(
        1 for t, p in zip(y_true, y_pred)
        if t == 0 and p == 1
    )

    fn = sum(
        1 for t, p in zip(y_true, y_pred)
        if t == 1 and p == 0
    )

    total = len(y_true)

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
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    mcc_denominator = (
        (tp + fp)
        * (tp + fn)
        * (tn + fp)
        * (tn + fn)
    )

    if mcc_denominator > 0:
        mcc = (
            (tp * tn - fp * fn)
            / mcc_denominator ** 0.5
        )
    else:
        mcc = 0.0

    alert_rate = (
        sum(y_pred) / total
        if total
        else 0.0
    )

    false_positive_rate = (
        fp / (fp + tn)
        if fp + tn
        else 0.0
    )

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "mcc": mcc,
        "alert_rate": alert_rate,
        "false_positive_rate": false_positive_rate,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


# ============================================================================
# FUZZY ENGINE
# ============================================================================
def calculate_sensitivity(
    fields: Tuple[str, ...],
    field_sensitivity: Dict[str, str],
    mode: str = "mean",
) -> float:
    """
    Calculate s(C).

    mean:
        current production behavior.

    max:
        maximum field sensitivity.

    weighted:
        sensitivity-weighted mean:
            sum(s_i^2) / sum(s_i)
    """

    values = []

    for field in fields:

        level = field_sensitivity.get(
            field,
            DEFAULT_SENSITIVITY,
        )

        value = SENSITIVITY_ENCODING.get(
            level,
            SENSITIVITY_ENCODING[DEFAULT_SENSITIVITY],
        )

        values.append(value)

    if not values:
        return 0.0

    if mode == "mean":
        return sum(values) / len(values)

    if mode == "max":
        return max(values)

    if mode == "weighted":
        denominator = sum(values)

        if denominator == 0:
            return 0.0

        return sum(v * v for v in values) / denominator

    raise ValueError(
        f"Unknown sensitivity aggregation mode: {mode}"
    )


def perturb_membership_config(
    config: Dict[str, Any],
    factor: float,
) -> Dict[str, Any]:
    """
    Multiply membership parameters by (1 + factor).

    Example:
        -0.10 -> -10%
        +0.10 -> +10%

    For normalized inputs (uniqueness/sensitivity), values are clipped
    to [0, 1].

    This preserves the ordering of parameters for the tested functions.
    """

    new_config = copy.deepcopy(config)

    for key in (
        "k_fuzzy_sets",
        "uniqueness_fuzzy_sets",
        "sensitivity_fuzzy_sets",
    ):

        fuzzy_sets = new_config.get(key, {})

        for definition in fuzzy_sets.values():

            parameters = definition["parameters"]

            updated = [
                value * (1.0 + factor)
                for value in parameters
            ]

            if key in (
                "uniqueness_fuzzy_sets",
                "sensitivity_fuzzy_sets",
            ):
                updated = [
                    min(1.0, max(0.0, value))
                    for value in updated
                ]

            definition["parameters"] = updated

    return new_config


def remove_variable_from_rules(
    rules: List[Dict[str, Any]],
    variable: str,
) -> List[Dict[str, Any]]:
    """
    Input ablation.

    Removes conditions involving one variable.

    Rules that become empty are discarded.
    """

    result = []

    for rule in rules:

        new_rule = copy.deepcopy(rule)

        conditions = [
            condition
            for condition in new_rule.get("conditions", [])
            if condition.get("variable") != variable
        ]

        if not conditions:
            continue

        new_rule["conditions"] = conditions
        result.append(new_rule)

    return result


def get_rule_id(rule: Dict[str, Any]) -> str:
    """
    Return the identifier used by the fuzzy rule.

    Supports:
    - rule_id
    - id
    - _id
    """

    return str(
        rule.get(
            "rule_id",
            rule.get(
                "id",
                rule.get(
                    "_id",
                    "",
                ),
            ),
        )
    )


def remove_rules(
    rules: List[Dict[str, Any]],
    rule_ids: set[str],
) -> List[Dict[str, Any]]:
    """
    Remove rules by their logical rule identifier.
    """

    rule_ids = {str(rule_id) for rule_id in rule_ids}

    remaining_rules = []

    for rule in rules:

        current_id = get_rule_id(rule)

        if current_id not in rule_ids:
            remaining_rules.append(rule)

    return remaining_rules


# ============================================================================
# SCORE ONE COMBINATION
# ============================================================================

def score_combination(
    records: List[Dict[str, Any]],
    fields: Tuple[str, ...],
    config: Dict[str, Any],
    rules: List[Dict[str, Any]],
    field_sensitivity: Dict[str, str],
    sensitivity_mode: str = "mean",
) -> Dict[str, Any]:
    """
    Reproduce the production fuzzy scoring pipeline
    while allowing robustness experiments.
    """

    analysis = CombinationAnalyzer.analyze(
        records,
        fields,
    )

    k = analysis["k"]
    uniqueness = analysis["uniqueness"]
    sample_size = analysis["sample_size"]

    sensitivity = calculate_sensitivity(
        fields,
        field_sensitivity,
        mode=sensitivity_mode,
    )

    min_sample_size = config.get(
        "min_sample_size",
        20,
    )

    # Same fail-safe behavior as production.
    if k <= 0 or sample_size < min_sample_size:
        score = 0.0

        return {
            "k": k,
            "uniqueness": uniqueness,
            "sample_size": sample_size,
            "avg_sensitivity": sensitivity,
            "score": score,
            "prediction": int(score >= FUZZY_THRESHOLD),
        }

    k_fuzzy = fuzzify_k_risk(
        k,
        config,
    )

    u_fuzzy = fuzzify_uniqueness(
        uniqueness,
        config,
    )

    s_fuzzy = fuzzify_sensitivity(
        sensitivity,
        config,
    )
    if fields == ["age", "sex"] or fields == ["age", "race"] or fields == ["age", "education"]:
        print("\n[DEBUG COMBINATION]")
        print("fields =", fields)
        print("k =", k)
        print("uniqueness =", uniqueness)
        print("sensitivity =", sensitivity)
        print("k_fuzzy =", k_fuzzy)
        print("u_fuzzy =", u_fuzzy)
        print("s_fuzzy =", s_fuzzy)
        print("rules =", [get_rule_id(r) for r in rules])

    activations = _apply_rules(
        k_fuzzy,
        u_fuzzy,
        s_fuzzy,
        rules,
    )

    if not activations:
        score = 0.0
    else:
        score = _defuzzify(
            activations,
            config["output_levels"],
        )

    return {
        "k": k,
        "uniqueness": uniqueness,
        "sample_size": sample_size,
        "avg_sensitivity": sensitivity,
        "score": score,
        "prediction": int(score >= FUZZY_THRESHOLD),
    }
# ============================================================================
# BASELINE
# ============================================================================

def compute_baseline(
    arx_rows: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
    config: Dict[str, Any],
    rules: List[Dict[str, Any]],
    field_sensitivity: Dict[str, str],
) -> List[Dict[str, Any]]:

    # ==============================================================
    # DEBUG C01 - RULE IMPACT
    # ==============================================================

    print("\n" + "=" * 70)
    print("DEBUG C01 - RULE IMPACT")
    print("=" * 70)

    c01_fields = ["age", "sex"]

    all_rules_score = score_combination(
        records,
        c01_fields,
        config,
        rules,
        field_sensitivity,
    )

    rules_without_r23 = [
        r for r in rules
        if get_rule_id(r) != "R23"
    ]

    no_r23_score = score_combination(
        records,
        c01_fields,
        config,
        rules_without_r23,
        field_sensitivity,
    )

    rules_without_r23_r26 = [
        r for r in rules
        if get_rule_id(r) not in {"R23", "R24", "R25", "R26"}
    ]

    no_new_rules_score = score_combination(
        records,
        c01_fields,
        config,
        rules_without_r23_r26,
        field_sensitivity,
    )

    print("C01 with all rules     :", all_rules_score["score"])
    print("C01 without R23        :", no_r23_score["score"])
    print("C01 without R23-R26    :", no_new_rules_score["score"])
    print("=" * 70)

    # ==============================================================
    # BASELINE
    # ==============================================================

    results = []

    for row in arx_rows:

        result = score_combination(
            records,
            row["fields"],
            config,
            rules,
            field_sensitivity,
        )

        results.append(
            {
                **row,
                **result,
            }
        )

    return results
    

def print_baseline_diagnostic(
    baseline: List[Dict[str, Any]],
) -> None:

    print("\n" + "=" * 70)
    print("BASELINE DIAGNOSTIC")
    print("=" * 70)

    for result in baseline:
        print(
            f"{result['id']:>3} | "
            f"score={result['score']:.6f} | "
            f"pred={result['prediction']} | "
            f"ARX={result['arx_label']}"
        )

    predictions = [
        result["prediction"]
        for result in baseline
    ]

    labels = [
        result["arx_label"]
        for result in baseline
    ]

    metrics = compute_metrics(
        labels,
        predictions,
    )

    print("\nConfusion matrix:")
    print(f"    TP = {metrics['tp']}")
    print(f"    TN = {metrics['tn']}")
    print(f"    FP = {metrics['fp']}")
    print(f"    FN = {metrics['fn']}")

    print("\nMetrics:")
    print(f"    Accuracy    = {metrics['accuracy']:.4f}")
    print(f"    Precision   = {metrics['precision']:.4f}")
    print(f"    Recall      = {metrics['recall']:.4f}")
    print(f"    Specificity = {metrics['specificity']:.4f}")
    print(f"    F1          = {metrics['f1']:.4f}")
    print(f"    MCC         = {metrics['mcc']:.4f}")

    print("=" * 70)
# ============================================================================
# COMMON EXPERIMENT HELPER
# ============================================================================

def experiment_metrics(
    name: str,
    predictions: List[int],
    baseline_predictions: List[int],
    y_true: List[int],
    scores: List[float] | None = None,
    baseline_scores: List[float] | None = None,
) -> Dict[str, Any]:

    metrics = compute_metrics(
        y_true,
        predictions,
    )

    changed = sum(
        p != b
        for p, b in zip(
            predictions,
            baseline_predictions,
        )
    )

    result = {
        "experiment": name,
        "changed_decisions": changed,
        "changed_decision_rate": (
            changed / len(predictions)
            if predictions
            else 0.0
        ),
        **metrics,
    }

    if scores is not None and baseline_scores is not None:

        deltas = [
            s - b
            for s, b in zip(
                scores,
                baseline_scores,
            )
        ]

        abs_deltas = [
            abs(x)
            for x in deltas
        ]

        result["mean_score_delta"] = (
            sum(deltas) / len(deltas)
            if deltas
            else 0.0
        )

        result["mean_absolute_score_delta"] = (
            sum(abs_deltas) / len(abs_deltas)
            if abs_deltas
            else 0.0
        )

    return result


# ============================================================================
# EXPERIMENT 1 - MEMBERSHIP FUNCTIONS
# ============================================================================

def run_membership_experiment(
    arx_rows,
    records,
    config,
    rules,
    field_sensitivity,
    baseline,
):

    rows = []

    baseline_predictions = [
        r["prediction"]
        for r in baseline
    ]

    baseline_scores = [
        r["score"]
        for r in baseline
    ]

    y_true = [
        r["arx_label"]
        for r in baseline
    ]

    for label, factor in [
        ("minus_20_percent", -0.20),
        ("minus_10_percent", -0.10),
        ("baseline", 0.0),
        ("plus_10_percent", 0.10),
        ("plus_20_percent", 0.20),
    ]:

        perturbed_config = perturb_membership_config(
            config,
            factor,
        )

        predictions = []
        scores = []

        for row in arx_rows:

            result = score_combination(
                records,
                row["fields"],
                perturbed_config,
                rules,
                field_sensitivity,
            )

            predictions.append(result["prediction"])
            scores.append(result["score"])

        result = experiment_metrics(
            label,
            predictions,
            baseline_predictions,
            y_true,
            scores,
            baseline_scores,
        )

        baseline_f1 = compute_metrics(
            y_true,
            baseline_predictions,
        )["f1"]

        result["delta_f1"] = result["f1"] - baseline_f1
        result["perturbation_percent"] = factor * 100

        rows.append(result)

    return rows


# ============================================================================
# EXPERIMENT 2 - INPUT ABLATION
# ============================================================================

def run_input_ablation(
    arx_rows,
    records,
    config,
    rules,
    field_sensitivity,
    baseline,
):

    rows = []

    baseline_predictions = [
        r["prediction"]
        for r in baseline
    ]

    baseline_scores = [
        r["score"]
        for r in baseline
    ]

    y_true = [
        r["arx_label"]
        for r in baseline
    ]

    experiments = {
        "without_k": "k",
        "without_uniqueness": "uniqueness",
        "without_sensitivity": "sensitivity",
    }

    baseline_f1 = compute_metrics(
        y_true,
        baseline_predictions,
    )["f1"]

    for name, variable in experiments.items():

        ablated_rules = remove_variable_from_rules(
            rules,
            variable,
        )

        predictions = []
        scores = []

        for row in arx_rows:

            result = score_combination(
                records,
                row["fields"],
                config,
                ablated_rules,
                field_sensitivity,
            )

            predictions.append(result["prediction"])
            scores.append(result["score"])

        result = experiment_metrics(
            name,
            predictions,
            baseline_predictions,
            y_true,
            scores,
            baseline_scores,
        )

        result["delta_f1"] = result["f1"] - baseline_f1

        rows.append(result)

    return rows


# ============================================================================
# EXPERIMENT 3 - RULE ABLATION
# ============================================================================

def run_rule_ablation(
    arx_rows,
    records,
    config,
    rules,
    field_sensitivity,
    baseline,
):

    rows = []

    baseline_predictions = [
        r["prediction"]
        for r in baseline
    ]

    baseline_scores = [
        r["score"]
        for r in baseline
    ]

    y_true = [
        r["arx_label"]
        for r in baseline
    ]

    experiments = {
        "critical_R11_R12": {"R11", "R12"},
        "R23": {"R23"},
        "R24": {"R24"},
        "R25": {"R25"},
        "R26": {"R26"},
    }

    baseline_f1 = compute_metrics(
        y_true,
        baseline_predictions,
    )["f1"]

    for name, rule_ids in experiments.items():

        ablated_rules = remove_rules(
            rules,
            rule_ids,
        )

        predictions = []
        scores = []

        for row in arx_rows:

            result = score_combination(
                records,
                row["fields"],
                config,
                ablated_rules,
                field_sensitivity,
            )

            predictions.append(result["prediction"])
            scores.append(result["score"])

        result = experiment_metrics(
            name,
            predictions,
            baseline_predictions,
            y_true,
            scores,
            baseline_scores,
        )

        result["delta_f1"] = result["f1"] - baseline_f1
        result["removed_rules"] = ",".join(sorted(rule_ids))

        rows.append(result)

    return rows


# ============================================================================
# EXPERIMENT 4 - SENSITIVITY AGGREGATION
# ============================================================================

def run_sensitivity_aggregation(
    arx_rows,
    records,
    config,
    rules,
    field_sensitivity,
    baseline,
):

    rows = []

    baseline_predictions = [
        r["prediction"]
        for r in baseline
    ]

    baseline_scores = [
        r["score"]
        for r in baseline
    ]

    y_true = [
        r["arx_label"]
        for r in baseline
    ]

    baseline_f1 = compute_metrics(
        y_true,
        baseline_predictions,
    )["f1"]

    for mode in (
        "mean",
        "max",
        "weighted",
    ):

        predictions = []
        scores = []

        for row in arx_rows:

            result = score_combination(
                records,
                row["fields"],
                config,
                rules,
                field_sensitivity,
                sensitivity_mode=mode,
            )

            predictions.append(result["prediction"])
            scores.append(result["score"])

        result = experiment_metrics(
            mode,
            predictions,
            baseline_predictions,
            y_true,
            scores,
            baseline_scores,
        )

        result["delta_f1"] = result["f1"] - baseline_f1

        rows.append(result)

    return rows


# ============================================================================
# EXPERIMENT 5 - MISSING METADATA
# ============================================================================

def run_missing_metadata(
    arx_rows,
    records,
    config,
    rules,
    field_sensitivity,
    baseline,
):

    rows = []

    baseline_predictions = [
        r["prediction"]
        for r in baseline
    ]

    y_true = [
        r["arx_label"]
        for r in baseline
    ]

    all_fields = sorted(
        field_sensitivity.keys()
    )

    rng = random.Random(
        RANDOM_SEED
    )

    rng.shuffle(all_fields)

    for percentage in (
        0,
        10,
        25,
        50,
    ):

        number_missing = round(
            len(all_fields)
            * percentage
            / 100
        )

        missing_fields = set(
            all_fields[:number_missing]
        )

        # --------------------------------------------------------------
        # Fail-closed policy:
        # if ANY field of the combination has missing metadata,
        # trigger an alert.
        # --------------------------------------------------------------

        predictions = []

        for row in arx_rows:

            has_missing_metadata = any(
                field in missing_fields
                for field in row["fields"]
            )

            if has_missing_metadata:
                prediction = 1

            else:
                prediction = baseline[
                    len(predictions)
                ]["prediction"]

            predictions.append(
                prediction
            )

        metrics = compute_metrics(
            y_true,
            predictions,
        )

        changed = sum(
            p != b
            for p, b in zip(
                predictions,
                baseline_predictions,
            )
        )

        rows.append(
            {
                "missing_metadata_percent": percentage,
                "number_missing_fields": number_missing,
                "changed_decisions": changed,
                "changed_decision_rate": (
                    changed / len(predictions)
                    if predictions
                    else 0.0
                ),
                **metrics,
            }
        )

    return rows


# ============================================================================
# EXPERIMENT 6 - DEFUZZIFICATION
# ============================================================================

def run_defuzzification(
    baseline,
):

    metrics = compute_metrics(
        [r["arx_label"] for r in baseline],
        [r["prediction"] for r in baseline],
    )

    return [
        {
            "method": "weighted_average_current",
            "available": True,
            "number_distinct_scores": len(
                set(round(r["score"], 10) for r in baseline)
            ),
            "f1": metrics["f1"],
            "note": (
                "Current production defuzzification using "
                "output_levels and weighted average."
            ),
        },
        {
            "method": "centroid",
            "available": False,
            "number_distinct_scores": "",
            "f1": "",
            "note": (
                "Not computable from the current configuration: "
                "output linguistic terms have singleton numerical "
                "values but no output membership functions."
            ),
        },
    ]


# ============================================================================
# CSV WRITER
# ============================================================================
def write_csv(filename, rows):
    path = OUTPUT_DIR / filename

    if not rows:
        print(f"[WARNING] No rows to write: {filename}")
        return

    # Collect all keys appearing in all rows
    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] {path}")

# ============================================================================
# MAIN
# ============================================================================

async def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print("STREAMSHIELD - ROBUSTNESS ANALYSIS")
    print("=" * 70)

    print("\n[1] Loading ARX labels...")
    arx_rows = load_arx_labels()
    print(f"    {len(arx_rows)} combinations loaded.")

    print("\n[2] Loading Adult dataset...")
    records = load_dataset()
    print(f"    {len(records)} records loaded.")

    print("\n[3] Loading fuzzy configuration...")
    config = await load_fuzzy_config(
        force_refresh=True
    )

    print(
        f"    threshold = {config.get('threshold')}"
    )

    print("\n[4] Loading fuzzy rules...")
    rules = await load_fuzzy_rules(
        force_refresh=True
    )

    print(
        f"    {len(rules)} enabled rules loaded."
    )
    print("\n[DEBUG] Rule IDs:")

    for rule in rules:
        print(
            f"    {get_rule_id(rule)}"
        )

    print("\n[5] Loading field sensitivities...")
    field_sensitivity = await load_field_sensitivity(
        force_refresh=True
    )

    print(
        f"    {len(field_sensitivity)} fields loaded."
    )

    # ----------------------------------------------------------------------
    # BASELINE
    # ----------------------------------------------------------------------

    print("\n[6] Computing baseline...")
    baseline = compute_baseline(
        arx_rows,
        records,
        config,
        rules,
        field_sensitivity,
    )

    baseline_predictions = [
        r["prediction"]
        for r in baseline
    ]
    print_baseline_diagnostic(baseline)

    baseline_true = [
        r["arx_label"]
        for r in baseline
    ]

    baseline_metrics = compute_metrics(
        baseline_true,
        baseline_predictions,
    )

    print("\nBaseline:")
    for key in (
        "accuracy",
        "precision",
        "recall",
        "specificity",
        "f1",
        "mcc",
    ):
        print(
            f"    {key:15s}: "
            f"{baseline_metrics[key]:.4f}"
        )
    print("\n" + "=" * 70)
    print("BASELINE SCORES")
    print("=" * 70)

    for result in baseline:
        print(
            f"{result['id']:>3} | "
            f"score={result['score']:.6f} | "
            f"pred={result['prediction']} | "
            f"ARX={result['arx_label']}"
        )

    print("=" * 70)

    # ----------------------------------------------------------------------
    # EXPERIMENTS
    # ----------------------------------------------------------------------

    print("\n[7] Membership sensitivity...")
    membership_results = run_membership_experiment(
        arx_rows,
        records,
        config,
        rules,
        field_sensitivity,
        baseline,
    )

    print("\n[8] Input ablation...")
    input_results = run_input_ablation(
        arx_rows,
        records,
        config,
        rules,
        field_sensitivity,
        baseline,
    )

    print("\n[9] Rule ablation...")
    rule_results = run_rule_ablation(
        arx_rows,
        records,
        config,
        rules,
        field_sensitivity,
        baseline,
    )

    print("\n[10] Sensitivity aggregation...")
    sensitivity_results = run_sensitivity_aggregation(
        arx_rows,
        records,
        config,
        rules,
        field_sensitivity,
        baseline,
    )

    print("\n[11] Missing metadata / fail-closed...")
    missing_results = run_missing_metadata(
        arx_rows,
        records,
        config,
        rules,
        field_sensitivity,
        baseline,
    )

    print("\n[12] Defuzzification...")
    defuzzification_results = run_defuzzification(
        baseline
    )

    # ----------------------------------------------------------------------
    # SAVE
    # ----------------------------------------------------------------------

    print("\n[13] Writing results...")

    write_csv(
        "membership_sensitivity.csv",
        membership_results,
    )

    write_csv(
        "input_ablation.csv",
        input_results,
    )

    write_csv(
        "rule_ablation.csv",
        rule_results,
    )

    write_csv(
        "sensitivity_aggregation.csv",
        sensitivity_results,
    )

    write_csv(
        "missing_metadata.csv",
        missing_results,
    )

    write_csv(
        "defuzzification.csv",
        defuzzification_results,
    )

    # Summary
    summary = []

    summary.append(
        {
            "category": "baseline",
            "experiment": "production_configuration",
            **baseline_metrics,
        }
    )

    for row in membership_results:
        summary.append(
            {
                "category": "membership",
                **row,
            }
        )

    for row in input_results:
        summary.append(
            {
                "category": "input_ablation",
                **row,
            }
        )

    for row in rule_results:
        summary.append(
            {
                "category": "rule_ablation",
                **row,
            }
        )

    for row in sensitivity_results:
        summary.append(
            {
                "category": "sensitivity_aggregation",
                **row,
            }
        )

    for row in missing_results:
        summary.append(
            {
                "category": "missing_metadata",
                **row,
            }
        )

    write_csv(
        "robustness_summary.csv",
        summary,
    )

    print("\n" + "=" * 70)
    print("ROBUSTNESS ANALYSIS FINISHED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())