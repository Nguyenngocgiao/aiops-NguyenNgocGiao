#!/usr/bin/env bash
# inject.sh — Tái hiện lỗi cạn kiệt bộ nhớ trên payment-db (W3-D3)

echo "[1/3] Bắt đầu tái hiện lỗi (Time: $(date -u +%Y-%m-%dT%H:%M:%SZ))"
echo "Tạo tiến trình ngốn 95% RAM trên container payment-db..."

# Bơm memory fill fault
docker exec payment-db stress-ng --vm 1 --vm-bytes 95% --timeout 120s &
INJECT_PID=$!

echo "[2/3] Lỗi đã được bơm. Hệ thống sẽ cạn RAM trong 2 phút tới."
echo "Hệ thống AIOps sẽ bắt đầu thu thập metric và sinh Alert."

# Đợi fault chạy xong
wait $INJECT_PID

echo "[3/3] Quá trình lỗi kết thúc. Trả lại RAM cho hệ thống (Rollback)."
echo "Hệ thống dần phục hồi về mức Baseline."
