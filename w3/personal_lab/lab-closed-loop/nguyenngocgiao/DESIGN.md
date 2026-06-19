# DESIGN.md — Ronki Closed-Loop Orchestrator

## 1. Did you choose a rule-based or LLM-based decision engine? Why? What are the trade-offs?

- Chọn: Rule-based.

Lý do: Stack Ronki có 3 loại alert được định nghĩa rõ ràng (`HighLatency`, `HighErrorRate`, `InstanceDown`) và mỗi loại map 1-1 với một runbook cụ thể. Rule-based cho latency cực nhanh  và đảm bảo tính xác định. Nó không tốn kém chi phí gọi API và hoàn toàn hoạt động độc lập . Nếu mở rộng hệ thống lên hàng trăm loại lỗi không xác định, ta mới cân nhắc LLM.

## 2. Your blast-radius config: specific values and the reason you chose them

```yaml
blast_radius:
  max_actions_per_minute: 3
  max_restarts_per_service_per_hour: 5
```

Lý do:
- max_actions_per_minute: 3: Stack có 5 service. Nếu xử lý song song, cho phép tối đa 3 tác vụ mỗi phút giúp ngăn tình trạng restart toàn bộ hệ thống cùng lúc
- max_restarts_per_service_per_hour: 5: Giới hạn số lần thử. Nếu 1 service bị restart > 5 lần/giờ mà vẫn lỗi, đó là biểu hiện của lỗi mã nguồn hoặc cấu hình, cần manual review

## 3. What metric does your verify step check? What is the threshold? What is the timeout?

- Metric kiểm tra: Dựa trên `baseline.json`, kiểm tra `latency_p99_max_ms` và `up`
- `latency_p99_max_ms: 500`: Khoảng cách an toàn so với baseline của dịch vụ chậm nhất 
- `verify_timeout_seconds: 60`: Đủ thời gian cho container khởi động và Prometheus thu thập metric ổn định 
- `verify_min_samples: 3`: Yêu cầu ít nhất 3 sample liên tiếp thành công để chống "false positive" 

## 4. CWhen does your circuit breaker reset? Manual or automatic? Why?
- Manual 
- Lý do: Circuit Breaker chỉ mở khi có 3 lần verify thất bại liên tiếp, hoặc action lỗi 3 lần. Đây là dấu hiệu khủng hoảng nghiêm trọng. Việc tự động reset có thể dẫn đến vòng lặp vô tận. Chế độ manual sẽ giúp dev kiểm tra log, tìm root cause và tự tay bật lại hệ thống
