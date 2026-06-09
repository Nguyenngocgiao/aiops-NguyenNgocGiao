## 1. Cluster chính: root cause là gì + lý do
- Root cause là payment-svc bị lỗi connection pool exhaustion -> dẫn tới việc phản hồi cực kỳ chậm, kéo theo các dịch vụ checkout và API gateway bị lỗi theo. 
- Lí do: payment-svc báo lỗi sớm nhất trong log và khớp hoàn hảo với sự cố quá khứ INC-2025-11-08 (độ tương đồng 0.80)
## 2. Confidence — có dám deploy auto-remediation dựa trên output này không?
- Có. vì confidence đạt 0.8 là rất cao. Ta có thể set thêm threshold là chỉ auto-remediation những cái có điểm số confidence >= 0.8 Nếu nhỏ hơn 0.8 thì cần xem xét lại vì bối cảnh lỗi bị lệch nhiều so với lịch sử đã ghi nhận trước đó. Nếu auto-remediation thì lỗi vẫn sẽ ko hết mà có thể làm gián đoạn đến những cái khác
## 3. 1 case mà bạn không chắc — vì sao
- Khi mà third party bị sập. Ví dụ như khi chúng ta thanh toán, payment-svc sẽ gửi request tới cho các third party như momo, zalo pay, ... payment-svc bị timeout nếu các third party đó bị sập -> connection pool exhaustion -> cùng triệu chứng với lỗi trước đó đã được ghi nhận -> auto-remediation nhưng nguyên do ko phải là của payment-svc -> ko giải quyết được gì

