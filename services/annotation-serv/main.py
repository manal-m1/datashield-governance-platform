import uuid
import random
import os
import csv
import re
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum

import requests
import uvicorn
import numpy as np

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.database.mongodb import db


# ====================================================================
# CONFIGURATION
# ====================================================================

ANNOTATION_SERVICE_PORT = 8007

CLEANING_SERVICE_URL = os.getenv(
    "CLEANING_SERVICE_URL",
    "http://cleaning-service:8004"
).rstrip("/")

ETHIMASK_SERVICE_URL = os.getenv(
    "ETHIMASK_SERVICE_URL",
    "http://ethimask-service:8009"
).rstrip("/")
PRESIDIO_SERVICE_URL = os.getenv(
    "PRESIDIO_SERVICE_URL",
    "http://presidio-service:8003"
).rstrip("/")
PRESIDIO_TIMEOUT = int(
    os.getenv("PRESIDIO_TIMEOUT", "30")
)

# Nombre maximum de valeurs identiques analysées une seule fois
PRESIDIO_CACHE_ENABLED = True
# Shared volume with Airflow / Cleaning exports.
# docker-compose: ./airflow/datasets:/opt/airflow/datasets
DATASET_DIR = "/opt/airflow/datasets"

# Permanent certified/masked CSV files.
EXPORT_DIR = os.path.join(DATASET_DIR, "certified")

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)


# ====================================================================
# CONSTANTS
# ====================================================================

MAX_SAMPLE_FIELDS = 30
MAX_VALUE_LENGTH = 500
MAX_DETECTIONS_PER_TASK = 50

CLEANING_TIMEOUT = int(os.getenv("CLEANING_TIMEOUT", "120"))
ETHIMASK_TIMEOUT = int(os.getenv("ETHIMASK_TIMEOUT", "120"))

# Nombre de lignes envoyées à EthiMask par appel /mask/batch
MASK_BATCH_SIZE = int(os.getenv("MASK_BATCH_SIZE", "100"))

# Config d'export : force_masking=True => le masquage ne dépend PAS du rôle
EXPORT_MASK_CONFIG = {
    "role": "steward",
    "context": "data_governance",
    "purpose": "privacy_protection",
    "force_masking": True
}


# ====================================================================
# ENUMS
# ====================================================================

class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEW = "review"
    REJECTED = "rejected"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnnotationType(str, Enum):
    PII_VALIDATION = "pii_validation"
    CLASSIFICATION = "classification"
    CORRECTION = "correction"
    LABELING = "labeling"


# ====================================================================
# MODELS
# ====================================================================

class FileReference(BaseModel):
    file_id: Optional[str] = None
    filename: Optional[str] = None
    storage_key: Optional[str] = None
    content_type: Optional[str] = "text/csv"
    size_bytes: Optional[int] = None
    size_kb: Optional[float] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    created_at: Optional[str] = None
    path: Optional[str] = None
    generation: Optional[str] = None


class Annotation(BaseModel):
    field: str
    original_value: Optional[Any] = None
    annotated_value: Optional[Any] = None
    label: Optional[str] = None
    is_valid: Optional[bool] = None
    confidence: float = 1.0
    notes: Optional[str] = None
    corrected_data: Optional[Dict[str, Any]] = None
    sensitivity_level: Optional[str] = None
    context: Optional[str] = None
    corrected_entity_type: Optional[str] = None


class AnnotationTask(BaseModel):
    id: str
    dataset_id: str
    row_index: int
    data_sample: Dict[str, Any] = Field(default_factory=dict)
    detections: List[Dict[str, Any]] = Field(default_factory=list)
    annotation_type: AnnotationType
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    annotations: List[Annotation] = Field(default_factory=list)
    created_at: str
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    time_spent_seconds: Optional[int] = None
    required_skill: Optional[str] = None

    # NO complete masked data here: MongoDB stores only file metadata.
    masked_file: Optional[FileReference] = None
    masking_requested: bool = False
    masking_applied: int = 0
    masking_techniques: Dict[str, str] = Field(default_factory=dict)
    masking_audit: List[Dict[str, Any]] = Field(default_factory=list)


class CreateTaskRequest(BaseModel):
    dataset_id: str
    row_indices: List[int] = Field(default_factory=list)
    annotation_type: AnnotationType = AnnotationType.PII_VALIDATION
    priority: TaskPriority = TaskPriority.MEDIUM
    detections: List[Dict[str, Any]] = Field(default_factory=list)
    data_samples: Optional[List[Dict[str, Any]]] = None
    required_skill: Optional[str] = None


class AssignmentConfig(BaseModel):
    strategy: str = "round_robin"
    max_tasks_per_user: int = 20
    users: List[str] = Field(default_factory=list)


class SubmitAnnotationRequest(BaseModel):
    annotations: List[Annotation]
    time_spent_seconds: Optional[int] = None


class ApprovalRequest(BaseModel):
    apply_masking: bool = True


# ====================================================================
# SAFE / COMPACT DATA
# ====================================================================

def compact_value(value: Any, max_length: int = MAX_VALUE_LENGTH) -> Any:

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, str):
            return value[:max_length]
        return value

    if isinstance(value, dict):
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_SAMPLE_FIELDS:
                break
            result[str(key)] = compact_value(item, max_length)
        return result

    if isinstance(value, list):
        return [
            compact_value(item, max_length)
            for item in value[:MAX_DETECTIONS_PER_TASK]
        ]

    return str(value)[:max_length]


def compact_sample(sample: Any) -> Dict[str, Any]:

    if not isinstance(sample, dict):
        return {}

    result = {}

    for index, (key, value) in enumerate(sample.items()):
        if index >= MAX_SAMPLE_FIELDS:
            break
        result[str(key)] = compact_value(value)

    return result


def compact_detections(detections: Any) -> List[Dict[str, Any]]:

    if not isinstance(detections, list):
        return []

    result = []

    allowed_fields = [
        "field",
        "value",
        "entity_type",
        "original_entity_type",
        "sensitivity_level",
        "context",
        "confidence",
        "start",
        "end",
        "row_index",
        "row",
        "index"
    ]

    for detection in detections[:MAX_DETECTIONS_PER_TASK]:

        if not isinstance(detection, dict):
            continue

        compact_detection = {}

        for field in allowed_fields:

            if field not in detection:
                continue

            value = detection[field]

            if isinstance(value, str):
                value = value[:MAX_VALUE_LENGTH]
            elif isinstance(value, (dict, list)):
                value = compact_value(value)

            compact_detection[field] = value

        result.append(compact_detection)

    return result


def select_task_detections(
    detections: List[Dict],
    row_index: int,
    position: int
) -> List[Dict]:

    if not detections:
        return []

    # Nested detections
    if len(detections) > position and isinstance(detections[position], list):
        return compact_detections(detections[position])

    # Detections containing row_index
    row_specific = []

    for detection in detections:

        if not isinstance(detection, dict):
            continue

        detection_row = detection.get(
            "row_index",
            detection.get("row", detection.get("index"))
        )

        if detection_row is None:
            continue

        try:
            if int(detection_row) == int(row_index):
                row_specific.append(detection)
        except (TypeError, ValueError):
            continue

    if row_specific:
        return compact_detections(row_specific)

    return compact_detections(detections)


# ====================================================================
# TASK QUEUE
# ====================================================================

class TaskQueue:

    async def create_task(
        self,
        dataset_id: str,
        row_index: int,
        data_sample: Dict,
        annotation_type: AnnotationType,
        priority: TaskPriority,
        detections: List[Dict] = None,
        required_skill: str = None
    ) -> AnnotationTask:

        task = AnnotationTask(
            id=str(uuid.uuid4()),
            dataset_id=dataset_id,
            row_index=row_index,
            data_sample=compact_sample(data_sample),
            detections=compact_detections(detections or []),
            annotation_type=annotation_type,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            required_skill=required_skill
        )

        if db is not None:
            await db["tasks"].insert_one(task.dict())

        return task

    async def get_pending_tasks(self) -> List[AnnotationTask]:

        if db is None:
            return []

        cursor = db["tasks"].find({"status": TaskStatus.PENDING.value})

        tasks = [AnnotationTask(**doc) async for doc in cursor]

        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        return sorted(
            tasks,
            key=lambda task: (
                priority_order.get(task.priority.value, 3),
                task.created_at
            )
        )

    async def get_user_tasks(
        self,
        user_id: str,
        status: TaskStatus = None
    ) -> List[AnnotationTask]:

        if db is None:
            return []

        query = {"assigned_to": user_id}

        if status:
            query["status"] = status.value

        cursor = db["tasks"].find(query)

        return [AnnotationTask(**doc) async for doc in cursor]

    async def get_task(self, task_id: str) -> Optional[AnnotationTask]:

        if db is None:
            return None

        document = await db["tasks"].find_one({"id": task_id})

        if not document:
            return None

        return AnnotationTask(**document)

    async def update_task(
        self,
        task_id: str,
        **updates
    ) -> Optional[AnnotationTask]:

        if db is None:
            return None

        clean_updates = {}

        for key, value in updates.items():

            if isinstance(value, Enum):
                clean_updates[key] = value.value

            elif (
                isinstance(value, list)
                and value
                and isinstance(value[0], BaseModel)
            ):
                clean_updates[key] = [item.dict() for item in value]

            elif isinstance(value, BaseModel):
                clean_updates[key] = value.dict()

            else:
                clean_updates[key] = value

        await db["tasks"].update_one(
            {"id": task_id},
            {"$set": clean_updates}
        )

        return await self.get_task(task_id)


# ====================================================================
# ASSIGNMENT MANAGER
# ====================================================================

class AssignmentManager:

    def __init__(self, queue: TaskQueue):
        self.queue = queue
        self.last_assigned_index = 0

    async def get_user_load(self, user_id: str) -> int:

        tasks = await self.queue.get_user_tasks(user_id)

        return len([
            task for task in tasks
            if task.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
        ])

    async def assign_round_robin(
        self,
        users: List[str]
    ) -> List[Tuple[str, str]]:

        if not users:
            return []

        pending = await self.queue.get_pending_tasks()

        assignments = []

        for i, task in enumerate(pending):

            user = users[(self.last_assigned_index + i) % len(users)]

            await self.queue.update_task(
                task.id,
                assigned_to=user,
                status=TaskStatus.ASSIGNED,
                assigned_at=datetime.now().isoformat()
            )

            assignments.append((task.id, user))

        if pending:
            self.last_assigned_index = (
                self.last_assigned_index + len(pending)
            ) % len(users)

        return assignments

    async def assign_smart(
        self,
        users_data: List[Dict],
        max_tasks: int = 20
    ) -> List[Tuple[str, str]]:

        pending = await self.queue.get_pending_tasks()

        assignments = []

        for task in pending:

            candidates = []

            required_skill = task.required_skill

            for user in users_data:

                username = user.get("username")

                if not username:
                    continue

                workload = await self.get_user_load(username)

                if workload >= max_tasks:
                    continue

                load_score = 0.4 * (1 - workload / max_tasks)

                skill_match = (
                    0.3
                    if required_skill and required_skill in user.get("skills", [])
                    else 0
                )

                accuracy = user.get("performance_history", {}).get("accuracy", 0.5)

                performance_score = 0.3 * accuracy

                total_score = load_score + skill_match + performance_score

                candidates.append((username, total_score))

            if candidates:

                best_user, _ = max(candidates, key=lambda item: item[1])

                await self.queue.update_task(
                    task.id,
                    assigned_to=best_user,
                    status=TaskStatus.ASSIGNED,
                    assigned_at=datetime.now().isoformat()
                )

                assignments.append((task.id, best_user))

        return assignments


# ====================================================================
# FASTAPI
# ====================================================================

app = FastAPI(
    title="DataShield Annotation Service",
    version="5.1.0"
)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"]
)

task_queue = TaskQueue()

assignment_manager = AssignmentManager(task_queue)


# ====================================================================
# HEALTH
# ====================================================================

@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "service": "annotation-service",
        "port": ANNOTATION_SERVICE_PORT,
        "cleaning_service": CLEANING_SERVICE_URL,
        "ethimask_service": ETHIMASK_SERVICE_URL
    }


# ====================================================================
# TASK CREATION
# ====================================================================

@app.post("/tasks")
async def create_tasks(request: CreateTaskRequest):

    created_tasks = []

    row_indices = request.row_indices or [0]

    for position, row_index in enumerate(row_indices):

        if request.data_samples and position < len(request.data_samples):
            data_sample = request.data_samples[position]
        else:
            data_sample = {"sample": row_index}

        task_detections = select_task_detections(
            request.detections,
            row_index,
            position
        )

        task = await task_queue.create_task(
            dataset_id=request.dataset_id,
            row_index=row_index,
            data_sample=data_sample,
            annotation_type=request.annotation_type,
            priority=request.priority,
            detections=task_detections,
            required_skill=request.required_skill
        )

        created_tasks.append(task.id)

    return {
        "created": len(created_tasks),
        "task_ids": created_tasks
    }


# ====================================================================
# TASK LIST
# ====================================================================

@app.get("/tasks")
async def list_tasks(status: str = None, user_id: str = None):

    if db is None:
        return {"tasks": []}

    query = {}

    if status:
        query["status"] = status

    if user_id:
        query["assigned_to"] = user_id

    cursor = db["tasks"].find(query)

    tasks = []

    async for document in cursor:
        tasks.append(AnnotationTask(**document).dict())

    return {"tasks": tasks}


# ====================================================================
# ASSIGNMENT
# ====================================================================

@app.post("/assign")
async def assign_tasks(config: AssignmentConfig):

    if config.strategy == "smart":

        users_data = [
            {
                "username": user,
                "skills": ["Finance", "PII"] if user == "admin" else ["PII"],
                "performance_history": {
                    "accuracy": 0.95 if user == "admin" else 0.70
                }
            }
            for user in config.users
        ]

        assignments = await assignment_manager.assign_smart(
            users_data,
            config.max_tasks_per_user
        )

    else:

        assignments = await assignment_manager.assign_round_robin(
            config.users
        )

    return {
        "assignments": [
            {"task_id": task_id, "user_id": user_id}
            for task_id, user_id in assignments
        ]
    }


# ====================================================================
# USER QUEUE
# ====================================================================

@app.get("/tasks/my-queue")
async def get_my_queue(user_id: str, role: str = None):

    tasks = await task_queue.get_user_tasks(user_id)

    queue = [
        task for task in tasks
        if task.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
    ]

    is_steward = bool(role) and "steward" in role.lower()

    if is_steward and db is not None:

        cursor = db["tasks"].find({"status": TaskStatus.REVIEW.value})

        review_tasks = [AnnotationTask(**document) async for document in cursor]

        existing_ids = {task.id for task in queue}

        for task in review_tasks:
            if task.id not in existing_ids:
                queue.append(task)

    elif not is_steward:

        pending_tasks = await task_queue.get_pending_tasks()

        existing_ids = {task.id for task in queue}

        for task in pending_tasks:
            if task.id not in existing_ids:
                queue.append(task)

    return {
        "user_id": user_id,
        "queue": [task.dict() for task in queue],
        "count": len(queue)
    }


# ====================================================================
# MANUAL ASSIGN
# ====================================================================

@app.post("/assign/{task_id}")
async def assign_manual(task_id: str, user_id: str):

    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_queue.update_task(
        task_id,
        assigned_to=user_id,
        status=TaskStatus.ASSIGNED,
        assigned_at=datetime.now().isoformat()
    )

    return {
        "status": "assigned",
        "task_id": task_id,
        "user_id": user_id
    }


# ====================================================================
# SUBMIT ANNOTATIONS
# ====================================================================

@app.post("/tasks/{task_id}/submit")
async def submit_task(task_id: str, request: SubmitAnnotationRequest):

    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_queue.update_task(
        task_id,
        annotations=request.annotations,
        status=TaskStatus.REVIEW,
        time_spent_seconds=request.time_spent_seconds
    )

    return {
        "status": "submitted_for_review",
        "task_id": task_id
    }


# ====================================================================
# REVIEW
# ====================================================================

@app.post("/tasks/{task_id}/review")
async def review_task(task_id: str):

    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_queue.update_task(task_id, status=TaskStatus.REVIEW)

    return {
        "status": "in_review",
        "task_id": task_id
    }


# ====================================================================
# USER STATS
# ====================================================================

@app.get("/users/{user_id}/stats")
async def get_user_stats(user_id: str):

    completed_tasks = await task_queue.get_user_tasks(
        user_id, TaskStatus.COMPLETED
    )

    active_tasks = await task_queue.get_user_tasks(
        user_id, TaskStatus.ASSIGNED
    )

    in_progress_tasks = await task_queue.get_user_tasks(
        user_id, TaskStatus.IN_PROGRESS
    )

    completed_count = len(completed_tasks)

    pending_count = len(active_tasks) + len(in_progress_tasks)

    times = [
        task.time_spent_seconds
        for task in completed_tasks
        if task.time_spent_seconds
    ]

    total_time_seconds = sum(times)

    throughput = (
        completed_count / (total_time_seconds / 3600)
        if total_time_seconds > 0
        else 0
    )

    avg_time = float(np.mean(times)) if times else 0

    accuracy = 85.0

    labels = [
        1 if annotation.is_valid else 0
        for task in completed_tasks
        for annotation in task.annotations
        if annotation.is_valid is not None
    ]

    if len(labels) < 2:

        kappa = 0.0

    else:

        consensus = [
            label if random.random() < 0.9 else 1 - label
            for label in labels
        ]

        po = np.mean(np.array(labels) == np.array(consensus))

        pe = (
            np.mean(labels) * np.mean(consensus)
            + (1 - np.mean(labels)) * (1 - np.mean(consensus))
        )

        kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0

    speed_normalized = (
        max(0.1, min(1.0, 30 / avg_time))
        if avg_time > 0
        else 0.5
    )

    quality_score = (
        0.5 * (accuracy / 100)
        + 0.3 * kappa
        + 0.2 * speed_normalized
    )

    return {
        "completed": completed_count,
        "pending": pending_count,
        "avg_time": round(avg_time, 1),
        "accuracy": accuracy,
        "kappa": round(float(kappa), 2),
        "throughput": round(float(throughput), 2),
        "quality_score": round(float(quality_score), 2)
    }


# ====================================================================
# DATASET RETRIEVAL FROM CLEANING SERVICE
# ====================================================================

async def get_original_dataset_from_cleaning(
    dataset_id: str
) -> Dict[str, Any]:
    """
    Retrieve the COMPLETE dataset from the Cleaning Service.
    Cleaning Service is the owner of dataset metadata.
    """

    url = f"{CLEANING_SERVICE_URL}/dataset/{dataset_id}/json"

    params = {"sample": "false"}

    print("=" * 52)
    print("📥 Retrieving dataset from Cleaning Service")
    print(f"   dataset_id = {dataset_id}")
    print(f"   URL = {url}")

    try:
        response = requests.get(url, params=params, timeout=CLEANING_TIMEOUT)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Cleaning Service unavailable: {exc}"
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=(
                "Dataset not found in Cleaning Service "
                f"for dataset_id='{dataset_id}'"
            )
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                "Cleaning Service returned "
                f"HTTP {response.status_code}: {response.text[:500]}"
            )
        )

    try:
        result = response.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Cleaning Service returned invalid JSON"
        )

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="Invalid dataset response from Cleaning Service"
        )

    returned_dataset_id = result.get("dataset_id")

    if returned_dataset_id and returned_dataset_id != dataset_id:
        raise HTTPException(
            status_code=502,
            detail=(
                "Dataset ID mismatch: requested "
                f"'{dataset_id}', received '{returned_dataset_id}'"
            )
        )

    data = result.get("data")

    if not isinstance(data, list):
        raise HTTPException(
            status_code=502,
            detail=(
                "Cleaning Service response does not contain "
                "a complete 'data' list"
            )
        )

    filename = result.get("filename", f"{dataset_id}.csv")

    print(f"✅ Dataset retrieved: {filename}")
    print(f"   rows = {len(data)}")

    if data and isinstance(data[0], dict):
        print(f"   columns = {len(data[0])}")

    print("=" * 52)

    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "data": data
    }


# ====================================================================
# FIELD RESOLUTION
# ====================================================================

def resolve_annotation_field(
    annotation: Dict[str, Any],
    sample: Dict[str, Any]
) -> Optional[str]:

    if not isinstance(sample, dict):
        return None

    field = annotation.get("field")

    # 1. Exact column name
    if field in sample:
        return field

    # 2. Search by original value
    original_value = annotation.get("original_value")

    if original_value is None:
        return None

    for column, value in sample.items():
        if str(value) == str(original_value):
            return column

    # 3. Search by detection information
    detections = annotation.get("detections", [])

    if isinstance(detections, list):

        for detection in detections:

            if not isinstance(detection, dict):
                continue

            detection_field = detection.get("field") or detection.get("column")

            if detection_field in sample:
                return detection_field

    return None


# ====================================================================
# ENTITY TYPE NORMALIZATION
# ====================================================================

def normalize_entity_type(entity_type: Any, field: str = "") -> str:
    """
    Normalise les entités provenant de :
      - Presidio
      - annotations humaines
      - anciens pipelines
      - noms de colonnes

    Le nom de colonne n'est PAS la source principale.
    Il sert uniquement de fallback.
    """

    value = str(entity_type or "").strip().lower()
    field_value = str(field or "").strip().lower()

    # ================================================================
    # MOROCCAN IDENTIFIERS
    # ================================================================

    if value in {
        "cin",
        "cin_ma",
        "cin_maroc",
        "nationalid",
        "national_id",
        "national_identity_number",
    }:
        return "cin"

    if value in {
        "phone",
        "phone_ma",
        "phone_number",
        "telephone",
        "mobile",
        "mobile_phone",
    }:
        return "phone"

    if value in {
        "rib",
        "rib_ma",
        "account",
        "account_number",
        "bank_account",
        "iban",
        "iban_ma",
    }:
        return "account_number"

    if value in {
        "cnss",
        "cnss_ma",
    }:
        return "cnss"

    if value in {
        "passport",
        "passport_ma",
        "ma_passport",
    }:
        return "passport"

    if value in {
        "permis",
        "permis_ma",
        "driver_license",
        "drivers_license",
    }:
        return "driver_license"

    # ================================================================
    # INTERNATIONAL / GENERIC PII
    # ================================================================

    if value in {
        "email",
        "email_address",
        "mail",
    }:
        return "email"

    if value in {
        "person",
        "person_name",
        "name",
        "full_name",
        "firstname",
        "lastname",
    }:
        return "name"

    if value in {
        "credit_card",
        "creditcard",
        "payment_card",
    }:
        return "credit_card"

    if value in {
        "salary",
        "salary_mad",
        "income",
    }:
        return "salary"

    if value in {
        "birth_date",
        "date_of_birth",
        "dob",
    }:
        return "birth_date"

    if value in {
        "age",
    }:
        return "age"

    # ================================================================
    # FALLBACK COLUMN NAME
    # ================================================================

    field_aliases = {
        "cin": "cin",
        "national_id": "cin",
        "nationalid": "cin",

        "phone": "phone",
        "telephone": "phone",
        "mobile": "phone",
        "mobile_phone": "phone",

        "email": "email",
        "email_address": "email",

        "name": "name",
        "full_name": "name",
        "person_name": "name",

        "salary": "salary",
        "income": "salary",

        "birth_date": "birth_date",
        "date_of_birth": "birth_date",
        "dob": "birth_date",
    }

    return field_aliases.get(
        field_value,
        value or field_value
    )


# ====================================================================
# MASKING : RÈGLES PAR COLONNE (calculées UNE fois par tâche)
# ====================================================================

def _to_float(value: Any, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_task_column_rules(
    task: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    colonne -> {entity_type, sensitivity_level, confidence}

    1. détections initiales du système
    2. surchargées par les annotations du labeler
       (is_valid=False retire la colonne)
    """

    rules: Dict[str, Dict[str, Any]] = {}

    sample = task.get("data_sample", {}) or {}

    # 1. Détections initiales
    for detection in task.get("detections", []) or []:

        if not isinstance(detection, dict):
            continue

        field = detection.get("field") or detection.get("column")

        if not field:
            continue

        raw_type = (
            detection.get("entity_type")
            or detection.get("original_entity_type")
            or field
        )

        rules[field] = {
            "entity_type": normalize_entity_type(raw_type, field),
            "sensitivity_level": detection.get("sensitivity_level") or "high",
            "confidence": _to_float(
                detection.get("confidence", detection.get("score", 1.0))
            )
        }

    # 2. Annotations du labeler (priorité)
    for annotation in task.get("annotations", []) or []:

        if not isinstance(annotation, dict):
            continue

        # L'annotation globale "pii_validation" n'est pas résolue => ignorée
        field = resolve_annotation_field(annotation, sample)

        if not field:
            continue

        if annotation.get("is_valid") is False:
            rules.pop(field, None)
            continue

        raw_type = (
            annotation.get("corrected_entity_type")
            or annotation.get("label")
            or (rules.get(field) or {}).get("entity_type")
            or field
        )

        rules[field] = {
            "entity_type": normalize_entity_type(raw_type, field),
            "sensitivity_level": (
                annotation.get("sensitivity_level")
                or (rules.get(field) or {}).get("sensitivity_level")
                or "high"
            ),
            "confidence": _to_float(annotation.get("confidence", 1.0))
        }

    return rules


def build_row_detections(
    rules: Dict[str, Dict[str, Any]],
    row: Dict[str, Any]
) -> List[Dict[str, Any]]:

    detections = []

    for field, rule in rules.items():

        if field not in row:
            continue

        value = row.get(field)

        if value is None or str(value).strip() == "":
            continue

        detections.append({
            "field": field,
            "value": str(value),
            **rule
        })

    return detections


# ====================================================================
# ETHIMASK - BATCH
# ====================================================================

def mask_rows_batch(
    batch_requests: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    try:
        response = requests.post(
            f"{ETHIMASK_SERVICE_URL}/mask/batch",
            json={"requests": batch_requests},
            timeout=ETHIMASK_TIMEOUT
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"EthiMask Service unavailable: {exc}"
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"EthiMask masking failed: {response.text[:1000]}"
        )

    try:
        results = response.json().get("results", [])
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="EthiMask returned invalid JSON"
        )

    if len(results) != len(batch_requests):
        raise HTTPException(
            status_code=502,
            detail="EthiMask batch size mismatch"
        )

    return results


# ====================================================================
# MASK COMPLETE DATASET
# ====================================================================

def build_export_filename(task_id: str, original_filename: str) -> str:

    base_name = os.path.splitext(os.path.basename(original_filename))[0]

    safe_base_name = re.sub(r"[^a-zA-Z0-9_-]", "_", base_name)

    safe_task_id = re.sub(r"[^a-zA-Z0-9_-]", "_", task_id)

    return f"{safe_base_name}_masked_{safe_task_id}.csv"


def discover_dataset_masking_rules(
    dataset: Dict[str, Any],
    task_document: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Découvre automatiquement les champs sensibles du dataset COMPLET.

    Sources :
      1. Presidio
      2. detections déjà présentes dans la tâche
      3. annotations humaines

    Le nom de colonne n'est jamais requis.

    Retour :
        {
            "NationalID": {
                "entity_type": "cin",
                "sensitivity_level": "high",
                "confidence": 0.98,
                "source": "presidio"
            },
            ...
        }
    """

    data = dataset.get("data", [])

    if not isinstance(data, list) or not data:
        return {}

    # ================================================================
    # 1. Toutes les colonnes
    # ================================================================

    columns = []

    seen_columns = set()

    for row in data:

        if not isinstance(row, dict):
            continue

        for field in row.keys():

            field = str(field)

            if field not in seen_columns:
                seen_columns.add(field)
                columns.append(field)

    if not columns:
        return {}

    print("=" * 60)
    print("🔎 DYNAMIC PII DISCOVERY")
    print(f"   rows    = {len(data)}")
    print(f"   columns = {len(columns)}")
    print("=" * 60)

    rules: Dict[str, Dict[str, Any]] = {}

    # ================================================================
    # 2. Cache Presidio
    # ================================================================

    presidio_cache: Dict[str, List[Dict[str, Any]]] = {}

    # ================================================================
    # 3. Analyse de chaque cellule avec Presidio
    # ================================================================

    for field in columns:

        print(f"🔍 Analyzing column: {field}")

        column_detections = []

        for row_index, row in enumerate(data):

            if not isinstance(row, dict):
                continue

            value = row.get(field)

            if value is None:
                continue

            text = str(value).strip()

            if not text:
                continue

            # --------------------------------------------------------
            # Cache : une même valeur n'est analysée qu'une fois
            # --------------------------------------------------------

            cache_key = text

            if (
                PRESIDIO_CACHE_ENABLED
                and cache_key in presidio_cache
            ):

                detections = presidio_cache[cache_key]

            else:

                try:

                    response = requests.post(
                        f"{PRESIDIO_SERVICE_URL}/analyze",
                        json={
                            "text": text,
                            "language": "fr",
                            "score_threshold": 0.30
                        },
                        timeout=PRESIDIO_TIMEOUT
                    )

                    if response.status_code != 200:

                        print(
                            f"   ⚠️ Presidio HTTP "
                            f"{response.status_code} "
                            f"for column={field}"
                        )

                        detections = []

                    else:

                        payload = response.json()

                        detections = payload.get(
                            "detections",
                            []
                        )

                except requests.RequestException as exc:

                    print(
                        f"   ⚠️ Presidio unavailable "
                        f"for column={field}: {exc}"
                    )

                    detections = []

                except Exception as exc:

                    print(
                        f"   ⚠️ Presidio analysis error "
                        f"for column={field}: {exc}"
                    )

                    detections = []

                if PRESIDIO_CACHE_ENABLED:
                    presidio_cache[cache_key] = detections

            # --------------------------------------------------------
            # Enregistrer les détections
            # --------------------------------------------------------

            for detection in detections:

                entity_type = detection.get(
                    "entity_type"
                )

                score = _to_float(
                    detection.get("score", 0)
                )

                if not entity_type:
                    continue

                normalized_type = normalize_entity_type(
                    entity_type,
                    field
                )

                # On ignore les résultats trop faibles
                if score < 0.30:
                    continue

                column_detections.append({
                    "entity_type": normalized_type,
                    "confidence": score,
                    "row_index": row_index,
                    "value": text
                })

        # ============================================================
        # 4. Agrégation par colonne
        # ============================================================

        if column_detections:

            # Entité la plus fréquente
            counts: Dict[str, int] = {}

            for detection in column_detections:

                entity = detection["entity_type"]

                counts[entity] = counts.get(entity, 0) + 1

            best_entity = max(
                counts,
                key=counts.get
            )

            best_detections = [
                d
                for d in column_detections
                if d["entity_type"] == best_entity
            ]

            confidence = max(
                d["confidence"]
                for d in best_detections
            )

            rules[field] = {
                "entity_type": best_entity,
                "sensitivity_level": "high",
                "confidence": confidence,
                "source": "presidio",
                "detections_count": len(best_detections)
            }

            print(
                f"   ✅ {field} → "
                f"{best_entity} "
                f"({len(best_detections)} detections)"
            )

    # ================================================================
    # 5. Ajouter les détections existantes de la Task
    # ================================================================

    for detection in task_document.get(
        "detections",
        []
    ) or []:

        if not isinstance(detection, dict):
            continue

        field = (
            detection.get("field")
            or detection.get("column")
        )

        if not field:
            continue

        raw_type = (
            detection.get("entity_type")
            or detection.get("original_entity_type")
            or field
        )

        normalized_type = normalize_entity_type(
            raw_type,
            field
        )

        # Seulement si Presidio n'a rien trouvé
        if field not in rules:

            rules[field] = {
                "entity_type": normalized_type,
                "sensitivity_level": (
                    detection.get(
                        "sensitivity_level"
                    )
                    or "high"
                ),
                "confidence": _to_float(
                    detection.get(
                        "confidence",
                        detection.get(
                            "score",
                            1.0
                        )
                    )
                ),
                "source": "task_detection"
            }

    # ================================================================
    # 6. Annotations humaines
    # ================================================================

    sample = task_document.get(
        "data_sample",
        {}
    ) or {}

    for annotation in task_document.get(
        "annotations",
        []
    ) or []:

        if not isinstance(annotation, dict):
            continue

        field = resolve_annotation_field(
            annotation,
            sample
        )

        if not field:
            continue

        # Le labeler a explicitement invalidé
        if annotation.get("is_valid") is False:

            rules.pop(field, None)

            print(
                f"   🚫 {field} "
                f"removed by human annotation"
            )

            continue

        raw_type = (
            annotation.get(
                "corrected_entity_type"
            )
            or annotation.get("label")
            or (
                rules.get(field, {})
                .get("entity_type")
            )
            or field
        )

        rules[field] = {
            "entity_type": normalize_entity_type(
                raw_type,
                field
            ),
            "sensitivity_level": (
                annotation.get(
                    "sensitivity_level"
                )
                or rules.get(field, {})
                .get(
                    "sensitivity_level",
                    "high"
                )
            ),
            "confidence": _to_float(
                annotation.get(
                    "confidence",
                    rules.get(field, {})
                    .get(
                        "confidence",
                        1.0
                    )
                )
            ),
            "source": "human_annotation"
        }

    # ================================================================
    # 7. Résultat final
    # ================================================================

    print("=" * 60)
    print("🔐 FINAL MASKING RULES")

    for field, rule in rules.items():

        print(
            f"   {field} → "
            f"{rule['entity_type']} "
            f"[{rule.get('source')}]"
        )

    print(
        f"   TOTAL SENSITIVE FIELDS = {len(rules)}"
    )

    print("=" * 60)

    return rules

def write_masked_dataset(
    task_document: Dict[str, Any],
    dataset: Dict[str, Any],
    export_path: str
) -> Dict[str, Any]:
    """
    Génère le CSV certifié masqué.

    Flux :
        dataset complet
            ↓
        Presidio / task / annotations
            ↓
        règles de masquage par colonne
            ↓
        EthiMask /mask/batch
            ↓
        CSV masqué permanent

    MongoDB ne reçoit jamais les données du CSV.
    """

    data = dataset.get("data", [])

    if not isinstance(data, list) or not data:
        raise HTTPException(
            status_code=400,
            detail="Dataset is empty or invalid"
        )

    # ------------------------------------------------------------
    # 1. Découverte des règles
    # ------------------------------------------------------------

    rules = discover_dataset_masking_rules(
        dataset,
        task_document
    )

    if not rules:
        raise HTTPException(
            status_code=422,
            detail=(
                "No sensitive fields detected. "
                "Certified masked export cannot be generated."
            )
        )

    print("=" * 60)
    print("🔐 MASKING RULES")
    for field, rule in rules.items():
        print(
            f"   {field} -> "
            f"{rule['entity_type']} "
            f"[{rule.get('source', 'unknown')}]"
        )
    print("=" * 60)

    # ------------------------------------------------------------
    # 2. Préparer les lignes par batch
    # ------------------------------------------------------------

    masked_rows = []

    total_masking_applied = 0
    technique_used: Dict[str, str] = {}
    total_audit_events = 0

    total_rows = len(data)

    for batch_start in range(
        0,
        total_rows,
        MASK_BATCH_SIZE
    ):

        batch_rows = data[
            batch_start:
            batch_start + MASK_BATCH_SIZE
        ]

        batch_requests = []

        for row in batch_rows:

            if not isinstance(row, dict):
                row = {}

            detections = build_row_detections(
                rules,
                row
            )

            batch_requests.append({
                "data": dict(row),
                "detections": detections,
                "config": EXPORT_MASK_CONFIG
            })

        print(
            f"🔐 EthiMask batch "
            f"{batch_start + 1}-"
            f"{min(batch_start + MASK_BATCH_SIZE, total_rows)} "
            f"/ {total_rows}"
        )

        # --------------------------------------------------------
        # 3. Appel EthiMask
        # --------------------------------------------------------

        results = mask_rows_batch(
            batch_requests
        )

        # --------------------------------------------------------
        # 4. Traiter les résultats
        # --------------------------------------------------------

        for result in results:

            if not isinstance(result, dict):
                raise HTTPException(
                    status_code=502,
                    detail="Invalid result returned by EthiMask"
                )

            masked_data = result.get(
                "masked_data"
            )

            if not isinstance(masked_data, dict):
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "EthiMask result does not contain "
                        "valid masked_data"
                    )
                )

            masked_rows.append(
                masked_data
            )

            # Nombre réellement masqué
            total_masking_applied += int(
                result.get(
                    "masking_applied",
                    0
                )
            )

            # Techniques
            result_techniques = result.get(
                "technique_used",
                {}
            )

            if isinstance(result_techniques, dict):

                for field, technique in result_techniques.items():

                    if technique and technique != "none":
                        technique_used[field] = technique

            # Audit
            audit_log = result.get(
                "audit_log",
                []
            )

            if isinstance(audit_log, list):
                total_audit_events += len(
                    audit_log
                )

    # ------------------------------------------------------------
    # 5. Vérification sécurité
    # ------------------------------------------------------------

    if total_masking_applied <= 0:

        raise HTTPException(
            status_code=422,
            detail=(
                "EthiMask completed but no sensitive value "
                "was actually masked."
            )
        )

    if len(masked_rows) != len(data):

        raise HTTPException(
            status_code=500,
            detail=(
                "Masked dataset row count mismatch: "
                f"expected {len(data)}, "
                f"received {len(masked_rows)}"
            )
        )

    # ------------------------------------------------------------
    # 6. Créer le dossier
    # ------------------------------------------------------------

    os.makedirs(
        os.path.dirname(export_path),
        exist_ok=True
    )

    # ------------------------------------------------------------
    # 7. Déterminer les colonnes
    # ------------------------------------------------------------

    columns = []

    seen = set()

    for row in data:

        if not isinstance(row, dict):
            continue

        for field in row.keys():

            field = str(field)

            if field not in seen:
                seen.add(field)
                columns.append(field)

    # ------------------------------------------------------------
    # 8. Écrire le CSV MASQUÉ
    # ------------------------------------------------------------

    try:

        with open(
            export_path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as csv_file:

            writer = csv.DictWriter(
                csv_file,
                fieldnames=columns,
                extrasaction="ignore"
            )

            writer.writeheader()

            for row in masked_rows:

                normalized_row = {
                    column: row.get(column, "")
                    for column in columns
                }

                writer.writerow(
                    normalized_row
                )

    except OSError as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to write certified CSV: {exc}"
            )
        )

    # ------------------------------------------------------------
    # 9. Vérification physique
    # ------------------------------------------------------------

    if not os.path.isfile(export_path):

        raise HTTPException(
            status_code=500,
            detail=(
                "Certified CSV does not exist "
                "after writing"
            )
        )

    if os.path.getsize(export_path) == 0:

        raise HTTPException(
            status_code=500,
            detail="Certified CSV is empty"
        )

    print("=" * 60)
    print("✅ MASKED DATASET GENERATED")
    print(f"   rows              = {len(masked_rows)}")
    print(f"   columns           = {len(columns)}")
    print(
        f"   masking_applied   = "
        f"{total_masking_applied}"
    )
    print(
        f"   audit_events      = "
        f"{total_audit_events}"
    )
    print(
        f"   techniques        = "
        f"{technique_used}"
    )
    print(f"   output            = {export_path}")
    print("=" * 60)

    return {
        "rows": len(masked_rows),
        "columns": len(columns),
        "masking_applied": total_masking_applied,
        "technique_used": technique_used,
        "audit_events": total_audit_events
    }
# ====================================================================
# APPROVE TASK
# ====================================================================

@app.post("/tasks/{task_id}/approve")
async def approve_task(
    task_id: str,
    request: ApprovalRequest = Body(default=ApprovalRequest())
):
    """
    Steward approval.

    task -> dataset_id -> Cleaning Service -> complete dataset
         -> EthiMask (/mask/batch, force_masking)
         -> /opt/airflow/datasets/certified/*.csv
         -> MongoDB metadata only
    """

    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable")

    # 1. Retrieve task
    task_document = await db["tasks"].find_one({"id": task_id})

    if not task_document:
        raise HTTPException(status_code=404, detail="Task not found")

    # 2. Only REVIEW tasks can be approved
    current_status = task_document.get("status")

    if current_status != TaskStatus.REVIEW.value:

        if current_status == TaskStatus.COMPLETED.value:
            raise HTTPException(
                status_code=409,
                detail="Task is already completed"
            )

        raise HTTPException(
            status_code=409,
            detail="Only tasks in 'review' status can be approved"
        )

    dataset_id = task_document.get("dataset_id")

    if not dataset_id:
        raise HTTPException(
            status_code=400,
            detail="Task does not contain dataset_id"
        )

    # 3. Retrieve FULL dataset from Cleaning Service
    dataset = await get_original_dataset_from_cleaning(dataset_id)

    original_filename = dataset.get("filename", f"{dataset_id}.csv")

    now = datetime.now().isoformat()

    # 4. If masking was not requested
    if not request.apply_masking:

        await db["tasks"].update_one(
            {"id": task_id},
            {
                "$set": {
                    "status": TaskStatus.COMPLETED.value,
                    "completed_at": now,
                    "masking_requested": False,
                    "masked_file": None,
                    "masking_applied": 0,
                    "masking_techniques": {},
                    "masking_audit": []
                },
                "$unset": {
                    "masked_data": "",
                    "masked_data_full": "",
                    "masked_csv": "",
                    "masked_rows": "",
                    "masked_dataset": "",
                    "export_path": ""
                }
            }
        )

        return {
            "status": "approved",
            "task_id": task_id,
            "dataset_id": dataset_id,
            "masking_requested": False,
            "masking_applied": 0,
            "generation": "not_requested",
            "masked_file": None
        }

    # 5. Permanent export filename
    export_filename = build_export_filename(task_id, original_filename)

    export_path = os.path.join(EXPORT_DIR, export_filename)

    # 6. Generate PERMANENT masked CSV
    print("=" * 52)
    print("🔐 MASKING DATASET")
    print(f"   task_id    = {task_id}")
    print(f"   dataset_id = {dataset_id}")
    print(f"   original   = {original_filename}")
    print(f"   output     = {export_path}")

    try:

        # run_in_threadpool : ne bloque plus la boucle async
        masking_result = await run_in_threadpool(
            write_masked_dataset,
            task_document,
            dataset,
            export_path
        )

    except HTTPException:

        if os.path.isfile(export_path):
            os.remove(export_path)

        raise

    except Exception as exc:

        if os.path.isfile(export_path):
            os.remove(export_path)

        print(f"❌ Masking failed: {exc}")

        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate certified masked CSV: {exc}"
        )

    # 7. Verify file
    if not os.path.isfile(export_path):
        raise HTTPException(
            status_code=500,
            detail="Certified masked CSV was not generated"
        )
    # ================================================================
# SECURITY GUARD
# Aucun CSV certifié ne doit être créé si aucune valeur n'a
# réellement été masquée.
# ================================================================

    if masking_result.get("masking_applied", 0) <= 0:

        if os.path.isfile(export_path):
            os.remove(export_path)

        raise HTTPException(
            status_code=422,
            detail=(
                "Certified export refused: "
                "EthiMask did not mask any sensitive value."
            )
        )

    file_size = os.path.getsize(export_path)

    # 8. ONLY METADATA in MongoDB
    masked_file_metadata = {
        "file_id": task_id,
        "filename": export_filename,
        "content_type": "text/csv",
        "storage_key": f"certified/{export_filename}",
        "path": export_path,
        "size_bytes": file_size,
        "size_kb": round(file_size / 1024, 1),
        "rows": masking_result["rows"],
        "columns": masking_result["columns"],
        "created_at": now,
        "generation": "on_approval"
    }

    update_data = {
        "status": TaskStatus.COMPLETED.value,
        "completed_at": now,
        "masking_requested": True,
        "masked_file": masked_file_metadata,
        "masking_applied": masking_result["masking_applied"],
        "masking_techniques": masking_result["technique_used"],
        # Audit entries not stored, only a count.
        "masking_audit": [
            {
                "event_count": masking_result["audit_events"],
                "created_at": now
            }
        ]
    }

    await db["tasks"].update_one(
        {"id": task_id},
        {
            "$set": update_data,
            "$unset": {
                "masked_data": "",
                "masked_data_full": "",
                "masked_csv": "",
                "masked_rows": "",
                "masked_dataset": "",
                "export_path": ""
            }
        }
    )

    print("✅ Certified masked CSV created")
    print(f"   file     = {export_filename}")
    print(f"   rows     = {masking_result['rows']}")
    print(f"   columns  = {masking_result['columns']}")
    print(f"   size     = {round(file_size / 1024, 1)} KB")
    print(f"   masking  = {masking_result['masking_applied']}")
    print("=" * 52)

    return {
        "status": "approved",
        "task_id": task_id,
        "dataset_id": dataset_id,
        "masking_requested": True,
        "masking_applied": masking_result["masking_applied"],
        "generation": "on_approval",
        "masked_file": masked_file_metadata
    }


# ====================================================================
# REJECT TASK
# ====================================================================

@app.post("/tasks/{task_id}/reject")
async def reject_task(task_id: str):

    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_queue.update_task(
        task_id,
        status=TaskStatus.PENDING,
        assigned_to=None
    )

    return {
        "status": "rejected_reassigned",
        "task_id": task_id
    }


# ====================================================================
# EXPORT HISTORY
# ====================================================================

@app.get("/exports")
async def exports():
    """
    Return the certified MASKED CSV files present in:
        /opt/airflow/datasets/certified

    Only files generated by /approve ("_masked_" in the name) are listed,
    so an old unmasked file can never appear in Export History.
    MongoDB only enriches metadata. CSV content is NEVER stored in MongoDB.
    """

    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR, exist_ok=True)

    results = []

    for filename in os.listdir(EXPORT_DIR):

        if not filename.lower().endswith(".csv"):
            continue

        # Uniquement les fichiers masqués
        if "_masked_" not in filename:
            continue

        file_path = os.path.join(EXPORT_DIR, filename)

        if not os.path.isfile(file_path):
            continue

        stat = os.stat(file_path)

        file_size = stat.st_size

        created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()

        task_document = None

        if db is not None:
            task_document = await db["tasks"].find_one({
                "masked_file.filename": filename
            })

        if task_document:

            masked_file = task_document.get("masked_file", {}) or {}

            results.append({
                "filename": filename,
                "size": file_size,
                "size_kb": round(file_size / 1024, 1),
                "created_at": masked_file.get("created_at") or created_at,
                "type": "csv",
                "task_id": task_document.get("id"),
                "dataset_id": task_document.get("dataset_id"),
                "rows": masked_file.get("rows"),
                "columns": masked_file.get("columns"),
                "generation": masked_file.get("generation", "on_approval"),
                "download_url": f"/exports/download/{task_document.get('id')}"
            })

        else:

            results.append({
                "filename": filename,
                "size": file_size,
                "size_kb": round(file_size / 1024, 1),
                "created_at": created_at,
                "type": "csv",
                "task_id": None,
                "dataset_id": None,
                "rows": None,
                "columns": None,
                "generation": "physical_file",
                "download_url": f"/exports/download-file/{filename}"
            })

    results.sort(
        key=lambda item: item.get("created_at") or "",
        reverse=True
    )

    return results


# ====================================================================
# DOWNLOAD PERMANENT CERTIFIED CSV
# ====================================================================

@app.get("/exports/download/{task_id}")
async def download_export(task_id: str):
    """
    Download the CSV already generated during approval.
    NO masking and NO call to EthiMask here.
    """

    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable")

    task = await db["tasks"].find_one({"id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="Export task not found")

    if task.get("status") != TaskStatus.COMPLETED.value:
        raise HTTPException(
            status_code=409,
            detail="This task has not been approved for export"
        )

    if not task.get("masking_requested", False):
        raise HTTPException(
            status_code=400,
            detail="Masking was not requested for this task"
        )

    masked_file = task.get("masked_file", {}) or {}

    filename = masked_file.get("filename")

    if not filename:
        raise HTTPException(
            status_code=404,
            detail="No certified file metadata found for this task"
        )

    # SECURITY: never trust a path coming from the frontend.
    if not re.match(r"^[a-zA-Z0-9_.-]+\.csv$", filename):
        raise HTTPException(status_code=400, detail="Invalid export filename")

    file_path = os.path.join(EXPORT_DIR, filename)

    export_root = os.path.abspath(EXPORT_DIR)

    absolute_file_path = os.path.abspath(file_path)

    if not absolute_file_path.startswith(export_root + os.sep):
        raise HTTPException(status_code=400, detail="Invalid export path")

    if not os.path.isfile(absolute_file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Certified masked CSV no longer exists: {filename}"
        )

    return FileResponse(
        path=absolute_file_path,
        media_type="text/csv",
        filename=filename
    )


@app.get("/exports/download-file/{filename}")
async def download_export_file(filename: str):
    """
    Download an existing certified CSV directly
    from /opt/airflow/datasets/certified.
    """

    if not re.match(r"^[a-zA-Z0-9_.-]+\.csv$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    export_root = os.path.abspath(EXPORT_DIR)

    file_path = os.path.abspath(os.path.join(EXPORT_DIR, filename))

    if not file_path.startswith(export_root + os.sep):
        raise HTTPException(status_code=400, detail="Invalid export path")

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Certified file '{filename}' not found"
        )

    return FileResponse(
        path=file_path,
        media_type="text/csv",
        filename=filename
    )


# ====================================================================
# ROOT
# ====================================================================

@app.get("/")
async def root():

    return {
        "service": "DataShield Annotation Service",
        "version": "5.1.0",
        "status": "running"
    }


# ====================================================================
# MAIN
# ====================================================================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=ANNOTATION_SERVICE_PORT
    )