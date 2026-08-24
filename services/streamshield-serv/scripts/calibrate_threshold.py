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
# """
# StreamShield - Calibration du seuil et comparaison des scorers (v2)

# v2 : ajoute la comparaison entre RiskScorer (formule linéaire pondérée)
# et FuzzyRiskScorer (logique floue) sur le MÊME jeu de test étiqueté, pour
# choisir objectivement lequel offre le meilleur rappel/précision avant
# de décider lequel utiliser en production.

# Méthodologie (inchangée) :
#   1. Jeu de combinaisons ÉTIQUETÉES indépendamment du score (vérité
#      terrain = k(C) réel <= K_RISKY_THRESHOLD).
#   2. Pour chaque scorer, mesurer précision/rappel/F1 à plusieurs seuils.
#   3. Recommander le meilleur (scorer, seuil) : priorité au rappel
#      (un cas manqué est pire qu'une fausse alerte).

# Usage:
#     python -m scripts.calibrate_threshold
# """
# import random
# from dataclasses import dataclass
# from typing import List, Tuple, Callable

# import pandas as pd

# from detection.fuzzy_risk_scorer import FuzzyRiskScorer, RiskWeights
# from detection.fuzzy_risk_scorer import FuzzyRiskScorer
# from detection.frequency_counter import CombinationAnalyzer

# K_RISKY_THRESHOLD = 5
# CANDIDATE_THRESHOLDS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
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
#     v2 : le bruit doit lui-même contenir des répétitions réalistes (pas
#     uniquement des combinaisons uniques), sinon Unicité(C) reste
#     artificiellement haute peu importe k_target -- biais découvert lors
#     de la calibration (TN=0 sur tous les seuils, alors que k=50 devrait
#     clairement être reconnu comme non risqué).
#     """
#     records = []
#     target = {
#         "ville": "Casablanca", "code_postal": "20500",
#         "sexe": "F", "date_naissance": "1985-07-22",
#     }
#     records.extend([dict(target) for _ in range(k_target)])

#     # v2 : pool restreint de combinaisons de bruit (5 villes x 4 codes
#     # postaux x 2 sexes x 6 dates = 240 combinaisons possibles), pour que
#     # le bruit se répète naturellement sur 300 enregistrements -- comme
#     # dans un vrai flux où beaucoup de gens partagent des caractéristiques
#     # communes.
#     noise_villes = ["Rabat", "Fes", "Marrakech", "Tanger", "Agadir"]
#     noise_codes = ["10000", "30000", "40000", "90000"]
#     noise_sexes = ["M", "F"]
#     noise_dates = ["1970-03-12", "1975-06-01", "1980-09-23", "1988-11-05", "1995-02-17", "2000-07-30"]

#     for i in range(total - k_target):
#         records.append({
#             "ville": noise_villes[i % len(noise_villes)],
#             "code_postal": noise_codes[i % len(noise_codes)],
#             "sexe": noise_sexes[i % len(noise_sexes)],
#             "date_naissance": noise_dates[i % len(noise_dates)],
#         })
#     return LabeledCase(records=records, fields=FIELDS, true_k=k_target,
#                         is_risky=(k_target <= K_RISKY_THRESHOLD))

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
#     random.seed(42)
#     for size in sample_sizes:
#         sample = df.sample(n=min(size, len(df)), random_state=42)
#         fields = ("education", "sex")
#         records = sample[list(fields)].to_dict(orient="records")
#         analysis = CombinationAnalyzer.analyze(records, fields)
#         cases.append(LabeledCase(records=records, fields=fields, true_k=analysis["k"],
#                                   is_risky=(analysis["k"] <= K_RISKY_THRESHOLD)))
#     return cases


# def evaluate_threshold(cases: List[LabeledCase], threshold: float, score_fn: Callable) -> dict:
#     """
#     score_fn(case) -> RiskResult -- abstraction pour tester indifféremment
#     RiskScorer ou FuzzyRiskScorer avec la même boucle d'évaluation.
#     """
#     tp = fp = tn = fn = 0
#     for case in cases:
#         result = score_fn(case)
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


# def _print_results(name: str, results: list):
#     print(f"\n=== {name} ===")
#     print(f"{'Seuil':<8}{'TP':<5}{'FP':<5}{'TN':<5}{'FN':<5}{'Précision':<12}{'Rappel':<10}{'F1':<8}")
#     print("-" * 65)
#     for r in results:
#         print(
#             f"{r['threshold']:<8}{r['tp']:<5}{r['fp']:<5}{r['tn']:<5}{r['fn']:<5}"
#             f"{r['precision']:<12.3f}{r['recall']:<10.3f}{r['f1']:<8.3f}"
#         )


# def _recommend(name: str, results: list) -> dict:
#     eligible = [r for r in results if r["recall"] >= RECALL_FLOOR]
#     if eligible:
#         best = max(eligible, key=lambda r: r["threshold"])
#         print(
#             f"[{name}] Recommandation : seuil={best['threshold']} "
#             f"(rappel={best['recall']:.3f} >= {RECALL_FLOOR}, précision={best['precision']:.3f}, F1={best['f1']:.3f})"
#         )
#     else:
#         best = max(results, key=lambda r: r["recall"])
#         print(
#             f"[{name}] Aucun seuil n'atteint un rappel >= {RECALL_FLOOR}. "
#             f"Meilleur rappel : seuil={best['threshold']} (rappel={best['recall']:.3f})"
#         )
#     return best


# def run_calibration():
#     synthetic = build_synthetic_dataset()
#     uci = build_uci_dataset()
#     all_cases = synthetic + uci

#     n_risky = sum(1 for c in all_cases if c.is_risky)
#     n_safe = len(all_cases) - n_risky
#     print(f"Jeu de calibration : {len(all_cases)} cas ({n_risky} risqués, {n_safe} non risqués)")
#     print(f"Vérité terrain : risqué si k <= {K_RISKY_THRESHOLD}")

#     # --- RiskScorer (formule linéaire actuelle) ---
#     linear_weights = RiskWeights()  # w1=0.5, w2=0.3, w3=0.2
#     linear_scorer = FuzzyRiskScorerweights=linear_weights, threshold=0.0, min_sample_size=0)
#     # threshold=0.0 ici : on veut le SCORE brut, la décision triggered est
#     # recalculée nous-mêmes dans evaluate_threshold() pour chaque seuil candidat
#     linear_results = [
#         evaluate_threshold(all_cases, t, lambda case: linear_scorer.score(case.records, case.fields))
#         for t in CANDIDATE_THRESHOLDS
#     ]
#     _print_results("RiskScorer (linéaire pondéré)", linear_results)
#     best_linear = _recommend("RiskScorer", linear_results)

#     # --- FuzzyRiskScorer (logique floue) ---
#     fuzzy_scorer = FuzzyRiskScorer(trigger_threshold=0.0, min_sample_size=0)
#     fuzzy_results = [
#         evaluate_threshold(all_cases, t, lambda case: fuzzy_scorer.score(case.records, case.fields))
#         for t in CANDIDATE_THRESHOLDS
#     ]
#     _print_results("FuzzyRiskScorer (logique floue)", fuzzy_results)
#     best_fuzzy = _recommend("FuzzyRiskScorer", fuzzy_results)
#     print_fuzzy_scores(all_cases)
#     # --- Verdict final ---
#     print("\n=== Verdict ===")
#     if best_fuzzy["f1"] > best_linear["f1"]:
#         print(
#             f"FuzzyRiskScorer l'emporte sur F1 ({best_fuzzy['f1']:.3f} vs {best_linear['f1']:.3f}) "
#             f"-- recommandé pour production, seuil={best_fuzzy['threshold']}"
#         )
#     elif best_linear["f1"] > best_fuzzy["f1"]:
#         print(
#             f"RiskScorer (linéaire) l'emporte sur F1 ({best_linear['f1']:.3f} vs {best_fuzzy['f1']:.3f}) "
#             f"-- recommandé pour production, seuil={best_linear['threshold']}"
#         )
#     else:
#         print(
#             f"Égalité sur F1 ({best_linear['f1']:.3f}) -- RiskScorer recommandé par défaut "
#             f"pour sa simplicité d'interprétation, sauf si la lisibilité des règles "
#             f"floues est jugée prioritaire pour la soutenance/documentation"
#         )
    


# def print_fuzzy_scores(cases):
#     scorer = FuzzyRiskScorer(
#         trigger_threshold=0.5,
#         min_sample_size=0
#     )

#     print("\n=== Scores Fuzzy détaillés ===")
#     print(
#         f"{'k':<6}"
#         f"{'Unicité':<12}"
#         f"{'Sensibilité':<15}"
#         f"{'Score':<10}"
#         f"{'Terrain':<10}"
#     )

#     print("-" * 65)

#     for case in cases:
#         result = scorer.score(
#             case.records,
#             case.fields
#         )

#         print(
#             f"{case.true_k:<6}"
#             f"{result.uniqueness:<12.3f}"
#             f"{result.avg_sensitivity:<15.3f}"
#             f"{result.score:<10.3f}"
#             f"{str(case.is_risky):<10}"
#         )
# if __name__ == "__main__":
#     run_calibration()
    