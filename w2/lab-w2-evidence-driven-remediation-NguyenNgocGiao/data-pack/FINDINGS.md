# Findings & Reflections

## 1. Which similarity function did you choose for Layer 2, and why? Reference at least one alternative you considered and an empirical reason for choosing the one you did.
- Chọn Weighted Feature Intersection (Giao thoa đặc trưng có trọng số - tương tự Jaccard Similarity).
- Lý do: dữ liệu lịch sử khá thưa. Thay vì dùng Cosine Similarity tính toán phức tạp trên các đoạn văn bản dài, hàm Jaccard của so sánh sự trùng lặp 
- Trùng chữ ký lỗi (Log signature): Trọng số cao nhất (0.6)
- Trùng cảnh báo (Alert): Trọng số (0.2)
- Trùng service bị lỗi (Topology): Trọng số (0.2)
Cách này giúp hệ thống chống lại được "Log spam" (không bị nhiễu bởi những service rác xả hàng ngàn dòng log vô nghĩa).

## 2. How does outcome-weighted voting change the candidate ranking versus a pure-similarity ranking? Demonstrate with a concrete eval incident.
- Cơ chế "Outcome-weighted voting" giúp tránh lặp lại sai lầm trong quá khứ Bằng cách cộng điểm nếu hành động quá khứ thành công và trừ điểm nếu hành động quá khứ thất bại, hệ thống thà chọn một cách sửa ít giống hơn (0.6) nhưng an toàn, còn hơn chọn một cách sửa giống hệt (0.8) nhưng từng gây thảm họa. Điều này giúp tăng độ tin cậy lên rất nhiều.

## 3. For one eval incident, explain the EV calculation in full — the candidate set, weights, P_success values, costs, and which action won and by how much.
Lấy sự kiện E01 làm ví dụ:
- Top 3 sự kiện giống nhất có điểm tương đồng là 0.8 và đều thành công. Điểm đồng thuận  cho hành động `rollback_service` trên `payment-svc` là 0.8.
- Độ tin cậy: Chuẩn hóa điểm số: `min(0.8 / 1.5, 1.0) = 0.53`.
- Rủi ro Hành động `rollback_service` có mức ảnh hưởng hệ thống là 1 (đọc từ file actions.yaml).
- Theo luật của Cổng an toàn (Safety Gate), rủi ro mức 1 sẽ bị phạt 0.1 điểm (Penalty), và yêu cầu độ tin cậy tối thiểu là 0.3.
- `Reliability (0.53) - Penalty (0.1) = 0.43`.
- Kết quả: Vì `EU (0.43) > 0` và Độ tin cậy `(0.53) >= 0.3`, hệ thống tự tin cho phép tự động chạy lệnh `rollback_service` và lưu vào `audit.jsonl`.

## 4. When did your engine choose to escalate (page_oncall) instead of auto-act? Was that choice correct against the eval ground truth?
Hệ thống quyết định gọi người trực (`page_oncall`) thay vì tự sửa cho các sự kiện: E02, E04, E07, và E08.
- Ở sự kiện E02: Lịch sử ghi nhận rõ ràng hành động tốt nhất cho lỗi này là gọi người trực.
- Ở các sự kiện E04, E07, E08: Đây là các lỗi lạ chưa từng gặp (Out-Of-Distribution). Điểm tương đồng cao nhất chỉ là 0.3 và 0.0, thấp hơn ngưỡng cho phép (Threshold = 0.4).
So với đáp án chấm điểm, quyết định này là đúng. Hệ thống đã hoạt động đúng thiết kế: khi chứng cứ yếu hoặc gặp lỗi lạ, thà gọi con người chứ tuyệt đối không đoán bừa.

## 5. What is the most likely class of incident that breaks your engine? Propose one concrete improvement that would help, but explain why you did not implement it within the time budget.
Hệ thống dễ bị lừa nhất bởi các sự cố có conflicting-signal, ví dụ như sự kiện E06: số lượng log báo lỗi rác xả ra quá nhiều ở `payment-svc`, trong khi biểu đồ đường truyền (Traces) lại chỉ ra lỗi thực sự nằm ở `cart-svc`. Vì chúng ta đang chốt cứng trọng số (Logs chiếm 0.6 và Traces chiếm 0.2), hệ thống bị "mờ mắt" bởi tiếng ồn của Logs và chọn sai mục tiêu.

- Giải pháp: sử dụng weight dynamic kết hợp quy tắc 3-Sigma. 
Nếu hệ thống thấy Z-score của độ trễ Traces vọt lên mức cực kỳ nguy hiểm (vd: Z-score > 5.0), nó sẽ tự động đảo ngược trọng số (Tin Traces 0.6, Tin Logs 0.2). Tôi chưa cài đặt giải pháp này vì việc tự động thay đổi trọng số trên một tập dữ liệu quá nhỏ (~30 dòng) rất dễ gây ra hiện tượng Học vẹt (Overfitting) và làm hệ thống mất ổn định ở các ca bệnh thông thường.
