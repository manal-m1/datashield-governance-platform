"""
StreamShield - Tâche 2, étape 6 (v2 - validation étendue après revue)

CHANGEMENT v2 : la version précédente ne testait que 4 combinaisons fixes,
ce qui donnait dans les faits seulement k=1 (age+sex, age+sex+native_country,
age+sex+race+native_country) et k=20 (education+sex) -- aucune couverture
intermédiaire. On ajoute ici un balayage systématique sur des tailles
d'échantillon variées pour faire apparaître des k intermédiaires (2,3,5,10),
ce qui permet de vérifier concrètement que la correction d'Unicité(C) et
le retrait de l'élagage Apriori (v2) font remonter ces cas au-dessus du
seuil de déclenchement -- pas seulement k=1.
"""
import random
import pandas as pd

from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.frequency_counter import CombinationAnalyzer

COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "education_num",
    "marital_status", "occupation", "relationship", "race", "sex",
    "capital_gain", "capital_loss", "hours_per_week", "native_country", "income",
]

DATA_PATH = "data/adult_reference.csv"

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
    return df[list(fields)].to_dict(orient="records")


def run_comparison():
    df = load_reference_dataset()
    print(f"Jeu UCI Adult chargé : {len(df)} enregistrements (après nettoyage des valeurs manquantes)\n")

    scorer = FuzzyRiskScorer(threshold=0.5)

    print("=== Combinaisons de référence (jeu complet) ===")
    print(f"{'Combinaison':<45}{'k(C)':<8}{'Unicité':<10}{'Score':<8}{'Déclenché'}")
    print("-" * 85)

    for fields in REFERENCE_COMBINATIONS:
        records = to_records(df, fields)
        result = scorer.score(records, fields)
        print(
            f"{str(fields):<45}{result.k:<8}{round(result.uniqueness, 3):<10}"
            f"{round(result.score, 3):<8}{result.triggered}"
        )

    # v2 : balayage systématique sur k intermédiaires -- on sous-échantillonne
    # la fenêtre à différentes tailles pour faire varier k(C) naturellement,
    # plutôt que de ne dépendre que des combinaisons fixes ci-dessus.
    print("\n=== Balayage k intermédiaires (sous-échantillons, combinaison age+sex+native_country) ===")
    print(f"{'Taille échantillon':<20}{'k(C)':<8}{'Unicité':<10}{'Score':<8}{'Déclenché'}")
    print("-" * 65)

    target_fields = ("age", "sex", "native_country")
    random.seed(42)  # reproductibilité

    for sample_size in [50, 150, 400, 1000, 3000, 8000, len(df)]:
        sample_df = df.sample(n=min(sample_size, len(df)), random_state=42)
        records = to_records(sample_df, target_fields)
        result = scorer.score(records, target_fields)
        print(
            f"{sample_size:<20}{result.k:<8}{round(result.uniqueness, 3):<10}"
            f"{round(result.score, 3):<8}{result.triggered}"
        )

    print(
        "\nAttendu : k(C) croît avec la taille de l'échantillon (plus de "
        "monde -> plus de chances de partager la même combinaison), donc le "
        "score doit décroître progressivement -- pas de saut brutal entre "
        "'déclenché' et 'non déclenché' au voisinage du seuil."
    )

    print("\n--- Repère de la littérature ---")
    print(
        "Sweeney (2000) : date de naissance + sexe + code postal ré-identifie ~87% de la\n"
        "population américaine (jeu de recensement 1990). Notre combinaison la plus proche\n"
        "disponible ici (age + sexe + native_country, sans code postal dans ce jeu UCI) sert\n"
        "de point de comparaison qualitatif -- pas une reproduction exacte du chiffre 87%."
    )


if __name__ == "__main__":
    run_comparison()