import os
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = "/app/validation/arx/baselines"
OUTPUT_DIR = os.path.join(BASE_DIR, "figures")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# DONNEES VALIDATION ROBUSTE
# ============================================================

methods = [
    "Fuzzy Risk Score",
    "K-anonymity",
    "LightGBM",
]

f1_mean = [0.853333, 0.471429, 0.480000]
f1_std = [0.144530, 0.108327, 0.501996]

recall = [1.0, 1.0, 0.5]
specificity = [0.8, 0.05, 0.9]

# ============================================================
# FIGURE 1 : F1
# ============================================================

plt.figure(figsize=(9, 6))

plt.bar(
    methods,
    f1_mean,
    yerr=f1_std,
    capsize=5
)

plt.ylabel("F1-score")
plt.xlabel("Méthode")
plt.title("F1-score moyen et écart-type - Validation croisée 5-fold")
plt.ylim(0, 1.15)
plt.grid(axis="y", alpha=0.3)

plt.tight_layout()

path = os.path.join(
    OUTPUT_DIR,
    "f1_validation_robuste.png"
)

plt.savefig(path, dpi=300)
plt.close()

print(f"Figure 1 sauvegardée : {path}")

# ============================================================
# FIGURE 2 : RECALL VS SPECIFICITY
# ============================================================

plt.figure(figsize=(9, 6))

x = range(len(methods))
width = 0.35

plt.bar(
    [i - width / 2 for i in x],
    recall,
    width=width,
    label="Recall"
)

plt.bar(
    [i + width / 2 for i in x],
    specificity,
    width=width,
    label="Specificity"
)

plt.xticks(list(x), methods)
plt.ylabel("Score")
plt.xlabel("Méthode")
plt.title("Recall et spécificité - Validation croisée 5-fold")
plt.ylim(0, 1.1)
plt.legend()
plt.grid(axis="y", alpha=0.3)

plt.tight_layout()

path = os.path.join(
    OUTPUT_DIR,
    "recall_specificity_validation.png"
)

plt.savefig(path, dpi=300)
plt.close()

print(f"Figure 2 sauvegardée : {path}")

# ============================================================
# FIGURE 3 : SHAP
# ============================================================

features = [
    "uniqueness",
    "num_qi",
    "avg_sensitivity",
    "k",
    "sample_size",
]

shap_values = [
    1.281367,
    0.398819,
    0.061048,
    0.0,
    0.0,
]

plt.figure(figsize=(9, 6))

plt.barh(
    features[::-1],
    shap_values[::-1]
)

plt.xlabel("Mean |SHAP value|")
plt.ylabel("Feature")
plt.title("Importance globale des variables selon SHAP - LightGBM")

plt.grid(axis="x", alpha=0.3)

plt.tight_layout()

path = os.path.join(
    OUTPUT_DIR,
    "shap_global_importance.png"
)

plt.savefig(path, dpi=300)
plt.close()

print(f"Figure 3 sauvegardée : {path}")

print()
print("=" * 60)
print("GENERATION DES FIGURES TERMINEE")
print("=" * 60)
# ============================================================
# FIGURE 4 : FUZZY SCORE VS ARX RISK
# ============================================================

FUZZY_ARX_FILE = "/app/validation/arx/fuzzy_vs_arx_results.csv"

df = pd.read_csv(FUZZY_ARX_FILE)

# Vérification
required_columns = [
    "combination",
    "arx_average_risk",
    "arx_label",
    "fuzzy_score",
]

missing = [
    col for col in required_columns
    if col not in df.columns
]

if missing:
    raise ValueError(
        f"Colonnes manquantes : {missing}"
    )

# Corrélation Pearson
correlation = df["arx_average_risk"].corr(
    df["fuzzy_score"]
)

print()
print("=" * 60)
print("ANALYSE FUZZY VS ARX")
print("=" * 60)

print(f"Nombre de combinaisons : {len(df)}")
print(f"Corrélation Pearson    : {correlation:.4f}")

# ------------------------------------------------------------
# Figure
# ------------------------------------------------------------

plt.figure(figsize=(10, 7))

risk_0 = df[df["arx_label"] == 0]
risk_1 = df[df["arx_label"] == 1]

plt.scatter(
    risk_0["arx_average_risk"],
    risk_0["fuzzy_score"],
    s=70,
    alpha=0.75,
    label="ARX non risqué (label = 0)"
)

plt.scatter(
    risk_1["arx_average_risk"],
    risk_1["fuzzy_score"],
    s=70,
    alpha=0.75,
    label="ARX risqué (label = 1)"
)

# Ajouter les noms des combinaisons
for _, row in df.iterrows():

    plt.annotate(
        row["combination"],
        (
            row["arx_average_risk"],
            row["fuzzy_score"]
        ),
        xytext=(5, 5),
        textcoords="offset points",
        fontsize=8
    )

plt.xlabel(
    "Risque moyen ARX",
    fontsize=12
)

plt.ylabel(
    "Fuzzy Risk Score",
    fontsize=12
)

plt.title(
    "Relation entre le risque ARX et le Fuzzy Risk Score",
    fontsize=14
)

plt.grid(
    True,
    alpha=0.3
)

plt.legend()

plt.text(
    0.02,
    0.95,
    f"Corrélation de Pearson = {correlation:.3f}",
    transform=plt.gca().transAxes,
    fontsize=11,
    verticalalignment="top"
)

plt.tight_layout()

path = os.path.join(
    OUTPUT_DIR,
    "fuzzy_score_vs_arx_risk.png"
)

plt.savefig(
    path,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print(
    f"Figure 4 sauvegardée : {path}"
)