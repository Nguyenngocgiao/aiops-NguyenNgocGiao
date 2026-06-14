# AIOps Pipeline Model Serving Design

## Pipeline Architecture
Hệ thống serving được thiết kế dựa trên kiến trúc 3-layer pipeline được gói gọn trong endpoint của FastAPI. Dataflow chính như sau:
1. `POST /incident` nhận batch alerts từ hệ thống monitoring thông qua body JSON. Payload được validate tự động nhờ các schema Pydantic (`IncidentRequest`).
2. Tầng Glue (trong `pipeline.py`) chuyển Pydantic models thành dict chuẩn và gọi hàm `process_batch`.
3. Trong `process_batch`, Layer 1 (Correlate) gom nhóm alert dựa trên topology service graph và cửa sổ thời gian.
4. Cluster có số alert lớn nhất sẽ được chọn làm primary cluster và đưa xuống Layer 2 (RCA).
5. RCA so sánh topo candidates (PageRank) và query similarity với incidents_history (Graph + Retrieval).
6. FastAPI serialize output trở lại JSON (`IncidentResponse`) và trả về cho client. 
Kiến trúc này cho phép encapsulate logic phức tạp đằng sau một API đơn giản và dễ tích hợp.

## Latency Budget Breakdown
Dựa vào kiến trúc, latency budget được phân bổ như sau (tổng p99 <= 10s):
- Validate payload Pydantic: ~2-5ms
- Layer 1 (Correlate alerts + Topology matching): ~10-20ms (scale tuỳ theo số lượng alerts và size của graph)
- Layer 2 (RCA):
  - PageRank calculation: ~5ms
  - History retrieval matching: ~10ms
- Nếu tích hợp LLM (External API Call): chiếm phần lớn latency, khoảng ~2s tới ~8s. (Đây là bottleneck chính yếu).
- Serialization: ~1-2ms.
Tổng cộng khi không có LLM call (Graph-only), endpoint mất chưa tới 50ms để xử lý một batch.

## Concrete Decisions
- **gap_sec=120s**: Quyết định chọn cửa sổ thời gian 120 giây (2 phút) để gom nhóm (sessionize) alerts. Trong hệ thống microservices, lỗi lan truyền từ database layer lên edge layer thường diễn ra rất nhanh, thường trong vòng vài giây đến vài chục giây. Cửa sổ 120s cung cấp đủ độ trễ an toàn để bắt gọn một đợt bùng phát alert do cùng một sự cố (cascade effect), mà không quá dài để bị gộp nhầm hai sự cố độc lập xảy ra liên tiếp.
- **max_hop=2**: Khi sử dụng topology correlation, chọn khoảng cách tối đa 2 hop. Khoảng cách này bao phủ được phần lớn các luồng tương tác quan trọng gây lỗi (VD: `Edge -> Checkout -> Payment` hoặc `Payment -> Database`), giúp cắt giảm noise mà không gặp hiện tượng "gom chung toàn bộ hệ thống" khi có biến cố lớn.

## Production Concern: Concurrency và State Management
Pipeline có sử dụng `GRAPH` và `HISTORY` cache trên memory. Nếu dùng FastAPI với Uvicorn chạy nhiều worker (ví dụ `--workers 4`), mỗi worker sẽ clone các cấu trúc dữ liệu này dẫn đến tốn memory và có thể gặp lỗi về consistency nếu graph được update định kỳ (không cross-worker).
**Giải pháp:** 
Hiện tại để giảm thiểu lỗi race condition, tôi thiết kế các biến cache graph và history dạng stateless cho process handling (chỉ read-only, load một lần lúc khởi động) và tránh modify chúng trong runtime. Trong trường hợp cần cập nhật service graph linh hoạt, có thể tính đến Redis hoặc Database riêng để fetch động ở mỗi worker, hoặc chạy 1 single worker nếu load cho phép.

## Trade-off: Vì sao chọn FastAPI
- **vs Flask:** FastAPI có sẵn tính năng Data Validation (thông qua Pydantic) thay vì phải tự viết if-else kiểm tra key trong dictionary như Flask. Việc generate OpenAPI document tự động cũng giúp quá trình test trở nên vô cùng thuận lợi. Ngoài ra, khả năng xử lý Async I/O Native giúp scale IO-bound tasks (gọi LLM API).
- **vs BentoML:** Mặc dù BentoML chuyên cho model serving (như batching native, versioning), pipeline hiện tại không sử dụng Deep Learning/ML nặng nề cần batching GPU. Việc setup BentoML sẽ quá cồng kềnh (overhead cao) cho một workload logic rule-based và API IO-bound thông thường như này. FastAPI mang lại độ linh hoạt phù hợp hơn.
