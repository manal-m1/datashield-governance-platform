from typing import Dict, Tuple, List
from detection.frequency_counter import CombinationAnalyzer

from detection.risk_scorer import (
    RiskResult,
    SENSITIVITY_ENCODING,
)
from detection.fuzzy_config_repository import load_fuzzy_config
from detection.fuzzy_rule_repository import load_fuzzy_rules
import logging
from detection.field_sensitivity_repository import (
    DEFAULT_SENSITIVITY,
)
logger = logging.getLogger("streamshield.fuzzy_risk_scorer")
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

def fuzzify_k_risk(
    k: int,
    config: Dict,
) -> Dict[str, float]:
    """
    Fuzzification du risque associé au k-anonymat.

    Les paramètres des fonctions d'appartenance
    sont chargés depuis MongoDB.
    """

    if k <= 0:
        return {
            "faible": 0.0,
            "moyen": 0.0,
            "eleve": 0.0,
            "critique": 0.0,
        }

    x = float(k)

    fuzzy_sets = config["k_fuzzy_sets"]

    result = {}

    for level, definition in fuzzy_sets.items():

        membership_type = definition["type"]
        parameters = definition["parameters"]

        if membership_type == "trapezoidal":
            result[level] = _trapezoidal(
                x,
                *parameters,
            )

        elif membership_type == "triangular":
            result[level] = _triangular(
                x,
                *parameters,
            )

        elif membership_type == "left_shoulder":
            result[level] = _left_shoulder(
                x,
                *parameters,
            )

        elif membership_type == "right_shoulder":
            result[level] = _right_shoulder(
                x,
                *parameters,
            )

        else:
            raise ValueError(
                f"Type de fonction fuzzy inconnu : {membership_type}"
            )

    return result
# ============================================================================
# FUZZIFICATION - UNIQUENESS
# ============================================================================
def fuzzify_uniqueness(
    u: float,
    config: Dict,
) -> Dict[str, float]:
    """
    Fuzzification de l'unicité.

    Les paramètres sont chargés depuis MongoDB.
    """

    u = max(0.0, min(1.0, float(u)))

    fuzzy_sets = config["uniqueness_fuzzy_sets"]

    result = {}

    for level, definition in fuzzy_sets.items():

        membership_type = definition["type"]
        parameters = definition["parameters"]

        if membership_type == "trapezoidal":
            result[level] = _trapezoidal(
                u,
                *parameters,
            )

        elif membership_type == "triangular":
            result[level] = _triangular(
                u,
                *parameters,
            )

        elif membership_type == "left_shoulder":
            result[level] = _left_shoulder(
                u,
                *parameters,
            )

        elif membership_type == "right_shoulder":
            result[level] = _right_shoulder(
                u,
                *parameters,
            )

        else:
            raise ValueError(
                f"Type de fonction fuzzy inconnu : {membership_type}"
            )

    return result
# ============================================================================
# FUZZIFICATION - SENSITIVITY
# ============================================================================
def fuzzify_sensitivity(
    s: float,
    config: Dict,
) -> Dict[str, float]:
    """
    Fuzzification de la sensibilité.

    Les paramètres sont chargés depuis MongoDB.
    """

    s = max(0.0, min(1.0, float(s)))

    fuzzy_sets = config["sensitivity_fuzzy_sets"]

    result = {}

    for level, definition in fuzzy_sets.items():

        membership_type = definition["type"]
        parameters = definition["parameters"]

        if membership_type == "trapezoidal":
            result[level] = _trapezoidal(
                s,
                *parameters,
            )

        elif membership_type == "triangular":
            result[level] = _triangular(
                s,
                *parameters,
            )

        elif membership_type == "left_shoulder":
            result[level] = _left_shoulder(
                s,
                *parameters,
            )

        elif membership_type == "right_shoulder":
            result[level] = _right_shoulder(
                s,
                *parameters,
            )

        else:
            raise ValueError(
                f"Type de fonction fuzzy inconnu : {membership_type}"
            )

    return result
# ============================================================================
# OUTPUT LEVELS
# ============================================================================

# OUTPUT_LEVELS = {
#     "faible": 0.15,
#     "modere": 0.45,
#     "eleve": 0.70,
#     "critique": 0.92,
# }


# ============================================================================
# FUZZY INFERENCE
# ============================================================================
def _apply_rules(
    k_fuzzy: Dict[str, float],
    u_fuzzy: Dict[str, float],
    s_fuzzy: Dict[str, float],
    rules: List[Dict],
) -> Dict[str, float]:

    activations = {
        "faible": 0.0,
        "modere": 0.0,
        "eleve": 0.0,
        "critique": 0.0,
    }

    fuzzy_variables = {
        "k": k_fuzzy,
        "uniqueness": u_fuzzy,
        "sensitivity": s_fuzzy,
    }

    def activate(
        level: str,
        degree: float,
    ) -> None:

        if level not in activations:
            return

        degree = max(
            0.0,
            min(1.0, degree),
        )

        activations[level] = max(
            activations[level],
            degree,
        )

    for rule in rules:

        conditions = rule.get(
            "conditions",
            [],
        )

        output = rule.get("output")

        if not conditions or not output:
            continue

        degrees = []

        for condition in conditions:

            variable = condition["variable"]
            fuzzy_set = condition["set"]

            variable_values = fuzzy_variables.get(
                variable
            )

            if variable_values is None:
                raise ValueError(
                    f"Variable fuzzy inconnue : {variable}"
                )

            degree = variable_values.get(
                fuzzy_set,
                0.0,
            )

            degrees.append(degree)

        if not degrees:
            continue

        # AND fuzzy = minimum
        rule_activation = min(degrees)

        activate(
            output,
            rule_activation,
        )

    return activations
# ============================================================================
# DEFUZZIFICATION
# ============================================================================

def _defuzzify(
    activations: Dict[str, float],
    output_levels: Dict[str, float],
) -> float:
    """
    Défuzzification par moyenne pondérée.
    """

    total = sum(activations.values())

    if total <= 0.0:
        return 0.0

    score = sum(
        output_levels[level] * degree
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

        self.field_sensitivity = field_sensitivity or {}

        self.min_sample_size = (
            min_sample_size
            if min_sample_size is not None
            else self.MIN_SAMPLE_SIZE_FOR_RELIABLE_SCORE
        )

        # Configuration fuzzy chargée depuis MongoDB
        self.fuzzy_config = None
        self.fuzzy_rules = []

    async def load_fuzzy_configuration(self):
        """
        Charge la configuration et les règles fuzzy depuis MongoDB.
        """

        self.fuzzy_config = await load_fuzzy_config()
        self.fuzzy_rules = await load_fuzzy_rules()

        self.min_sample_size = self.fuzzy_config.get(
            "min_sample_size",
            self.MIN_SAMPLE_SIZE_FOR_RELIABLE_SCORE,
        )

        logger.info(
            "Configuration fuzzy chargée depuis MongoDB : "
            f"{len(self.fuzzy_rules)} règles"
        )    
    
    def _average_sensitivity(
        self,
        fields: Tuple[str, ...],
    ) -> float:

        if not fields:
            return 0.0

        values = []

        for field in fields:

            # ------------------------------------------------------------
            # Sensibilité récupérée depuis MongoDB
            # ------------------------------------------------------------

            sensitivity_level = self.field_sensitivity.get(field)

            # ------------------------------------------------------------
            # Champ absent
            # ------------------------------------------------------------

            if sensitivity_level is None:
                logger.warning(
                    f"Champ '{field}' absent de "
                    "streamshield_field_sensitivity. "
                    f"Valeur par défaut utilisée : "
                    f"'{DEFAULT_SENSITIVITY}'."
                )

                sensitivity_level = DEFAULT_SENSITIVITY

            # ------------------------------------------------------------
            # Niveau invalide
            # ------------------------------------------------------------

            if sensitivity_level not in SENSITIVITY_ENCODING:

                logger.warning(
                    f"Niveau de sensibilité invalide pour "
                    f"'{field}' : '{sensitivity_level}'. "
                    f"Valeur par défaut utilisée : "
                    f"'{DEFAULT_SENSITIVITY}'."
                )

                sensitivity_level = DEFAULT_SENSITIVITY

            # ------------------------------------------------------------
            # Conversion niveau -> valeur numérique
            # SENSITIVITY_ENCODING reste en Python
            # ------------------------------------------------------------

            sensitivity_value = SENSITIVITY_ENCODING[
                sensitivity_level
            ]

            values.append(sensitivity_value)

        return sum(values) / len(values)
    def score(
        self,
        records: List[dict],
        fields: Tuple[str, ...],
    ) -> RiskResult:
        logger.info(
            f"SCORER CALLED | "
            f"fields={fields} | "
            f"records={len(records)}"
        )

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

        if self.fuzzy_config is None:
            raise RuntimeError(
                "La configuration fuzzy n'est pas chargée. "
                "Appelez load_fuzzy_configuration() avant score()."
            )

        k_fuzzy = fuzzify_k_risk(
            k,
            self.fuzzy_config,
        )

        u_fuzzy = fuzzify_uniqueness(
            uniqueness,
            self.fuzzy_config,
        )

        s_fuzzy = fuzzify_sensitivity(
            avg_sensitivity,
            self.fuzzy_config,
        )

        # --------------------------------------------------------------------
        # Inference
        # --------------------------------------------------------------------

        activations = _apply_rules(
            k_fuzzy,
            u_fuzzy,
            s_fuzzy,
            self.fuzzy_rules,
        )

        # --------------------------------------------------------------------
        # Defuzzification
        # --------------------------------------------------------------------

        score = _defuzzify(
            activations,
            self.fuzzy_config["output_levels"],
        )
        logger.info(
            f"FUZZY SCORE | "
            f"fields={fields} | "
            f"k={k} | "
            f"uniqueness={uniqueness:.4f} | "
            f"avg_sensitivity={avg_sensitivity:.4f} | "
            f"activations={activations} | "
            f"score={score:.4f}"
        )

        # --------------------------------------------------------------------
        # Final result
        # --------------------------------------------------------------------
        return RiskResult(
            fields=fields,
            k=k,
            uniqueness=uniqueness,
            avg_sensitivity=avg_sensitivity,
            score=score,
            triggered=(score >= self.threshold),
            sample_size=sample_size,
)
