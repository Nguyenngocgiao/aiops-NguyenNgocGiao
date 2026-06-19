#!/usr/bin/env python3
"""AIOps W1 Individual Lab — Anomaly Detection Pipeline.

HTTP endpoint that receives streaming metrics and logs from generator,
detects anomalies using statistical methods, and writes alerts to alerts.jsonl.

Detection strategy:
- memory_leak:          Memory usage growing monotonically + GC pause rising
- traffic_spike:        RPS and queue_depth sudden jump (z-score on sliding window)
- dependency_timeout:   upstream_timeout_rate sudden spike (z-score + absolute threshold)
"""

import json
import math
import os
import uvicorn
from collections import deque
from fastapi import FastAPI, Request
from datetime import datetime, timezone
from typing import Dict, Any, Optional

app = FastAPI(title="AIOps Anomaly Detection Pipeline")

# ─── Configuration ──────────────────────────────────────────────────────────

# Absolute path: always write next to pipeline.py, regardless of where you run from
ALERTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts.jsonl")
PORT = 8000

# Sliding window size for baseline statistics
WINDOW_SIZE = 30          # data points (~30 ticks ≈ 15 min production time at 30s/tick)
WARMUP_POINTS = 5         # minimum points before we fire any alert (kept low so we don't miss early faults)

# Alert cooldown: don't re-fire the same alert type within N ticks
COOLDOWN_TICKS = 10

# Z-score threshold for "unusual" values
ZSCORE_THRESHOLD = 3.0

# Absolute thresholds (safety net, hard limits from lab spec)
MEMORY_UTIL_CRITICAL   = 0.80   # 80% of 2 GB
UPSTREAM_TIMEOUT_HIGH  = 5.0    # % (baseline is 0–0.4)
RPS_MULTIPLIER         = 3.0    # sudden 3x RPS vs window mean
QUEUE_DEPTH_HIGH       = 30     # baseline 2–10
GC_PAUSE_HIGH          = 50     # ms (baseline 8–18)

# ─── State ──────────────────────────────────────────────────────────────────

# Rolling windows (deque of float values)
windows: Dict[str, deque] = {
    "memory_usage_bytes":    deque(maxlen=WINDOW_SIZE),
    "cpu_usage_percent":     deque(maxlen=WINDOW_SIZE),
    "http_requests_per_sec": deque(maxlen=WINDOW_SIZE),
    "http_p99_latency_ms":   deque(maxlen=WINDOW_SIZE),
    "http_5xx_rate":         deque(maxlen=WINDOW_SIZE),
    "jvm_gc_pause_ms_avg":   deque(maxlen=WINDOW_SIZE),
    "queue_depth":           deque(maxlen=WINDOW_SIZE),
    "upstream_timeout_rate": deque(maxlen=WINDOW_SIZE),
}

tick_count = 0
last_alert_tick: Dict[str, int] = {}   # cooldown per alert type


# ─── Statistics helpers ──────────────────────────────────────────────────────

def mean(values) -> float:
    return sum(values) / len(values) if values else 0.0


def std(values) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def zscore(value: float, history: deque) -> float:
    """How many standard deviations is `value` from the window mean."""
    if len(history) < 2:
        return 0.0
    s = std(history)
    if s == 0:
        return 0.0
    return (value - mean(history)) / s


def is_monotonically_increasing(history: deque, min_points: int = 10) -> bool:
    """Return True if the last `min_points` values trend strictly upward."""
    if len(history) < min_points:
        return False
    recent = list(history)[-min_points:]
    # Count how many consecutive increases (allow 1 dip due to noise)
    increases = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
    return increases >= min_points - 2   # tolerate 1 noisy tick


def slope(history: deque, last_n: int = 10) -> float:
    """Simple linear slope over last_n points (rise/run)."""
    if len(history) < last_n:
        return 0.0
    ys = list(history)[-last_n:]
    xs = list(range(last_n))
    mx, my = mean(xs), mean(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(last_n))
    den = sum((xs[i] - mx) ** 2 for i in range(last_n))
    return num / den if den != 0 else 0.0


# ─── Detection logic ────────────────────────────────────────────────────────

def detect_memory_leak(metrics: Dict) -> Optional[Dict]:
    """
    Detects memory leak via:
    1. Absolute: memory_util > 80% (hard threshold)
    2. Trend: positive memory slope over sliding window (noise-tolerant)
    3. GC pressure: GC pause rising dramatically
    """
    mem_bytes = metrics["memory_usage_bytes"]
    mem_limit = metrics["memory_limit_bytes"]
    mem_util  = mem_bytes / mem_limit

    gc_pause  = metrics["jvm_gc_pause_ms_avg"]
    mem_win   = windows["memory_usage_bytes"]
    gc_win    = windows["jvm_gc_pause_ms_avg"]

    # Condition 1: absolute memory util critically high
    mem_high = mem_util > MEMORY_UTIL_CRITICAL

    # Condition 2: GC pause spiked above baseline
    gc_z = zscore(gc_pause, gc_win)
    gc_high = gc_pause > GC_PAUSE_HIGH and gc_z > ZSCORE_THRESHOLD

    # Condition 3: positive memory slope — primary leak signal
    # NOTE: monotonic check removed — real leak data has noise dips,
    # slope (linear regression) is noise-tolerant
    n = min(15, len(mem_win))
    mem_slope_val = slope(mem_win, last_n=n) if n >= 5 else 0.0
    # 2MB/tick ≈ 2σ of baseline noise slope → ~2% false positive rate
    mem_sloping = mem_slope_val > 2_000_000

    # Condition 4: GC slope also rising (corroborates memory leak)
    gc_slope_val = slope(gc_win, last_n=min(10, len(gc_win)))
    gc_sloping = gc_slope_val > 0.5  # baseline GC is flat ~12ms

    # Fire if: hard threshold hit, OR slope detected (+GC corroboration), OR GC spiked
    if mem_high or (mem_sloping and gc_sloping) or mem_sloping or gc_high:
        severity = "critical" if mem_util > 0.88 else "warning"
        evidence = []
        if mem_high:
            evidence.append(f"memory at {mem_util*100:.1f}%")
        if mem_sloping:
            evidence.append(f"memory slope +{mem_slope_val/1e6:.1f}MB/tick over last {n} ticks")
        if gc_high:
            evidence.append(f"GC pause {gc_pause:.0f}ms (z={gc_z:.1f})")
        elif gc_sloping and mem_sloping:
            evidence.append(f"GC also rising slope={gc_slope_val:.1f}ms/tick")
        if not evidence:
            evidence.append(f"memory at {mem_util*100:.1f}%")
        return {
            "type": "memory_leak",
            "severity": severity,
            "message": "Memory leak detected — " + "; ".join(evidence),
        }
    return None


def detect_traffic_spike(metrics: Dict) -> Optional[Dict]:
    """
    Detects:
    - RPS jumped to > 3× window mean (sudden burst)
    - Queue depth exploded above threshold
    - Both corroborating: latency also spiked
    """
    rps       = metrics["http_requests_per_sec"]
    queue     = metrics["queue_depth"]
    latency   = metrics["http_p99_latency_ms"]

    rps_win   = windows["http_requests_per_sec"]
    q_win     = windows["queue_depth"]
    lat_win   = windows["http_p99_latency_ms"]

    rps_mean  = mean(rps_win) if rps_win else rps
    rps_z     = zscore(rps, rps_win)
    q_z       = zscore(queue, q_win)
    lat_z     = zscore(latency, lat_win)

    # RPS is a huge multiple of normal, or z-score very high
    rps_spike = (rps_mean > 10 and rps > rps_mean * RPS_MULTIPLIER) or rps_z > ZSCORE_THRESHOLD

    # Queue blew up
    queue_spike = queue > QUEUE_DEPTH_HIGH or q_z > ZSCORE_THRESHOLD

    # Need at least 2 corroborating signals to avoid false positives
    signals = sum([rps_spike, queue_spike, lat_z > ZSCORE_THRESHOLD])

    if signals >= 2:
        severity = "critical" if rps_z > 5 or queue > 100 else "warning"
        evidence = []
        if rps_spike:
            evidence.append(f"RPS={rps:.0f} (mean={rps_mean:.0f}, z={rps_z:.1f})")
        if queue_spike:
            evidence.append(f"queue_depth={queue} (z={q_z:.1f})")
        if lat_z > ZSCORE_THRESHOLD:
            evidence.append(f"p99_latency={latency:.0f}ms (z={lat_z:.1f})")
        return {
            "type": "traffic_spike",
            "severity": severity,
            "message": "Traffic spike detected — " + "; ".join(evidence),
        }
    return None


def detect_dependency_timeout(metrics: Dict) -> Optional[Dict]:
    """
    Detects:
    - upstream_timeout_rate spikes above 5% (baseline ≈ 0–0.4%)
    - 5xx rate surges corroboratively
    - latency also rising (upstream waits on timeouts)
    """
    timeout_rate = metrics["upstream_timeout_rate"]
    rate_5xx     = metrics["http_5xx_rate"]
    latency      = metrics["http_p99_latency_ms"]

    to_win       = windows["upstream_timeout_rate"]
    err_win      = windows["http_5xx_rate"]
    lat_win      = windows["http_p99_latency_ms"]

    to_z   = zscore(timeout_rate, to_win)
    err_z  = zscore(rate_5xx, err_win)
    lat_z  = zscore(latency, lat_win)

    # Hard threshold: timeout rate jumped well beyond normal
    timeout_high = timeout_rate > UPSTREAM_TIMEOUT_HIGH or to_z > ZSCORE_THRESHOLD

    # 5xx rate also elevated
    err_high = rate_5xx > 2.0 or err_z > ZSCORE_THRESHOLD

    # Need both timeout + one of 5xx or latency spike
    signals = sum([timeout_high, err_high, lat_z > ZSCORE_THRESHOLD])

    if timeout_high and signals >= 2:
        severity = "critical" if timeout_rate > 20 or rate_5xx > 10 else "warning"
        evidence = []
        evidence.append(f"upstream_timeout_rate={timeout_rate:.1f}% (z={to_z:.1f})")
        if err_high:
            evidence.append(f"http_5xx_rate={rate_5xx:.1f}% (z={err_z:.1f})")
        if lat_z > ZSCORE_THRESHOLD:
            evidence.append(f"p99_latency={latency:.0f}ms (z={lat_z:.1f})")
        return {
            "type": "dependency_timeout",
            "severity": severity,
            "message": "Dependency timeout cascade detected — " + "; ".join(evidence),
        }
    return None


DETECTORS = [detect_memory_leak, detect_traffic_spike, detect_dependency_timeout]


# ─── Alert writer ────────────────────────────────────────────────────────────

def write_alert(alert: Dict[str, Any]):
    """Append alert JSON line to alerts.jsonl."""
    try:
        with open(ALERTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[ERROR] Failed to write alert: {e}")


def in_cooldown(alert_type: str) -> bool:
    """Return True if we recently fired this alert type (suppress duplicate)."""
    last = last_alert_tick.get(alert_type, -COOLDOWN_TICKS - 1)
    return (tick_count - last) < COOLDOWN_TICKS


# ─── HTTP endpoints ──────────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest(request: Request):
    """Receive metrics + logs from generator, run anomaly detection."""
    global tick_count

    try:
        payload   = await request.json()
        timestamp = payload["timestamp"]
        metrics   = payload["metrics"]
        logs      = payload["logs"]

        tick_count += 1

        # Update rolling windows
        for key in windows:
            if key in metrics:
                windows[key].append(float(metrics[key]))

        # Log summary every tick
        mem_util = metrics["memory_usage_bytes"] / metrics["memory_limit_bytes"]
        print(
            f"[TICK {tick_count:04d}] {timestamp[:19]} | "
            f"mem={mem_util*100:.1f}% | cpu={metrics['cpu_usage_percent']}% | "
            f"rps={metrics['http_requests_per_sec']} | "
            f"q={metrics['queue_depth']} | "
            f"timeout={metrics['upstream_timeout_rate']}% | "
            f"gc={metrics['jvm_gc_pause_ms_avg']}ms"
        )

        # Scan logs for ERROR/FATAL lines (corroborating evidence)
        for log in logs:
            if log.get("level") in ("ERROR", "FATAL"):
                print(f"  [LOG {log['level']}] {log['message']}")

        # Skip detection during warmup to avoid false positives
        if tick_count < WARMUP_POINTS:
            return {"status": "ok", "tick": tick_count, "phase": "warmup"}

        # Run all detectors
        for detector in DETECTORS:
            result = detector(metrics)
            if result is None:
                continue
            alert_type = result["type"]
            if in_cooldown(alert_type):
                continue
            # Fire alert
            alert = {
                "timestamp": timestamp,
                "type": alert_type,
                "severity": result["severity"],
                "message": result["message"],
            }
            write_alert(alert)
            last_alert_tick[alert_type] = tick_count
            print(f"  ⚠️  [ALERT] type={alert_type} severity={result['severity']}")
            print(f"      {result['message']}")

        return {"status": "ok", "tick": tick_count}

    except Exception as e:
        print(f"[ERROR] Failed to process request: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "running",
        "tick": tick_count,
        "endpoint": "/ingest",
    }


@app.get("/status")
async def status():
    """Current window stats for debugging."""
    if tick_count == 0:
        return {"status": "waiting for data"}
    stats = {}
    for key, win in windows.items():
        if win:
            stats[key] = {
                "mean": round(mean(win), 2),
                "std":  round(std(win), 2),
                "last": round(win[-1], 2),
            }
    return {"tick": tick_count, "windows": stats, "alerts_fired": list(last_alert_tick.keys())}


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[PIPELINE] AIOps Anomaly Detection Pipeline")
    print(f"[PIPELINE] Listening on http://0.0.0.0:{PORT}/ingest")
    print(f"[PIPELINE] Alerts → {ALERTS_FILE}")
    print(f"[PIPELINE] Warmup: {WARMUP_POINTS} ticks | Window: {WINDOW_SIZE} | Cooldown: {COOLDOWN_TICKS}")
    print("─" * 60)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
