import time
import logging
import json
import traceback
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from prometheus_client import make_asgi_app, Counter, Histogram

from pipeline import process_batch, GRAPH, HISTORY, GRAPH_LOADED_AT

# Setup Logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name
        }
        if hasattr(record, "extra"):
            log_record.update(record.extra)
        return json.dumps(log_record)

logger = logging.getLogger("aiops_serving")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Prometheus metrics
aiops_incident_requests_total = Counter('aiops_incident_requests_total', 'Total requests', ['status'])
aiops_incident_latency_seconds = Histogram('aiops_incident_latency_seconds', 'Request latency')
aiops_llm_failures_total = Counter('aiops_llm_failures_total', 'LLM call failures', ['reason'])
aiops_clusters_per_request = Histogram('aiops_clusters_per_request', 'Clusters per request')

app = FastAPI()
app.mount('/metrics', make_asgi_app())

# Middleware for latency
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    logger.info("request", extra={"extra": {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": duration_ms
    }})
    return response

# Schemas
class Alert(BaseModel):
    id: str
    ts: str
    service: str
    metric: str
    severity: str
    value: float
    threshold: float | None = None
    labels: dict = {}

class IncidentRequest(BaseModel):
    alerts: list[Alert]

class RootCause(BaseModel):
    service: str
    class_name: str = Field(alias="class")
    confidence: float

class Cluster(BaseModel):
    cluster_id: str
    alert_count: int
    services: list[str]
    alert_ids: list[str]
    time_range: list[str]
    max_severity: str
    fingerprints: list[str]

class IncidentResponse(BaseModel):
    clusters: list[Cluster]
    root_cause: RootCause
    recommended_actions: list[str]
    similar_incidents: list[str]

# Endpoints
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    checks = {}
    if GRAPH.number_of_nodes() == 0:
        checks['graph'] = "Graph not loaded"
    if len(HISTORY) == 0:
        checks['history'] = "History not loaded"
        
    if checks:
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ok"}

@app.get("/version")
def version():
    return {
        "app": "1.2.0",
        "graph_version": "g-2026060801",
        "graph_loaded_at": GRAPH_LOADED_AT,
        "graph_source": "otel-tempo",
        "graph_node_count": GRAPH.number_of_nodes(),
        "graph_edge_count": GRAPH.number_of_edges(),
        "pipeline_config": {
            "gap_sec": 120,
            "max_hop": 2,
            "rca_method": "graph+retrieval"
        }
    }

@app.post("/incident", response_model=IncidentResponse)
def handle_incident(req: IncidentRequest):
    if len(req.alerts) == 0:
        raise HTTPException(status_code=400, detail="Alerts array cannot be empty")
        
    with aiops_incident_latency_seconds.time():
        try:
            alerts_dict = [a.model_dump() for a in req.alerts]
            res = process_batch(alerts_dict)
            
            cluster_count = len(res['clusters'])
            aiops_clusters_per_request.observe(cluster_count)
            
            logger.info('Processed incident', extra={'extra': {
                'cluster_count': cluster_count,
                'root_cause': res['root_cause']['service'],
                'confidence': res['root_cause']['confidence']
            }})
            
            aiops_incident_requests_total.labels(status='success').inc()
            
            # Pack results to match IncidentResponse schema
            rc = res['root_cause']
            root_cause_obj = RootCause(
                service=rc['service'],
                **{"class": rc['class']},
                confidence=rc['confidence']
            )
            
            return IncidentResponse(
                clusters=res['clusters'],
                root_cause=root_cause_obj,
                recommended_actions=res['recommended_actions'],
                similar_incidents=res['similar_incidents']
            )
        except Exception as e:
            aiops_incident_requests_total.labels(status='error').inc()
            logger.error("Pipeline error", extra={"extra": {"traceback": traceback.format_exc()}})
            raise HTTPException(status_code=500, detail="Internal server error while processing pipeline")
