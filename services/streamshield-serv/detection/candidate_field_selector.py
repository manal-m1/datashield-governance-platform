"""
Sélection générique des champs candidats pour StreamShield.

Objectif :
- fonctionner avec différents datasets ;
- accepter des noms de champs français ou anglais ;
- éviter les identifiants directs ;
- ne sélectionner que les champs réellement présents ;
- limiter le nombre de champs envoyés au CombinationDetector.
"""

import re
from typing import Iterable, Sequence


# ============================================================================
# ALIAS DE CHAMPS POTENTIELLEMENT QI
# ============================================================================

QI_FIELD_ALIASES = {
    # ------------------------------------------------------------------------
    # Localisation
    # ------------------------------------------------------------------------
    "ville",
    "city",
    "town",
    "municipality",
    "region",
    "state",
    "province",
    "country",
    "pays",
    "native_country",
    "code_postal",
    "postal_code",
    "postcode",
    "zip_code",
    "zipcode",

    # ------------------------------------------------------------------------
    # Démographie
    # ------------------------------------------------------------------------
    "age",
    "age_group",
    "age_category",
    "sexe",
    "sex",
    "genre",
    "gender",
    "race",
    "ethnicity",
    "nationality",
    "civil_status",
    "marital_status",
    "situation_matrimoniale",

    # ------------------------------------------------------------------------
    # Éducation
    # ------------------------------------------------------------------------
    "education",
    "education_level",
    "education_num",
    "niveau_education",
    "niveau_etude",
    "diplome",
    "degree",
    "formation",
    "universite",
    "university",
    "school",

    # ------------------------------------------------------------------------
    # Profession / emploi
    # ------------------------------------------------------------------------
    "profession",
    "occupation",
    "job",
    "job_title",
    "workclass",
    "industry",
    "secteur",
    "department",
    "departement",

    # ------------------------------------------------------------------------
    # Expérience / ancienneté
    # ------------------------------------------------------------------------
    "experience",
    "experience_years",
    "experience_annees",
    "years_experience",
    "total_working_years",
    "years_at_company",
    "years_in_current_role",
    "years_since_last_promotion",
    "years_with_curr_manager",

    # ------------------------------------------------------------------------
    # Dates pouvant être des QI
    # ------------------------------------------------------------------------
    "date_naissance",
    "birth_date",
    "date_of_birth",
    "birth_year",
    "annee_naissance",
    "date_embauche",
    "hire_date",
    "date_maj",
}


# ============================================================================
# IDENTIFIANTS DIRECTS À EXCLURE
# ============================================================================

DIRECT_IDENTIFIER_NAMES = {
    "id",
    "uuid",
    "guid",
    "email",
    "email_address",
    "mail",
    "telephone",
    "phone",
    "phone_number",
    "mobile",
    "mobile_number",
    "nom",
    "name",
    "first_name",
    "firstname",
    "last_name",
    "lastname",
    "prenom",
    "adresse",
    "address",
    "street",
    "iban",
    "cin",
    "passport",
    "passport_number",
    "national_id",
    "nationalid",
}


def normalize_field_name(field: str) -> str:
    """
    Normalise un nom de colonne pour faciliter les comparaisons.

    Exemple :
        "Date of Birth" -> "date_of_birth"
        "Date-de-naissance" -> "date_de_naissance"
        "Years At Company" -> "years_at_company"
    """

    value = str(field).strip().lower()

    value = re.sub(r"[^a-z0-9]+", "_", value)

    value = re.sub(r"_+", "_", value)

    return value.strip("_")


def is_direct_identifier(field: str) -> bool:
    """
    Détermine si un champ est probablement un identifiant direct.
    """

    normalized = normalize_field_name(field)

    if normalized in DIRECT_IDENTIFIER_NAMES:
        return True

    # Quelques variantes évidentes
    direct_patterns = (
        "email",
        "phone",
        "telephone",
        "passport",
        "national_id",
        "nationalid",
        "iban",
    )

    return any(
        pattern in normalized
        for pattern in direct_patterns
    )


def is_candidate_qi(field: str) -> bool:
    """
    Détermine si un champ peut être considéré comme QI
    à partir de son nom normalisé.
    """

    normalized = normalize_field_name(field)

    if is_direct_identifier(normalized):
        return False

    if normalized in QI_FIELD_ALIASES:
        return True

    return False


def select_candidate_fields(
    records: Sequence[dict],
    max_candidates: int = 12,
) -> tuple[str, ...]:
    """
    Sélectionne automatiquement les champs QI présents dans le dataset.

    - aucun champ n'est ajouté artificiellement ;
    - les identifiants directs sont exclus ;
    - les noms français/anglais sont supportés ;
    - un plafond évite l'explosion combinatoire.
    """

    if not records:
        return ()

    available_fields = list(records[0].keys())

    candidates = []

    for field in available_fields:

        if is_direct_identifier(field):
            continue

        if is_candidate_qi(field):
            candidates.append(field)

    # Protection contre l'explosion combinatoire.
    candidates = candidates[:max_candidates]

    return tuple(candidates)