"""
DataShield - Complete Data Processing Pipeline

Complete flow:

Upload
  -> Profile
  -> Clean
  -> PII Detection
      -> Taxonomie
      -> Presidio
  -> Classification
  -> Correction
  -> Quality
  -> StreamShield Risk Analysis
  -> Annotation Tasks
  -> Masking / Certification
  -> Store Results

Airflow is the orchestrator.
The actual full-dataset masking is delegated to Annotation Service
and EthiMask.
"""

from datetime import datetime, timedelta
import os
import requests
import yaml

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule


# ====================================================================
# CONFIGURATION
# ====================================================================

def load_config():

    config_path = os.path.join(
        os.path.dirname(__file__),
        "../config/pipeline_config.yaml"
    )

    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    except Exception as e:

        print(
            f"Could not load pipeline config. "
            f"Using defaults: {e}"
        )

        return {
            "configuration": {}
        }


PIPELINE_CONFIG = load_config()


def is_feature_enabled(feature_name: str) -> bool:

    return PIPELINE_CONFIG.get(
        "configuration",
        {}
    ).get(
        feature_name,
        True
    )


# ====================================================================
# MICROSERVICE URLS
# ====================================================================

SERVICE_URLS = {

    "cleaning":
        "http://cleaning-service:8004",

    "taxonomie":
        "http://taxonomie-service:8002",

    "presidio":
        "http://presidio-service:8003",

    "classification":
        "http://classification-service:8005",

    "correction":
        "http://correction-service:8006",

    "annotation":
        "http://annotation-service:8007",

    "quality":
        "http://quality-service:8008",

    "ethimask":
        "http://ethimask-service:8009",

    "streamshield":
        "http://streamshield-serv:8010",
}


# ====================================================================
# DEFAULT ARGS
# ====================================================================

default_args = {

    "owner": "data_governance_team",

    "depends_on_past": False,

    "email": [
        "admin@example.com"
    ],

    "email_on_failure": True,

    "email_on_retry": False,

    "retries": 3,

    "retry_delay": timedelta(
        minutes=5
    ),
}


# ====================================================================
# COMMON HELPERS
# ====================================================================

def get_dataset_id(**context):

    dataset_id = context["ti"].xcom_pull(
        key="dataset_id"
    )

    if not dataset_id:

        raise ValueError(
            "dataset_id not found in XCom"
        )

    return dataset_id


# ====================================================================
# 1. SERVICE HEALTH
# ====================================================================

def check_service_health(
    service_name: str,
    **context
):

    url = SERVICE_URLS.get(
        service_name
    )

    if not url:

        raise ValueError(
            f"Unknown service: {service_name}"
        )

    try:

        response = requests.get(
            f"{url}/health",
            timeout=10
        )

        response.raise_for_status()

        print(
            f"Service {service_name} is healthy"
        )

        return True

    except Exception as e:

        raise Exception(
            f"Cannot reach {service_name}: {e}"
        )


# ====================================================================
# 2. UPLOAD / REUSE DATASET
# ====================================================================

def upload_dataset(
    file_path: str,
    **context
):

    dag_run = context.get(
        "dag_run"
    )

    # ------------------------------------------------------------
    # Reuse existing dataset
    # ------------------------------------------------------------

    if (
        dag_run
        and dag_run.conf
        and dag_run.conf.get("dataset_id")
    ):

        dataset_id = dag_run.conf[
            "dataset_id"
        ]

        print(
            f"Reusing existing dataset: "
            f"{dataset_id}"
        )

        context["ti"].xcom_push(
            key="dataset_id",
            value=dataset_id
        )

        return dataset_id

    # ------------------------------------------------------------
    # Upload new dataset
    # ------------------------------------------------------------

    url = (
        f"{SERVICE_URLS['cleaning']}"
        "/upload"
    )

    with open(
        file_path,
        "rb"
    ) as f:

        files = {

            "file": (
                os.path.basename(file_path),
                f
            )
        }

        response = requests.post(
            url,
            files=files,
            timeout=600
        )

    response.raise_for_status()

    result = response.json()

    dataset_id = result[
        "dataset_id"
    ]

    print(
        f"Dataset uploaded: "
        f"{dataset_id}"
    )

    context["ti"].xcom_push(
        key="dataset_id",
        value=dataset_id
    )

    return dataset_id


# ====================================================================
# 3. PROFILE
# ====================================================================

def profile_data(**context):

    dataset_id = get_dataset_id(
        **context
    )

    url = (
        f"{SERVICE_URLS['cleaning']}"
        f"/profile/{dataset_id}"
    )

    response = requests.get(
        url,
        timeout=600
    )

    response.raise_for_status()

    try:

        result = response.json()

        print(
            "Profile completed:"
        )

        print(result)

        return result

    except Exception:

        print(
            "Profile generated as HTML"
        )

        return {
            "status": "completed"
        }


# ====================================================================
# 4. CLEAN
# ====================================================================

def clean_data(**context):

    if not is_feature_enabled(
        "enable_cleaning"
    ):

        print(
            "Cleaning disabled"
        )

        return {
            "status": "skipped"
        }

    dataset_id = get_dataset_id(
        **context
    )

    url = (
        f"{SERVICE_URLS['cleaning']}"
        f"/clean/{dataset_id}"
    )

    response = requests.post(
        url,
        json={

            "remove_duplicates":
                is_feature_enabled(
                    "remove_duplicates"
                ),

            "handle_missing":
                "mean",

            "remove_outliers":
                True
        },
        timeout=900
    )

    response.raise_for_status()

    result = response.json()

    print(
        "Cleaning completed"
    )

    print(result)

    return result


# ====================================================================
# 5. TAXONOMIE PII
# ====================================================================

def detect_pii_taxonomie(**context):

    dataset_id = get_dataset_id(
        **context
    )

    preview_url = (
        f"{SERVICE_URLS['cleaning']}"
        f"/datasets/{dataset_id}/preview"
        "?rows=100"
    )

    response = requests.get(
        preview_url,
        timeout=300
    )

    response.raise_for_status()

    rows = response.json().get(
        "preview",
        []
    )

    detections = []

    for row in rows:

        text = " ".join(
            f"{key}: {value}"
            for key, value in row.items()
            if value is not None
            and str(value).strip()
        )

        if not text:
            continue

        response = requests.post(

            f"{SERVICE_URLS['taxonomie']}"
            "/analyze",

            json={
                "text": text
            },

            timeout=60
        )

        if response.status_code == 200:

            result = response.json()

            detections.extend(
                result.get(
                    "detections",
                    []
                )
            )

    print(
        f"Taxonomie detected "
        f"{len(detections)} entities"
    )

    context["ti"].xcom_push(
        key="taxonomie_detections",
        value=detections
    )

    return detections


# ====================================================================
# 6. PRESIDIO PII
# ====================================================================

def detect_pii_presidio(**context):

    dataset_id = get_dataset_id(
        **context
    )

    preview_url = (
        f"{SERVICE_URLS['cleaning']}"
        f"/datasets/{dataset_id}/preview"
        "?rows=100"
    )

    response = requests.get(
        preview_url,
        timeout=300
    )

    response.raise_for_status()

    rows = response.json().get(
        "preview",
        []
    )

    detections = []

    for row in rows:

        text = " ".join(
            f"{key}: {value}"
            for key, value in row.items()
            if value is not None
            and str(value).strip()
        )

        if not text:
            continue

        response = requests.post(

            f"{SERVICE_URLS['presidio']}"
            "/analyze",

            json={
                "text": text
            },

            timeout=60
        )

        if response.status_code == 200:

            result = response.json()

            detections.extend(
                result.get(
                    "detections",
                    []
                )
            )

    print(
        f"Presidio detected "
        f"{len(detections)} entities"
    )

    context["ti"].xcom_push(
        key="presidio_detections",
        value=detections
    )

    return detections


# ====================================================================
# 7. CLASSIFICATION
# ====================================================================

def classify_sensitivity(**context):

    dataset_id = get_dataset_id(
        **context
    )

    preview_url = (
        f"{SERVICE_URLS['cleaning']}"
        f"/datasets/{dataset_id}/preview"
        "?rows=100"
    )

    response = requests.get(
        preview_url,
        timeout=300
    )

    response.raise_for_status()

    rows = response.json().get(
        "preview",
        []
    )

    if not rows:

        print(
            "No rows available"
        )

        return {}

    columns = {}

    for row in rows:

        for key, value in row.items():

            columns.setdefault(
                key,
                []
            ).append(value)

    response = requests.post(

        f"{SERVICE_URLS['classification']}"
        "/classify",

        json={

            "dataset_id":
                dataset_id,

            "data_sample":
                columns
        },

        timeout=600
    )

    response.raise_for_status()

    result = response.json()

    classifications = result.get(
        "classifications",
        {}
    )

    pii_count = sum(

        1

        for value
        in classifications.values()

        if value.get(
            "level",
            0
        ) >= 3
    )

    print(
        f"Classified "
        f"{len(classifications)} columns"
    )

    print(
        f"Sensitive columns: "
        f"{pii_count}"
    )

    context["ti"].xcom_push(
        key="classifications",
        value=result
    )

    return result


# ====================================================================
# 8. CORRECTION - DETECT
# ====================================================================

def detect_inconsistencies(**context):

    dataset_id = get_dataset_id(
        **context
    )

    preview_url = (
        f"{SERVICE_URLS['cleaning']}"
        f"/datasets/{dataset_id}/preview"
        "?rows=100"
    )

    response = requests.get(
        preview_url,
        timeout=300
    )

    response.raise_for_status()

    rows = response.json().get(
        "preview",
        []
    )

    total = 0
    inconsistencies = []

    for row in rows:

        response = requests.post(

            f"{SERVICE_URLS['correction']}"
            "/detect",

            json={
                "row": {
                    key:
                        str(value)
                        if value is not None
                        else ""
                    for key, value
                    in row.items()
                }
            },

            timeout=60
        )

        if response.status_code == 200:

            result = response.json()

            total += result.get(
                "count",
                0
            )

            inconsistencies.extend(
                result.get(
                    "inconsistencies",
                    []
                )
            )

    print(
        f"Found {total} inconsistencies"
    )

    context["ti"].xcom_push(
        key="inconsistencies",
        value=inconsistencies
    )

    return {
        "total_inconsistencies":
            total,

        "rows_checked":
            len(rows)
    }


# ====================================================================
# 9. CORRECTION - APPLY
# ====================================================================

def apply_corrections(**context):

    dataset_id = get_dataset_id(
        **context
    )

    preview_url = (
        f"{SERVICE_URLS['cleaning']}"
        f"/datasets/{dataset_id}/preview"
        "?rows=100"
    )

    response = requests.get(
        preview_url,
        timeout=300
    )

    response.raise_for_status()

    rows = response.json().get(
        "preview",
        []
    )

    corrections = 0

    for row in rows:

        response = requests.post(

            f"{SERVICE_URLS['correction']}"
            "/correct",

            json={
                "row": {
                    key:
                        str(value)
                        if value is not None
                        else ""
                    for key, value
                    in row.items()
                }
            },

            timeout=60
        )

        if response.status_code == 200:

            result = response.json()

            corrections += len(
                result.get(
                    "corrections",
                    []
                )
            )

    print(
        f"Applied {corrections} corrections"
    )

    return {
        "corrections_applied":
            corrections,

        "rows_processed":
            len(rows)
    }


# ====================================================================
# 10. QUALITY
# ====================================================================

def evaluate_quality(**context):

    dataset_id = get_dataset_id(
        **context
    )

    preview_url = (
        f"{SERVICE_URLS['cleaning']}"
        f"/datasets/{dataset_id}/preview"
        "?rows=1000"
    )

    response = requests.get(
        preview_url,
        timeout=300
    )

    response.raise_for_status()

    rows = response.json().get(
        "preview",
        []
    )

    requests.post(

        f"{SERVICE_URLS['quality']}"
        f"/datasets/{dataset_id}/register",

        json={
            "records": rows
        },

        timeout=300
    )

    response = requests.post(

        f"{SERVICE_URLS['quality']}"
        f"/evaluate/{dataset_id}",

        timeout=600
    )

    response.raise_for_status()

    result = response.json()

    print(
        f"Quality score: "
        f"{result.get('global_score')}%"
    )

    print(
        f"Quality grade: "
        f"{result.get('grade')}"
    )

    context["ti"].xcom_push(
        key="quality_report",
        value=result
    )

    return result


# ====================================================================
# 11. STREAMSHIELD
# ====================================================================

def analyze_streamshield_risk(**context):

    dataset_id = get_dataset_id(
        **context
    )

    response = requests.post(

        f"{SERVICE_URLS['streamshield']}"
        f"/analyze/{dataset_id}",

        timeout=900
    )

    response.raise_for_status()

    result = response.json()

    print(
        "StreamShield analysis completed"
    )

    print(
        f"Risk combinations: "
        f"{result.get('combinations_at_risk', 0)}"
    )

    context["ti"].xcom_push(
        key="streamshield_result",
        value=result
    )

    return result


# ====================================================================
# 12. CREATE ANNOTATION TASKS
# ====================================================================

def create_annotation_tasks(**context):

    dataset_id = get_dataset_id(
        **context
    )

    taxonomie = (
        context["ti"].xcom_pull(
            key="taxonomie_detections"
        )
        or []
    )

    presidio = (
        context["ti"].xcom_pull(
            key="presidio_detections"
        )
        or []
    )

    all_detections = (
        taxonomie + presidio
    )

    print(
        f"Creating annotation tasks "
        f"from {len(all_detections)} detections"
    )

    # ------------------------------------------------------------
    # We create tasks from the detected information.
    # The Annotation Service remains responsible for the
    # complete dataset masking after Steward approval.
    # ------------------------------------------------------------

    response = requests.post(

        f"{SERVICE_URLS['annotation']}"
        "/tasks",

        json={

            "dataset_id":
                dataset_id,

            "annotation_type":
                "pii_validation",

            "priority":
                "medium",

            "detections":
                all_detections[:500]
        },

        timeout=600
    )

    if response.status_code not in [200, 201]:

        raise Exception(
            f"Annotation task creation failed: "
            f"{response.text}"
        )

    result = response.json()

    print(
        f"Created "
        f"{result.get('created', 0)} "
        f"annotation tasks"
    )

    context["ti"].xcom_push(
        key="annotation_result",
        value=result
    )

    return result


# ====================================================================
# 13. MASK / CERTIFY
# ====================================================================

def certify_dataset(**context):

    dataset_id = get_dataset_id(
        **context
    )

    print(
        "=" * 70
    )

    print(
        f"Starting final certification "
        f"for dataset {dataset_id}"
    )

    print(
        "=" * 70
    )

    # ------------------------------------------------------------
    # IMPORTANT
    #
    # Do NOT mask only 10 preview rows here.
    #
    # Annotation Service must:
    #
    # 1. Retrieve the COMPLETE dataset
    # 2. Discover sensitive columns
    # 3. Build rules
    # 4. Process ALL rows
    # 5. Call EthiMask /mask/batch
    # 6. Write the certified CSV
    # ------------------------------------------------------------

    # If your annotation API exposes a dedicated certification
    # endpoint, call it here.
    #
    # This endpoint name must match your actual annotation main.py.

    response = requests.post(

        f"{SERVICE_URLS['annotation']}"
        f"/pipeline/certify/{dataset_id}",

        json={
            "apply_masking": True
        },

        timeout=1800
    )

    response.raise_for_status()

    result = response.json()

    print(
        "Dataset certification completed"
    )

    print(
        f"Result: {result}"
    )

    context["ti"].xcom_push(
        key="certification_result",
        value=result
    )

    return result


# ====================================================================
# 14. STORE RESULTS
# ====================================================================

def store_results(**context):

    dataset_id = get_dataset_id(
        **context
    )

    quality = (
        context["ti"].xcom_pull(
            key="quality_report"
        )
        or {}
    )

    certification = (
        context["ti"].xcom_pull(
            key="certification_result"
        )
        or {}
    )

    print(
        "=" * 70
    )

    print(
        f"Pipeline completed for "
        f"{dataset_id}"
    )

    print(
        f"Quality: "
        f"{quality.get('global_score', 'N/A')}%"
    )

    print(
        f"Certified export: "
        f"{certification.get('filename', 'N/A')}"
    )

    print(
        "=" * 70
    )

    return {
        "dataset_id":
            dataset_id,

        "status":
            "completed",

        "quality_grade":
            quality.get("grade"),

        "certification":
            certification
    }


# ====================================================================
# DAG
# ====================================================================

dag = DAG(

    "data_processing_pipeline",

    default_args=default_args,

    description=(
        "Complete DataShield data governance "
        "and masking pipeline"
    ),

    schedule_interval=None,

    start_date=datetime(
        2024,
        1,
        1
    ),

    catchup=False,

    max_active_runs=1,

    tags=[
        "datashield",
        "data-governance",
        "pii",
        "quality",
        "streamshield",
        "ethimask"
    ]
)


# ====================================================================
# TASKS
# ====================================================================

start = EmptyOperator(
    task_id="start",
    dag=dag
)


# Health checks

check_cleaning = PythonOperator(
    task_id="check_cleaning_health",
    python_callable=check_service_health,
    op_kwargs={
        "service_name": "cleaning"
    },
    dag=dag
)

check_taxonomie = PythonOperator(
    task_id="check_taxonomie_health",
    python_callable=check_service_health,
    op_kwargs={
        "service_name": "taxonomie"
    },
    dag=dag
)

check_presidio = PythonOperator(
    task_id="check_presidio_health",
    python_callable=check_service_health,
    op_kwargs={
        "service_name": "presidio"
    },
    dag=dag
)


# Upload

upload = PythonOperator(
    task_id="upload_dataset",
    python_callable=upload_dataset,
    op_kwargs={
        "file_path":
            "/opt/airflow/datasets/test_data/MASTER_DATAGOV_TEST.csv"
    },
    dag=dag
)


# Profile

profile = PythonOperator(
    task_id="profile_data",
    python_callable=profile_data,
    dag=dag
)


# Clean

clean = PythonOperator(
    task_id="clean_data",
    python_callable=clean_data,
    dag=dag
)


# PII detection

detect_taxonomie = PythonOperator(
    task_id="detect_pii_taxonomie",
    python_callable=detect_pii_taxonomie,
    dag=dag
)

detect_presidio = PythonOperator(
    task_id="detect_pii_presidio",
    python_callable=detect_pii_presidio,
    dag=dag
)


# Classification

classify = PythonOperator(
    task_id="classify_sensitivity",
    python_callable=classify_sensitivity,
    dag=dag
)


# Correction

detect_issues = PythonOperator(
    task_id="detect_inconsistencies",
    python_callable=detect_inconsistencies,
    dag=dag
)

correct = PythonOperator(
    task_id="apply_corrections",
    python_callable=apply_corrections,
    dag=dag
)


# Quality

quality = PythonOperator(
    task_id="evaluate_quality",
    python_callable=evaluate_quality,
    dag=dag
)


# StreamShield

streamshield = PythonOperator(
    task_id="analyze_streamshield_risk",
    python_callable=analyze_streamshield_risk,
    dag=dag
)


# Annotation

annotate = PythonOperator(
    task_id="create_annotation_tasks",
    python_callable=create_annotation_tasks,
    dag=dag
)


# Final masking / certification

certify = PythonOperator(
    task_id="certify_and_mask_dataset",
    python_callable=certify_dataset,
    dag=dag
)


# Store

store = PythonOperator(
    task_id="store_results",
    python_callable=store_results,
    trigger_rule=TriggerRule.ALL_SUCCESS,
    dag=dag
)


# End

end = EmptyOperator(
    task_id="end",
    dag=dag
)


# ====================================================================
# DEPENDENCIES
# ====================================================================

# ------------------------------------------------------------
# START -> HEALTH CHECKS
# ------------------------------------------------------------

start >> [
    check_cleaning,
    check_taxonomie,
    check_presidio
]


# ------------------------------------------------------------
# HEALTH CHECKS -> UPLOAD
# ------------------------------------------------------------

[
    check_cleaning,
    check_taxonomie,
    check_presidio
] >> upload


# ------------------------------------------------------------
# UPLOAD -> PROFILE -> CLEAN
# ------------------------------------------------------------

upload >> profile >> clean


# ------------------------------------------------------------
# CLEAN -> PII DETECTION
# ------------------------------------------------------------

clean >> [
    detect_taxonomie,
    detect_presidio
]


# ------------------------------------------------------------
# PII -> CLASSIFICATION
# ------------------------------------------------------------

[
    detect_taxonomie,
    detect_presidio
] >> classify


# ------------------------------------------------------------
# CLASSIFICATION -> CORRECTION
# ------------------------------------------------------------

classify >> detect_issues >> correct


# ------------------------------------------------------------
# CORRECTION -> QUALITY
# ------------------------------------------------------------

correct >> quality


# ------------------------------------------------------------
# QUALITY -> STREAMSHIELD
# ------------------------------------------------------------

quality >> streamshield


# ------------------------------------------------------------
# STREAMSHIELD -> ANNOTATION
# ------------------------------------------------------------

streamshield >> annotate


# ------------------------------------------------------------
# ANNOTATION -> MASKING/CERTIFICATION
# ------------------------------------------------------------

annotate >> certify


# ------------------------------------------------------------
# CERTIFICATION -> STORE -> END
# ------------------------------------------------------------

certify >> store >> end