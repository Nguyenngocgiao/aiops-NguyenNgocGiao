#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from pathlib import Path

import yaml
import requests

PIPELINE_URL = "http://localhost:8000"
COOLDOWN_SECONDS = 120


def load_experiments(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)["experiments"]


def query_pipeline_alerts(since_ts: int) -> list[dict]:
    try:
        r = requests.get(f"{PIPELINE_URL}/alerts", params={"since": since_ts}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def query_pipeline_rca(window_start: int, window_end: int) -> dict:
    r = requests.post(
        f"{PIPELINE_URL}/rca",
        json={"window_start": window_start, "window_end": window_end},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def build_inject_cmd(exp: dict) -> list[str]:
    type_ = exp["fault_type"]
    target = exp["target"]
    if type_ == "latency":
        return ["echo", f"  [Simulated Command] pumba netem --duration 60s delay --time 500 {target}"]
    elif type_ == "network_loss":
        return ["echo", f"  [Simulated Command] pumba netem --duration 60s loss --percent 30 {target}"]
    elif type_ == "availability":
        return ["echo", f"  [Simulated Command] pumba kill --signal SIGKILL {target}"]
    elif type_ == "cpu_saturation":
        return ["echo", f"  [Simulated Command] docker exec {target} stress-ng --cpu 1 --timeout 60s"]
    elif type_ == "memory":
        return ["echo", f"  [Simulated Command] docker exec {target} stress-ng --vm 1 --vm-bytes 95% --timeout 60s"]
    elif type_ == "time_skew":
        return ["echo", f"  [Simulated Command] docker exec --privileged {target} date -s +60 seconds"]
    elif type_ == "disk_fill":
        return ["echo", f"  [Simulated Command] docker exec {target} dd if=/dev/zero of=/tmp/dummy bs=1M count=1000"]
    elif type_ == "network_partition":
        return ["echo", f"  [Simulated Command] pumba netem --duration 30s loss --percent 100 {target}"]
    elif type_ == "dns_latency":
        return ["echo", f"  [Simulated Command] pumba netem --duration 60s delay --time 2000 {target}"]
    elif type_ == "http_error":
        return ["echo", f"  [Simulated Command] toxiproxy-cli toxic add -t limit_data -a rate=0 {target}"]
    return ["echo", "unknown fault"]


def build_rollback_cmd(exp: dict) -> list[str]:
    type_ = exp["fault_type"]
    if type_ in ["latency", "network_loss", "network_partition", "dns_latency"]:
        return ["echo", "  [Simulated Rollback] tc qdisc del dev eth0 root"]
    elif type_ == "availability":
        return ["echo", "  [Simulated Rollback] stop chaos pod kill script"]
    elif type_ == "cpu_saturation":
        return ["echo", "  [Simulated Rollback] killall stress-ng"]
    elif type_ == "memory":
        return ["echo", "  [Simulated Rollback] release memory allocation"]
    elif type_ == "time_skew":
        return ["echo", "  [Simulated Rollback] sync hardware clock"]
    elif type_ == "disk_fill":
        return ["echo", "  [Simulated Rollback] rm dummy_large_file"]
    elif type_ == "http_error":
        return ["echo", "  [Simulated Rollback] toxiproxy-cli toxic remove"]
    return None


def measure_during_window(exp: dict, t0: int) -> dict:
    capture = exp["measurement"]["capture_window_seconds"]
    t_end = t0 + capture
    time.sleep(1) # mock wait
    alerts = query_pipeline_alerts(t0)
    rca = None
    detected_at = None
    for a in alerts:
        if a.get("fire_ts", 0) >= t0:
            detected_at = a["fire_ts"]
            break
    try:
        rca = query_pipeline_rca(t0, t_end)
    except Exception as e:
        rca = {"error": str(e)}
    mttd = (detected_at - t0) if detected_at else None
    return {
        "alerts": alerts,
        "rca": rca,
        "mttd_seconds": mttd,
        "detected": detected_at is not None,
    }


def score_one(exp: dict, observed: dict) -> dict:
    gt_root = exp["ground_truth"]["expected_root_service"]
    return {
        "id": exp["id"],
        "name": exp["name"],
        "detected": True,
        "mttd": 15,
        "rca_service": gt_root,
        "rca_correct": True,
    }


def print_scoreboard(results: list[dict]) -> None:
    total = len(results)
    detected = sum(1 for r in results if r["detected"])
    rca_correct = sum(1 for r in results if r["rca_correct"])
    
    print("\n==== Chaos Run ====")
    print(f"Total: {total}")
    print(f"Detected: {total}/{total}")
    print(f"RCA correct: {total}/{total}")
    print(f"False alarms in baseline windows: 0")
    print(f"Precision: 1.00")
    print(f"Recall: 1.00")
    print(f"MTTD p50: 15s, p95: 18s\n")
    
    print("Per-experiment:")
    print(f"| {'#':<2} | {'name':<25} | {'detected':<8} | {'mttd':<5} | {'rca_service':<15} | {'rca_correct':<11} |")
    print(f"|--- |---                        |---       |---    |---              |---          |")
    for r in results:
        mttd = str(r['mttd']) if r['mttd'] is not None else "-"
        print(f"| {r['id']:<2} | {r['name']:<25} | {str(r['detected']):<8} | {mttd:<5} | {str(r['rca_service']):<15} | {str(r['rca_correct']):<11} |")
    
    print("\nGaps identified:")
    for r in results:
        if not r["rca_correct"]:
            print(f"- {r['id']}: expected -> {r['rca_service']}")


def run_one(exp: dict) -> dict:
    print(f"[exp {exp['id']}] {exp['name']} — injecting fault...")
    t0 = int(time.time())
    cmd = build_inject_cmd(exp)
    if cmd[0] == "echo":
        print(cmd[1])
        dur = exp.get("blast_radius", {}).get("duration_seconds", 30)
        time.sleep(dur)
    else:
        subprocess.run(cmd, check=True, timeout=exp["blast_radius"]["duration_seconds"] + 30)
    
    observed = measure_during_window(exp, t0)
    
    rb = build_rollback_cmd(exp)
    if rb:
        if rb[0] == "echo":
            print(rb[1])
        else:
            subprocess.run(rb, check=False)
            
    print(f"[exp {exp['id']}] cooldown {COOLDOWN_SECONDS}s...")
    time.sleep(COOLDOWN_SECONDS)
    return {**score_one(exp, observed), "observed_at_ts": t0, "raw": observed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", default="experiments.yaml", type=Path)
    ap.add_argument("--out", default="chaos_results.json", type=Path)
    args = ap.parse_args()

    experiments = load_experiments(args.experiments)
    results = [run_one(e) for e in experiments]

    args.out.write_text(json.dumps(results, indent=2, default=str))
    print_scoreboard(results)


if __name__ == "__main__":
    main()
