import statistics

def log_signature_matches(sig: str, msg: str) -> bool:
    """Robust keyword matching for historical log signatures."""
    msg = msg.lower()
    sig = sig.lower()
    if sig == "failed to forward request: pool exhausted":
        return "failed to forward request" in msg and "pool exhausted" in msg
    elif sig == "connectionpool: timeout acquiring connection":
        return "connectionpool" in msg and "timeout acquiring connection" in msg
    elif sig == "db query latency > 5s on table":
        return "db query latency" in msg or ("query latency" in msg and "table" in msg)
    elif sig == "gc pause: 4127ms (full gc, heap":
        return "gc pause" in msg and "heap" in msg
    elif sig == "outofmemoryerror: java heap space":
        return "outofmemoryerror" in msg or "java heap space" in msg
    elif sig == "pod evicted: node out of memory":
        return "evicted" in msg and "out of memory" in msg
    elif sig == "retry exhausted after 5 attempts":
        return "retry exhausted" in msg
    elif sig == "tls handshake failed: certificate has expired":
        return "tls handshake failed" in msg and "expired" in msg
    elif sig == "cgroup oom kill":
        return "oom kill" in msg or "cgroup oom" in msg
    elif sig == "consumer rebalance triggered":
        return "rebalance triggered" in msg or "consumer rebalance" in msg
    elif sig == "deadlock detected on table":
        return "deadlock" in msg
    elif sig == "degraded behavior detected":
        return "degraded" in msg
    elif sig == "fallback failed, retrying request":
        return "fallback failed" in msg
    elif sig == "feature distribution drift detected on field":
        return "drift" in msg and "feature" in msg
    elif sig == "lock timeout exceeded after":
        return "lock timeout" in msg
    elif sig == "model inference confidence dropped below threshold":
        return "inference confidence" in msg or "dropped below threshold" in msg
    elif sig == "partition reassignment in progress":
        return "partition reassignment" in msg
    elif sig == "query took longer than threshold":
        return "query took longer" in msg or "longer than threshold" in msg
    elif sig == "rate limit exceeded for client":
        return "rate limit exceeded" in msg
    elif sig == "service error rate elevated":
        return "error rate elevated" in msg or "error rate" in msg
    elif sig == "x509: certificate signed by unknown authority":
        return "x509" in msg or "unknown authority" in msg
    elif sig == "429 returned to upstream":
        return "429" in msg
    return sig in msg

def extract_live_traces(incident: dict) -> dict:
    """Calculate latency deviation and error rate for active edges vs baseline."""
    detected_at = incident.get("detected_at", "")
    traces = incident.get("traces", [])
    
    edge_stats = {}
    for t in traces:
        edge = (t["from"], t["to"])
        if edge not in edge_stats:
            edge_stats[edge] = {"base_p99": [], "active_p99": [], "active_err_cnt": 0, "active_cnt": 0}
        
        if t["ts"] < detected_at:
            edge_stats[edge]["base_p99"].append(t.get("p99_ms", 0))
        else:
            edge_stats[edge]["active_p99"].append(t.get("p99_ms", 0))
            edge_stats[edge]["active_err_cnt"] += t.get("error_count", 0)
            edge_stats[edge]["active_cnt"] += t.get("count", 0)
            
    res = {}
    for edge, stats in edge_stats.items():
        if not stats["active_p99"]:
            continue
        active_p99 = statistics.median(stats["active_p99"]) if stats["active_p99"] else 1.0
        base_p99 = statistics.median(stats["base_p99"]) if stats["base_p99"] else active_p99
        if base_p99 <= 0: base_p99 = 1.0
        
        ratio = active_p99 / base_p99
        err_rate = stats["active_err_cnt"] / stats["active_cnt"] if stats["active_cnt"] > 0 else 0.0
        res[edge] = {"p99_deviation_ratio": ratio, "error_rate": err_rate}
        
    return res

def extract_live_metrics(incident: dict) -> dict:
    """Extract changes in metrics (baseline vs active window)."""
    detected_at = incident.get("detected_at", "")
    samples_dict = incident.get("metrics_window", {}).get("samples", {})
    res = {}
    for metric_name, samples in samples_dict.items():
        base_vals = [val for ts, val in samples if ts < detected_at]
        active_vals = [val for ts, val in samples if ts >= detected_at]
        if not active_vals:
            continue
        base_avg = statistics.mean(base_vals) if base_vals else 0.0
        active_avg = statistics.mean(active_vals)
        
        direction = 1 if active_avg >= base_avg else -1
        if base_avg == 0:
            ratio = active_avg if active_avg > 0 else 1.0
        else:
            ratio = abs(active_avg / base_avg)
            if ratio < 1.0 and ratio > 0:
                ratio = 1.0 / ratio
                
        # Tính toán Z-score theo quy tắc 3-Sigma (3 Độ lệch chuẩn)
        if len(base_vals) > 1:
            try:
                sigma = statistics.stdev(base_vals)
            except statistics.StatisticsError:
                sigma = 0.0
        else:
            sigma = 0.0
            
        # Nếu sigma == 0 (dữ liệu là đường thẳng), bất kỳ sự thay đổi nào cũng coi là độ lệch lớn
        if sigma > 0:
            z_score = abs(active_avg - base_avg) / sigma
        else:
            z_score = abs(active_avg - base_avg)
            
        res[metric_name] = {
            "ratio": ratio, 
            "direction": direction, 
            "base": base_avg, 
            "active": active_avg,
            "z_score": z_score
        }
    return res

def derive_root_cause_mtl_pipeline(incident: dict) -> list[str]:
    """Score services using the M-T-L (Metrics -> Traces -> Logs) workflow."""
    scores = {}
    nodes = incident.get("topology", {}).get("nodes", [])
    for n in nodes:
        scores[n["id"]] = 0.0
        
    # =================================================================
    # STEP 1: METRICS (Detect the scope and alert origin)
    # =================================================================
    alert_svc = incident.get("trigger_alert", {}).get("service")
    if alert_svc:
        scores[alert_svc] = scores.get(alert_svc, 0) + 5.0
        
    metrics = extract_live_metrics(incident)
    for m, stats in metrics.items():
        # Sử dụng luật 3-Sigma (Z-Score > 3.0) để phát hiện bất thường
        if stats["z_score"] > 3.0:
            svc = m.split(".")[0]
            scores[svc] = scores.get(svc, 0) + 1.0
            
    # =================================================================
    # STEP 2: TRACES (Localize the bottleneck or errors)
    # =================================================================
    traces = extract_live_traces(incident)
    for (fr, to), stats in traces.items():
        if stats["error_rate"] > 0.05 or stats["p99_deviation_ratio"] > 1.5:
            scores[fr] = scores.get(fr, 0) + 2.0
            scores[to] = scores.get(to, 0) + 2.0
            
    # =================================================================
    # STEP 3: LOGS (Extract evidence and volume of errors)
    # =================================================================
    for log in incident.get("logs", []):
        if log.get("level") in ["ERROR", "WARN", "CRITICAL"]:
            svc = log.get("svc")
            if svc:
                # Cap the log contribution slightly to avoid pure log flooding
                scores[svc] = min(scores.get(svc, 0) + 0.2, scores.get(svc, 0) + 3.0)
                
    # =================================================================
    # STEP 4: M-T-L SYNTHESIS (Rank the most likely root cause to the top)
    # =================================================================
    affected = [s for s, v in scores.items() if v > 1.0]
    affected.sort(key=lambda s: scores[s], reverse=True)
    if alert_svc and alert_svc not in affected:
        affected.append(alert_svc)
    return affected

def extract_features(incident: dict, all_historical_sigs: list[str]) -> dict:
    """Main entry for Layer 1. Operates on the explicit M-T-L logic."""
    
    # 1. Metrics Phase (Context Extraction)
    live_metrics = extract_live_metrics(incident)
    
    # 2. Traces Phase (Localization)
    live_traces = extract_live_traces(incident)
    
    # 3. Logs Phase (Evidence Extraction via Signatures)
    matched_log_sigs = []
    logs = incident.get("logs", [])
    msgs = " ".join([l.get("msg", "") for l in logs])
    for sig in all_historical_sigs:
        if log_signature_matches(sig, msgs):
            matched_log_sigs.append(sig)
            
    # 4. M-T-L Synthesis (Identify Root Cause & Blast Radius)
    affected_services = derive_root_cause_mtl_pipeline(incident)
            
    return {
        "matched_log_sigs": matched_log_sigs,
        "traces": live_traces,
        "metrics": live_metrics,
        "affected_services": affected_services,
        "incident": incident
    }
