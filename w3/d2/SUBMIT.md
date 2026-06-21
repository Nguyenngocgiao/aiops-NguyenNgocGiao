# W3-D2 Submission — Nguyễn Ngọc Giao

## 3 thứ tôi học được về AIOps pipeline của mình
1. **Sức mạnh của Topological Correlation:** Trong kịch bản bão truy vấn lặp (Retry Storm) tại `checkout-svc`, việc dùng đồ thị liên kết đã giúp AI lờ đi kẻ gây nhiễu trên bề mặt (checkout) để chỉ đích danh kẻ làm sập hệ thống (payment-svc). Cách xử lý nguyên nhân gốc rễ (Root Cause) này khôn ngoan hơn nhiều so với việc chỉ đếm số lượng lỗi
2. **Giá trị của Baseline:** Nếu không định nghĩa thế nào là "Bình thường" (thông qua Baseline window), hệ thống sẽ không có cơ sở để nhận diện "Bất thường". Việc liên tục làm mới baseline để giữ cho AI ko false alarm khi lưu lượng hệ thống tăng giảm tự nhiên trong ngày
3. **Giới hạn của Fallback Logic:** Dù hệ thống đạt 10/10 trong kịch bản giả lập, nhưng thiết kế bắt buộc phải trả về một service làm đáp án rủi ro ở chỗ nó có thể gây nhiễu cho Engineer khi xảy ra sự cố do bên thứ ba (như đứt cáp quang biển, lỗi AWS). AI cần tránh hallucination.\

## 1 fault mà tôi mong pipeline catch nhưng nó miss
- **Experiment:** Tấn công quá tải RAM cục bộ ở tầng Redis Cache (không có trong danh sách 10 test chuẩn nhưng tôi đã thử hình dung).
- **Why I expected detection:** Tôi kỳ vọng rằng khi Cache sập, DB sẽ phải gánh toàn bộ tải (Cache Stampede), dẫn đến DB sinh ra lỗi. RCA sẽ tìm ra điểm sập ban đầu là Cache.
- **Why pipeline missed (hypothesis):** Thực tế nếu Cache bị ngắt kết nối mà ứng dụng không bắn log lỗi (fail-silent) mà ngầm chuyển hướng sang DB, thì Prometheus chỉ thấy tải DB tăng (vẫn trong ngưỡng an toàn) chứ không hề biết Cache đã chết. Việc thiếu các Metric chuyên biệt cho Cache Hit/Miss Ratio sẽ làm AI bị mù hoàn toàn.

## 1 trade-off trong design pipeline mà tôi muốn rethink
**Sự đánh đổi giữa Tính toán Thời gian thực (Real-time Computing) và Lưu trữ Dữ liệu Lịch sử (Historical RAG)**
Hiện tại, để đưa ra quyết định nhanh dưới 20 giây (MTTD ~15s), tôi phải hi sinh bớt độ sâu của việc đối chiếu lịch sử sự cố (incidents_history). Tuy nhiên, với một hệ thống khổng lồ, việc tính toán lại Topology Graph mỗi vài giây khi có Alert nổ ra là vô cùng tốn CPU. Tôi muốn thiết kế lại theo hướng **Cập nhật Cây phụ thuộc nền (Background Graph Refresh)** mỗi phút một lần, và khi Alert nổ, RCA Module chỉ việc lấy đồ thị có sẵn ra để tra cứu (Lookup) thay vì phải xây dựng lại đồ thị từ con số không.

## Scoreboard summary
- **detected**: 10/10
- **rca_correct**: 10/10
- **mttd_p50**: 15s
- **false_alarms**: 0
- **verdict**: pass
