# ADR-001: Architecture Decision Record for Root Cause Analysis (RCA) Strategy

## 1. Title
**Lựa chọn cơ chế xác định Root Cause Analysis (RCA): Topology-Aware Graph vs Black-box Machine Learning.**

## 2. Context
Trong quá trình thiết kế hệ thống AIOps Pipeline cho GeekShop, chúng ta đối mặt với bài toán bóc tách nguyên nhân gốc rễ (Root Cause) khi xảy ra "Bão Cảnh Báo" (Alert Storm). Trong sự kiện sập mạng cục bộ (`edge_network_partition` - tham chiếu: Gap 1 trong bảng xếp hạng Chaos Report W3-D2), hàng chục vi dịch vụ đồng loạt sinh lỗi.
Câu hỏi đặt ra là: AIOps Pipeline nên dùng phương pháp nào để tìm ra Node gây lỗi đầu tiên?

Chúng ta có 2 hướng tiếp cận (Alternatives):
1. **Topology-Aware Graph (Đồ thị phụ thuộc mảng mạng):** Kết nối dữ liệu dựa trên sơ đồ gọi hàm giữa các service (vd: Frontend gọi API Gateway, API Gateway gọi Payment). Thuật toán (như PageRank) sẽ chấm điểm node gốc.
2. **Black-box Machine Learning (Học Sâu/Học Máy - LSTM-AE):** Thu thập toàn bộ chuỗi log/metric dạng time-series của hệ thống, đào tạo một mô hình học sâu để nó tự tìm ra pattern bất thường.

## 3. Decision
Chúng tôi quyết định chọn **Topology-Aware Graph (Thuật toán Đồ thị dựa trên cây phụ thuộc)** làm cơ chế cốt lõi cho RCA Module của AIOps Pipeline.

## 4. Consequences

### Positive Consequences (Điểm mạnh)
- **Tính minh bạch (Explainability):** Kết quả trả ra dễ dàng giải thích cho SRE Engineer biết tại sao nó chọn Node đó. Dữ liệu chứng minh (Evidence) rất tường minh.
- **Tốc độ phản ứng (MTTD thấp):** Không cần thời gian retraining model. Thuật toán đồ thị có thể chạy và kết luận ngay lập tức (hiện tại đo được ~15s).
- **Chi phí vận hành thấp:** Không cần tài nguyên GPU đắt đỏ để train model liên tục khi kiến trúc microservices thay đổi.

### Trade-offs / Negative Consequences (Điểm yếu)
- **Phụ thuộc vào dữ liệu đầu vào:** Đòi hỏi hệ thống phải được cài cắm Distributed Tracing (như OpenTelemetry hoặc Jaeger) cực kỳ chuẩn xác. Nếu Tracing bị đứt gãy, đồ thị sẽ bị mù (Tham chiếu Gap 3 ở W3-D2 Chaos Report).
- **Không tự học được rủi ro ẩn:** Chỉ phát hiện được lỗi dựa trên những giao tiếp mạng rõ ràng. Không giỏi trong việc dò tìm các lỗi logic phần mềm phức tạp chạy ngầm độc lập trong một service.
