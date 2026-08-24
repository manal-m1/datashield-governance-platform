from typing import Dict, Tuple, List
from detection.frequency_counter import CombinationAnalyzer
from detection.risk_scorer import (
    RiskResult,
    SENSITIVITY_ENCODING,
    DEFAULT_FIELD_SENSITIVITY,
)

# ============================================================================
# Membership functions
# ============================================================================

def _triangular(
    x: float,
    a: float,
    b: float,
    c: float,
) -> float:
    """
    Fonction d'appartenance triangulaire.

    a : début
    b : sommet
    c : fin
    """

    if x <= a or x >= c:
        return 0.0

    if x == b:
        return 1.0

    if x < b:
        return (x - a) / (b - a)

    return (c - x) / (c - b)


def _trapezoidal(
    x: float,
    a: float,
    b: float,
    c: float,
    d: float,
) -> float:
    """
    Fonction d'appartenance trapézoïdale.

    Gère également les cas particuliers :
    - a == b : épaule gauche
    - c == d : épaule droite
    """

    x = float(x)

    # En dehors du support
    if x < a or x > d:
        return 0.0

    # Épaule gauche : a == b
    if a == b and x <= b:
        return 1.0

    # Épaule droite : c == d
    if c == d and x >= c:
        return 1.0

    # Plateau
    if b <= x <= c:
        return 1.0

    # Montée
    if x < b:
        return (x - a) / (b - a)

    # Descente
    if x > c:
        return (d - x) / (d - c)

    return 0.0 
def _left_shoulder(
    x: float,
    a: float,
    b: float,
) -> float:
    """
    Ensemble flou décroissant.

    Appartenance = 1 pour x <= a
    Appartenance = 0 pour x >= b
    """

    if x <= a:
        return 1.0

    if x >= b:
        return 0.0

    return (b - x) / (b - a)


def _right_shoulder(
    x: float,
    a: float,
    b: float,
) -> float:
    """
    Ensemble flou croissant.

    Appartenance = 0 pour x <= a
    Appartenance = 1 pour x >= b
    """

    if x <= a:
        return 0.0

    if x >= b:
        return 1.0

    return (x - a) / (b - a)


# ============================================================================
# FUZZIFICATION - K
# ============================================================================

def fuzzify_k_risk(k: int) -> Dict[str, float]:
    """
    Fuzzification du risque associé au k-anonymat.

    Interprétation métier :

        k = 1       -> critique
        k = 2       -> élevé
        k = 3       -> élevé / moyen
        k = 4-5     -> moyen
        k = 6       -> moyen / faible
        k >= 7      -> faible

    Le k constitue le signal principal du risque.
    """

    if k <= 0:
        return {
            "faible": 0.0,
            "moyen": 0.0,
            "eleve": 0.0,
            "critique": 0.0,
        }

    x = float(k)

    return {
        # ------------------------------------------------------------
        # CRITIQUE
        # k = 1 principalement
        # ------------------------------------------------------------
        "critique": _trapezoidal(
            x,
            0.5,
            1.0,
            1.0,
            1.8,
        ),

        # ------------------------------------------------------------
        # ÉLEVÉ
        # k = 2-3 principalement
        # ------------------------------------------------------------
        "eleve": _trapezoidal(
            x,
            1.5,
            2.0,
            2.5,
            3.5,
        ),

        # ------------------------------------------------------------
        # MOYEN
        # k = 3-6
        # ------------------------------------------------------------
        "moyen": _trapezoidal(
            x,
            2.5,
            3.5,
            5.0,
            6.5,
        ),

        # ------------------------------------------------------------
        # FAIBLE
        # k >= 6
        # ------------------------------------------------------------
        "faible": _right_shoulder(
            x,
            5.5,
            7.0,
        ),
    }


# ============================================================================
# FUZZIFICATION - UNIQUENESS
# ============================================================================

def fuzzify_uniqueness(u: float) -> Dict[str, float]:
    """
    u ∈ [0,1]

    faible  : faible unicité
    moyenne : unicité intermédiaire
    elevee  : forte unicité
    """

    u = max(0.0, min(1.0, float(u)))

    return {
        "faible": _trapezoidal(
            u,
            0.0,
            0.0,
            0.15,
            0.30,
        ),

        "moyenne": _triangular(
            u,
            0.20,
            0.50,
            0.75,
        ),

        "elevee": _trapezoidal(
            u,
            0.60,
            0.80,
            1.0,
            1.0,
        ),
    }


# ============================================================================
# FUZZIFICATION - SENSITIVITY
# ============================================================================

def fuzzify_sensitivity(s: float) -> Dict[str, float]:
    """
    s ∈ [0,1]

    faible
    moyenne
    elevee
    """

    s = max(0.0, min(1.0, float(s)))

    return {
        "faible": _trapezoidal(
            s,
            0.0,
            0.0,
            0.25,
            0.40,
        ),

        "moyenne": _triangular(
            s,
            0.30,
            0.50,
            0.70,
        ),

        "elevee": _trapezoidal(
            s,
            0.60,
            0.80,
            1.0,
            1.0,
        ),
    }


# ============================================================================
# OUTPUT LEVELS
# ============================================================================

OUTPUT_LEVELS = {
    "faible": 0.15,
    "modere": 0.45,
    "eleve": 0.70,
    "critique": 0.92,
}


# ============================================================================
# FUZZY INFERENCE
# ============================================================================
def _apply_rules(
    k_fuzzy: Dict[str, float],
    u_fuzzy: Dict[str, float],
    s_fuzzy: Dict[str, float],
) -> Dict[str, float]:

    activations = {
        "faible": 0.0,
        "modere": 0.0,
        "eleve": 0.0,
        "critique": 0.0,
    }

    def activate(level: str, degree: float) -> None:
        degree = max(0.0, min(1.0, degree))
        activations[level] = max(
            activations[level],
            degree,
        )

    # ================================================================
    # CRITIQUE
    # ================================================================

    # R1 : k critique -> critique
    activate(
        "critique",
        k_fuzzy["critique"],
    )

    # ================================================================
    # ÉLEVÉ
    # ================================================================

    # R2 : k élevé -> élevé
    activate(
        "eleve",
        k_fuzzy["eleve"],
    )

    # R3 : k moyen + unicité élevée -> élevé
    activate(
        "eleve",
        min(
            k_fuzzy["moyen"],
            u_fuzzy["elevee"],
        ),
    )

    # R4 : k moyen + sensibilité élevée -> élevé
    activate(
        "eleve",
        min(
            k_fuzzy["moyen"],
            s_fuzzy["elevee"],
        ),
    )

    # ================================================================
    # MODÉRÉ
    # ================================================================

    # R5 : k moyen -> modéré
    activate(
        "modere",
        k_fuzzy["moyen"],
    )

    # R6 : k moyen + unicité faible -> modéré
    activate(
        "modere",
        min(
            k_fuzzy["moyen"],
            u_fuzzy["faible"],
        ),
    )

    # R7 : k moyen + sensibilité faible -> modéré
    activate(
        "modere",
        min(
            k_fuzzy["moyen"],
            s_fuzzy["faible"],
        ),
    )

    # ================================================================
    # FAIBLE
    # ================================================================

    # R8 : k faible + unicité faible -> faible
    activate(
        "faible",
        min(
            k_fuzzy["faible"],
            u_fuzzy["faible"],
        ),
    )

    # R9 : k faible + sensibilité faible -> faible
    activate(
        "faible",
        min(
            k_fuzzy["faible"],
            s_fuzzy["faible"],
        ),
    )

    return activations
# def _apply_rules(
#     k_fuzzy: Dict[str, float],
#     u_fuzzy: Dict[str, float],
#     s_fuzzy: Dict[str, float],
# ) -> Dict[str, float]:
#     """
#     Moteur d'inférence fuzzy.

#     Principe :

#     1. Le k-anonymat constitue le facteur structurel principal.
#     2. L'unicité augmente le risque.
#     3. La sensibilité augmente le risque.
#     4. Une absence d'unicité/sensibilité ne doit jamais annuler
#        le risque déterminé par un k faible.
#     """

#     activations = {
#         "faible": 0.0,
#         "modere": 0.0,
#         "eleve": 0.0,
#         "critique": 0.0,
#     }

#     def activate(
#         level: str,
#         degree: float,
#     ) -> None:

#         degree = max(
#             0.0,
#             min(1.0, degree),
#         )

#         activations[level] = max(
#             activations[level],
#             degree,
#         )

#     # ========================================================================
#     # 1. CRITIQUE
#     # ========================================================================

#     # R1 : k critique -> critique
#     activate(
#         "critique",
#         k_fuzzy["critique"],
#     )

#     # R2 : k élevé + unicité élevée -> critique
#     activate(
#         "critique",
#         min(
#             k_fuzzy["eleve"],
#             u_fuzzy["elevee"],
#         ),
#     )

#     # R3 : k élevé + sensibilité élevée -> critique
#     activate(
#         "critique",
#         min(
#             k_fuzzy["eleve"],
#             s_fuzzy["elevee"],
#         ),
#     )

#     # ========================================================================
#     # 2. ÉLEVÉ
#     # ========================================================================

#     # R4 : k élevé -> élevé
#     #
#     # IMPORTANT :
#     # cette règle garantit que k=2 ne retourne jamais 0.
#     activate(
#         "eleve",
#         k_fuzzy["eleve"],
#     )

#     # R5 : k moyen + unicité élevée -> élevé
#     activate(
#         "eleve",
#         min(
#             k_fuzzy["moyen"],
#             u_fuzzy["elevee"],
#         ),
#     )

#     # R6 : k moyen + sensibilité élevée -> élevé
#     activate(
#         "eleve",
#         min(
#             k_fuzzy["moyen"],
#             s_fuzzy["elevee"],
#         ),
#     )

#     # R7 : k moyen + unicité moyenne + sensibilité moyenne
#     activate(
#         "eleve",
#         min(
#             k_fuzzy["moyen"],
#             u_fuzzy["moyenne"],
#             s_fuzzy["moyenne"],
#         ),
#     )

#     # ========================================================================
#     # 3. MODÉRÉ
#     # ========================================================================

#     # R8 : k moyen -> modéré
#     activate(
#         "modere",
#         k_fuzzy["moyen"],
#     )

#     # R9 : k moyen + unicité faible
#     activate(
#         "modere",
#         min(
#             k_fuzzy["moyen"],
#             u_fuzzy["faible"],
#         ),
#     )

#     # R10 : k moyen + sensibilité faible
#     activate(
#         "modere",
#         min(
#             k_fuzzy["moyen"],
#             s_fuzzy["faible"],
#         ),
#     )

#     # ========================================================================
#     # 4. FAIBLE
#     # ========================================================================

#     # R11 : k faible + unicité faible
#     activate(
#         "faible",
#         min(
#             k_fuzzy["faible"],
#             u_fuzzy["faible"],
#         ),
#     )

#     # R12 : k faible + sensibilité faible
#     activate(
#         "faible",
#         min(
#             k_fuzzy["faible"],
#             s_fuzzy["faible"],
#         ),
#     )

#     # R13 : k faible + unicité moyenne + sensibilité faible
#     activate(
#         "faible",
#         min(
#             k_fuzzy["faible"],
#             u_fuzzy["moyenne"],
#             s_fuzzy["faible"],
#         ),
#     )

#     return activations


# ============================================================================
# DEFUZZIFICATION
# ============================================================================

def _defuzzify(
    activations: Dict[str, float],
) -> float:
    """
    Défuzzification par moyenne pondérée.

    Retourne toujours un score dans [0,1].
    """

    total = sum(activations.values())

    if total <= 0.0:
        return 0.0

    score = sum(
        OUTPUT_LEVELS[level] * degree
        for level, degree in activations.items()
    ) / total

    return max(
        0.0,
        min(1.0, score),
    )


# ============================================================================
# FUZZY RISK SCORER
# ============================================================================

class FuzzyRiskScorer:

    MIN_SAMPLE_SIZE_FOR_RELIABLE_SCORE = 20
    def __init__(
        self,
        threshold: float = 0.5,
        field_sensitivity: Dict[str, str] = None,
        min_sample_size: int = None,
    ):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"Le seuil doit être compris entre 0 et 1. "
                f"Valeur reçue : {threshold}"
            )

        self.threshold = threshold

        self.field_sensitivity = (
            field_sensitivity
            if field_sensitivity is not None
            else DEFAULT_FIELD_SENSITIVITY.copy()
        )

        self.min_sample_size = (
            min_sample_size
            if min_sample_size is not None
            else self.MIN_SAMPLE_SIZE_FOR_RELIABLE_SCORE
        )

    def _average_sensitivity(
        self,
        fields: Tuple[str, ...],
    ) -> float:

        if not fields:
            return 0.0

        values = [
            SENSITIVITY_ENCODING.get(
                self.field_sensitivity.get(
                    field,
                    "medium",
                ),
                0.5,
            )
            for field in fields
        ]

        return sum(values) / len(values)

    def score(
        self,
        records: List[dict],
        fields: Tuple[str, ...],
    ) -> RiskResult:

        # --------------------------------------------------------------------
        # Validation
        # --------------------------------------------------------------------

        if not fields:

            return RiskResult(
                fields=fields,
                k=0,
                uniqueness=0.0,
                avg_sensitivity=0.0,
                score=0.0,
                triggered=False,
                sample_size=0,
            )

        # --------------------------------------------------------------------
        # Combination analysis
        # --------------------------------------------------------------------

        analysis = CombinationAnalyzer.analyze(
            records,
            fields,
        )

        k = analysis["k"]
        uniqueness = analysis["uniqueness"]
        sample_size = analysis["sample_size"]

        # --------------------------------------------------------------------
        # Insufficient data
        # --------------------------------------------------------------------

        if (
            k <= 0
            or sample_size < self.min_sample_size
        ):

            return RiskResult(
                fields=fields,
                k=k,
                uniqueness=0.0,
                avg_sensitivity=0.0,
                score=0.0,
                triggered=False,
                sample_size=sample_size,
            )

        # --------------------------------------------------------------------
        # Sensitivity
        # --------------------------------------------------------------------

        avg_sensitivity = self._average_sensitivity(
            fields
        )

        # --------------------------------------------------------------------
        # Fuzzification
        # --------------------------------------------------------------------

        k_fuzzy = fuzzify_k_risk(k)

        u_fuzzy = fuzzify_uniqueness(
            uniqueness
        )

        s_fuzzy = fuzzify_sensitivity(
            avg_sensitivity
        )

        # --------------------------------------------------------------------
        # Inference
        # --------------------------------------------------------------------

        activations = _apply_rules(
            k_fuzzy,
            u_fuzzy,
            s_fuzzy,
        )

        # --------------------------------------------------------------------
        # Defuzzification
        # --------------------------------------------------------------------

        score = _defuzzify(
            activations
        )

        # --------------------------------------------------------------------
        # Final result
        # --------------------------------------------------------------------
        return RiskResult(
            fields=fields, k=k, uniqueness=uniqueness,
            avg_sensitivity=avg_sensitivity, score=score,
            triggered=(score >= self.threshold),   # renommé
            sample_size=sample_size,
        )
if __name__ == "__main__":
    for k in [1, 2, 3, 4, 5, 6, 7, 8, 10, 20, 50]:
        print(f"k={k}: {fuzzify_k_risk(k)}")