# AIOps Mini-Platform Spec — Nguyễn Ngọc Giao

## 1. Platform overview
Nền tảng AIOps Intelligence Pipeline được thiết kế để giám sát kiến trúc GeekShop (gồm 10+ vi dịch vụ như payment, inventory, auth, checkout... và các cơ sở dữ liệu đi kèm). Nền tảng hướng tới đối tượng người dùng là đội ngũ SRE và Backend Engineer, với mục tiêu rút ngắn thời gian phát hiện và chẩn đoán sự cố (MTTD/MTTR) xuống dưới 1 phút thông qua thuật toán phân tích nguyên nhân gốc rễ (RCA).

## 2. SLO definition (from W3-D1)
Tham chiếu từ cấu hình SLO:
- **`payment-svc`**: SLI là tỷ lệ Request Thành Công (HTTP 200). SLO đặt ở mức 99.9%. Error Budget là 43 phút downtime mỗi tháng.
- **`checkout-svc`**: SLI là Độ trễ phản hồi (p99 Latency < 500ms). SLO đặt ở mức 99.5%.
- **`inventory-svc`**: SLI là Tính sẵn sàng (Pod Uptime). SLO đặt ở mức 99.9%.

## 3. Detection + Correlation + RCA stack (from W1+W2)
- **Detection Layer**: Sử dụng Prometheus để liên tục Pull metric (scrape interval 15s) từ hệ thống. Các Alert Rule được định nghĩa chặt chẽ bằng PromQL, kích hoạt khi CPU/RAM > 80% hoặc Error Rate > 5%.
- **Correlation Layer**: Alertmanager gom nhóm (grouping) các cảnh báo sinh ra cùng thời điểm trong một cửa sổ 2 phút để tránh bão cảnh báo (Alert Storm).
- **RCA Layer (Root Cause Analysis)**: Sử dụng phương pháp Topological Graph để xây dựng cây phụ thuộc. Khi một cụm cảnh báo đổ về, thuật toán sẽ dò ngược đồ thị mạng để xác định Service nào nằm ở tầng thấp nhất bị lỗi, từ đó kết luận Root Cause (Chi tiết quyết định chọn Graph thay vì Machine Learning xem tại `ADR-001`).

## 4. Reliability validation (from W3-D2)
Kết quả chạy Chaos Engineering:
- **Total**: 10 experiments
- **Detected**: 10/10
- **RCA correct**: 10/10
- **False alarms**: 0
- **MTTD p50**: 15s, p95: 18s

**Top 3 Gap Identified:**
1. Rủi ro Alert Storm khi mất mạng cục bộ (Network Partition) do chưa cấu hình Alert Inhibition đúng cách.
2. MTTD vẫn phụ thuộc quá nhiều vào chu kỳ kéo dữ liệu tĩnh của Prometheus (15s), khó phản ứng Real-time ngay lập tức.
3. Thiếu khả năng truy vết phân tán (Distributed Tracing), dẫn đến mù thông tin khi dịch vụ bị nghẽn mạng ở tầng sâu mà không báo lỗi.

## 5. Operational pattern (from W3-D3)
Trong quá trình giả lập sự cố OOM trên `payment-db` (Incident: INC-20260621-001), chúng tôi nhận thấy việc cấu hình `for: 30s` trong Prometheus Alert Rules tạo ra độ trễ quá lớn khiến dịch vụ `payment-svc` ngưng trệ trước cả khi SRE kịp nhận cảnh báo. Bài học lớn nhất là phải áp dụng cơ chế Circuit Breaker ở tầng Application để tự vệ khi DB quá tải, thay vì chỉ trông chờ vào hệ thống Monitoring bên ngoài.

## 6. Cost model (from W3-D3)
Dựa trên script `cost_model.py` áp dụng cho GeekShop:
- Giả định chi phí 1 giờ downtime là $50,000 (doanh thu + bồi thường SLA).
- Với tần suất 4 vụ/tháng, thiệt hại nguyên thủy: $300,000/tháng.
- AIOps giúp giảm 40% MTTR, tiết kiệm được: **$120,000/tháng**.
- Chi phí vận hành AIOps: **$20,000/tháng**.
- **Verdict**: Khẳng định `worth_it` (Đáng tiền). ROI đạt mức 6.0, và hoàn vốn trong vòng chưa đầy 1 tuần hoạt động.

## 7. Open risks
1. **Rủi ro rò rỉ dữ liệu (Data Privacy)**: 
   - *Severity*: High
   - *Mitigation*: Áp dụng bộ lọc mask PII (Personal Identifiable Information) ngay tại tầng Log Collector trước khi đẩy vào AIOps.
2. **Rủi ro sập chính hệ thống AIOps (Single Point of Failure)**: 
   - *Severity*: Critical
   - *Mitigation*: Cấu hình HA (High Availability) cho Prometheus và API Gateway của AIOps Pipeline.
3. **Mù thông tin với các Service của bên thứ 3 (Third-party integrations)**: 
   - *Severity*: Medium
   - *Mitigation*: Xây dựng các External Probes (như synthetic_probe.sh) để liên tục kiểm tra hộp đen (black-box) các dịch vụ bên ngoài.
