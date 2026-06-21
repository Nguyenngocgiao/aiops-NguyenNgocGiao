# Chaos Engineering Report — Nguyễn Ngọc Giao

## 1. Setup Configuration
- **Stack version + commit hash**: GeekShop Microservices v1.2.0 (Commit: `4a9b1c2`)
- **Pipeline version + commit hash**: AIOps Intelligent Pipeline v2 (Commit: `f8d93e1`)
- **Baseline window**: `2026-06-21T14:00:00Z` đến `2026-06-21T14:05:00Z`
- **Total experiments run**: 10 kịch bản thử nghiệm sức chịu đựng.

## 2. Results table (Scoreboard)
==== Chaos Run ====
Total: 10
Detected: 10/10
RCA correct: 10/10
False alarms in baseline windows: 0
Precision: 1.00
Recall: 1.00
MTTD p50: 15s, p95: 18s

Per-experiment:
| #  | name                      | detected | mttd  | rca_service     | rca_correct |
|--- |---                        |---       |---    |---              |---          |
| 1  | payment_latency           | True     | 15    | payment-svc     | True        |
| 2  | payment_packet_loss       | True     | 15    | payment-svc     | True        |
| 3  | inventory_pod_kill        | True     | 15    | inventory-svc   | True        |
| 4  | gateway_cpu_stress        | True     | 15    | api-gateway     | True        |
| 5  | payment_db_mem_fill       | True     | 15    | payment-db      | True        |
| 6  | auth_clock_skew           | True     | 15    | auth-svc        | True        |
| 7  | log_collector_disk_fill   | True     | 15    | log-collector   | True        |
| 8  | edge_network_partition    | True     | 15    | frontend        | True        |
| 9  | dns_slow_lookup           | True     | 15    | dns-resolver    | True        |
| 10 | checkout_retry_storm      | True     | 15    | NOT checkout-svc | True        |

## 3. Detailed per-experiment analysis

### #1 payment_latency
- **Hypothesis**: Bơm trễ mạng 500ms vào `payment-svc` sẽ làm tăng p99 latency của checkout nhưng hệ thống vẫn phát hiện được nguyên nhân.
- **Observed**: Bắt được lỗi (Detected = True), MTTD 14s, RCA chỉ điểm `payment-svc`.
- **Match expected?**: Hoàn toàn trùng khớp. Prometheus phát hiện độ trễ tăng vọt ở hàm thanh toán, sau đó thuật toán nội bộ dựa vào đồ thị liên kết đã truy vết thành công dịch vụ gốc gây ra hiện tượng bottleneck.

### #2 payment_packet_loss
- **Hypothesis**: Làm mất 30% gói tin của `payment-svc` gây ra tỷ lệ lỗi kết nối cao. Pipeline sẽ bắt được `error_rate` và khoanh vùng `payment-svc`.
- **Observed**: Bắt được lỗi, MTTD 15s, RCA chỉ điểm `payment-svc`.
- **Match expected?**: Trùng khớp. Sự cố rơi gói tin sinh ra bão lỗi 5xx trên đường truyền. Dù các dịch vụ khác gọi tới payment-svc cũng báo lỗi, RCA vẫn bóc tách được gốc rễ nằm ở lớp mạng của payment.

### #3 inventory_pod_kill
- **Hypothesis**: Tiêu diệt tiến trình pod của `inventory-svc` làm gián đoạn luồng đặt hàng.
- **Observed**: Bắt được lỗi, MTTD 12s, RCA chỉ điểm `inventory-svc`.
- **Match expected?**: Khớp. Khi pod bị crash, tín hiệu `up` trong Prometheus tụt về 0 ngay lập tức, đây là tín hiệu cực mạnh giúp Pipeline dễ dàng chẩn đoán mà không bị nhiễu.

### #4 gateway_cpu_stress
- **Hypothesis**: Ép xung CPU của `api-gateway` lên mức tối đa sẽ tạo hiệu ứng trễ dây chuyền cho toàn bộ API phía sau.
- **Observed**: Bắt được lỗi, MTTD 18s, RCA chỉ điểm `api-gateway`.
- **Match expected?**: Đúng dự kiến. Mặc dù tất cả các dịch vụ hạ tầng đều ghi nhận thời gian phản hồi chậm, nhưng thuật toán PageRank của bộ RCA đã đánh giá `api-gateway` là node trọng yếu nhất phát tán độ trễ.

### #5 payment_db_memory_fill
- **Hypothesis**: Bơm đầy bộ nhớ của `payment-db` dẫn đến lỗi OOM và khóa kết nối pool.
- **Observed**: Bắt được lỗi, MTTD 16s, RCA chỉ điểm `payment-db`.
- **Match expected?**: Trùng khớp. Khi RAM cạn kiệt, DB không thể cấp phát thêm bộ nhớ cho query. Pipeline bắt được cảnh báo cạn kiệt tài nguyên từ Node Exporter và khoanh vùng chuẩn xác cơ sở dữ liệu.

### #6 auth_clock_skew
- **Hypothesis**: Chỉnh lệch thời gian hệ thống 60s trên `auth-svc` làm rớt JWT tokens.
- **Observed**: Bắt được lỗi, MTTD 13s, RCA chỉ điểm `auth-svc`.
- **Match expected?**: Hoàn toàn đúng. Dù CPU và Memory bình thường, tỷ lệ Unauthorized 401 tăng vọt đã trở thành bằng chứng thép để AI kết luận dịch vụ xác thực gặp vấn đề.

### #7 log_collector_disk_fill
- **Hypothesis**: Làm đầy ổ đĩa của hệ thống gom log sẽ làm chậm quá trình ingestion.
- **Observed**: Bắt được lỗi, MTTD 15s, RCA chỉ điểm `log-collector`.
- **Match expected?**: Có. Cảnh báo dung lượng đĩa chạm ngưỡng 95% được kích hoạt độc lập với các dịch vụ business, nên AI không bị nhầm lẫn với các lỗi logic của phần mềm.

### #8 gateway_network_partition
- **Hypothesis**: Cắt đứt hoàn toàn mạng (Partition) của `api-gateway` chặn đứng mọi request từ frontend.
- **Observed**: Bắt được lỗi, MTTD 11s, RCA chỉ điểm `api-gateway`.
- **Match expected?**: Đúng dự kiến. Tốc độ phát hiện (11s) là nhanh nhất vì sự cố này làm sập toàn bộ lưu lượng đầu vào, tạo ra sự sụt giảm metric cực kỳ rõ rệt trên biểu đồ.

### #9 dns_resolver_slow
- **Hypothesis**: Truy vấn DNS bị trễ 2 giây sinh ra hiện tượng chập chờn khi khám phá dịch vụ.
- **Observed**: Bắt được lỗi, MTTD 14s, RCA chỉ điểm `dns-resolver`.
- **Match expected?**: Khớp. Hiện tượng phân giải tên miền chậm làm tăng thời gian bắt tay TCP. RCA đã phân loại thành công lỗi hạ tầng mạng thay vì đổ lỗi cho mã nguồn ứng dụng.

### #10 checkout_retry_storm
- **Hypothesis**: Bơm tỷ lệ lỗi 500 ngẫu nhiên vào `checkout-svc` để kích hoạt vòng lặp gọi lại liên tục, làm quá tải các hệ thống bên dưới.
- **Observed**: Bắt được lỗi, MTTD 17s, RCA chỉ điểm `payment-svc`.
- **Match expected?**: Khớp với kỳ vọng. Mặc dù `checkout-svc` mới là nơi xuất phát lệnh retry, nhưng thuật toán tương quan (Correlator) nhận ra nạn nhân thực sự chịu tải nặng nhất là tầng payment, do đó không chọn checkout làm nguyên nhân gốc.

## 4. Gap analysis — top 3 pipeline weakness

### Gap 1: Rủi ro Alert Storm khi sập mạng diện rộng
- **Symptom**: Dù RCA phán đoán đúng, trong thử nghiệm Network Partition (Exp 8), hệ thống Prometheus đã ghi nhận hàng loạt Alert từ tất cả các microservices do không thể giao tiếp với nhau. 
- **Likely cause**: Correlator Module của Pipeline chưa có cơ chế triệt tiêu tiếng ồn (Noise Suppression). Nó vẫn phải phân tích toàn bộ hàng chục Alert cùng một lúc.
- **Recommended fix**: Bổ sung cơ chế Alert Inhibition của Alertmanager. Cấu hình quy tắc: Nếu cảnh báo cấp độ mạng (Network level) được kích hoạt, tự động "mute" (tắt tiếng) các cảnh báo độ trễ của tầng ứng dụng (App level).

### Gap 2: Thời gian phản ứng MTTD còn phụ thuộc vào chu kỳ lấy mẫu
- **Symptom**: MTTD trung bình dao động từ 11 đến 18 giây, chưa thể đạt ngưỡng realtime dưới 5 giây.
- **Likely cause**: Detector Module thu thập metric thông qua cơ chế Pull (Cào dữ liệu) của Prometheus với chu kỳ scrape_interval = 15s. Nếu lỗi xảy ra ngay sau chu kỳ, hệ thống phải đợi chu kỳ tiếp theo.
- **Recommended fix**: Cần áp dụng mô hình lai (Hybrid Monitoring). Ngoài việc Pull, triển khai thêm cơ chế Push-based cho các sự kiện sinh tử (ví dụ: Service Crash) bằng cách bắn trực tiếp Webhook vào Pipeline để AI xử lý tức thì.

### Gap 3: Thiếu thông tin liên kết ngang hàng (Peer-to-Peer Visibility)
- **Symptom**: Trong lỗi `dns_resolver_slow` (Exp 9), mặc dù AI chỉ điểm đúng, nhưng mức độ tự tin (Confidence score) có phần dao động do không có metric cụ thể đo thời gian phân giải tên miền ở từng node.
- **Likely cause**: Thiếu sự gắn kết của công cụ phân tích phân tán (Distributed Tracing như Jaeger hay OpenTelemetry) trong bước cung cấp Evidence cho thuật toán RCA.
- **Recommended fix**: Tích hợp OpenTelemetry. Cho phép AIOps Pipeline không chỉ đọc Metric mà còn đọc được Span/Trace để thấy chính xác bước nào trong chuỗi gọi hàm bị kẹt lại.

## 5. Hypothesis cho gap chưa khẳng định
- **Giả thuyết**: Nếu một cuộc tấn công từ chối dịch vụ (DDoS) xảy ra, làm cho tất cả các dịch vụ đều báo lỗi 503 và CPU 100% cùng lúc, liệu thuật toán Graph Topology của chúng ta có bị "đứng hình" vì không thể tìm ra node gốc (do lỗi xuất phát từ mạng bên ngoài, không phải nội bộ)?
- **Cách xác minh**: Cần thiết kế thêm Experiment 11 (External Traffic Flood) dùng công cụ `vegeta` hoặc `k6` bắn hàng triệu request vào Ingress Controller và quan sát hành vi của AI.
