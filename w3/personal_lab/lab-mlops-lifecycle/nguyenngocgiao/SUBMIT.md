# SUBMIT.md — MLOps Lifecycle Reflection

## 1. What drift threshold did you choose and why? Did you validate that threshold against real data?
Tôi chọn ngưỡng drift threshold là 0.15. Khi đánh giá thử nghiệm nghiệm trên tập `baseline.csv` qua các thời điểm khác nhau, điểm drift tự nhiên dao động trong khoảng 0.05 đến 0.08. Lấy 0.15 gấp đôi bình thường là một mức an toàn để tránh cảnh báo giả mạo, nhưng vẫn đủ nhạy bén để bắt được mức drift thực tế > 0.20 khi phân phối dữ liệu thay đổi trên tập `drifted.csv`.

## 2. What happens if model v2 after retraining performs worse than v1 in production? How does your pipeline handle this case?
Khi model v2 được đưa lên sản xuất, kịch bản Post-deploy Monitoring  sẽ chạy để liên tục đánh giá độ chính xác. Nếu Precision của v2 rơi xuống dưới mức `0.65` trong 24 cycle đầu tiên, script `retrain.py` sẽ kích hoạt luồng auto rollback: hệ thống sẽ đổi alias của v2 thành `@archived`, khôi phục alias `@production` cho v1, sau đó tự động gọi API `/reload` trên `serve.py` để downgrade trực tiếp phục hồi lại dịch vụ với v1.

## 3. What is the difference between data drift and concept drift? Which type does Evidently detect in this lab?
- Data Drift là sự phân phối của các đặc trưng đầu vào (input X) thay đổi, nhưng quy luật/mối liên hệ giữa đầu vào và đầu ra (output y) vẫn giữ nguyên
- Concept Drift là mối quan hệ giữa dữ liệu đầu vào (X) và biến mục tiêu (y) đã bị thay đổi. Cùng một đặc trưng đầu vào, nhưng ý nghĩa hoặc kết quả dự đoán thực tế đã khác trước
- Trong bài lab này, công cụ chỉ phát hiện được Data Drift bằng cách đo lường độ lệch phân phối của từng feature. Do đó, để bắt được Concept Drift một cách toàn diện, chúng ta bắt buộc phải tự tính toán thêm hiệu suất mô hình (chỉ số Precision/Recall) thông qua tập dữ liệu đã gán nhãn.

## 4. Why is a blue-green swap more important than simply replacing the model file directly?
Nếu ta overwrite file model `v1.pkl` thành `v2.pkl` trên disk, hệ thống đang serve sẽ phải đối mặt với trạng thái không xác định  hoặc gián đoạn dịch vụ khi restart server. 
Blue-green swap qua cơ chế Alias (`@production`) đảm bảo v2 đã được register và test cẩn thận ở alias `@staging`. Sau đó, việc hoán đổi được thực hiện bằng cách thay đổi meta-data trên MLflow Registry một cách nguyên tử (atomic), đi kèm với webhook `/reload` giúp model được nạp lên memory mà không làm sập API.

## 5. If you had to automate the approval gate (no human required), what metric and threshold would you use?
- Để tự động hoá bước duyệt lên Production, em sẽ sử dụng phương pháp chạy ngầm. Giả sử v2 đã được release, em sẽ cho v2 chạy song song với v1. Giả sử như có giao dịch tới, v1 vẫn xử lí và trả kết quả về cho khách hàng nhưng cùng lúc đó, copy giao dịch và đẩy đến v2 để dự đoán thử. Sau đó, lấy kết quả v2 so với v1 bằng F1-score. Nếu điểm F1 của v2 cao hơn v1 ít nhất 2% và số lượng giao dịch v2 báo lỗi không tăng đột biến thì hệ thống sử tự động đưa v2 lên production 
