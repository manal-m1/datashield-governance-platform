"""
StreamShield - Tâche 2, étape 2
Compteur de fréquence des combinaisons de champs.

Pour une combinaison C (ex: ("ville", "sexe", "date_naissance")), calcule sur
les enregistrements d'une fenêtre :
  - k(C) : la taille de la plus petite classe d'équivalence -- le nombre
    minimal d'enregistrements qui partagent exactement les mêmes valeurs
    pour ces champs. C'est le dénominateur de Risque(C) = 1/k(C) (section 4.3).
  - Unicité(C) : la proportion de valeurs de cette combinaison qui
    n'apparaissent qu'une seule fois dans la fenêtre (plus c'est élevé,
    plus la combinaison est discriminante donc risquée).

Comptage EXACT (pas d'approximation ici) -- c'est volontairement fait sur les
seules combinaisons candidates retenues après élagage (étape 4, Apriori),
jamais sur toutes les combinaisons possibles à chaque fenêtre, ce qui garde
le coût de calcul raisonnable sans sacrifier la précision du résultat final.
"""
from collections import Counter
from typing import Any, Dict, List, Tuple


class CombinationAnalyzer:

    @staticmethod
    def _value_tuples(records: List[Dict[str, Any]], fields: Tuple[str, ...]) -> List[Tuple[Any, ...]]:
        """
        Extrait, pour chaque enregistrement, le tuple de valeurs de la combinaison C.
        Un enregistrement auquel il manque un des champs est ignoré (donnée
        incomplète -- ne doit pas fausser le calcul de risque sur les autres).
        """
        return [
            tuple(r[f] for f in fields)
            for r in records
            if all(f in r and r[f] is not None for f in fields)
        ]

    @classmethod
    def compute_k(cls, records: List[Dict[str, Any]], fields: Tuple[str, ...]) -> int:
        """
        k(C) = taille de la plus petite classe d'équivalence observée.
        Retourne 0 si aucun enregistrement complet n'est disponible pour C
        (pas de risque calculable -- à distinguer de k(C)=1, qui est le pire cas réel).
        """
        values = cls._value_tuples(records, fields)
        if not values:
            return 0
        counts = Counter(values)
        return min(counts.values())

    @classmethod
    def compute_uniqueness(cls, records: List[Dict[str, Any]], fields: Tuple[str, ...]) -> float:
        """
        Unicité(C) = proportion de GROUPES (classes d'équivalence) qui sont
        des singletons, PARMI LES GROUPES -- pas parmi les enregistrements.

        v2 (corrigée) : l'ancienne version (unique_records / len(values))
        se diluait avec la taille de la fenêtre -- 8 groupes uniques sur
        45222 enregistrements donnait ~0.0002, arrondi à 0.0, même quand
        k(C)=1 (risque maximal). La nouvelle version rapporte le nombre de
        classes d'équivalence uniques au nombre TOTAL de classes
        d'équivalence observées -- une mesure qui reste significative
        indépendamment de la taille de la fenêtre.
        """
        values = cls._value_tuples(records, fields)
        if not values:
            return 0.0
        counts = Counter(values)
        unique_groups = sum(1 for c in counts.values() if c == 1)
        total_groups = len(counts)
        return unique_groups / total_groups if total_groups else 0.0

    @classmethod
    def analyze(cls, records: List[Dict[str, Any]], fields: Tuple[str, ...]) -> Dict[str, Any]:
        values = cls._value_tuples(records, fields)
        if not values:
            return {"fields": fields, "k": 0, "uniqueness": 0.0, "sample_size": 0}
        counts = Counter(values)
        k = min(counts.values())
        unique_groups = sum(1 for c in counts.values() if c == 1)
        total_groups = len(counts)
        return {
            "fields": fields,
            "k": k,
            "uniqueness": unique_groups / total_groups if total_groups else 0.0,
            "sample_size": len(values),
        }