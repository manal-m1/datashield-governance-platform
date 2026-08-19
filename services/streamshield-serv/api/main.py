"""
StreamShield API - Consultation des risques et configuration des seuils

Couvre les 2 user stories administrateur restantes de la Tâche 2 :
  - "je veux visualiser les combinaisons de champs jugées à risque"
      -> GET /risks
  - "je veux ajuster le seuil de risque par domaine métier"
      -> GET/POST /config/threshold
"""
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.database.mongodb import db
from detection.threshold_manager import ThresholdManager

app = FastAPI(
    title="StreamShield API",
    description="Consultation des combinaisons à risque et configuration des seuils par domaine",
    version="1.0.0",
)

threshold_manager = ThresholdManager(db)


class ThresholdUpdate(BaseModel):
    domain: str
    threshold: float = Field(..., ge=0.0, le=1.0)


@app.get("/health")
async def health():
    return {"status": "healthy", "db_connected": db is not None}


@app.get("/risks")
async def list_risks(domain: Optional[str] = None, limit: int = 50, min_score: float = 0.0):
    """
    Liste les combinaisons à risque détectées récemment, les plus récentes
    d'abord -- répond à la user story administrateur "je veux visualiser les
    combinaisons de champs jugées à risque afin de prioriser les actions".
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Base de données non connectée")

    query = {"score": {"$gte": min_score}}
    if domain:
        query["domain"] = domain

    cursor = db.streamshield_risk_events.find(query).sort("timestamp", -1).limit(limit)
    events = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        events.append(doc)

    return {"count": len(events), "filters": {"domain": domain, "min_score": min_score}, "risks": events}


@app.get("/risks/summary")
async def risks_summary(domain: Optional[str] = None):
    """
    Vue agrégée : quelles combinaisons de champs reviennent le plus souvent
    à risque -- aide à prioriser les actions de protection (Tâche 3) sur les
    combinaisons les plus récurrentes plutôt que les plus récentes seulement.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Base de données non connectée")

    match_stage = {"$match": {"domain": domain}} if domain else {"$match": {}}
    pipeline = [
        match_stage,
        {"$group": {
            "_id": "$fields",
            "occurrences": {"$sum": 1},
            "avg_score": {"$avg": "$score"},
            "min_k_observed": {"$min": "$k"},
        }},
        {"$sort": {"occurrences": -1}},
        {"$limit": 20},
    ]
    results = [doc async for doc in db.streamshield_risk_events.aggregate(pipeline)]
    for r in results:
        r["fields"] = r.pop("_id")
        r["avg_score"] = round(r["avg_score"], 4)
    return {"summary": results}


@app.get("/config/threshold")
async def get_threshold(domain: str):
    """Consulte le seuil de risque actuellement configuré pour un domaine."""
    threshold = await threshold_manager.get_threshold(domain)
    return {"domain": domain, "threshold": threshold}


@app.get("/config/thresholds")
async def list_thresholds():
    """Liste tous les seuils configurés, par domaine."""
    return {"thresholds": await threshold_manager.list_all()}


@app.post("/config/threshold")
async def set_threshold(update: ThresholdUpdate):
    """
    Ajuste le seuil de déclenchement d'alerte pour un domaine -- répond à la
    user story administrateur "je veux ajuster le seuil de risque pour
    l'adapter au niveau de sensibilité de chaque domaine métier".
    Pris en compte par les consumers actifs sous 10 cycles de détection
    (rafraîchissement périodique, pas de redémarrage nécessaire).
    """
    try:
        await threshold_manager.set_threshold(update.domain, update.threshold)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "updated", "domain": update.domain, "threshold": update.threshold}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8010, reload=True)