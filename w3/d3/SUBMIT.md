# W3-D3 Submission — Nguyễn Ngọc Giao

## Outage chosen
Sự kiện cạn kiệt bộ nhớ dẫn đến sập cơ sở dữ liệu thanh toán: `payment-db` Memory Fill (OOM).

## 3 thứ tôi học từ outage này
1. **Sự nguy hiểm của Cấu hình "Mù":** Việc đặt Alert Rule với `for: 30s` (chỉ báo động nếu lỗi kéo dài hơn 30s) có mục đích tốt là lọc nhiễu, nhưng lại vô tình tạo ra một khoảng mù khiến hệ thống hoàn toàn bất lực trong 30 giây đầu tiên của cơn khủng hoảng.
2. **Vai trò của tự vệ chủ động (Circuit Breaker):** Hệ thống Monitoring dù có AI thông minh đến đâu cũng chỉ là người quan sát. Nếu tầng ứng dụng (`payment-svc`) không biết cách tự cắt kết nối khi bị Database kéo lùi, thì toàn bộ chuỗi hệ thống sẽ bị treo cứng.
3. **Giá trị của Blameless Culture:** Viết Postmortem mà không đổ lỗi giúp tập trung hoàn toàn vào rủi ro kỹ thuật (thiếu Limit RAM) thay vì truy cứu trách nhiệm cá nhân (ai đã gõ lệnh chạy tiến trình ngốn RAM).

## 1 thứ pipeline của tôi sẽ vẫn miss nếu outage này xảy ra real
- **Pattern:** Lỗi liên quan đến bộ nhớ đệm ẩn của hệ điều hành (Page Cache) hoặc Disk I/O Wait tăng đột biến nhưng RAM thực tế chưa báo đầy.
- **Why miss:** Pipeline hiện tại chỉ monitor tổng bộ nhớ đã dùng (`memory_usage_bytes`). Nó không phân tích sâu xuống I/O Wait hay hiện tượng Cache Trashing.
- **Mitigation idea:** Tích hợp bộ eBPF (như cilium/tetragon hoặc pixie) để theo dõi các system call cấp thấp ở nhân Linux, giúp AIOps có thêm dữ liệu Evidence siêu chi tiết.

## 1 quyết định trong ADR mà tôi không hoàn toàn chắc
Quyết định dùng **Thuật toán Đồ thị (Topology-Aware)** thay vì Machine Learning (ADR-001) khiến tôi lăn tăn. Dù đồ thị nhanh và chính xác với các kết nối API truyền thống, nhưng với sự bùng nổ của Event-Driven Architecture (nhắn tin qua Kafka/RabbitMQ), việc vẽ ra một cây phụ thuộc tuyến tính đang ngày càng bất khả thi. Có lẽ một mô hình kết hợp (Hybrid) giữa Graph và Machine Learning mới là chân ái trong tương lai.

## Cost model verdict cho stack của tôi
- **ROI:** 6.0
- **Payback:** Khoảng 5 ngày (0.17 tháng)
- **Verdict:** worth_it
