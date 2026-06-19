# EOD Checkpoint - Day 2

## 1.Confidence của top-1 trong cluster lớn nhất bạn xử lý là bao nhiêu? Nếu phải set threshold để auto-rollback (không cần SRE confirm), bạn pick số nào? Lý do?
- confidence của top-1 trong cluster lớn nhất đạt 0.8 
- Nếu set threshhold để auto-rollback thì nên pick số 0.8 vì theo quy ước tính điểm thì để đạt được >= 0.8 thì ta phải cần thêm ít nhất 0.4 điểm từ điểm bối cảnh ( 0.8 - 0.4 vì chắc chắn root cause service phải nằm trong cluster thì mới đạt được 0.8)
  + Điểm Overlap = 0.4 (tức là trùng ít nhất 2 service liên quan). Lúc này tổng điểm = 0.4 + 0.4 = 0.8 >= 0.8
  + Điểm Overlap = 0.2 (trùng 1 service) và điểm Severity = 0.2 (trùng độ nghiêm trọng). Lúc này tổng điểm = 0.4 + 0.2 + 0.2 = 0.8 >= 0.8

## 2. Variant bạn chọn cho classifier (A rule-based / B free LLM / C paid LLM). Chạy thực tế ra sao? Trade-off với variant bạn không chọn?
- Variant đã chọn: A
- Chạy thực tế: 
  + Thời gian chạy nhanh
  + Chi phí 0 đồng ( vì ko tốn tiền gọi API)
  + Dự đoán chính xác tuyệt đối nguyên nhân gốc rễ là payment-svc nhờ tìm được đúng sự cố tương tự trong quá khứ (INC-2025-11-08)
- Trade off
  + Vì ko dùng LLM nên sẽ tránh được hallucination và tối ưu chi phí vì ko phải gọi API và mua token. Ngoài ra, LLM bị phụ thuộc vào internet nên nếu đường truyền yếu sẽ ảnh hưởng đến latency
  + Điểm yếu: bị phụ thuộc vào history nên nếu có một sự cố mới chưa từng xảy ra thì sẽ báo lỗi chung chung là không xác định, dev sẽ phải kiểm tra manually

## 3. Đọc bảng Industry landscape (§6) — pipeline bạn xây gần product nào nhất? Trong domain GeekShop (e-commerce, alert volume cao, service map tương đối ổn định), lựa chọn đó hợp lý hay nên đổi?
- pipeline hiện tại đang xây dựng gần với Dynatrace Davis và BigPanda
- trong domain Geekshop, đây là lựa chọn hoàn toàn hợp lí vì
  + Volume của alert sẽ lớn -> việc gom nhóm lại là cần thiết và giảm noise
  + vì có services map tương đối ổn định nên thuật toán pagerank dùng để duyệt graph là hoàn toàn hợp lí 
