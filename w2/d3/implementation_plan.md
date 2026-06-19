# Model Serving — Đưa Pipeline Lên Production

Dựa vào file `instruction.md`, tôi đã nắm được yêu cầu của bài tập W2-D3 là chuyển đổi các module RCA từ notebook thành một API Service thực thụ sử dụng FastAPI.

## Proposed Changes

Tôi sẽ tạo các file sau trong thư mục `w2/d3/`:

### 1. File Code Chính
*   **`pipeline.py` (Glue Layer):** 
    *   Sẽ chứa logic gộp của Layer 1 (Correlate) từ `w2/d1/` và Layer 2 (RCA) từ `w2/d2/`. Vì code Layer 1 và 2 hiện nằm trong file `.ipynb` khó import trực tiếp, tôi sẽ trích xuất các hàm cần thiết (`fingerprint`, `correlate`, `build_graph`, `calculate_graph_temporal_candidates`, `retrieve_similar_incidents`, `classify_rca`) vào file này.
    *   Load sẵn `services.json` và `incidents_history.json` ở cấp module để cache vào memory.
*   **`serve.py` (FastAPI App):**
    *   Khai báo Pydantic schemas: `IncidentRequest` và `IncidentResponse`.
    *   Tạo middleware để đo lường và log `X-Response-Time-Ms`.
    *   Tạo các endpoint: `/healthz`, `/readyz`, và `/version`.
    *   Tạo endpoint chính `POST /incident`: Nhận data, gọi hàm `process_batch` từ `pipeline.py`, và handle Exception an toàn (trả về 500 thay vì rò rỉ stack trace).

### 2. File Phụ Trợ & Data
*   **Thư mục `dataset/` (tuỳ chọn):** Để module chạy ổn định, ta sẽ trỏ path tới file `dataset` có sẵn hoặc copy qua nếu cần (tôi sẽ ưu tiên dùng path tương đối trỏ về thư mục dataset chung là `../d1/dataset/` hoặc copy sang).

### 3. File Tài Liệu (Bắt Buộc)
*   **`DESIGN.md`:** Tôi sẽ viết document >= 100 từ mô tả:
    *   Kiến trúc pipeline trong endpoint.
    *   Latency budget.
    *   Cách xử lý concurrency/fault tolerance.
    *   Vì sao chọn FastAPI so với Flask/BentoML.
*   **`SUBMIT.md`:** Tôi sẽ chuẩn bị sẵn template và điền các câu trả lời cho 3 câu hỏi EOD checkpoint.
