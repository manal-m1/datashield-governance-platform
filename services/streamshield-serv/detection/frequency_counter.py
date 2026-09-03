"""
StreamShield - Tâche 2
Analyseur de fréquence des combinaisons de champs.

Pour une combinaison C (ex: ("ville", "sexe", "date_naissance")),
l'analyse calcule sur les enregistrements disponibles dans la fenêtre :

  - k(C) :
      taille de la plus petite classe d'équivalence.
      Il correspond au nombre minimal d'enregistrements partageant
      exactement les mêmes valeurs pour les champs de C.

  - Unicité(C) :
      proportion de classes d'équivalence qui sont des singletons.
      Une valeur élevée indique que la combinaison est fortement
      discriminante et peut augmenter le risque de ré-identification.

  - sample_size :
      nombre d'enregistrements complets utilisés pour l'analyse.

Le comptage est exact : aucune approximation probabiliste n'est utilisée.

Les combinaisons sont fournies par CombinationDetector, qui génère les
combinaisons candidates jusqu'à la profondeur maximale configurée.
"""


from collections import Counter
from typing import Any, Dict, List, Tuple


class CombinationAnalyzer:

    @staticmethod
    def _value_tuples(
        records: List[Dict[str, Any]],
        fields: Tuple[str, ...],
    ) -> List[Tuple[Any, ...]]:
        """
        Extrait le tuple de valeurs correspondant à une combinaison.

        Les enregistrements incomplets sont ignorés afin de ne pas
        fausser l'analyse de la combinaison.
        """
        return [
            tuple(record[field] for field in fields)
            for record in records
            if all(
                field in record and record[field] is not None
                for field in fields
            )
        ]

    @classmethod
    def compute_k(
        cls,
        records: List[Dict[str, Any]],
        fields: Tuple[str, ...],
    ) -> int:
        """
        Calcule k(C), c'est-à-dire la taille de la plus petite
        classe d'équivalence.

        Retourne 0 si aucun enregistrement complet n'est disponible.
        """
        values = cls._value_tuples(records, fields)

        if not values:
            return 0

        counts = Counter(values)

        return min(counts.values())

    @classmethod
    def compute_uniqueness(
        cls,
        records: List[Dict[str, Any]],
        fields: Tuple[str, ...],
    ) -> float:
        """
        Calcule l'unicité de la combinaison.

        Unicité(C) =
            nombre de classes singleton /
            nombre total de classes d'équivalence.

        Cette définition permet d'éviter que l'unicité soit artificiellement
        diminuée lorsque la taille de la fenêtre augmente.
        """
        values = cls._value_tuples(records, fields)

        if not values:
            return 0.0

        counts = Counter(values)

        unique_groups = sum(
            1 for count in counts.values()
            if count == 1
        )

        total_groups = len(counts)

        return (
            unique_groups / total_groups
            if total_groups
            else 0.0
        )

    @classmethod
    def analyze(
        cls,
        records: List[Dict[str, Any]],
        fields: Tuple[str, ...],
    ) -> Dict[str, Any]:
        """
        Calcule l'ensemble des métriques de fréquence pour une combinaison.
        """
        values = cls._value_tuples(records, fields)

        if not values:
            return {
                "fields": fields,
                "k": 0,
                "uniqueness": 0.0,
                "sample_size": 0,
            }

        counts = Counter(values)

        k = min(counts.values())

        unique_groups = sum(
            1 for count in counts.values()
            if count == 1
        )

        total_groups = len(counts)

        uniqueness = (
            unique_groups / total_groups
            if total_groups
            else 0.0
        )

        return {
            "fields": fields,
            "k": k,
            "uniqueness": uniqueness,
            "sample_size": len(values),
        }
