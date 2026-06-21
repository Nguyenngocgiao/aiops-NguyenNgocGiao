# Incident Postmortem: Payment Database Memory Exhaustion

## 1. Meta-data
- **Date**: 2026-06-21
- **Authors**: Nguyễn Ngọc Giao
- **Status**: Complete
- **Incident ID**: INC-20260621-001

## 2. Executive Summary
Vào lúc 13:00 UTC ngày 21/06/2026, hệ thống thanh toán (Payment Service) ghi nhận sự gia tăng đột biến về tỷ lệ lỗi 500, dẫn đến gián đoạn quy trình checkout của khách hàng trong 2 phút. Nguyên nhân gốc rễ được xác định là do sự cố cạn kiệt bộ nhớ (OOM) trên `payment-db`, khiến cơ sở dữ liệu phải sử dụng swap space và phản hồi cực kỳ chậm. Hệ thống tự động phục hồi hoàn toàn vào lúc 13:02 UTC sau khi tiến trình gây tốn RAM kết thúc.

## 3. Impact
- **Service disruption**: Tính năng thanh toán bị vô hiệu hóa hoàn toàn, khách hàng không thể hoàn tất đơn hàng.
- **Duration**: 2 phút (Từ 13:00:45 UTC đến 13:02:10 UTC).
- **Revenue impact**: Rớt khoảng 120 đơn hàng thành công, ước tính thiệt hại tiềm năng khoảng 2,400 USD.
- **Customer impact**: Khách hàng nhận được thông báo lỗi "Payment Gateway Timeout" trên giao diện giỏ hàng.

## 4. Root Cause
1. **Thiếu giới hạn tài nguyên cấp vùng**: Database `payment-db` bị chiếm dụng bộ nhớ bởi một tác vụ phân tích dữ liệu ngoại lai chưa được kiểm soát (mô phỏng bằng tiến trình stress-ng), đẩy RAM lên mức 95%.
2. **Cấu hình Alert chậm**: Cảnh báo rủi ro RAM (HighMemoryUsage) của Prometheus được cấu hình với tham số `for: 30s`, khiến cảnh báo không được kích hoạt kịp thời trong 30 giây đầu tiên, tạo khe hở để lỗi lan truyền sang tầng ứng dụng.
3. **Thiếu Circuit Breaker ở tầng Application**: `payment-svc` không có cơ chế ngắt mạch khi DB phản hồi chậm, dẫn đến toàn bộ luồng kết nối bị treo cứng (thread pool exhaustion) và trả về lỗi 500 hàng loạt.

## 5. Timeline (UTC)
- **13:00:00**: Bơm lỗi: Tiến trình stress-ng bắt đầu chiếm 95% RAM trên payment-db.
- **13:00:10**: Prometheus ghi nhận payment-db memory > 80% nhưng chưa sinh Alert do chưa vượt cấu hình `for: 30s`.
- **13:00:15**: Các truy vấn từ payment-svc đến payment-db bắt đầu chậm lại do DB phải dùng swap.
- **13:00:35**: Alert manager kích hoạt cảnh báo 'HighMemoryUsage' cho payment-db.
- **13:00:45**: payment-svc báo lỗi timeout 500 khi gọi DB (Bắt đầu ảnh hưởng user).
- **13:00:55**: AIOps Pipeline nhận được luồng Alert và phát hiện anomaly ở payment-svc và payment-db.
- **13:01:05**: RCA Module của Pipeline chỉ ra `payment-db` là root cause với confidence 0.99 dựa trên Topology Graph.
- **13:02:00**: Rollback lỗi: Tiến trình stress-ng bị kill, RAM được giải phóng dần.
- **13:02:10**: Hệ thống tự động phục hồi, phục vụ traffic bình thường (Kết thúc sự cố).

## 6. Action Items
| Type | Description | Owner | Status | Priority |
|---|---|---|---|---|
| Prevent | Áp dụng giới hạn tài nguyên (Memory Limits) chặt chẽ cho pod `payment-db` | SRE Team | TODO | High |
| Detect | Giảm thời gian trễ của Alert `HighMemoryUsage` từ `for: 30s` xuống `for: 15s` để báo động nhanh hơn. | Monitoring | TODO | Medium |
| Mitigate | Cài đặt mẫu thiết kế Circuit Breaker (vd: dùng Resilience4j) trên `payment-svc` để fail-fast khi DB chậm. | Backend | TODO | High |

## 7. Lessons Learned
- **What went well**: Mô hình AIOps Pipeline đã làm tốt việc phân loại "Bão Alert". Dù cả `payment-svc` và `payment-db` đều réo còi cảnh báo đỏ cùng lúc, thuật toán RCA vẫn tìm ra đúng gốc rễ ở phía DB chỉ trong 10 giây.
- **What went wrong**: Việc phụ thuộc hoàn toàn vào Prometheus Alert Rules (`for: 30s`) đã tạo ra một khoảng mù (blind spot) kéo dài nửa phút, khiến sự cố đã lan rộng ra user trước khi hệ thống kịp ứng phó.
- **Where we got lucky**: Sự cố giả lập này tự động kết thúc sau 2 phút. Nếu đây là một rò rỉ bộ nhớ thực tế (Memory Leak) kéo dài, database có thể đã bị Linux OOM Killer tiêu diệt, dẫn đến thời gian downtime lên tới 15-30 phút để restart và recover data.
