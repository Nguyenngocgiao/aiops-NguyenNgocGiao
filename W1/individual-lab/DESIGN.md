# Detection Approach — DESIGN.md

## Approach tôi dùng

**Linear regression slope + Z-score trên sliding window + absolute threshold**
(Sliding Window Statistical Anomaly Detection)

## Tại sao chọn approach này

Streaming data không có ground truth sẵn và không thể train model trước. Sliding window z-score phù hợp vì:

- **Không cần training data**: tự động học baseline từ 30 tick đầu tiên (~15 phút production)
- **Thích nghi với diurnal pattern**: window mean tự cập nhật theo thời gian, tránh false alarm khi traffic tăng theo chu kỳ ngày/đêm
- **Nhẹ và real-time**: O(1) per tick, không cần lưu toàn bộ history
- **Interpretable**: alert message kèm z-score giúp on-call engineer hiểu ngay độ nghiêm trọng

## Cách hoạt động

Mỗi tick nhận được, pipeline:

1. **Cập nhật sliding window** (size=30) cho 8 metrics chính
2. **Chạy 3 detector song song**, mỗi detector kiểm tra tổ hợp signals:
   - `memory_leak`: memory_util > 80% **hoặc** linear regression slope > 2MB/tick qua 15 tick gần nhất (noise-tolerant, không yêu cầu monotonic) **hoặc** GC pause > 50ms (z>3)
   - `traffic_spike`: RPS > 3× mean **và** queue_depth bùng nổ (ít nhất 2/3 signals vượt ngưỡng để tránh false positive)
   - `dependency_timeout`: upstream_timeout_rate > 5% (baseline 0–0.4%) **và** 5xx rate hoặc latency cũng tăng cùng lúc
3. **Cooldown 10 tick** sau mỗi alert để tránh spam cùng loại
4. **Warmup 5 tick** đầu không fire alert (xây dựng baseline tối thiểu)

### Công thức z-score

```
z = (x - mean(window)) / std(window)
```

Ngưỡng z > 3.0 → xác suất giá trị đó xuất hiện ngẫu nhiên trong phân phối bình thường là < 0.3%

### Công thức linear regression slope (dùng cho memory_leak)

```
slope = Σ(xi - mean_x)(yi - mean_y) / Σ(xi - mean_x)²
```

Linear regression noise-tolerant hơn monotonic check — 1–2 tick dip do noise không làm mất signal. Ngưỡng 2MB/tick ≈ 2σ của noise slope baseline → ~2% false positive rate.

## Parameters tôi chọn

| Parameter | Giá trị | Lý do |
|-----------|---------|-------|
| `WINDOW_SIZE` | 30 | ≈15 phút production time, đủ dài để ổn định baseline, đủ ngắn để phát hiện nhanh |
| `WARMUP_POINTS` | 5 | Giữ thấp để không bỏ lỡ fault inject sớm, nhưng đủ để build slope baseline |
| `ZSCORE_THRESHOLD` | 3.0 | Standard 3-sigma rule: < 0.3% false positive rate trên phân phối chuẩn |
| `COOLDOWN_TICKS` | 10 | Không re-fire cùng alert trong ~5 phút production — tránh spam |
| `MEMORY_UTIL_CRITICAL` | 80% | Generator inject fault tăng memory dần lên limit 2GB; 80% là early warning |
| `MEM_SLOPE_THRESHOLD` | 2MB/tick | ≈2σ của noise slope baseline → cân bằng giữa sensitivity và false positive rate |
| `UPSTREAM_TIMEOUT_HIGH` | 5% | Baseline 0–0.4%, nên 5% là 12× bình thường — rõ ràng bất thường |
| `RPS_MULTIPLIER` | 3× | Traffic spike inject lên đến 8×; 3× là threshold sớm nhưng không quá nhạy |
| `GC_PAUSE_HIGH` | 50ms | Baseline 8–18ms; 50ms là ~3× max bình thường |

## Cải thiện nếu có thêm thời gian

- **EWMA (Exponentially Weighted Moving Average)** thay vì simple mean: phản ứng nhanh hơn với thay đổi đột ngột
- **Seasonal decomposition**: tách diurnal pattern ra trước khi tính z-score, giảm false alarm vào giờ cao điểm
- **Multi-metric correlation**: dùng covariance matrix để phát hiện anomaly trong không gian đa chiều (PCA-based)
- **Hysteresis**: cần N ticks liên tiếp vượt ngưỡng mới fire (giảm false positive từ noise)
- **Log NLP**: parse message trong log entries để tăng confidence (ví dụ "OutOfMemoryWarning" → boost memory_leak score)
