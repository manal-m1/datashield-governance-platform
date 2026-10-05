import os
import re
import time
import json
import requests
import pandas as pd
from collections import defaultdict
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

DATASET = Path(
    r".\services\cleaning-serv\storage\uploads"
    r"\0db8b536-9813-4d94-aea8-4562ac603eaf_testV1.csv"
)

OUTPUT_DIR = Path(r".\services\taxonomie-serv\validation\discovery\results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TAXONOMY_URL = "http://localhost:8002/analyze"
PRESIDIO_URL = "http://localhost:8003/analyze"

N_LATENCY = 1000

# ------------------------------------------------------------
# Ground truth
# ------------------------------------------------------------

# CIN technique :
# 1-2 letters + exactly 6 digits
CIN_RE = re.compile(r"^[A-Z]{1,2}\d{6}$")

# Moroccan IBAN :
# MA + 24 digits
IBAN_MA_RE = re.compile(r"^MA\d{24}$")

# Date :
# YYYY-MM-DD
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ============================================================
# HELPERS
# ============================================================

def clean_value(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def build_text(column, value):
    """
    Adds column context deliberately.

    This is important because the Moroccan Presidio
    recognizers use contextual terms such as:
      - nationalid
      - iban
      - etc.
    """

    context = {
        "NationalID": "NationalID",
        "IBAN": "IBAN",
        "BirthDate": "BirthDate",
    }

    prefix = context.get(column, column)

    return f"{prefix}: {value}"


# ============================================================
# GROUND TRUTH
# ============================================================

def build_ground_truth(df):
    """
    Returns one ground-truth record per evaluated cell.

    Positive entities:
      CIN_MAROC
      IBAN_MA
      DATE_TIME

    All other values are treated as negative examples
    for the corresponding entity.
    """

    records = []

    columns = [
        "NationalID",
        "IBAN",
        "BirthDate",
    ]

    for row_id, row in df.iterrows():

        for column in columns:

            value = clean_value(row[column])

            if value is None:
                continue

            if column == "NationalID":

                entity = "CIN_MAROC"
                positive = bool(
                    CIN_RE.fullmatch(value.upper())
                )

            elif column == "IBAN":

                entity = "IBAN_MA"

                normalized = (
                    value
                    .replace(" ", "")
                    .upper()
                )

                positive = bool(
                    IBAN_MA_RE.fullmatch(normalized)
                )

            elif column == "BirthDate":

                entity = "DATE_TIME"
                positive = bool(
                    DATE_RE.fullmatch(value)
                )

            else:
                continue

            records.append({
                "row_id": int(row_id),
                "column": column,
                "value": value,
                "entity": entity,
                "ground_truth": positive,
            })

    return pd.DataFrame(records)


# ============================================================
# SERVICE CALLS
# ============================================================

def call_taxonomy(text):
    """
    Call Taxonomy service.
    """

    payload = {
        "text": text
    }

    try:
        response = requests.post(
            TAXONOMY_URL,
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        return data.get("detections", [])

    except Exception as e:

        return {
            "_error": str(e)
        }


def call_presidio(text, entity):
    """
    Call Moroccan Presidio service.

    We explicitly request the target entity when supported.
    """

    payload = {
        "text": text,
        "language": "en",
        "entities": [entity],
        "score_threshold": 0.3
    }

    try:

        response = requests.post(
            PRESIDIO_URL,
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        return data.get("detections", [])

    except Exception as e:

        return {
            "_error": str(e)
        }


# ============================================================
# ENTITY NORMALIZATION
# ============================================================

def normalize_entity(entity):
    """
    Converts implementation-specific entity names
    into benchmark entity names.
    """

    entity = str(entity).strip().upper()

    mapping = {

        # ----------------------------------------------------
        # CIN
        # ----------------------------------------------------
        "CIN_MAROC":
            "CIN_MAROC",

        "CIN_MAROC_FULL":
            "CIN_MAROC",

        "CIN_MAROC_SPACED":
            "CIN_MAROC",

        "CIN - CARTE D'IDENTITÉ NATIONALE":
            "CIN_MAROC",

        "CIN - CARTE D’IDENTITÉ NATIONALE":
            "CIN_MAROC",

        # ----------------------------------------------------
        # IBAN
        # ----------------------------------------------------
        "IBAN_MA":
            "IBAN_MA",

        "الحساب_البنكي":
            "IBAN_MA",

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------
        "DATE_TIME":
            "DATE_TIME",

        "DATE":
            "DATE_TIME",

        "DATETIME":
            "DATE_TIME",

        "DATE DE NAISSANCE":
            "DATE_TIME",
    }

    return mapping.get(entity, entity)


def detection_matches_value(detection, value):
    """
    Determines whether a detection corresponds
    to the evaluated cell value.
    """

    detected_value = detection.get("value")

    if detected_value is None:
        return False

    detected_value = str(detected_value).strip()
    value = str(value).strip()

    # --------------------------------------------------------
    # Direct comparison
    # --------------------------------------------------------

    if detected_value == value:
        return True

    # --------------------------------------------------------
    # Normalize spaces
    # --------------------------------------------------------

    if (
        detected_value.replace(" ", "")
        == value.replace(" ", "")
    ):
        return True

    # --------------------------------------------------------
    # Context-prefixed detection
    # Example:
    # "IBAN: MA123..."
    # --------------------------------------------------------

    if detected_value.upper().endswith(
        value.upper()
    ):
        return True

    # --------------------------------------------------------
    # Extract value from common "context: value" format
    # --------------------------------------------------------

    if ":" in detected_value:

        extracted = detected_value.split(
            ":", 1
        )[1].strip()

        if extracted == value:
            return True

        if (
            extracted.replace(" ", "")
            == value.replace(" ", "")
        ):
            return True

    return False


# ============================================================
# METRICS
# ============================================================

def compute_metrics(tp, fp, fn):

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

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
    }


# ============================================================
# BENCHMARK ONE METHOD
# ============================================================

def evaluate_method(gt, method):

    counters = defaultdict(
        lambda: {
            "TP": 0,
            "FP": 0,
            "FN": 0
        }
    )

    detailed_results = []

    for index, item in gt.iterrows():

        text = build_text(
            item["column"],
            item["value"]
        )

        entity = item["entity"]
        truth = bool(item["ground_truth"])

        if method == "taxonomy":

            detections = call_taxonomy(text)

        elif method == "presidio":

            detections = call_presidio(
                text,
                entity
            )

        else:

            raise ValueError(
                f"Unknown method: {method}"
            )

        if isinstance(detections, dict) and "_error" in detections:

            detailed_results.append({
                **item.to_dict(),
                "method": method,
                "error": detections["_error"],
                "detected": False,
            })

            continue

        normalized_detections = []

        for detection in detections:

            detected_entity = normalize_entity(
                detection.get("entity_type", "")
            )

            if detected_entity == entity:

                normalized_detections.append(
                    detection
                )

        detected = any(
            detection_matches_value(
                d,
                item["value"]
            )
            for d in normalized_detections
        )

        if truth and detected:

            counters[entity]["TP"] += 1

        elif truth and not detected:

            counters[entity]["FN"] += 1

        elif not truth and detected:

            counters[entity]["FP"] += 1

        detailed_results.append({
            **item.to_dict(),
            "method": method,
            "detected": detected,
            "detections_count": len(
                normalized_detections
            ),
        })

    return counters, detailed_results


# ============================================================
# LATENCY
# ============================================================

def benchmark_latency(gt):

    # Use first 1000 available cells.
    samples = gt.head(N_LATENCY).copy()

    # If fewer than 1000 exist, repeat deterministically.
    if len(samples) < N_LATENCY:

        repeats = (
            N_LATENCY // len(samples)
        ) + 1

        samples = pd.concat(
            [samples] * repeats,
            ignore_index=True
        ).head(N_LATENCY)

    print()
    print("=" * 60)
    print("LATENCY — 1000 CELLS")
    print("=" * 60)

    # --------------------------------------------------------
    # Taxonomy
    # --------------------------------------------------------

    start = time.perf_counter()

    taxonomy_ok = 0

    for _, item in samples.iterrows():

        text = build_text(
            item["column"],
            item["value"]
        )

        result = call_taxonomy(text)

        if not (
            isinstance(result, dict)
            and "_error" in result
        ):
            taxonomy_ok += 1

    taxonomy_time = (
        time.perf_counter() - start
    )

    # --------------------------------------------------------
    # Presidio
    # --------------------------------------------------------

    start = time.perf_counter()

    presidio_ok = 0

    for _, item in samples.iterrows():

        text = build_text(
            item["column"],
            item["value"]
        )

        result = call_presidio(
            text,
            item["entity"]
        )

        if not (
            isinstance(result, dict)
            and "_error" in result
        ):
            presidio_ok += 1

    presidio_time = (
        time.perf_counter() - start
    )

    latency = pd.DataFrame([
        {
            "method": "Regex / Taxonomy",
            "cells": N_LATENCY,
            "successful_calls": taxonomy_ok,
            "total_time_s": taxonomy_time,
            "mean_ms_per_cell":
                taxonomy_time * 1000 / N_LATENCY,
        },
        {
            "method": "Presidio + Moroccan",
            "cells": N_LATENCY,
            "successful_calls": presidio_ok,
            "total_time_s": presidio_time,
            "mean_ms_per_cell":
                presidio_time * 1000 / N_LATENCY,
        }
    ])

    latency.to_csv(
        OUTPUT_DIR / "latency_1000_cells.csv",
        index=False
    )

    print(latency.to_string(index=False))

    return latency


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("DISCOVERY BENCHMARK — E")
    print("=" * 60)

    print()
    print("Dataset:")
    print(DATASET)

    if not DATASET.exists():

        raise FileNotFoundError(
            f"Dataset not found: {DATASET}"
        )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    df = pd.read_csv(DATASET)

    print()
    print(f"Rows loaded: {len(df)}")

    # --------------------------------------------------------
    # Ground truth
    # --------------------------------------------------------

    gt = build_ground_truth(df)

    gt.to_csv(
        OUTPUT_DIR / "ground_truth.csv",
        index=False
    )

    print()
    print("Ground truth:")
    print(
        gt.groupby(
            ["entity", "ground_truth"]
        ).size()
    )

    # --------------------------------------------------------
    # Evaluate
    # --------------------------------------------------------

    all_metrics = []
    all_details = []

    for method in [
        "taxonomy",
        "presidio"
    ]:

        print()
        print("=" * 60)
        print(f"EVALUATING: {method}")
        print("=" * 60)

        counters, details = evaluate_method(
            gt,
            method
        )

        all_details.extend(details)

        for entity in [
            "CIN_MAROC",
            "IBAN_MA",
            "DATE_TIME"
        ]:

            c = counters[entity]

            metrics = compute_metrics(
                c["TP"],
                c["FP"],
                c["FN"]
            )

            metrics["method"] = method
            metrics["entity"] = entity

            all_metrics.append(metrics)

            print(
                f"{entity}: "
                f"P={metrics['Precision']:.4f} "
                f"R={metrics['Recall']:.4f} "
                f"F1={metrics['F1']:.4f} "
                f"TP={metrics['TP']} "
                f"FP={metrics['FP']} "
                f"FN={metrics['FN']}"
            )

    # --------------------------------------------------------
    # Save metrics
    # --------------------------------------------------------

    metrics_df = pd.DataFrame(
        all_metrics
    )

    metrics_df = metrics_df[
        [
            "method",
            "entity",
            "TP",
            "FP",
            "FN",
            "Precision",
            "Recall",
            "F1"
        ]
    ]

    metrics_df.to_csv(
        OUTPUT_DIR / "discovery_metrics.csv",
        index=False
    )

    details_df = pd.DataFrame(
        all_details
    )

    details_df.to_csv(
        OUTPUT_DIR / "discovery_details.csv",
        index=False
    )

    # --------------------------------------------------------
    # Overall metrics
    # --------------------------------------------------------

    overall = []

    for method in [
        "taxonomy",
        "presidio"
    ]:

        subset = metrics_df[
            metrics_df["method"] == method
        ]

        tp = int(subset["TP"].sum())
        fp = int(subset["FP"].sum())
        fn = int(subset["FN"].sum())

        m = compute_metrics(
            tp,
            fp,
            fn
        )

        m["method"] = method

        overall.append(m)

    overall_df = pd.DataFrame(overall)

    overall_df = overall_df[
        [
            "method",
            "TP",
            "FP",
            "FN",
            "Precision",
            "Recall",
            "F1"
        ]
    ]

    overall_df.to_csv(
        OUTPUT_DIR / "discovery_overall.csv",
        index=False
    )

    print()
    print("=" * 60)
    print("OVERALL")
    print("=" * 60)
    print(
        overall_df.to_string(index=False)
    )

    # --------------------------------------------------------
    # Latency
    # --------------------------------------------------------

    benchmark_latency(gt)

    # --------------------------------------------------------
    # Final information
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("FILES GENERATED")
    print("=" * 60)

    print(
        OUTPUT_DIR / "ground_truth.csv"
    )

    print(
        OUTPUT_DIR / "discovery_metrics.csv"
    )

    print(
        OUTPUT_DIR / "discovery_overall.csv"
    )

    print(
        OUTPUT_DIR / "discovery_details.csv"
    )

    print(
        OUTPUT_DIR / "latency_1000_cells.csv"
    )

    print()
    print("Benchmark finished.")


if __name__ == "__main__":
    main()