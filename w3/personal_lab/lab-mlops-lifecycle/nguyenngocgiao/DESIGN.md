# DESIGN.md — MLOps Lifecycle

## 1. Drift threshold
Tôi chọn ngưỡng drift score là `0.15` cho data drift. Khi chạy thử Evidently trên 2 nửa của tập `baseline.csv`, điểm drift dao động ở mức 0.05 - 0.08. Lấy ngưỡng 0.15 (gấp khoảng 2 lần mức bình thường) giúp tránh báo động giả (false positive). Khi chạy qua `drifted.csv`, điểm số lên khoảng ~0.20-0.30 nên sẽ kích hoạt retrain chuẩn xác. Nếu set ngưỡng quá thấp (VD: 0.05), hệ thống sẽ liên tục trigger retrain không cần thiết, làm tốn tài nguyên và tăng rủi ro lỗi mô hình.

## 2. Drift type
Bài toán có thể gặp cả Data drift và Concept drift . Script `drift_detector.py` sử dụng Evidently `DataDriftPreset` để phát hiện data drift và tính toán thêm Precision/Recall trên tập holdout để bắt được concept drift Chế độ `--check-mode combined` cho phép hệ thống báo lỗi khi bất kỳ loại. drift nào vượt ngưỡng, điều này hoàn toàn phù hợp với thực tế production thanh toán.

## 3. Retrain trigger configuration
- Check drift sẽ là automatic. Tuy nhiên việc promote lên production sẽ là thủ công bằng cách nếu v2 được tạo ra thì sẽ được đẩy vào @staging và in ra màn hình y/n để engineer duyệt. 
- Hiện tại timeout đang là 2h, nếu ko có response trong vòng 2 giờ thì hệ thống sẽ tự động reject để tránh trường hợp pipeline kẹt trong hàng chờ vô hạn
- Thay vì dùng chu kỳ cố định, em thiết kế hệ thống chạy theo sự kiện. Việc retrain mù quáng khi dữ liệu không bị drift vừa gây lãng phí tài nguyên máy chủ, vừa ép mô hình học lại tập dữ liệu cũ dẫn đến nguy cơ làm giảm độ chính xác của mô hình.

## 4. Versioning + rollback
Cơ chế versioning dựa trên tính năng **Alias** của MLflow (`@production`, `@staging`, `@archived`). Khi có phiên bản mới, ta không xoá v1 mà chỉ đổi alias của v2 thành `@production` (Blue-green deployment). 
Nếu v2 hoạt động kém sau deploy (Precision giảm xuống dưới `0.65` trong quá trình post-deploy monitoring trên `post_deploy_eval.csv`), cơ chế Auto-rollback sẽ tự động được kích hoạt: alias `@production` được gán lại cho v1, còn v2 bị đẩy sang `@archived`, sau đó gọi `/reload` API để đưa hệ thống về trạng thái ổn định ngay lập tức mà không cần can thiệp thủ công.
