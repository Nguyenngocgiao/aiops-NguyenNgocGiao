
## 1. SLI choice cho frontend. Tại sao chọn metric X thay vì Y? Frontend RUM cho 4 candidate signal (page load time, DOM ready, JS error rate, network error rate). Chọn cái nào, vì sao loại 3 cái còn lại?

Chọn: Composite = `dom_ready<2000ms AND js_error=false AND network_error=false`

Loại 3 candidates vì
- Page Load Time → đo cả ads/analytics mà user không cần
- JS Error alone → baseline fail_rate=1.39% chứa non-critical errors
- Network Error alone → transient, user retry được



## 2. SLO target cho api. Tại sao 99.9% chứ không 99% hoặc 99.99%? Cost của mỗi tier (§3.2) so với baseline hiện tại 99.7% (từ baseline.json).

Baseline: 97.63%

- Không 99%: Gap nhỏ (1.37%), không tạo pressure improve reliability  
- Không 99.9%: Gap lớn (2.27%), cần multi-AZ cost 3-5×, infra chưa sẵn sàng  - *Chọn 99.5%: Gap 1.87%, achievable với retry logic + connection pool tuning

Budget: 103,689 failures/month = 218 phút downtime


## 3. Latency threshold p99. Bạn cut latency ở mốc nào (200ms? 500ms? 1s?)? Plot distribution latency 7-day (text/table OK), defend choice.

- Chọn API: 500ms

- Latency distribution từ baseline.json:
```
API:      p99 = 156ms
DB:       p99 = 59ms  
Frontend: p99 = 1430ms
```

- Defend 500ms cho API:

+ Real-world variance không phải outliers: DB spike +100-200ms, GC pause + 50-100ms, cache miss +100-200ms
+ 500ms = 3× baseline → buffer cho natural variance
+ Cut tại 156ms → false positive khi system healthy

- Tại sao không 200ms hay 1s:
+ 200ms (1.3× baseline): Quá tight, trigger khi minor variance
+ 1s (6× baseline): Quá lỏng, user đã feel pain ở 500-700ms

---

## 4. 4xx exclusion. Tại sao loại 4xx ra khỏi error count (trừ 429)? Có log endpoint nào có rate 4xx > 5% mà không phải hệ thống lỗi không? Reference data.
- Loại 4xx ra khỏi error count (trừ 429) vì 
+ Các mã 4xx khác (400, 401, 404...) là lỗi từ phía người dùng (nhập sai mật khẩu, sai URL, lỗi thanh toán). Nếu tính vào Error Count sẽ làm giảm SLI một cách oan uổng 
+ Giữ lại 429 vì đây là lỗi do hệ thống chủ động từ chối phục vụ , được tính là Availability issue

- Trong log thực tế access_log.jsonl, tỉ lệ lỗi 4xx (non-429) ở tất cả các endpoint đều rất thấp và đồng đều ở mức ~2% (không có endpoint nào vượt quá 5%).


## 5. MWMBR tuning. Dùng Google default (14.4, 6, 1) hay tune? Nếu tune, dựa vào ảnh hưởng đến noise_reduction_pct và fn thế nào?

- Chọn tune sang bộ thông số (2.88, 1.2, 0.2)

- Ảnh hưởng đến noise_reduction_pct và fn
+ Về FN: Vì SLO chọn là  99.5% nên nếu giữ nguyên thông số mặc định của Google, bộ cảnh báo sẽ quá lỏng và bỏ sót mất 1 sự cố thực tế (FN = 1), đồng thời thời gian phát hiện lỗi bị trễ thêm 300 giây.
+ Dựa trên file validation_report.json được sinh ra từ chính script validate , cấu hình tuned này đã giúp giảm số lượng cảnh báo giả từ 22 xuống còn đúng 3 cảnh báo thực tế. Chỉ số giảm nhiễu đạt chính xác noise_reduction_pct = 86.4% với số lượng cảnh báo sai FP = 0, 

