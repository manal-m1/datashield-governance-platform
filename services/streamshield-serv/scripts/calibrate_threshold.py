"""
StreamShield - Calibration du seuil pour FuzzyRiskScorer (v4)

v4 : FuzzyRiskScorer retenu comme scorer de production -- ce script ne
calibre plus que son trigger_threshold, la comparaison avec RiskScorer
(formule linéaire) est terminée et n'est plus nécessaire.

Usage:
    python -m scripts.calibrate_threshold
"""
import random
from dataclasses import dataclass
from typing import List, Tuple

import pandas as pd

from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.frequency_counter import CombinationAnalyzer

K_RISKY_THRESHOLD = 5
CANDIDATE_THRESHOLDS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
RECALL_FLOOR = 0.9

FIELDS = ("ville", "code_postal", "sexe", "date_naissance")


@dataclass
class LabeledCase:
    records: List[dict]
    fields: Tuple[str, ...]
    true_k: int
    is_risky: bool


def _build_case(k_target: int, total: int = 300) -> LabeledCase:
    """
    Construit un cas synthétique dont le vrai k-anonymat est k_target.

    Toutes les classes d'équivalence sont créées avec exactement
    k_target occurrences afin d'éviter la création accidentelle
    de groupes singleton par le bruit aléatoire.
    """

    if k_target <= 0:
        raise ValueError("k_target doit être > 0")

    if total < k_target:
        raise ValueError(
            "total doit être >= k_target"
        )

    target = {
        "ville": "Casablanca",
        "code_postal": "20500",
        "sexe": "F",
        "date_naissance": "1985-07-22",
    }

    noise_groups = [
        {
            "ville": "Rabat",
            "code_postal": "10000",
            "sexe": "M",
            "date_naissance": "1970-03-12",
        },
        {
            "ville": "Fes",
            "code_postal": "30000",
            "sexe": "F",
            "date_naissance": "1975-06-01",
        },
        {
            "ville": "Marrakech",
            "code_postal": "40000",
            "sexe": "M",
            "date_naissance": "1980-09-23",
        },
        {
            "ville": "Tanger",
            "code_postal": "90000",
            "sexe": "F",
            "date_naissance": "1988-11-05",
        },
        {
            "ville": "Agadir",
            "code_postal": "80000",
            "sexe": "M",
            "date_naissance": "1995-02-17",
        },
    ]

    records = []

    # Groupe cible
    records.extend(
        [dict(target) for _ in range(k_target)]
    )

    # Ajouter des groupes dont la fréquence est également k_target.
    remaining = total - k_target

    group_index = 0

    while remaining >= k_target:
        group = noise_groups[
            group_index % len(noise_groups)
        ]

        records.extend(
            [dict(group) for _ in range(k_target)]
        )

        remaining -= k_target
        group_index += 1

    # Les éventuels enregistrements restants sont ajoutés
    # au dernier groupe afin de ne jamais créer de singleton.
    if remaining > 0:
        records.extend(
            [dict(noise_groups[group_index % len(noise_groups)])
             for _ in range(remaining)]
        )
    analysis = CombinationAnalyzer.analyze(
    records,
    FIELDS,
    )
    print(
        f"[DEBUG] k_target={k_target}, "
        f"k_reel={analysis['k']}, "
        f"uniqueness={analysis['uniqueness']:.3f}, "
        f"sample_size={analysis['sample_size']}"
    )
    return LabeledCase(
        records=records,
        fields=FIELDS,
        true_k=k_target,
        is_risky=(k_target <= K_RISKY_THRESHOLD),
    )


def build_synthetic_dataset() -> List[LabeledCase]:
    k_values = [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 5, 5, 8, 10, 10, 15, 20, 30, 50]
    return [_build_case(k) for k in k_values]


def build_uci_dataset(sample_sizes=(200, 1000, 5000)) -> List[LabeledCase]:
    try:
        df = pd.read_csv(
            "data/adult_reference.csv", header=None,
            names=["age", "workclass", "fnlwgt", "education", "education_num",
                   "marital_status", "occupation", "relationship", "race", "sex",
                   "capital_gain", "capital_loss", "hours_per_week", "native_country", "income"],
            na_values="?",
        ).dropna()
    except FileNotFoundError:
        print("[avertissement] data/adult_reference.csv introuvable -- calibration synthétique uniquement")
        return []

    cases = []
    for size in sample_sizes:
        sample = df.sample(n=min(size, len(df)), random_state=42)
        fields = ("education", "sex")
        records = sample[list(fields)].to_dict(orient="records")
        analysis = CombinationAnalyzer.analyze(records, fields)
        cases.append(LabeledCase(records=records, fields=fields, true_k=analysis["k"],
                                  is_risky=(analysis["k"] <= K_RISKY_THRESHOLD)))
    return cases


def evaluate_threshold(cases: List[LabeledCase], threshold: float, scorer: FuzzyRiskScorer) -> dict:
    tp = fp = tn = fn = 0
    for case in cases:
        result = scorer.score(case.records, case.fields)
        predicted_risky = result.score >= threshold

        if case.is_risky and predicted_risky:
            tp += 1
        elif case.is_risky and not predicted_risky:
            fn += 1
        elif not case.is_risky and predicted_risky:
            fp += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"threshold": threshold, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1}


def print_detailed_scores(
    cases: List[LabeledCase],
    scorer: FuzzyRiskScorer,
):
    print("\n=== Scores détaillés ===")
    print(
        f"{'k':<6}"
        f"{'Unicité':<12}"
        f"{'Sensibilité':<15}"
        f"{'Score':<10}"
        f"{'Terrain (risqué)':<18}"
    )
    print("-" * 65)

    for case in cases:
        result = scorer.score(
            case.records,
            case.fields,
        )

        print(
            f"{result.k:<6}"
            f"{result.uniqueness:<12.3f}"
            f"{result.avg_sensitivity:<15.3f}"
            f"{result.score:<10.3f}"
            f"{str(case.is_risky):<18}"
        )

def run_calibration():
    synthetic = build_synthetic_dataset()
    uci = build_uci_dataset()
    all_cases = synthetic + uci

    n_risky = sum(1 for c in all_cases if c.is_risky)
    n_safe = len(all_cases) - n_risky
    print(f"Jeu de calibration : {len(all_cases)} cas ({n_risky} risqués, {n_safe} non risqués)")
    print(f"Vérité terrain : risqué si k <= {K_RISKY_THRESHOLD}\n")

    # threshold=0.0 sur le scorer lui-même : on veut le SCORE brut,
    # la décision "declenché" est recalculée pour chaque seuil candidat ci-dessous
    scorer = FuzzyRiskScorer(threshold=0.0,min_sample_size=0)   
    print(f"{'Seuil':<8}{'TP':<5}{'FP':<5}{'TN':<5}{'FN':<5}{'Précision':<12}{'Rappel':<10}{'F1':<8}")
    print("-" * 65)

    results = []
    for threshold in CANDIDATE_THRESHOLDS:
        r = evaluate_threshold(all_cases, threshold, scorer)
        results.append(r)
        print(
            f"{r['threshold']:<8}{r['tp']:<5}{r['fp']:<5}{r['tn']:<5}{r['fn']:<5}"
            f"{r['precision']:<12.3f}{r['recall']:<10.3f}{r['f1']:<8.3f}"
        )

    eligible = [r for r in results if r["recall"] >= RECALL_FLOOR]
    if eligible:
        best = max(eligible, key=lambda r: r["f1"])
        print(
            f"\nSeuil recommandé : {best['threshold']} "
            f"(rappel={best['recall']:.3f} >= {RECALL_FLOOR}, précision={best['precision']:.3f}, F1={best['f1']:.3f})"
        )
    else:
        best = max(results, key=lambda r: r["recall"])
        print(
            f"\nAucun seuil n'atteint un rappel >= {RECALL_FLOOR}. "
            f"Meilleur rappel disponible : seuil={best['threshold']} (rappel={best['recall']:.3f}) -- "
            f"les règles floues elles-mêmes pourraient devoir être ajustées."
        )

    print_detailed_scores(all_cases, scorer)


if __name__ == "__main__":
    run_calibration()
