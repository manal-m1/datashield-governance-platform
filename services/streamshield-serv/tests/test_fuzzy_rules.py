# import pytest

# from detection.fuzzy_risk_scorer import FuzzyRiskScorer


# def build_window(k: int):
#     """
#     Construit une fenêtre contenant exactement k personnes
#     dans la même classe d'équivalence.
#     """

#     records = []

#     for _ in range(k):
#         records.append({
#             "ville": "Rabat",
#             "sexe": "M",
#             "date_naissance": "1990-01-01",
#         })

#     # Classe suffisamment grande pour ne pas modifier le k minimal.
#     for _ in range(50):
#         records.append({
#             "ville": "Casablanca",
#             "sexe": "F",
#             "date_naissance": "1970-01-01",
#         })

#     return records


# @pytest.mark.parametrize(
#     "k",
#     [1, 2, 3, 4, 5, 6, 10, 20]
# )
# def test_k_intermediate(k):
#     scorer = FuzzyRiskScorer(
#         trigger_threshold=0.5,
#         min_sample_size=20,
#     )

#     records = build_window(k)

#     result = scorer.score(
#         records,
#         ("ville", "sexe", "date_naissance"),
#     )

#     print(
#         f"k={result.k}, "
#         f"uniqueness={result.uniqueness:.3f}, "
#         f"sensitivity={result.avg_sensitivity:.3f}, "
#         f"score={result.score:.3f}, "
#         f"triggered={result.triggered}"
#     )

#     assert result.k == k
#     assert 0.0 <= result.score <= 1.0