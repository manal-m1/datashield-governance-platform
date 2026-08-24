"""
StreamShield - Tâche 2, étape 6
Validation avec jeu de données à vérité terrain connue (section 4.5).

Principe : on construit des fenêtres où k(C) est FIXÉ à l'avance par
construction (pas mesuré après coup), puis on compare la décision du
détecteur (qui utilise Score(C) et un seuil) à un critère de référence
INDÉPENDANT de la littérature du k-anonymat : une combinaison avec k < 5
est considérée réellement risquée (seuil couramment recommandé, ex. HIPAA
Safe Harbor). Ça évite toute circularité -- on ne redemande pas au système
s'il a raison, on le compare à une règle externe reconnue.

KPI visé (section 4.6) : taux de faux positifs < 10%.

Usage :
    python -m scripts.validate_detection
"""
import random
import string
from dataclasses import dataclass
from typing import List

from detection.fuzzy_risk_scorer import FuzzyRiskScorer

FIELDS = ("ville", "sexe", "date_naissance")
GROUND_TRUTH_K_THRESHOLD = 5  # k < 5 => réellement risqué (référence indépendante, pas la formule du système)

# Éventail de k(C) à tester, du cas le plus risqué au moins risqué
TEST_K_VALUES = [1, 1, 2, 2, 3, 4, 5, 6, 8, 10, 15, 20, 30, 50]


def _random_suffix(n=6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def build_window_with_known_k(target_k: int, background_class_size: int = 60, num_background_classes: int = 5) -> List[dict]:
    """
    Construit une fenêtre où la plus petite classe d'équivalence pour FIELDS
    a EXACTEMENT target_k enregistrements -- fixé par construction, pas mesuré.

    Le "bruit" environnant est composé de quelques classes de fond FIXES,
    chacune nettement plus grande que le plus grand target_k testé -- pour
    ne jamais accidentellement créer une classe plus petite que target_k
    (piège initial : un bruit à trop forte cardinalité crée plein de
    groupes de taille 1 qui écrasent le k(C) qu'on cherche à contrôler).
    """
    records = []

    # Le groupe cible : target_k enregistrements identiques sur FIELDS
    target_values = {"ville": "Rabat", "sexe": "M", "date_naissance": "1990-01-01"}
    for _ in range(target_k):
        records.append(dict(target_values))

    # Bruit : quelques classes de fond, chacune plus grande que le plus
    # grand target_k testé (donc jamais la plus petite classe de la fenêtre).
    background_villes = ["Casablanca", "Fes", "Marrakech", "Tanger", "Agadir"]
    for i in range(num_background_classes):
        bg_values = {
            "ville": background_villes[i % len(background_villes)],
            "sexe": "F" if i % 2 == 0 else "M",
            "date_naissance": f"19{60+i}-0{(i%9)+1}-15",
        }
        for _ in range(background_class_size):
            records.append(dict(bg_values))

    return records


@dataclass
class ValidationRow:
    target_k: int
    measured_k: int
    expected_risky: bool
    detected_triggered: bool
    score: float

    @property
    def correct(self) -> bool:
        return self.expected_risky == self.detected_triggered

    @property
    def construction_valid(self) -> bool:
        """Vérifie que le k(C) réellement mesuré correspond bien à target_k --
        sinon la fenêtre construite ne teste pas ce qu'on croit tester."""
        return self.measured_k == self.target_k


def run_validation(threshold: float = 0.5) -> List[ValidationRow]:
    scorer = FuzzyRiskScorer(threshold=threshold)
    rows = []

    for k in TEST_K_VALUES:
        window = build_window_with_known_k(k)
        result = scorer.score(window, FIELDS)
        expected_risky = k < GROUND_TRUTH_K_THRESHOLD
        rows.append(ValidationRow(
            target_k=k,
            measured_k=result.k,
            expected_risky=expected_risky,
            detected_triggered=result.triggered,
            score=result.score,
        ))
    return rows


def summarize(rows: List[ValidationRow]) -> dict:
    tp = sum(1 for r in rows if r.expected_risky and r.detected_triggered)
    fp = sum(1 for r in rows if not r.expected_risky and r.detected_triggered)
    fn = sum(1 for r in rows if r.expected_risky and not r.detected_triggered)
    tn = sum(1 for r in rows if not r.expected_risky and not r.detected_triggered)

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    fp_rate = fp / (fp + tn) if (fp + tn) else float("nan")

    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "fp_rate": fp_rate}


def print_report(rows: List[ValidationRow], stats: dict):
    print(f"\n{'k(C) cible':<12}{'k(C) mesuré':<14}{'Attendu risqué':<18}{'Détecté risqué':<18}{'Score':<10}{'Résultat'}")
    print("-" * 85)
    for r in rows:
        status = "✅ correct" if r.correct else "❌ ERREUR"
        if not r.construction_valid:
            status += "  ⚠️ construction invalide (k mesuré ≠ k cible)"
        print(f"{r.target_k:<12}{r.measured_k:<14}{str(r.expected_risky):<18}{str(r.detected_triggered):<18}{round(r.score,3):<10}{status}")

    print("\n--- Matrice de confusion ---")
    print(f"Vrais positifs (VP)  : {stats['tp']}")
    print(f"Faux positifs (FP)   : {stats['fp']}")
    print(f"Faux négatifs (FN)   : {stats['fn']}")
    print(f"Vrais négatifs (VN)  : {stats['tn']}")
    print(f"\nPrécision : {stats['precision']:.1%}")
    print(f"Rappel    : {stats['recall']:.1%}")
    print(f"Taux de faux positifs : {stats['fp_rate']:.1%}  (cible KPI section 4.6 : < 10%)")

    kpi_ok = stats["fp_rate"] < 0.10
    print(f"\n{'✅ KPI respecté' if kpi_ok else '❌ KPI NON respecté'} (taux de faux positifs < 10%)")


if __name__ == "__main__":
    rows = run_validation()
    stats = summarize(rows)
    print_report(rows, stats)