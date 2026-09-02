# """
# StreamShield - Calibration du seuil pour FuzzyRiskScorer (v4)

# v4 : FuzzyRiskScorer retenu comme scorer de production -- ce script ne
# calibre plus que son trigger_threshold, la comparaison avec RiskScorer
# (formule linéaire) est terminée et n'est plus nécessaire.

# Usage:
#     python -m scripts.calibrate_threshold
# """
# import random
# from dataclasses import dataclass
# from typing import List, Tuple
# import asyncio

# from detection.field_sensitivity_repository import load_field_sensitivity
# import pandas as pd

# from detection.fuzzy_risk_scorer import FuzzyRiskScorer
# from detection.frequency_counter import CombinationAnalyzer

# K_RISKY_THRESHOLD = 11
# CANDIDATE_THRESHOLDS = [
#     0.10,
#     0.15,
#     0.20,
#     0.25,
#     0.30,
#     0.35,
#     0.40,
#     0.45,
#     0.50,
#     0.55,
#     0.60,
#     0.65,
#     0.70,
#     0.75,
#     0.80,
#     0.85,
#     0.90,
# ]
# RECALL_FLOOR = 0.9

# FIELDS = ("ville", "code_postal", "sexe", "date_naissance")


# @dataclass
# class LabeledCase:
#     records: List[dict]
#     fields: Tuple[str, ...]
#     true_k: int
#     is_risky: bool


# def _build_case(k_target: int, total: int = 300) -> LabeledCase:
#     """
#     Construit un cas synthétique dont le vrai k-anonymat est k_target.

#     Toutes les classes d'équivalence sont créées avec exactement
#     k_target occurrences afin d'éviter la création accidentelle
#     de groupes singleton par le bruit aléatoire.
#     """

#     if k_target <= 0:
#         raise ValueError("k_target doit être > 0")

#     if total < k_target:
#         raise ValueError(
#             "total doit être >= k_target"
#         )

#     target = {
#         "ville": "Casablanca",
#         "code_postal": "20500",
#         "sexe": "F",
#         "date_naissance": "1985-07-22",
#     }

#     noise_groups = [
#         {
#             "ville": "Rabat",
#             "code_postal": "10000",
#             "sexe": "M",
#             "date_naissance": "1970-03-12",
#         },
#         {
#             "ville": "Fes",
#             "code_postal": "30000",
#             "sexe": "F",
#             "date_naissance": "1975-06-01",
#         },
#         {
#             "ville": "Marrakech",
#             "code_postal": "40000",
#             "sexe": "M",
#             "date_naissance": "1980-09-23",
#         },
#         {
#             "ville": "Tanger",
#             "code_postal": "90000",
#             "sexe": "F",
#             "date_naissance": "1988-11-05",
#         },
#         {
#             "ville": "Agadir",
#             "code_postal": "80000",
#             "sexe": "M",
#             "date_naissance": "1995-02-17",
#         },
#     ]

#     records = []

#     # Groupe cible
#     records.extend(
#         [dict(target) for _ in range(k_target)]
#     )

#     # Ajouter des groupes dont la fréquence est également k_target.
#     remaining = total - k_target

#     group_index = 0

#     while remaining >= k_target:
#         group = noise_groups[
#             group_index % len(noise_groups)
#         ]

#         records.extend(
#             [dict(group) for _ in range(k_target)]
#         )

#         remaining -= k_target
#         group_index += 1

#     # Les éventuels enregistrements restants sont ajoutés
#     # au dernier groupe afin de ne jamais créer de singleton.
#     if remaining > 0:
#         records.extend(
#             [dict(noise_groups[group_index % len(noise_groups)])
#              for _ in range(remaining)]
#         )
#     analysis = CombinationAnalyzer.analyze(
#     records,
#     FIELDS,
#     )
#     print(
#         f"[DEBUG] k_target={k_target}, "
#         f"k_reel={analysis['k']}, "
#         f"uniqueness={analysis['uniqueness']:.3f}, "
#         f"sample_size={analysis['sample_size']}"
#     )
#     return LabeledCase(
#         records=records,
#         fields=FIELDS,
#         true_k=k_target,
#         is_risky=(k_target <= K_RISKY_THRESHOLD),
#     )


# def build_synthetic_dataset() -> List[LabeledCase]:
#     k_values = [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 5, 5, 8, 10, 10, 15, 20, 30, 50]
#     return [_build_case(k) for k in k_values]


# def build_uci_dataset(sample_sizes=(200, 1000, 5000)) -> List[LabeledCase]:
#     try:
#         df = pd.read_csv(
#             "data/adult_reference.csv", header=None,
#             names=["age", "workclass", "fnlwgt", "education", "education_num",
#                    "marital_status", "occupation", "relationship", "race", "sex",
#                    "capital_gain", "capital_loss", "hours_per_week", "native_country", "income"],
#             na_values="?",
#         ).dropna()
#     except FileNotFoundError:
#         print("[avertissement] data/adult_reference.csv introuvable -- calibration synthétique uniquement")
#         return []

#     cases = []
#     for size in sample_sizes:
#         sample = df.sample(n=min(size, len(df)), random_state=42)
#         fields = ("education", "sex")
#         records = sample[list(fields)].to_dict(orient="records")
#         analysis = CombinationAnalyzer.analyze(records, fields)
#         cases.append(LabeledCase(records=records, fields=fields, true_k=analysis["k"],
#                                   is_risky=(analysis["k"] <= K_RISKY_THRESHOLD)))
#     return cases


# def evaluate_threshold(cases: List[LabeledCase], threshold: float, scorer: FuzzyRiskScorer) -> dict:
#     tp = fp = tn = fn = 0
#     for case in cases:
#         result = scorer.score(case.records, case.fields)
#         predicted_risky = result.score >= threshold

#         if case.is_risky and predicted_risky:
#             tp += 1
#         elif case.is_risky and not predicted_risky:
#             fn += 1
#         elif not case.is_risky and predicted_risky:
#             fp += 1
#         else:
#             tn += 1

#     precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
#     recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
#     f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

#     return {"threshold": threshold, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
#             "precision": precision, "recall": recall, "f1": f1}


# def print_detailed_scores(
#     cases: List[LabeledCase],
#     scorer: FuzzyRiskScorer,
# ):
#     print("\n=== Scores détaillés ===")
#     print(
#         f"{'k':<6}"
#         f"{'Unicité':<12}"
#         f"{'Sensibilité':<15}"
#         f"{'Score':<10}"
#         f"{'Terrain (risqué)':<18}"
#     )
#     print("-" * 65)

#     for case in cases:
#         result = scorer.score(
#             case.records,
#             case.fields,
#         )

#         print(
#             f"{result.k:<6}"
#             f"{result.uniqueness:<12.3f}"
#             f"{result.avg_sensitivity:<15.3f}"
#             f"{result.score:<10.3f}"
#             f"{str(case.is_risky):<18}"
#         )

# async def run_calibration():
#     synthetic = build_synthetic_dataset()
#     uci = build_uci_dataset()
#     all_cases = synthetic + uci

#     n_risky = sum(1 for c in all_cases if c.is_risky)
#     n_safe = len(all_cases) - n_risky
#     print(f"Jeu de calibration : {len(all_cases)} cas ({n_risky} risqués, {n_safe} non risqués)")
#     print(f"Vérité terrain : risqué si k <= {K_RISKY_THRESHOLD}\n")

#     # threshold=0.0 sur le scorer lui-même : on veut le SCORE brut,
#     # la décision "declenché" est recalculée pour chaque seuil candidat ci-dessous
#     field_sensitivity = await load_field_sensitivity(
#         force_refresh=True
#     )

#     print(f"Sensibilités chargées : {len(field_sensitivity)}")

#     scorer = FuzzyRiskScorer(
#         threshold=0.0,
#         field_sensitivity=field_sensitivity,
#         min_sample_size=0,
#     )

#     await scorer.load_fuzzy_configuration()

#     print("Configuration fuzzy chargée.")
#     print(f"{'Seuil':<8}{'TP':<5}{'FP':<5}{'TN':<5}{'FN':<5}{'Précision':<12}{'Rappel':<10}{'F1':<8}")
#     print("-" * 65)

#     results = []
#     for threshold in CANDIDATE_THRESHOLDS:
#         r = evaluate_threshold(all_cases, threshold, scorer)
#         results.append(r)
#         print(
#             f"{r['threshold']:<8}{r['tp']:<5}{r['fp']:<5}{r['tn']:<5}{r['fn']:<5}"
#             f"{r['precision']:<12.3f}{r['recall']:<10.3f}{r['f1']:<8.3f}"
#         )

#     eligible = [r for r in results if r["recall"] >= RECALL_FLOOR]
#     if eligible:
#         best = max(eligible, key=lambda r: r["f1"])
#         print(
#             f"\nSeuil recommandé : {best['threshold']} "
#             f"(rappel={best['recall']:.3f} >= {RECALL_FLOOR}, précision={best['precision']:.3f}, F1={best['f1']:.3f})"
#         )
#     else:
#         best = max(results, key=lambda r: r["recall"])
#         print(
#             f"\nAucun seuil n'atteint un rappel >= {RECALL_FLOOR}. "
#             f"Meilleur rappel disponible : seuil={best['threshold']} (rappel={best['recall']:.3f}) -- "
#             f"les règles floues elles-mêmes pourraient devoir être ajustées."
#         )

#     print_detailed_scores(all_cases, scorer)


# if __name__ == "__main__":
#     asyncio.run(run_calibration())
"""
StreamShield - Calibration du seuil FuzzyRiskScorer

Objectif
--------
Déterminer objectivement le seuil du FuzzyRiskScorer en utilisant
les labels ARX comme référence.

Référence :
    average_risk < 0.09  -> label 0
    average_risk >= 0.09 -> label 1

Critère de sélection :
    1. Recall >= 0.90
    2. meilleur F1
    3. en cas d'égalité : meilleure specificity
    4. en cas d'égalité : meilleure precision

IMPORTANT
---------
Ce script NE modifie PAS MongoDB.
Il sert uniquement à calibrer et à évaluer le seuil.

Usage depuis services/streamshield-serv :
    python -m scripts.calibrate_threshold
"""

import asyncio
import csv
from pathlib import Path
from typing import Dict, List, Tuple

from detection.field_sensitivity_repository import (
    load_field_sensitivity,
)
from detection.fuzzy_risk_scorer import FuzzyRiskScorer


# ============================================================
# CONFIGURATION
# ============================================================

ARX_THRESHOLD = 0.09

RECALL_FLOOR = 0.90

CANDIDATE_THRESHOLDS = [
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


# ============================================================
# CHEMINS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

DATASET_FILE = (
    BASE_DIR
    / "data"
    / "validation"
    / "uci_adult"
    / "processed"
    / "adult_prepared.csv"
)

ARX_LABELS_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "java"
    / "arx_30_labels.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "validation"
    / "arx"
    / "fuzzy_threshold_calibration.csv"
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

    print(f"Nombre de records : {len(records)}")
    print(
        f"Nombre de colonnes : "
        f"{len(reader.fieldnames or [])}"
    )

    return records


# ============================================================
# CHARGEMENT LABELS ARX
# ============================================================

def load_arx_labels() -> List[Dict]:
    print()
    print("=" * 70)
    print("       CHARGEMENT DES LABELS ARX")
    print("=" * 70)

    print(f"Fichier : {ARX_LABELS_FILE}")

    if not ARX_LABELS_FILE.exists():
        raise FileNotFoundError(
            f"Labels ARX introuvables : {ARX_LABELS_FILE}"
        )

    rows = []

    with open(
        ARX_LABELS_FILE,
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

        missing = required_columns - set(
            reader.fieldnames or []
        )

        if missing:
            raise ValueError(
                f"Colonnes manquantes dans les labels ARX : "
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

            arx_label = int(row["label"])

            # Vérification de cohérence du label ARX
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
        f"Combinaisons ARX chargées : {len(rows)}"
    )

    if len(rows) != 30:
        raise ValueError(
            "La validation attend exactement 30 "
            f"combinaisons ARX, mais {len(rows)} ont été trouvées."
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

    accuracy = (
        (tp + tn) / (tp + tn + fp + fn)
        if (tp + tn + fp + fn)
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
# CALCUL DES SCORES FUZZY
# ============================================================

async def compute_fuzzy_scores(
    arx_rows: List[Dict],
    records: List[Dict],
) -> List[Dict]:

    print()
    print("=" * 70)
    print("       CALCUL DES SCORES FUZZY")
    print("=" * 70)

    field_sensitivity = await load_field_sensitivity(
        force_refresh=True
    )

    print(
        f"Sensibilités chargées depuis MongoDB : "
        f"{len(field_sensitivity)}"
    )

    scorer = FuzzyRiskScorer(
        threshold=0.0,
        field_sensitivity=field_sensitivity,
        min_sample_size=0,
    )

    await scorer.load_fuzzy_configuration()

    print(
        f"Règles fuzzy chargées : "
        f"{len(scorer.fuzzy_rules)}"
    )

    results = []

    for row in arx_rows:

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
                "arx_average_risk": row["average_risk"],
                "arx_label": row["arx_label"],
                "k": result.k,
                "uniqueness": result.uniqueness,
                "avg_sensitivity": result.avg_sensitivity,
                "fuzzy_score": result.score,
                "sample_size": result.sample_size,
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

    if len(results) != 30:
        raise ValueError(
            f"Nombre de résultats Fuzzy inattendu : "
            f"{len(results)} au lieu de 30."
        )

    return results


# ============================================================
# EVALUATION DES SEUILS
# ============================================================

def evaluate_thresholds(
    results: List[Dict],
) -> List[Dict]:

    print()
    print("=" * 70)
    print("       EVALUATION DES SEUILS")
    print("=" * 70)

    y_true = [
        row["arx_label"]
        for row in results
    ]

    evaluations = []

    print()
    print(
        "SEUIL | ACC | PREC | RECALL | SPEC | "
        "F1 | YOUDEN | TP | FP | FN | TN"
    )

    print("-" * 100)

    for threshold in CANDIDATE_THRESHOLDS:

        y_pred = [
            int(
                row["fuzzy_score"] >= threshold
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

        evaluations.append(evaluation)

        print(
            f"{threshold:5.2f} | "
            f"{metrics['accuracy']:.3f} | "
            f"{metrics['precision']:.3f} | "
            f"{metrics['recall']:.3f} | "
            f"{metrics['specificity']:.3f} | "
            f"{metrics['f1']:.3f} | "
            f"{metrics['youden_j']:.3f} | "
            f"{metrics['tp']:2d} | "
            f"{metrics['fp']:2d} | "
            f"{metrics['fn']:2d} | "
            f"{metrics['tn']:2d}"
        )

    return evaluations


# ============================================================
# SELECTION DU SEUIL
# ============================================================

def select_best_threshold(
    evaluations: List[Dict],
) -> Dict:

    eligible = [
        evaluation
        for evaluation in evaluations
        if evaluation["recall"] >= RECALL_FLOOR
    ]

    print()
    print("=" * 70)
    print("       SELECTION DU SEUIL")
    print("=" * 70)

    print(
        f"Contrainte : Recall >= {RECALL_FLOOR:.2f}"
    )

    print(
        f"Seuils admissibles : {len(eligible)}"
    )

    if not eligible:

        print()
        print(
            "ATTENTION : aucun seuil ne respecte "
            f"Recall >= {RECALL_FLOOR:.2f}."
        )

        best = max(
            evaluations,
            key=lambda x: (
                x["recall"],
                x["f1"],
                x["specificity"],
            ),
        )

        print(
            "Le seuil retourné sera celui ayant "
            "le meilleur recall."
        )

        return best

    # Critère :
    # 1. meilleur F1
    # 2. meilleur recall
    # 3. meilleure specificity
    # 4. meilleure precision
    # 5. seuil plus élevé en dernier recours

    best = max(
        eligible,
        key=lambda x: (
            x["f1"],
            x["recall"],
            x["specificity"],
            x["precision"],
            x["threshold"],
        ),
    )

    print()
    print(
        f"SEUIL RETENU : {best['threshold']:.2f}"
    )

    print(
        f"Accuracy     : {best['accuracy']:.4f}"
    )

    print(
        f"Precision    : {best['precision']:.4f}"
    )

    print(
        f"Recall       : {best['recall']:.4f}"
    )

    print(
        f"Specificity  : {best['specificity']:.4f}"
    )

    print(
        f"F1           : {best['f1']:.4f}"
    )

    print(
        f"Youden J     : {best['youden_j']:.4f}"
    )

    print(
        f"TP={best['tp']} | "
        f"FP={best['fp']} | "
        f"FN={best['fn']} | "
        f"TN={best['tn']}"
    )

    return best


# ============================================================
# SAUVEGARDE
# ============================================================

def save_results(
    evaluations: List[Dict],
    best: Dict,
) -> None:

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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

        writer.writerows(evaluations)

    print()
    print(
        f"Résultats sauvegardés : {OUTPUT_FILE}"
    )

    print()
    print(
        f"SEUIL FINAL PROPOSÉ : "
        f"{best['threshold']:.2f}"
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("=" * 70)
    print("       STREAMSHIELD - CALIBRATION FUZZY")
    print("=" * 70)

    print()
    print(
        f"Référence ARX : "
        f"average_risk >= {ARX_THRESHOLD} -> label 1"
    )

    print(
        f"Contrainte Recall : >= {RECALL_FLOOR}"
    )

    # --------------------------------------------------------
    # 1. Dataset
    # --------------------------------------------------------

    records = load_dataset()

    # --------------------------------------------------------
    # 2. Labels ARX
    # --------------------------------------------------------

    arx_rows = load_arx_labels()

    # --------------------------------------------------------
    # 3. Scores Fuzzy
    # --------------------------------------------------------

    results = await compute_fuzzy_scores(
        arx_rows,
        records,
    )

    # --------------------------------------------------------
    # 4. Evaluation des seuils
    # --------------------------------------------------------

    evaluations = evaluate_thresholds(
        results
    )

    # --------------------------------------------------------
    # 5. Sélection
    # --------------------------------------------------------

    best = select_best_threshold(
        evaluations
    )

    # --------------------------------------------------------
    # 6. Sauvegarde
    # --------------------------------------------------------

    save_results(
        evaluations,
        best,
    )

    # --------------------------------------------------------
    # 7. Conclusion
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("       CALIBRATION TERMINEE")
    print("=" * 70)

    print()
    print(
        "Le seuil proposé a été déterminé à partir "
        "des labels ARX des 30 combinaisons."
    )

    print(
        "MongoDB n'a pas été modifié."
    )

    print()
    print(
        "IMPORTANT : ce seuil doit être validé "
        "sur un ensemble indépendant avant "
        "d'être considéré comme seuil final de production."
    )


if __name__ == "__main__":
    asyncio.run(main())