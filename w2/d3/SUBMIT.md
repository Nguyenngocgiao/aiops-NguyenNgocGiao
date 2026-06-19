# EOD Checkpoint - Day 3 (AIOps W2)

## 1. Latency thực của endpoint
- **Đo lường (p50 / p99):** Chạy 20 request với bộ dataset mẫu (20 alert/request), p50 đo được ở khoảng ~30ms, trong khi p99 là ~45ms.
- **Phase chiếm phần lớn:** Hiện tại do LLM chưa được tích hợp (bypass) nên phần tốn thời gian nhất là RCA Phase (Graph Topology Matching - thuật toán PageRank và Similarity Search trên list object), sau đó là Pydantic data validation (validation schema array nhiều phần tử).
- **Linear scale vs Fixed cost:**
  - **Validation & Layer 1 (Correlate):** Sẽ scale linear nếu số lượng alerts/input tăng gấp 10x, đặc biệt là Pydantic validation và tạo list.
  - **Layer 2 RCA (Graph PageRank):** Fixed cost đối với input length vì nó chỉ extract nodes subgraph rồi phân tích PageRank trên đó, không phụ thuộc tuyến tính vào số alert (miễn là subgraph không quá lớn). LLM call (nếu có) thường là fixed cost (về latency) phụ thuộc model provider chứ không phụ thuộc trực tiếp lượng dữ liệu vào trong prompt.

## 2. LLM Provider Down hoặc Concurrency
- **Concurrency Test:** Khi mô phỏng `ab -n 20 -c 4` (chạy 4 concurrent requests).
- **Bottleneck đầu tiên:** Với single-worker (`--workers 1`), request sẽ bị queue vì process hiện tại chạy code thuần đồng bộ (sync block) trong CPU-bound tasks (PageRank) mà không yielding lại Event Loop (mặc dù endpoint có thể là async). Do vậy, bottleneck chính là sự gia tăng đột biến của thời gian chờ (Queue time) của các request đến sau nếu có call blocking như IO (LLM API hang).
- **Fallback path:** Để xử lý LLM down, ứng dụng hiện triển khai phương pháp "Graph-Only Fallback". Nếu không query được LLM hoặc history score quá thấp (< 0.2), pipeline tự động lấy Candidate cao nhất trên đồ thị làm `root_cause` với độ tin cậy thấp hơn và return kết quả kèm string `"method": "graph-only-fallback"`.

## 3. Health Check vs Readiness
- **Health check (`/healthz`):** Chỉ check xem process Python (FastAPI app) còn đang chạy, không chết hay freeze không (Liveness probe).
- **Readiness check (`/readyz`):** Check các "Downstream Dependency" bắt buộc để đảm bảo việc pipeline chạy không gặp lỗi 500 do thiếu dữ liệu tĩnh, ví dụ Graph đã được nạp và History data có len > 0.
- **Vì sao tách 2 endpoint?** Kubernetes cần phân biệt việc một Pod cần khởi động lại (restart) (nếu `/healthz` fail) so với việc Pod tạm thời không phục vụ traffic (chỉ bỏ khỏi loadbalancer) (nếu `/readyz` fail).
- **Khi LLM API down, `/readyz` fail hay pass?** Vẫn Pass. LLM là external enhancement có thể được cấu hình fallback, không nên fail Readiness khiến Kubernetes gỡ toàn bộ pod xuống làm mất khả năng phục vụ theo cơ chế Graph-Only. Tốt hơn là tự handle Exception ở /incident, hoặc dùng feature flag tắt hẳn LLM call.
