from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI()

class Alert(BaseModel):
    id: str
    ts: int         
    service: str     
    metric: str      
    severity: str    
    value: float     
    threshold: float 
    labels: Dict[str, str] 

class IncidentRequest(BaseModel):
    alerts: List[Alert]

class IncidentResponse(BaseModel):
    clusters: List[Any]
    root_cause: Dict[str, Any]
    recommended_actions: List[str]
    similar_incidents: List[Any]

@app.get("/healthz")
def health_check():
    return {"status": "ok"}

@app.post("/incident")
def process_incident(request: IncidentRequest):
    if not request.alerts:
        raise HTTPException(status_code=400, detail="Alerts list cannot be empty")
    mock_result = {
        "clusters": [["alert_id_1", "alert_id_2"]],
        "root_cause": {
            "suspected_service": "database",
            "reason": "Connection pool exhausted"
        },
        "recommended_actions": [
            "Restart the database connection pool",
            "Scale up database replicas"
        ],
        "similar_incidents": ["INC-8821A", "INC-9912B"]
    }
    
    return mock_result
