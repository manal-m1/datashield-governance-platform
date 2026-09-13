"""
EthiMask Service - Tâche 9
Contextual Data Masking Framework (Mongo Persisted)
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
from contextlib import asynccontextmanager
import os

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.database.mongodb import db
from backend.score_calculator import MaskingPerceptron, UserRole, MaskingLevel
from backend.masking_techniques import ContextualMasker, MaskingTechnique
from backend.he_key_manager import he_manager, HEAccessDenied
from backend.token_vault import TokenVault


# ====================================================================
# MODELS
# ====================================================================

class SensitivityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MaskingConfig(BaseModel):
    role: UserRole = UserRole.DATA_LABELER
    context: str = "default"
    purpose: str = "general"
    history_stats: Optional[Dict[str, float]] = {
        "conformity": 0.8,
        "frequency": 0.5,
        "violations": 0.0
    }


class Detection(BaseModel):
    field: str
    value: Any
    entity_type: str
    sensitivity_level: str
    confidence: float = 1.0


class MaskRequest(BaseModel):
    data: Dict[str, Any]
    detections: List[Detection]
    config: MaskingConfig


class MaskResponse(BaseModel):
    masked_data: Dict[str, Any]
    masking_applied: int
    technique_used: Dict[str, str]
    audit_log: List[Dict]


# ====================================================================
# NOUVEAUX MODELS POUR LE BATCH
# ====================================================================

class MaskBatchRequest(BaseModel):
    """
    Contient plusieurs demandes de masquage.
    Chaque demande respecte exactement le même format que /mask.
    """
    requests: List[MaskRequest]


class MaskBatchResponse(BaseModel):
    """
    Résultat du masquage pour chaque demande du batch.
    """
    results: List[MaskResponse]


class MaskingPolicy(BaseModel):
    entity_type: str
    role: str
    level: MaskingLevel
    technique: MaskingTechnique


class ConfigUpdate(BaseModel):
    ws: float = Field(..., ge=-1.0, le=1.0)
    wr: float = Field(..., ge=-1.0, le=1.0)
    wc: float = Field(..., ge=-1.0, le=1.0)
    wp: float = Field(..., ge=-1.0, le=1.0)
    bias: float = Field(0.4, ge=-1.0, le=1.0)
    alpha: float = Field(0.5, ge=0.0, le=1.0)


# ====================================================================
# CONFIG MANAGER
# ====================================================================

class ConfigManager:

    DEFAULT_CONFIG = {
        "weights": [0.35, -0.30, 0.20, 0.15],
        "bias": 0.4,
        "alpha": 0.5
    }

    async def get_config(self) -> Dict:
        if db is not None:
            doc = await db.ethimask_config.find_one(
                {"_id": "global_config"}
            )

            if doc:
                return {
                    "weights": doc["weights"],
                    "bias": doc["bias"],
                    "alpha": doc.get("alpha", 0.5)
                }

        return self.DEFAULT_CONFIG

    async def update_config(self, config: ConfigUpdate):

        new_weights = [
            config.ws,
            config.wr,
            config.wc,
            config.wp
        ]

        if db is not None:
            await db.ethimask_config.update_one(
                {"_id": "global_config"},
                {
                    "$set": {
                        "weights": new_weights,
                        "bias": config.bias,
                        "alpha": config.alpha
                    }
                },
                upsert=True
            )

        perceptron.update_weights(
            new_weights,
            config.bias
        )


# ====================================================================
# POLICY MANAGER
# ====================================================================

class PolicyManager:

    DEFAULT_POLICIES = [
        {
            "entity_type": "*",
            "role": "admin",
            "level": "none",
            "technique": "pseudonymization"
        },
        {
            "entity_type": "cin",
            "role": "steward",
            "level": "partial",
            "technique": "pseudonymization"
        },
        {
            "entity_type": "cin",
            "role": "labeler",
            "level": "encrypted",
            "technique": "fpe"
        },
        {
            "entity_type": "phone",
            "role": "*",
            "level": "partial",
            "technique": "fpe"
        },
        {
            "entity_type": "account_number",
            "role": "*",
            "level": "partial",
            "technique": "fpe"
        },
        {
            "entity_type": "*",
            "role": "labeler",
            "level": "encrypted",
            "technique": "encryption"
        },
        {
            "entity_type": "*",
            "role": "annotator",
            "level": "partial",
            "technique": "generalization"
        },
    ]

    async def get_policy(
        self,
        entity_type: str,
        role: str
    ) -> Optional[MaskingPolicy]:

        if db is not None:

            doc = await db.masking_policies.find_one(
                {
                    "entity_type": entity_type,
                    "role": role
                }
            )

            if not doc:
                doc = await db.masking_policies.find_one(
                    {
                        "entity_type": "*",
                        "role": role
                    }
                )

            if doc:
                return MaskingPolicy(**doc)

        for p in self.DEFAULT_POLICIES:

            if (
                p["entity_type"] == entity_type
                or p["entity_type"] == "*"
            ) and p["role"] == role:

                return MaskingPolicy(**p)

        return None

    async def add_policy(self, policy: MaskingPolicy):

        if db is not None:

            await db.masking_policies.update_one(
                {
                    "entity_type": policy.entity_type,
                    "role": policy.role
                },
                {
                    "$set": policy.dict()
                },
                upsert=True
            )

    async def get_all_policies(self) -> List[MaskingPolicy]:

        if db is not None:

            cursor = db.masking_policies.find()

            return [
                MaskingPolicy(**doc)
                async for doc in cursor
            ]

        return [
            MaskingPolicy(**p)
            for p in self.DEFAULT_POLICIES
        ]


# ====================================================================
# AUDIT LOG
# SCHÉMA STRICT
# ====================================================================

AUDIT_ALLOWED_KEYS = {
    "field",
    "entity_type",
    "sensitivity",
    "masking_level",
    "technique",
    "role",
    "timestamp"
}


def build_audit_entry(
    field: str,
    entity_type: str,
    sensitivity: str,
    level,
    technique: str,
    role
) -> dict:

    entry = {
        "field": field,
        "entity_type": entity_type,
        "sensitivity": sensitivity,
        "masking_level": (
            level.value
            if hasattr(level, "value")
            else level
        ),
        "technique": technique,
        "role": (
            role.value
            if hasattr(role, "value")
            else role
        ),
        "timestamp": datetime.now().isoformat()
    }

    assert set(entry.keys()) == AUDIT_ALLOWED_KEYS, (
        "Audit entry contains unexpected keys: "
        f"{set(entry.keys()) - AUDIT_ALLOWED_KEYS}"
    )

    return entry


# ====================================================================
# FASTAPI APP
# ====================================================================

perceptron = MaskingPerceptron()

vault = TokenVault(db)

masker = ContextualMasker(
    db=db,
    vault=vault,
    he_context_provider=he_manager.get_public_context
)

policy_manager = PolicyManager()

config_manager = ConfigManager()


# ====================================================================
# TECHNIQUE COVERAGE
# ====================================================================

async def _verify_technique_coverage():

    """
    Empêche toute technique déclarée dans l'enum
    mais non câblée dans mask().
    """

    test_cases = {

        MaskingTechnique.PSEUDONYMIZATION:
            ("test_value", "name"),

        MaskingTechnique.GENERALIZATION:
            ("test_value", "age"),

        MaskingTechnique.SUPPRESSION:
            ("test_value", "generic"),

        MaskingTechnique.PERTURBATION:
            (100.0, "salary"),

        MaskingTechnique.HASHING:
            ("test_value", "generic"),

        MaskingTechnique.ENCRYPTION:
            (100.0, "generic"),

        MaskingTechnique.FPE:
            ("AB123456", "cin"),

        MaskingTechnique.TOKENIZATION:
            ("4242424242424242", "card"),
    }

    expected = {

        MaskingTechnique.PSEUDONYMIZATION:
            "pseudonymization",

        MaskingTechnique.GENERALIZATION:
            "generalization",

        MaskingTechnique.SUPPRESSION:
            "suppression",

        MaskingTechnique.PERTURBATION:
            "differential_privacy_laplace",

        MaskingTechnique.HASHING:
            "hashing",

        MaskingTechnique.ENCRYPTION:
            "homomorphic_encryption",

        MaskingTechnique.FPE:
            "format_preserving_encryption",

        MaskingTechnique.TOKENIZATION:
            "tokenization",
    }

    for technique, (val, etype) in test_cases.items():

        _, tech_used = await masker.mask(
            val,
            etype,
            MaskingLevel.PARTIAL,
            technique
        )

        if (
            tech_used != expected[technique]
            and "fallback" not in tech_used
        ):

            raise RuntimeError(
                f"MaskingTechnique.{technique.name} "
                f"produit '{tech_used}', "
                f"attendu '{expected[technique]}' — "
                f"vérifier l'implémentation dans mask()"
            )


# ====================================================================
# LIFESPAN
# ====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    config = await config_manager.get_config()

    perceptron.update_weights(
        config["weights"],
        config["bias"]
    )

    await _verify_technique_coverage()

    yield


app = FastAPI(
    title="EthiMask Service",
    description=(
        "Tâche 9 - Contextual Data Masking Framework "
        "(Mongo Persisted)"
    ),
    version="2.2.0",
    lifespan=lifespan
)


# ====================================================================
# MIDDLEWARE
# ====================================================================

@app.middleware("http")
async def set_root_path(request: Request, call_next):

    root_path = request.headers.get(
        "x-forwarded-prefix"
    )

    if root_path:
        request.scope["root_path"] = root_path

    return await call_next(request)


ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://localhost:3000"
).split(",")


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS"
    ],
    allow_headers=[
        "Content-Type",
        "Authorization"
    ],
)


# ====================================================================
# STARTUP
# ====================================================================

@app.get("/")
async def root():

    log_count = 0

    if db is not None:
        log_count = await db.audit_logs.count_documents({})

    return {
        "service": "EthiMask Service",
        "status": "running",
        "db_connected": db is not None,
        "audit_logs_count": log_count
    }


@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }


# ====================================================================
# MASKING - LOGIQUE COMMUNE
# ====================================================================

async def _apply_masking(
    request: MaskRequest
) -> MaskResponse:

    """
    Applique le masquage à une seule demande.

    Cette fonction contient exactement la logique
    qui existait auparavant dans POST /mask.

    Elle est utilisée par :
        - POST /mask
        - POST /mask/batch

    Aucune fonctionnalité de masquage n'est modifiée.
    """

    masked_data = request.data.copy()

    techniques_used = {}

    audit_logs_batch = []

    for detection in request.detections:

        field = detection.field

        if field not in masked_data:
            continue

        level, confidence = perceptron.decide_masking(
            detection.sensitivity_level,
            request.config.role,
            request.config.context,
            request.config.purpose,
            history=request.config.history_stats
        )

        policy = await policy_manager.get_policy(
            detection.entity_type,
            request.config.role.value
        )

        if policy:

            level = policy.level
            technique = policy.technique

        else:

            technique = None

        masked_val, tech_used = await masker.mask(
            masked_data[field],
            detection.entity_type,
            level,
            technique
        )

        masked_data[field] = masked_val

        techniques_used[field] = tech_used

        audit_logs_batch.append(
            build_audit_entry(
                field,
                detection.entity_type,
                detection.sensitivity_level,
                level,
                tech_used,
                request.config.role
            )
        )

    # ================================================================
    # PERSISTENCE AUDIT
    # ================================================================

    if db is not None and audit_logs_batch:

        result = await db.audit_logs.insert_many(
            audit_logs_batch
        )

        for i, log in enumerate(audit_logs_batch):

            log["_id"] = str(
                result.inserted_ids[i]
            )

    # ================================================================
    # RESPONSE
    # ================================================================

    return MaskResponse(

        masked_data=masked_data,

        masking_applied=len([
            t
            for t in techniques_used.values()
            if t != "none"
        ]),

        technique_used=techniques_used,

        audit_log=audit_logs_batch
    )


# ====================================================================
# MASKING - ENDPOINT EXISTANT
# ====================================================================

@app.post(
    "/mask",
    response_model=MaskResponse
)
async def mask_data(
    request: MaskRequest
):

    """
    Endpoint existant.

    Il reste compatible avec les appels actuels.
    """

    return await _apply_masking(request)


# ====================================================================
# MASKING - NOUVEAU ENDPOINT BATCH
# ====================================================================

@app.post(
    "/mask/batch",
    response_model=MaskBatchResponse
)
async def mask_data_batch(
    request: MaskBatchRequest
):

    """
    Applique le masquage à plusieurs demandes
    dans une seule requête HTTP.

    Chaque élément du batch utilise exactement
    la même logique que POST /mask.
    """

    if not request.requests:

        return MaskBatchResponse(
            results=[]
        )

    results = []

    for mask_request in request.requests:

        result = await _apply_masking(
            mask_request
        )

        results.append(result)

    return MaskBatchResponse(
        results=results
    )


# ====================================================================
# DECIDE
# ====================================================================

@app.post("/decide")
def get_masking_decision(
    sensitivity: str,
    role: UserRole,
    context: str = "default",
    purpose: str = "general"
):

    return perceptron.get_decision_explanation(
        sensitivity,
        role,
        context,
        purpose
    )


# ====================================================================
# POLICIES
# ====================================================================

@app.get("/policies")
async def list_policies():

    policies = await policy_manager.get_all_policies()

    return {
        "policies": [
            p.dict()
            for p in policies
        ]
    }


@app.post("/policies")
async def add_policy(
    policy: MaskingPolicy
):

    await policy_manager.add_policy(
        policy
    )

    return {
        "status": "added/updated"
    }


# ====================================================================
# CONFIG
# ====================================================================

@app.get("/config")
async def get_config():

    config = await config_manager.get_config()

    return {

        "sensitivity_weight":
            config["weights"][0],

        "role_weight":
            config["weights"][1],

        "context_weight":
            config["weights"][2],

        "purpose_weight":
            config["weights"][3],

        "bias":
            config["bias"],

        "alpha":
            config["alpha"]
    }


@app.post("/config")
async def update_config(
    config: ConfigUpdate
):

    await config_manager.update_config(
        config
    )

    return {
        "status": "configuration saved",
        "new_config": config
    }


# ====================================================================
# AUDIT LOGS
# ====================================================================

@app.get("/audit-logs")
async def get_audit_logs(
    limit: int = 100
):

    if db is not None:

        cursor = (
            db.audit_logs
            .find()
            .sort("timestamp", -1)
            .limit(limit)
        )

        logs = []

        async for doc in cursor:

            doc["_id"] = str(
                doc["_id"]
            )

            logs.append(doc)

        return {
            "logs": logs
        }

    return {
        "logs": []
    }


@app.get("/audit")
async def get_masking_audit_report(
    limit: int = 100,
    role: Optional[str] = None,
    entity_type: Optional[str] = None
):

    if db is None:
        return {
            "logs": []
        }

    query = {}

    if role:
        query["role"] = role

    if entity_type:
        query["entity_type"] = entity_type

    cursor = (
        db.audit_logs
        .find(query)
        .sort("timestamp", -1)
        .limit(limit)
    )

    logs = []

    async for doc in cursor:

        doc["_id"] = str(
            doc["_id"]
        )

        logs.append(doc)

    return {
        "count": len(logs),
        "filters": {
            "role": role,
            "entity_type": entity_type
        },
        "logs": logs
    }


# ====================================================================
# RETRAIN
# ====================================================================

@app.post("/retrain")
async def retrain_on_audit_logs():

    if db is None:

        raise HTTPException(
            status_code=500,
            detail="Database not connected"
        )

    cursor = (
        db.audit_logs
        .find()
        .sort("timestamp", -1)
        .limit(500)
    )

    logs = [
        doc
        async for doc in cursor
    ]

    if not logs:

        return {
            "status": "skipped",
            "message": "No logs available for training"
        }

    sensitivity_shift = 0.0
    role_shift = 0.0

    for log in logs:

        level = log.get(
            "masking_level"
        )

        sens = log.get(
            "sensitivity"
        )

        if (
            sens in ["high", "critical"]
            and level == "none"
        ):
            sensitivity_shift += 0.01

        if (
            sens == "low"
            and log.get("role") == "admin"
            and level != "none"
        ):
            role_shift += 0.01

    config = await config_manager.get_config()

    weights = config["weights"]

    weights[0] = min(
        1.0,
        max(
            -1.0,
            weights[0] + sensitivity_shift
        )
    )

    weights[1] = min(
        1.0,
        max(
            -1.0,
            weights[1] + role_shift
        )
    )

    new_config = ConfigUpdate(
        ws=weights[0],
        wr=weights[1],
        wc=weights[2],
        wp=weights[3],
        bias=config["bias"]
    )

    await config_manager.update_config(
        new_config
    )

    return {

        "status": "success",

        "message":
            f"Retrained on {len(logs)} samples",

        "updates": {

            "sensitivity_weight":
                weights[0],

            "role_trust_weight":
                weights[1]
        }
    }


# ====================================================================
# HOMOMORPHIC ENCRYPTION
# ====================================================================

@app.get("/he/public-context")
async def get_public_context():

    """
    Distribuable à n'importe quel service
    pour chiffrer/calculer.

    Ne permet jamais de déchiffrer.
    """

    return {
        "public_context":
            he_manager
            .get_public_context()
            .serialize()
            .hex()
    }


@app.post("/he/decrypt")
async def decrypt_he_value(
    serialized_hex: str,
    role: UserRole
):

    """
    Réservé aux rôles admin/steward.
    """

    try:

        result = he_manager.decrypt(
            bytes.fromhex(serialized_hex),
            role.value
        )

        return {
            "decrypted": result
        }

    except HEAccessDenied as e:

        raise HTTPException(
            status_code=403,
            detail=str(e)
        )


# ====================================================================
# TOKEN VAULT
# ====================================================================

@app.post("/vault/detokenize")
async def detokenize(
    token: str,
    role: UserRole
):

    try:

        value = await vault.detokenize(
            token,
            role.value
        )

        return {
            "value": value
        }

    except PermissionError as e:

        raise HTTPException(
            status_code=403,
            detail=str(e)
        )

    except KeyError:

        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )


# ====================================================================
# MAIN
# ====================================================================

if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("🔒 ETHIMASK SERVICE (MONGO) - Tâche 9")
    print("=" * 60)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8009,
        reload=True
    )
