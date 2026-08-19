"""
StreamShield - Tâche 2, étape 6 (suite)
Comparaison au jeu de référence académique UCI Adult / Census Income
(section 4.5 : "jeu de référence académique... pour comparer les résultats
de StreamShield à des benchmarks publiés et crédibiliser la méthode").

Source : Becker, B. & Kohavi, R. (1996). Adult [Dataset]. UCI Machine
Learning Repository. https://doi.org/10.24432/C5XW20

Ce jeu contient l'exemple canonique de la littérature sur le k-anonymat :
age + sexe + native-country est un quasi-identifiant bien documenté.
On vérifie que notre détecteur retrouve un ordre de grandeur cohérent avec
ce qui est publié dans la littérature (ex. Sweeney 2000, El Emam et al.),
sans prétendre reproduire un chiffre exact -- les jeux de données diffèrent.

Usage :
    python -m scripts.validate_against_reference
"""
import pandas as pd

from detection.risk_scorer import RiskScorer
from detection.frequency_counter import CombinationAnalyzer

COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "education_num",
    "marital_status", "occupation", "relationship", "race", "sex",
    "capital_gain", "capital_loss", "hours_per_week", "native_country", "income",
]

DATA_PATH = "data/adult_reference.csv"

# Combinaisons classiques de la littérature sur le k-anonymat, testées sur
# ce jeu -- age+sexe+pays_origine est l'exemple canonique de quasi-identifiant.
REFERENCE_COMBINATIONS = [
    ("age", "sex"),
    ("age", "sex", "native_country"),
    ("age", "sex", "race", "native_country"),
    ("education", "sex"),
]


def load_reference_dataset() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, header=None, names=COLUMNS, na_values="?")
    return df.dropna()


def to_records(df: pd.DataFrame, fields) -> list:
    """Convertit les colonnes utiles en liste de dicts, format attendu par le scorer."""
    return df[list(fields)].to_dict(orient="records")


def run_comparison():
    df = load_reference_dataset()
    print(f"Jeu UCI Adult chargé : {len(df)} enregistrements (après nettoyage des valeurs manquantes)\n")

    scorer = RiskScorer(threshold=0.5)

    print(f"{'Combinaison':<45}{'k(C)':<8}{'Unicité':<10}{'Score':<8}{'Déclenché'}")
    print("-" * 85)

    for fields in REFERENCE_COMBINATIONS:
        records = to_records(df, fields)
        result = scorer.score(records, fields)
        print(
            f"{str(fields):<45}{result.k:<8}{round(result.uniqueness, 3):<10}"
            f"{round(result.score, 3):<8}{result.triggered}"
        )

    print("\n--- Repère de la littérature ---")
    print(
        "Sweeney (2000) : date de naissance + sexe + code postal ré-identifie ~87% de la\n"
        "population américaine (jeu de recensement 1990). Notre combinaison la plus proche\n"
        "disponible ici (age + sexe + native_country, sans code postal dans ce jeu UCI) sert\n"
        "de point de comparaison qualitatif : on s'attend à un k(C) bas et un score élevé,\n"
        "cohérent avec le phénomène documenté -- pas une reproduction exacte du chiffre 87%,\n"
        "qui vient d'un jeu de données et de champs différents."
    )


if __name__ == "__main__":
    run_comparison()