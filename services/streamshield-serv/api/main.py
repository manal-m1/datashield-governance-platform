"""
StreamShield API

Responsabilités :
- récupérer les datasets nettoyés depuis Cleaning Service
- récupérer les métadonnées depuis Apache Atlas
- analyser les combinaisons de quasi-identifiants
- calculer le fuzzy risk score
- enregistrer les risques dans MongoDB
- consulter les risques
- gérer les seuils par domaine
"""

import os
import logging
import time
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

import requests
import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from backend.database.mongodb import db
from bson import ObjectId
from detection.threshold_manager import ThresholdManager
from detection.fuzzy_risk_scorer import FuzzyRiskScorer
from detection.combination_detector import CombinationDetector, DetectionConfig
from detection.field_sensitivity_repository import load_field_sensitivity

from atlas_integration.client import AtlasClient
from detection.candidate_field_selector import select_candidate_fields
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# ============================================================================
# LOGGING
# ============================================================================


def serialize_mongo_object(obj):
    if isinstance(obj, ObjectId):
        return str(obj)

    if isinstance(obj, dict):
        return {
            key: serialize_mongo_object(value)
            for key, value in obj.items()
        }

    if isinstance(obj, list):
        return [
            serialize_mongo_object(item)
            for item in obj
        ]

    return obj
# ============================================================================
# CONFIGURATION
# ============================================================================
logger = logging.getLogger("streamshield.api")
CLEANING_SERVICE_URL = os.getenv(
    "CLEANING_SERVICE_URL",
    "http://cleaning-service:8004"
)

CLEANING_TIMEOUT = float(
    os.getenv("CLEANING_TIMEOUT", "30")
)


# ============================================================================
# CLIENTS
# ============================================================================

atlas_client = AtlasClient()

threshold_manager = ThresholdManager(db)


# ============================================================================
# FASTAPI
# ============================================================================

app = FastAPI(
    title="StreamShield API",
    description=(
        "Détection du risque de ré-identification par combinaison "
        "de quasi-identifiants"
    ),
    version="1.0.0",
)


# ============================================================================
# MÉTRIQUES PROMETHEUS
# Défini une seule fois, ici, juste après la création de `app` — évite tout
# risque de double-enregistrement (Prometheus refuse deux métriques du même
# nom dans le même registre) et tout risque d'utiliser `app` avant sa
# définition.
# ============================================================================

RISK_COMBINATIONS_DETECTED = Counter(
    "streamshield_risk_combinations_detected_total",
    "Nombre de combinaisons à risque détectées",
    ["domain"]
)

ANALYSIS_LATENCY = Histogram(
    "streamshield_analysis_latency_seconds",
    "Latence bout-en-bout d'une analyse de dataset (récupération + scoring + stockage)",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60]
)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ============================================================================
# MODELS
# ============================================================================

class ThresholdUpdate(BaseModel):
    domain: str
    threshold: float = Field(..., ge=0.0, le=1.0)


# ============================================================================
# CLEANING SERVICE
# ============================================================================

async def get_clean_dataset(dataset_id: str) -> Dict[str, Any]:
    """
    Récupère un dataset nettoyé depuis le Cleaning Service.

    StreamShield ne lit donc plus directement la collection
    clean_datasets pour récupérer les données.

    Flux :

        StreamShield
              ↓
        Cleaning Service
              ↓
            MongoDB
    """

    url = (
        f"{CLEANING_SERVICE_URL}"
        f"/datasets/{dataset_id}/full-scan-data"
    )

    try:
        logger.info(
            f"Récupération du dataset nettoyé depuis Cleaning : "
            f"{dataset_id}"
        )

        response = requests.get(
            url,
            timeout=CLEANING_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            raise HTTPException(
                status_code=422,
                detail="Cleaning Service a retourné une réponse vide"
            )

        return data

    except requests.exceptions.Timeout:
        logger.error(
            f"Timeout lors de la récupération du dataset "
            f"{dataset_id} depuis Cleaning Service"
        )

        raise HTTPException(
            status_code=504,
            detail="Cleaning Service ne répond pas"
        )

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 502

        logger.error(
            f"Erreur Cleaning Service : "
            f"{status_code} - {e.response.text if e.response else ''}"
        )

        if status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset '{dataset_id}' introuvable dans Cleaning Service"
            )

        raise HTTPException(
            status_code=502,
            detail="Erreur lors de la récupération du dataset depuis Cleaning Service"
        )

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Cleaning Service indisponible : {e}"
        )

        raise HTTPException(
            status_code=503,
            detail="Cleaning Service indisponible"
        )


# ============================================================================
# ATLAS
# ============================================================================

def resolve_domain(
    dataset_name: str,
    manual_domain: Optional[str]
) -> Tuple[str, str]:
    """
    Détermine le domaine métier.

    Priorité :
        1. domaine fourni manuellement
        2. Apache Atlas
        3. nom du dataset
    """

    if manual_domain:
        return manual_domain, "manual"

    try:
        metadata = atlas_client.get_dataset_metadata(dataset_name)

        if metadata:
            attributes = metadata.get("attributes", {})

            # Plusieurs possibilités selon la façon dont
            # le domaine est stocké dans Atlas.
            atlas_domain = (
                attributes.get("domain")
                or attributes.get("businessDomain")
                or attributes.get("business_domain")
            )

            if atlas_domain:
                return atlas_domain, "atlas"

    except Exception as e:
        logger.warning(
            f"Atlas indisponible pour résoudre le domaine "
            f"du dataset '{dataset_name}' : {e}"
        )

    return dataset_name, "fallback"


def get_atlas_metadata(
    dataset_name: str
) -> Optional[Dict[str, Any]]:
    """
    Récupère les métadonnées du dataset depuis Apache Atlas.
    """

    try:
        metadata = atlas_client.get_dataset_metadata(dataset_name)

        if metadata:
            logger.info(
                f"Métadonnées Atlas récupérées pour '{dataset_name}'"
            )

        else:
            logger.warning(
                f"Aucune métadonnée Atlas pour '{dataset_name}'"
            )

        return metadata

    except Exception as e:
        logger.warning(
            f"Impossible de récupérer les métadonnées Atlas "
            f"pour '{dataset_name}' : {e}"
        )

        return None


# ============================================================================
# HEALTH
# ============================================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "db_connected": db is not None,
        "cleaning_service": CLEANING_SERVICE_URL,
    }
@app.get("/datasets")
async def list_cleaned_datasets():
    """
    Récupère les datasets disponibles depuis Cleaning Service.
    Le contenu réel du dataset sera récupéré ensuite via
    /full-scan-data/{dataset_id}.
    """

    url = f"{CLEANING_SERVICE_URL}/datasets"

    try:
        response = requests.get(
            url,
            timeout=CLEANING_TIMEOUT
        )

        response.raise_for_status()

        datasets = response.json()

        if not isinstance(datasets, list):
            raise HTTPException(
                status_code=502,
                detail="Format inattendu depuis Cleaning Service"
            )

        logger.info(
            "Datasets récupérés depuis Cleaning : %d",
            len(datasets)
        )

        # Ne pas filtrer sur le status.
        # Certains datasets sont encore marqués processing_pipeline
        # alors que /full-scan-data fonctionne correctement.
        available_datasets = [
            dataset
            for dataset in datasets
            if dataset.get("id") and dataset.get("name")
        ]

        logger.info(
            "Datasets disponibles pour StreamShield : %d",
            len(available_datasets)
        )

        return {
            "datasets": available_datasets
        }

    except requests.Timeout:
        logger.error(
            "Timeout lors de la récupération des datasets depuis Cleaning"
        )

        raise HTTPException(
            status_code=504,
            detail="Timeout lors de la récupération des datasets depuis Cleaning Service"
        )

    except requests.RequestException as e:
        logger.error(
            "Impossible de contacter le Cleaning Service : %s",
            e
        )

        raise HTTPException(
            status_code=503,
            detail="Cleaning Service indisponible"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            "Erreur inattendue lors de la récupération des datasets"
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
# ============================================================================
# DATASETS
# ============================================================================

# 
# ============================================================================
# RISKS
# ============================================================================

@app.get("/risks")
async def list_risks(
    domain: Optional[str] = None,
    dataset_id: Optional[str] = None,
    limit: int = 50,
    min_score: float = 0.0
):

    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Base de données non connectée"
        )

    query = {
        "score": {
            "$gte": min_score
        }
    }

    if domain:
        query["domain"] = domain

    if dataset_id:
        query["dataset_id"] = dataset_id

    cursor = (
        db.streamshield_risk_events
        .find(query)
        .sort("timestamp", -1)
        .limit(limit)
    )

    events = []

    async for doc in cursor:

        doc["_id"] = str(doc["_id"])

        events.append(doc)

    return {
        "count": len(events),
        "filters": {
            "domain": domain,
            "dataset_id": dataset_id,
            "min_score": min_score
        },
        "risks": events
    }


# ============================================================================
# RISKS SUMMARY
# ============================================================================

@app.get("/risks/summary")
async def risks_summary(
    domain: Optional[str] = None,
    dataset_id: Optional[str] = None
):

    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Base de données non connectée"
        )

    match = {}

    if domain:
        match["domain"] = domain

    if dataset_id:
        match["dataset_id"] = dataset_id

    pipeline = [
        {
            "$match": match
        },
        {
            "$group": {
                "_id": "$fields",
                "occurrences": {
                    "$sum": 1
                },
                "avg_score": {
                    "$avg": "$score"
                },
                "min_k_observed": {
                    "$min": "$k"
                }
            }
        },
        {
            "$sort": {
                "occurrences": -1
            }
        },
        {
            "$limit": 20
        }
    ]

    results = [
        doc
        async for doc
        in db.streamshield_risk_events.aggregate(pipeline)
    ]

    for result in results:

        result["fields"] = result.pop("_id")

        result["avg_score"] = round(
            result["avg_score"],
            4
        )

    return {
        "summary": results
    }


# ============================================================================
# THRESHOLD
# ============================================================================

@app.get("/config/threshold")
async def get_threshold(domain: str):

    threshold = await threshold_manager.get_threshold(domain)

    return {
        "domain": domain,
        "threshold": threshold
    }


@app.get("/config/thresholds")
async def list_thresholds():

    return {
        "thresholds": await threshold_manager.list_all()
    }


@app.post("/config/threshold")
async def set_threshold(
    update: ThresholdUpdate
):

    try:

        await threshold_manager.set_threshold(
            update.domain,
            update.threshold
        )

    except ValueError as e:

        raise HTTPException(
            status_code=422,
            detail=str(e)
        )

    return {
        "status": "updated",
        "domain": update.domain,
        "threshold": update.threshold
    }


# ============================================================================
# ANALYZE DATASET
# ============================================================================
@app.post("/analyze/{dataset_id}")
async def analyze_dataset(
    dataset_id: str,
    fields: Optional[str] = None,
    max_depth: int = 2,
    domain: Optional[str] = None
):
    _start_time = time.monotonic()

    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Base de données non connectée"
        )

    # ========================================================================
    # 1. RÉCUPÉRER LE DATASET DEPUIS CLEANING
    # ========================================================================

    logger.info(
        "Début analyse StreamShield | dataset_id=%s",
        dataset_id
    )

    cleaning_response = await get_clean_dataset(dataset_id)

    records = cleaning_response.get("data", [])

    if not records:
        raise HTTPException(
            status_code=422,
            detail="Dataset vide ou indisponible"
        )

    dataset_name = (
        cleaning_response.get("filename")
        or cleaning_response.get("name")
        or dataset_id
    )

    logger.info(
        "Dataset récupéré | name=%s | records=%d",
        dataset_name,
        len(records)
    )

    # ========================================================================
    # 2. ATLAS
    # ========================================================================

    atlas_metadata = get_atlas_metadata(dataset_name)

    # ========================================================================
    # 3. DOMAINE
    # ========================================================================

    resolved_domain, domain_source = resolve_domain(
        dataset_name,
        domain
    )

    logger.info(
        "Domaine résolu | domain=%s | source=%s",
        resolved_domain,
        domain_source
    )

    # ========================================================================
    # 4. CHARGER LA SENSIBILITÉ
    # ========================================================================

    field_sensitivity = await load_field_sensitivity()

    scorer = FuzzyRiskScorer(
        field_sensitivity=field_sensitivity
    )

    # Configuration fuzzy + règles MongoDB
    await scorer.load_fuzzy_configuration()

    logger.info(
        "Fuzzy scorer prêt | threshold=%.3f | min_sample_size=%d",
        scorer.threshold,
        scorer.min_sample_size
    )

    # ========================================================================
    # 5. CHAMPS CANDIDATS
    # ========================================================================

    if fields:

        candidate_fields = tuple(
            field.strip()
            for field in fields.split(",")
            if field.strip()
        )

    else:

        candidate_fields = select_candidate_fields(
            records,
            max_candidates=12
        )

    logger.info(
        "Champs candidats : %s",
        candidate_fields
    )

    # ========================================================================
    # 6. DÉTECTION DES COMBINAISONS
    # ========================================================================

    config = DetectionConfig(
        candidate_fields=candidate_fields,
        max_depth=max_depth
    )

    detector = CombinationDetector(
        scorer=scorer,
        config=config
    )

    all_results = detector.detect(records)

    logger.info(
        "Combinaisons testées : %d",
        len(all_results)
    )

    # ========================================================================
    # 7. CONVERTIR LES RÉSULTATS
    # ========================================================================

    results = []

    for result in all_results:

        result_data = {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,

            "domain": resolved_domain,
            "domain_source": domain_source,

            "fields": list(result.fields),

            "k": result.k,
            "uniqueness": result.uniqueness,
            "avg_sensitivity": result.avg_sensitivity,

            "score": round(result.score, 6),

            "triggered": bool(result.triggered),

            "sample_size": result.sample_size,

            "atlas_metadata_available": (
                atlas_metadata is not None
            ),

            "timestamp": datetime.utcnow()
        }

        results.append(result_data)

    # ========================================================================
    # 8. SÉPARER LES RISQUES
    # ========================================================================

    triggered_results = [
        result
        for result in results
        if result["triggered"]
    ]

    # ========================================================================
    # 9. STOCKAGE MONGODB — historique complet des scores calculés
    # (collection streamshield_risk_scores : TOUTES les combinaisons testées,
    # déclenchées ou non ; remplace l'historique précédent de ce dataset)
    # ========================================================================

    if results:

        # On supprime les anciens scores de ce dataset
        # afin que la collection représente la dernière analyse.
        await db.streamshield_risk_scores.delete_many(
            {
                "dataset_id": dataset_id
            }
        )

        await db.streamshield_risk_scores.insert_many(
            results
        )

        # ⚠️ insert_many() MUTE chaque dict de `results` en y ajoutant
        # un champ "_id" (ObjectId) — non sérialisable en JSON par FastAPI.
        # On le retire immédiatement après l'insertion, avant que la réponse
        # HTTP ne soit construite (results_sorted référence les mêmes objets).
        for r in results:
            r.pop("_id", None)

        logger.info(
            "Scores enregistrés MongoDB | dataset_id=%s | count=%d",
            dataset_id,
            len(results)
        )

    # ========================================================================
    # 10. ENREGISTRER LES RISQUES DÉCLENCHÉS
    # (collection streamshield_risk_events : uniquement triggered=True,
    # lue par /risks et /risks/summary)
    # ========================================================================

    if triggered_results:

        risk_events = []

        for result in triggered_results:

            event = {
                "dataset_id": result["dataset_id"],
                "dataset_name": result["dataset_name"],

                "domain": result["domain"],
                "domain_source": result["domain_source"],

                "fields": result["fields"],

                "k": result["k"],
                "uniqueness": result["uniqueness"],
                "avg_sensitivity": result["avg_sensitivity"],

                "score": result["score"],
                "sample_size": result["sample_size"],

                "atlas_metadata_available": (
                    result["atlas_metadata_available"]
                ),

                "timestamp": result["timestamp"]
            }

            risk_events.append(event)

        await db.streamshield_risk_events.insert_many(
            risk_events
        )

        # Même précaution que pour `results` ci-dessus : insert_many()
        # mute risk_events en y ajoutant "_id" (ObjectId). risk_events
        # n'est pas renvoyé dans la réponse HTTP actuelle, mais on nettoie
        # quand même pour éviter un piège si un jour on l'expose.
        for e in risk_events:
            e.pop("_id", None)

        logger.info(
            "Risques enregistrés | dataset_id=%s | count=%d",
            dataset_id,
            len(risk_events)
        )

    # ========================================================================
    # 11. MÉTRIQUES PROMETHEUS
    # Placé ici, APRÈS le calcul de triggered_results (section 8) — jamais
    # avant, sous peine de UnboundLocalError.
    # ========================================================================

    analysis_duration = time.monotonic() - _start_time

    ANALYSIS_LATENCY.observe(analysis_duration)

    logger.info(
        "Analyse StreamShield terminée | dataset_id=%s | duration=%.3fs",
        dataset_id,
        analysis_duration
    )

    if triggered_results:
        RISK_COMBINATIONS_DETECTED.labels(domain=resolved_domain).inc(len(triggered_results))

    # ========================================================================
    # 12. STATISTIQUES
    # ========================================================================

    scores = [
        result["score"]
        for result in results
    ]

    max_score = max(scores) if scores else 0.0

    avg_score = (
        sum(scores) / len(scores)
        if scores
        else 0.0
    )

    # Classement décroissant
    results_sorted = sorted(
        results,
        key=lambda x: x["score"],
        reverse=True
    )

    # ========================================================================
    # 13. RÉPONSE FRONTEND
    # ========================================================================

    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "domain": resolved_domain,
        "domain_source": domain_source,
        "records_analyzed": len(records),
        "combinations_tested": len(results),
        "combinations_at_risk": len(triggered_results),
        "threshold": scorer.threshold,
        "max_score": round(max_score, 6),
        "average_score": round(avg_score, 6),
        "atlas_metadata": serialize_mongo_object(atlas_metadata),
        "results": results_sorted

    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8010,
        reload=True
    )