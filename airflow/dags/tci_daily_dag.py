"""
airflow/dags/tci_pipeline.py

DAG Airflow unique — Pipeline TCI
Fonctionne en deux modes :
  - Planifié (cron quotidien) : utilise les valeurs par défaut (table "cv", etc.)
  - À la demande (upload) : utilise table_name/user_id/model_name passés via dag_run.conf

Séquence :
  1. health_check      : vérifie que tous les services sont UP
  2. compute_l1        : calcul L1 (data-quality) sur la table cible
  3. compute_l2        : calcul L2 (model-quality)   [parallèle]
  4. compute_l3        : calcul L3 (user-profile)    [parallèle]
  5. compute_tci       : agrège L1+L2+L3 → TCI (tci-engine)
  6. mca_evaluate      : évalue les actions critiques (mca-engine)
  7. notify            : log du résultat final
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_URLS = {
    "data_quality":  "http://data-quality:8011",
    "model_quality": "http://model-quality:8012",
    "user_profile":  "http://user-profile:8013",
    "tci_engine":    "http://tci-engine:8014",
    "mca_engine":    "http://mca-engine:8015",
}

# Valeurs par défaut (utilisées si dag_run.conf n'est pas fourni, ex: run planifié)
DEFAULT_TABLE      = "cv"
DEFAULT_MODEL_NAME = "rf_cv"
DEFAULT_USER_ID    = "system_batch"

MCA_ACTIONS = ["read_data", "model_inference", "write_decision"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _post(url: str, payload: dict, timeout: int = 30) -> dict:
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get(url: str, timeout: int = 10) -> dict:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_conf(ctx, key, default):
    """Récupère un paramètre depuis dag_run.conf, avec fallback (run planifié)."""
    conf = ctx["dag_run"].conf or {}
    return conf.get(key, default)


# ── Tasks ─────────────────────────────────────────────────────────────────────

def task_health_check(**ctx):
    """Vérifie que tous les services répondent avant de lancer le pipeline."""
    errors = []
    for name, base_url in BASE_URLS.items():
        try:
            resp = _get(f"{base_url}/health")
            print(f"[OK] {name} : {resp}")
        except Exception as e:
            errors.append(f"{name} : {e}")
    if errors:
        raise RuntimeError("Services indisponibles :\n" + "\n".join(errors))
    print("Tous les services sont UP.")


def task_compute_l1(**ctx):
    """Calcule L1 sur la table cible (uploadée ou par défaut)."""
    table_name = _get_conf(ctx, "table_name", DEFAULT_TABLE)

    result = _post(
        f"{BASE_URLS['data_quality']}/l1/compute",
        payload={"table": table_name}
    )
    print(f"L1 calculé pour {table_name} : {result['l1']:.4f}")
    ctx["ti"].xcom_push(key="l1_score", value=result["l1"])
    return result


def task_compute_l2(**ctx):
    """Calcule L2 sur le modèle cible."""
    model_name = _get_conf(ctx, "model_name", DEFAULT_MODEL_NAME)

    result = _post(
        f"{BASE_URLS['model_quality']}/l2/compute",
        payload={"model_name": model_name}
    )
    print(f"L2 calculé : {result['l2']:.4f}")
    ctx["ti"].xcom_push(key="l2_score", value=result["l2"])
    return result


def task_compute_l3(**ctx):
    """Calcule L3 pour l'utilisateur cible (celui qui a uploadé, ou batch)."""
    user_id = _get_conf(ctx, "user_id", DEFAULT_USER_ID)

    result = _post(
        f"{BASE_URLS['user_profile']}/l3/compute",
        payload={
            "user_id":         user_id,
            "expertise":       0.8,
            "nb_interactions": 120,
            "nb_correctes":    105,
            "appareil":        "serveur",
            "reseau":          "prive",
            "consentement":    "complet",
            "expire_jours":    365,
        }
    )
    print(f"L3 calculé : {result['l3']:.4f}")
    ctx["ti"].xcom_push(key="l3_score", value=result["l3"])
    return result


def task_compute_tci(**ctx):
    """Agrège L1+L2+L3 et calcule le TCI final."""
    table_name = _get_conf(ctx, "table_name", DEFAULT_TABLE)
    model_name = _get_conf(ctx, "model_name", DEFAULT_MODEL_NAME)
    user_id    = _get_conf(ctx, "user_id", DEFAULT_USER_ID)
    domain     = _get_conf(ctx, "domain", "default")

    result = _post(
        f"{BASE_URLS['tci_engine']}/tci/compute",
        payload={
            "table":      table_name,
            "model_name": model_name,
            "user_id":    user_id,
            "domain":     domain,
        }
    )
    tci = result["tci"]
    print(f"TCI calculé pour {table_name} : {tci:.4f}  →  Niveau : {result['level']}")
    ctx["ti"].xcom_push(key="tci_score", value=tci)
    ctx["ti"].xcom_push(key="tci_level", value=result["level"])
    return result


def task_mca_evaluate(**ctx):
    """Évalue les actions critiques avec le MCA."""
    ti         = ctx["ti"]
    user_id    = _get_conf(ctx, "user_id", DEFAULT_USER_ID)
    tci_score  = ti.xcom_pull(key="tci_score", task_ids="compute_tci")
    l1         = ti.xcom_pull(key="l1_score",  task_ids="compute_l1")
    l2         = ti.xcom_pull(key="l2_score",  task_ids="compute_l2")
    l3         = ti.xcom_pull(key="l3_score",  task_ids="compute_l3")

    verdicts = {}
    for action in MCA_ACTIONS:
        result = _post(
            f"{BASE_URLS['mca_engine']}/mca/evaluate",
            payload={
                "action":  action,
                "user_id": user_id,
                "tci":     tci_score,
                "l1":      l1,
                "l2":      l2,
                "l3":      l3,
            }
        )
        verdicts[action] = result["verdict"]
        print(f"MCA [{action}] → {result['verdict']} — {result['message']}")

    ctx["ti"].xcom_push(key="mca_verdicts", value=verdicts)
    return verdicts


def task_notify(**ctx):
    """Log final du pipeline."""
    ti         = ctx["ti"]
    table_name = _get_conf(ctx, "table_name", DEFAULT_TABLE)
    tci        = ti.xcom_pull(key="tci_score",  task_ids="compute_tci")
    level      = ti.xcom_pull(key="tci_level",  task_ids="compute_tci")
    verdicts   = ti.xcom_pull(key="mca_verdicts", task_ids="mca_evaluate")

    print("=" * 60)
    print(f"  Pipeline TCI terminé pour la table : {table_name}")
    print(f"  TCI Final : {tci:.4f}  |  Niveau : {level}")
    print("  Verdicts MCA :")
    for action, verdict in verdicts.items():
        print(f"    · {action:<25} → {verdict}")
    print("=" * 60)


# ── DAG definition ────────────────────────────────────────────────────────────
default_args = {
    "owner":            "datagov",
    "retries":          2,
    "retry_delay":      timedelta(minutes=1),
    "email_on_failure": False,
}

with DAG(
    dag_id="tci_pipeline",
    default_args=default_args,
    description="Pipeline TCI unique : planifié (quotidien) ou déclenché à l'upload",
    schedule_interval="0 2 * * *",     # exécution planifiée à 02h00 UTC avec valeurs par défaut
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["tci", "mca", "datagov"],
) as dag:

    health_check = PythonOperator(
        task_id="health_check",
        python_callable=task_health_check,
    )
    compute_l1 = PythonOperator(
        task_id="compute_l1",
        python_callable=task_compute_l1,
    )
    compute_l2 = PythonOperator(
        task_id="compute_l2",
        python_callable=task_compute_l2,
    )
    compute_l3 = PythonOperator(
        task_id="compute_l3",
        python_callable=task_compute_l3,
    )
    compute_tci = PythonOperator(
        task_id="compute_tci",
        python_callable=task_compute_tci,
    )
    mca_evaluate = PythonOperator(
        task_id="mca_evaluate",
        python_callable=task_mca_evaluate,
    )
    notify = PythonOperator(
        task_id="notify",
        python_callable=task_notify,
    )

    health_check >> [compute_l1, compute_l2, compute_l3]
    [compute_l1, compute_l2, compute_l3] >> compute_tci
    compute_tci >> mca_evaluate >> notify