# AIOps W2 — RCA & Smart Response
## W2-D3: Model Serving — Đưa Pipeline Lên Production
*15 min read | 3042 words*

---

## Mở đầu: Từ Notebook đến Service

Bạn đã có 2 module chạy được trong notebook:
1. Gom alert thành cluster.
2. Tìm root cause.

Tuy nhiên, notebook không phải là môi trường production. Hôm nay, chúng ta sẽ biến nó thành một API service — một hệ thống monitoring có thể POST batch alert vào và nhận lại incident report.

**Serving Architecture:**  
`Alert batch` → `FastAPI` → `3-layer pipeline` → `JSON response`

Khi nói “serving” trong AIOps, không chỉ là serve ML model, mà là serve toàn bộ pipeline (correlation + RCA + LLM call) như 1 unit có:
- HTTP endpoint
- Latency budget (p99 ≤ 10s)
- Health check
- Versioning + rollback
- Self-monitoring

Mục tiêu cuối ngày là bạn có file `serve.py` chạy được, biến pipeline trong notebook thành HTTP service nhận request từ bên ngoài.

> **Quy tắc vàng:** Code trong notebook khác code production ở 3 thứ — concurrency, failure handling, observability. Đừng đợi đến lúc lên production mới nghĩ về 3 thứ này.

---

## 1. Framework — FastAPI vs Flask vs BentoML

Dưới đây là 3 framework phổ biến cho Python serving và sự so sánh:

| Framework | Khi nào dùng | Ưu điểm | Nhược điểm |
| :--- | :--- | :--- | :--- |
| **Flask** | Quick prototype | Đơn giản, ít magic | Sync only, không validate input native |
| **FastAPI** ⭐ | Production API, mixed workload | Async, Pydantic validation, OpenAPI auto, type hints | Magic hơn Flask một chút |
| **BentoML** | ML model–centric | Model versioning, batching native, Yatai deploy | Học curve cao, overhead cho non-ML workload |

Trong bài tập này, chúng ta dùng **FastAPI**. Lý do: 
- Pipeline có LLM call (IO-bound → hưởng lợi từ async).
- Input cần schema rõ ràng (Pydantic dễ dùng).
- Test dễ dàng bằng OpenAPI auto-document.

```bash
uv pip install fastapi uvicorn pydantic
```

---

## 2. Endpoint cơ bản

### 2.1 Skeleton — Các thành phần cần thiết

File `serve.py` sẽ khởi tạo FastAPI app và 2 schema sử dụng Pydantic:

- **Input schema (`IncidentRequest`)**: List của Alert, mỗi alert có 8 field (`id`, `ts`, `service`, `metric`, `severity`, `value`, `threshold`, `labels`).
- **Output schema (`IncidentResponse`)**: Danh sách `clusters`, `root_cause` object, danh sách `recommended_actions`, danh sách `similar_incidents`.

Hai endpoint cần có:
- `GET /healthz`: Trả về `{"status": "ok"}`. Không validate gì cả, chỉ để load balancer biết process còn sống.
- `POST /incident`: Nhận `IncidentRequest`, gọi pipeline và trả về `IncidentResponse`. Nếu alerts rỗng → raise `HTTPException(400)`.

Chạy server với lệnh:
```bash
uvicorn serve:app --port 8000 --reload
```

### 2.2 Pydantic Validation — Không phải Optional

Khi định nghĩa schema bằng BaseModel, Pydantic tự động kiểm tra mọi field lúc request đến. Nếu thiếu field bắt buộc, sai type, hoặc value ngoài range, nó sẽ tự động trả về lỗi `422 Unprocessable Entity` với detail chỉ rõ field nào sai. Bạn không cần tự code validation. Đảm bảo endpoint luôn trả về 400/422 với message cụ thể khi input sai, không bao giờ là 500.

---

## 3. Topology — Service Graph là Input

Pipeline correlation và RCA của bạn sử dụng service graph như 1 input. Trên production, graph có lifecycle riêng (stale, version, scale).

### 3.1 4 Nguồn sinh Service Graph

| Source | Cách hoạt động | Điểm mạnh | Điểm yếu |
| :--- | :--- | :--- | :--- |
| **Distributed tracing** *(OTel/Jaeger)* | Aggregate spans qua N phút → edge weight | Auto-discover, real-time, weight theo traffic thật | Cần instrument app, sampling rate ảnh hưởng accuracy |
| **Service mesh** *(Istio/Linkerd)* | Log mọi request L7 → metric `istio_requests_total` | Không cần thay đổi code app, 100% coverage traffic | Chỉ thấy L7, miss raw TCP |
| **Manual / IaC** | Tự điền `services.json`, OpenAPI specs | Source-of-truth cho < 20 services | Dễ bị drift nhanh (1 tuần có thể sai) |
| **Code analysis** | Static AST parse client init hoặc eBPF capture | Bắt được rare path không có trong traffic mẫu | Tooling phức tạp, false positive cao |

> Trong setup hiện tại, chúng ta dùng **"Manual"** (file JSON tĩnh) vì có ít hơn 20 service. Ở scale lớn (100+), cần chuyển sang tracing hoặc mesh.

### 3.2 Graph Freshness — Silent Failure khi Stale
- Nếu team deploy service mới mà không reload graph, topology correlation sẽ bị lệch.
- **Giải pháp**:
  1. Reload mỗi N phút: Worker thread tự động đọc lại file mỗi 5 phút.
  2. Subscribe event: Lắng nghe event từ registry để reload ngay lập tức (zero lag).

### 3.3 Graph như một "Model" — Versioning
Khi cluster ratio đột nhiên kém, có thể do code bị regress hoặc do graph mới gây ra. Endpoint `/version` nên trả về thông tin của graph:

```json
GET /version
{
  "app": "1.2.0",
  "graph_version": "g-2026060801",
  "graph_loaded_at": "2026-06-08T03:14:22Z",
  "graph_node_count": 87,
  "graph_edge_count": 142
}
```

### 3.4 Scale Performance (9 vs 1000 Service)

| Operation | Cost ở 9 service | Cost ở 1000 service | Đánh giá |
| :--- | :--- | :--- | :--- |
| **PageRank** (reverse subgraph) | < 1ms | ~50ms | OK, tiếp tục dùng |
| **All-pairs shortest path** | < 1ms | ~1s (O(V³)) | **KHÔNG ỔN**, cần cache hoặc index |
| **Subgraph extraction** | < 1ms | ~10ms | OK |
| **Community detection** | < 1ms | ~200ms | OK nếu chạy offline mỗi N phút |

---

## 4. Chain 3 Layer Lại Cùng Nhau

**Glue layer (`pipeline.py`)** ráp 3 module lại:

- **Khởi tạo:** Load service graph và incident history từ dataset vào cache global, chạy một lần khi import.
- **`process_batch(alerts)`:**
  1. Gọi `correlate` từ Layer 1 → `list cluster`. Nếu rỗng, return early.
  2. Pick cluster lớn nhất làm primary incident.
  3. Gọi `run_rca` từ Layer 2 → nhận dict (`root_cause`, `confidence`, `actions`, `similar_incidents`).
  4. Đóng gói lại thành định dạng match với `IncidentResponse`.

- **Endpoint `/incident`:** Dùng `model_dump()` chuyển input Pydantic thành plain dict. Bọc quá trình bằng `try/except`, nếu lỗi log full traceback và trả ra HTTPException 500 (không bao giờ leak traceback cho client).

---

## 5. Latency Budget

### 5.1 Đo trước, tối ưu sau
LLM call thường chiếm tới 91% tổng thời gian request. Hãy thêm Middleware trong FastAPI bằng hàm tính `time.perf_counter()` và đưa kết quả vào header `X-Response-Time-Ms` cùng log structured.

### 5.2 Tối ưu cho LLM call — 4 kỹ thuật

| Kỹ thuật | Cách thực hiện | Hiệu quả |
| :--- | :--- | :--- |
| **Cache** | Hash prompt → `cachetools.TTLCache`. | Hit rate cao cho cùng pattern (20-30%). |
| **Async + Concurrent** | `asyncio.gather` gọi song song nhiều LLM. | Khi enrich nhiều cluster cùng lúc. |
| **Smaller Model** | Chuyển từ `gpt-4o` sang `gpt-4o-mini`. | Task RCA cần cấu trúc JSON, model nhỏ nhanh hơn 2x và rẻ hơn 5x. |
| **Skip LLM** | Nếu confidence của Graph ≥ 0.9, bỏ qua LLM. | 60-70% sự cố rõ ràng không cần LLM tốn kém. |

### 5.3 Bắt buộc cấu hình Timeout
Mọi network call (vd OpenAI SDK hoặc request HTTP) đều **phải có timeout** để tránh việc thread/connection bị treo vĩnh viễn (hang forever).

---

## 6. Concurrency & Khởi chạy

### 6.1 Worker vs Concurrency
Mặc định FastAPI chạy 1 worker. Production nên chạy nhiều workers:
```bash
uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6.2 Race Condition với Shared State
Nhiều worker sẽ dẫn tới duplicate state in-memory. Giải pháp chuẩn là dùng cache bên ngoài (Redis) hoặc chấp nhận stateless/single-worker (cần document rõ trong file thiết kế).

---

## 7. Health Check và Readiness

- `/healthz`: Liveness probe. Chỉ để check ứng dụng (process) còn sống.
- `/readyz`: Readiness probe. Check dependency. Ví dụ kiểm tra xem graph đã load xong hay lịch sử incident đã có. Nếu dependencies thiếu, return 503 để k8s không gởi traffic tới.

---

## 8. Tự Giám Sát (Self-Monitoring)

Sử dụng thư viện `prometheus-client` để xuất metrics cho `/metrics`:
- `aiops_incident_requests_total` (Counter, status = success/error)
- `aiops_incident_latency_seconds` (Histogram)
- `aiops_llm_failures_total` (Counter, theo reason)
- `aiops_clusters_per_request` (Histogram)

Log ra **JSON format** để dễ đẩy vào ELK/Loki:
```json
{
  "ts": "2026-06-12 09:45:00",
  "level": "INFO",
  "msg": "Processed incident",
  "cluster_count": 3,
  "root_cause": "payment-svc",
  "confidence": 0.84
}
```

---

## Bài Tập Thực Hành: Code `serve.py` + `DESIGN.md`

### 1. Requirements & Quy ước nộp bài
- Cấu trúc thư mục: `aiops-<tên>/w2/d3/`
- Tên files bắt buộc: `serve.py`, `DESIGN.md`, `SUBMIT.md`

### 2. Các Bước (Steps)
1. Khởi tạo `serve.py` với API FastAPI.
2. Thêm endpoint `/healthz`, `/readyz`.
3. Thêm Latency Middleware.
4. Đấu nối `correlate` từ d1 và `run_rca` từ d2 tạo thành End-to-End Pipeline.
5. Viết **`DESIGN.md` (≥ 100 từ)** giải thích architecture, latency budget, xử lý concurrency, lý do dùng FastAPI.
6. Viết **`SUBMIT.md`** trả lời 3 câu hỏi EOD.

### 3. EOD Checkpoint (Trả lời trong `SUBMIT.md`)
1. **Latency thực:** Phase nào chiếm thời gian nhất? Cái nào scale tuyến tính với input, cái nào là fixed cost?
2. **Concurrency / LLM Failure:** Nếu test concurrency bằng lệnh `ab`, bạn thấy gì ở hệ thống? Bạn có giải pháp fallback nào không?
3. **Health vs Ready:** Phân biệt chúng? Nếu LLM down, ready probe có nên fail hay pass?

*(Nguồn: My Learning Notes - AIOps)*
