

## 1. Chọn `gap_sec` bao nhiêu và tại sao?
- Chọn gap_sec là 120 vì trong thực tế khi một services gặp lỗi, nó hiếm khi chết cứng luôn mà sẽ retry lại. Ví dụ như khi A gọi B không được thì A sẽ thử lại sau 10s. nếu sau nhiều lần thử vẫn bị lỗi thì sẽ là alert. Việc để gap_sec = 120s là hợp lí vì có khả năng bao trùm các chu kì retry 
---

## 2. Chọn `max_hop` bao nhiêu và tại sao?
- Chọn max_hop là 2 vì thường là các services luôn giao tiếp với nhau bằng API. Giả sử services A gọi services B, ta sẽ có A -> API -> B. Nếu B sập thì sẽ kéo theo A lỗi. Nếu dùng max_hop = 2 thì ta sẽ gộp được (A, API, B) thành 1 incident có root cause là B. dùng max_hop = 1 thì sẽ phân ra 2 incident (A, API) và B -> nhiều alert dư thừa

---

## 3. Alert ID nào bị "miss" (không match cluster chính)?

- Alert a-0013 và a-0016, không bị merge vào cluster chính vì nó nằm cách xa payment-svc xa (hop > 2) 

---

## 4. Nếu có 10.000 alert, code sẽ chậm ở đâu?
- Chậm ở phần topology. Code hiện tại đang bắt cặp từng services bị lỗi với nhau bằng 2 vòng lặp: 
    for i, s1 in enumerate(services_with_alerts):
        for s2 in services_with_alerts[i+1:]:
  Nếu nhiều services lên thì vòng lặp này sẽ phình to ra

- Chậm ở phần fingerprint vì dùng self.store để ghi nhớ các alert. Nếu chạy liên tục thì sẽ bị bottleneck ở RAM
---

## 5. EOD Checkpoint 

1. Vì sao fingerprint không include timestamp hay value? Cho ví dụ nếu include thì hệ thống behave ra sao.
    - Không include timestamp với value vì đó là 2 giá trị luôn thay đổi. Việc include 2 cái đó sẽ làm việc phân loại alert trở nên khó khăn hơn (ko có alert nào cùng fingerprint)
    - ví dụ: giả sử có 2 alert: 
    Alert 1: ts: 10:00, service: web, metric: cpu, sev: High, value: 95
    Alert 2: ts: 10:01, service: web, metric: cpu, sev: High, value: 97
    - Nếu ko thêm timestamp với value vào thì mã của 2 alert trên là web, cpu, high
    - Nếu thêm timestamp với value thì 2 alert trên sẽ khác fingerprint -> tưởng là 3 lỗi ko liên quan đến nhau -> alert fartigue
2. Sự khác biệt giữa “duplicate” và “correlated” alert? Ví dụ cụ thể từ dataset.
    - Duplicate: cùng fingerprint
    - correlated: khác fingerprint nhưng cùng time-window và topology 
    Ví dụ: 
    - Duplicate: a-0003, a-0008 và a-0015 có fingerprint giống hệt nhau 
    - correlated: a-0001, a-0003, a-0005, a-0006, a-0007, a-0009 khác fingerprint nhưng nó cùng time-window và topology 
3. gap_sec = 30 vs gap_sec = 600 — mỗi cái ảnh hưởng output thế nào? 1 dòng cho mỗi case.
    - gap_sec = 30: có nguy cơ những sự cố liên quan với nhau bị tách ra thành nhiều nhóm khác nhau
    - gap_sec = 600: có nguy cơ gộp những alert ko liên quan vào 1 nhóm
4. Trong scenario chính (payment-svc pool exhaustion), recommender-svc cũng alert (batch retrain). Correlator của bạn có gom recommender vào cluster chính không? Vì sao có / không?
    - Không gộp vì hop > 2 trong khi max_hop = 2 mặc dù nó cùng time-window -> tách riêng thành cluster khác 
5. Limitation lớn nhất của topology grouping mà bạn nhận ra? Đề xuất 1 cách khắc phục.
- Toopology bị phụ thuộc lớn vào service graph. Nếu có services mới nhưng vẫn chưa update vào service graph -> alert sẽ bị tách thành 1 cluster khác mặc dù nó liên quan với nhau. 
- Cách khắc phục: build graph 1 cách automatic bằng cách sử dụng distributed tracing (mỗi request để lại trace cho thấy service nào gọi service nào. Graph được cập nhật liên tục theo traffic thực, không cần cập nhật tay)