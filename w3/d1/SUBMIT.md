# W3-D1 Submission — Nguyen Ngoc Giao

## 3 thứ tôi học được
1. **MWMBR giảm noise hiệu quả:** Phối hợp long/short window giúp giảm nhiễu đến 86.4% mà vẫn giữ tốc độ phát hiện sự cố nhanh. Nhờ AND logic, alert sẽ tự tắt ngay (~5 phút) sau khi hết lỗi, khắc phục hoàn toàn nhược điểm treo alert của single-window.
2. **SLI phải bám sát trải nghiệm người dùng:** Các chỉ số tài nguyên như CPU/Memory chỉ là saturation signals để lập kế hoạch tài nguyên, không phản ánh trực tiếp sự hài lòng của user và không dùng làm SLI. SLI tốt phải đo từ phía user (success rate, latency, RUM).
3. **Error budget là công cụ để Dev và Ops đồng thuận:** Lượng hóa chất lượng hệ thống bằng số lượng lỗi cho phép trong tháng (ví dụ: ~103k lỗi cho SLO 99.5%). Dev có thể tự do deploy khi còn budget, và phải dừng lại tối ưu hệ thống khi hết budget.

## 1 thứ vẫn chưa rõ
- Làm thế nào để định nghĩa và tối ưu hóa SLO ban đầu cho một dịch vụ hoàn toàn mới khi chưa có bất kỳ dữ liệu baseline lịch sử nào?

## 1 trade-off trong SLO decision của tôi mà tôi không chắc
- **Frontend SLO (99%):** Đặt ở 99% để an toàn vì frontend phụ thuộc nhiều vào mạng client và CDN (baseline thực tế là 98.61%). Tuy nhiên, mức này có thể quá lỏng cho các luồng quan trọng như Checkout (thường cần 99.9%). Tôi phân vân giữa việc giữ single SLO cho đơn giản hay chia nhỏ SLO theo critical path (như Checkout) / User tier (Premium vs Free) để tối ưu trải nghiệm, chấp nhận tăng độ phức tạp trong giám sát.

## Validation report
- **noise_reduction_pct**: 86.4%
- **mttd_delta_s**: 60s
- **false_negative**: 0
- **verdict**: pass
