Title: Live Content Description: Fetched live Source: https://learning-notes-dz2.pages.dev/xbrain/aiops-w3/w3-d2-chaos-engineering/ \--- 

[My Learning Notes](https://learning-notes-dz2.pages.dev/ "My Learning Notes \(Alt + H\)")

  * [Archive](https://learning-notes-dz2.pages.dev/archives "Archive")
  * [Search](https://learning-notes-dz2.pages.dev/search/ "Search \(Alt + /\)")
  * [Tags](https://learning-notes-dz2.pages.dev/tags/ "Tags")
  * [Notes](https://learning-notes-dz2.pages.dev/notes/ "Notes")
  * [XBrain](https://learning-notes-dz2.pages.dev/xbrain/ "XBrain")

[← AIOps W3 — Reliability Engineering & Postmortem](https://learning-notes-dz2.pages.dev/xbrain/aiops-w3/)

# W3-D2: Chaos Engineering — Validate AIOps Pipeline

14 min read 2939 words

Table of Contents

* [Chaos Engineering — Fault Injection để Validate AIOps Pipeline](#chaos-engineering-fault-injection-để-validate-aiops-pipeline)
  * [1. Định nghĩa](#1-định-nghĩa)
  * [2. 5 nguyên tắc cốt lõi](#2-5-nguyên-tắc-cốt-lõi)
  * [3. Fault categories](#3-fault-categories)
    * [3.1 Network faults](#31-network-faults)
    * [3.2 Resource faults](#32-resource-faults)
    * [3.3 Application faults](#33-application-faults)
    * [3.4 State faults](#34-state-faults)
  * [4. Tool landscape](#4-tool-landscape)
  * [5. Experiment design template](#5-experiment-design-template)
    * [5.1 Hypothesis viết đúng](#51-hypothesis-viết-đúng)
    * [5.2 Blast radius escalation](#52-blast-radius-escalation)
  * [6. Measurement framework cho AIOps pipeline](#6-measurement-framework-cho-aiops-pipeline)
    * [6.1 Confusion matrix per experiment](#61-confusion-matrix-per-experiment)
    * [6.2 RCA accuracy](#62-rca-accuracy)
    * [6.3 Scoreboard sau N experiment](#63-scoreboard-sau-n-experiment)
    * [6.4 External steady-state signal — synthetic probes](#64-external-steady-state-signal-synthetic-probes)
  * [7. Pipeline failure modes — observed in real incidents](#7-pipeline-failure-modes-observed-in-real-incidents)
    * [7.1 Detector miss: anomaly chìm dưới noise floor](#71-detector-miss-anomaly-chìm-dưới-noise-floor)
    * [7.2 Correlator false positive: gộp fault độc lập thành 1 incident](#72-correlator-false-positive-gộp-fault-độc-lập-thành-1-incident)
    * [7.3 RCA wrong root: pick service ồn nhất, không phải gốc](#73-rca-wrong-root-pick-service-ồn-nhất-không-phải-gốc)
    * [7.4 LLM hallucination với confidence cao](#74-llm-hallucination-với-confidence-cao)
    * [7.5 Monitoring dependency loop](#75-monitoring-dependency-loop)
  * [8. Bài tập](#8-bài-tập)
    * [8.1 Setup được cung cấp](#81-setup-được-cung-cấp)
    * [8.2 Bước 1 — Capture baseline + start synthetic probe](#82-bước-1-capture-baseline-start-synthetic-probe)
    * [8.3 Bước 2 — Experiment catalog](#83-bước-2-experiment-catalog)
    * [8.4 Bước 3 — Fill `experiments.yaml`](#84-bước-3-fill-experimentsyaml)
    * [8.5 Bước 4 — Implement `chaos_runner.py`](#85-bước-4-implement-chaos_runnerpy)
    * [8.6 Bước 5 — Chạy 10 experiment + score](#86-bước-5-chạy-10-experiment-score)
    * [8.7 Bước 6 — Viết `chaos_report.md`](#87-bước-6-viết-chaos_reportmd)
    * [8.8 Bước 7 — `SUBMIT.md`](#88-bước-7-submitmd)
    * [8.9 Acceptance checklist](#89-acceptance-checklist)
  * [9. Anti-patterns](#9-anti-patterns)
  * [10. References](#10-references)

# Chaos Engineering — Fault Injection để Validate AIOps Pipeline

## 1. Định nghĩa

**Chaos Engineering** — discipline thực nghiệm có chủ đích inject fault vào distributed system để khám phá weakness _trước khi_ fault xảy ra tự nhiên trong prod.

Khác biệt với 3 thứ thường nhầm:

Thực hành| Mục tiêu| Khi nào chạy  
---|---|---  
Unit test| Verify code đúng spec| CI/CD  
Load test| Verify system chịu được tải dự kiến| Pre-launch, periodic  
Penetration test| Tìm security vulnerability| Quarterly  
**Chaos engineering**| **Tìm reliability weakness do interaction giữa các component**| **Continuously, in production-like env**  
  
Source: Casey Rosenthal et al., _Principles of Chaos Engineering_ , [principlesofchaos.org](https://principlesofchaos.org/) (2017, refined 2019).

* * *

## 2. 5 nguyên tắc cốt lõi

Theo principlesofchaos.org:

  1. **Build a hypothesis around steady-state behavior** — define "system OK" bằng metric đo lường được trước khi inject.
  2. **Vary real-world events** — inject fault mô phỏng real failure: instance crash, network latency, dependency timeout.
  3. **Run experiments in production** — staging không reproduce được scale/traffic shape của prod. Chỉ prod-chaos mới catch được class of bug do scale.
  4. **Automate experiments to run continuously** — manual chaos = 1 lần/quý = không đáng tin. Automated chaos = continuous verification.
  5. **Minimize blast radius** — start nhỏ (1 instance, 1% traffic), tăng dần. Có rollback đủ nhanh.



* * *

## 3. Fault categories

4 lớp fault, mỗi lớp có tool và mechanism chuẩn:

### 3.1 Network faults

Fault| Mechanism| Tool  
---|---|---  
Latency injection| `tc netem delay 500ms ± 100ms`| Pumba, Chaos Mesh, Toxiproxy  
Packet loss| `tc netem loss 30%`| Pumba `netem`, Chaos Mesh `NetworkChaos`  
Bandwidth throttle| `tc tbf rate 1mbit`| Pumba  
Partition (split-brain)| `iptables -A INPUT -s X -j DROP`| Chaos Mesh `partition`, Pumba  
DNS slow/fail| Override resolver| Toxiproxy, Chaos Mesh `DNSChaos`  
  
### 3.2 Resource faults

Fault| Mechanism| Tool  
---|---|---  
CPU stress| `stress-ng --cpu 4 --cpu-load 90`| Pumba `stress`, Chaos Mesh `StressChaos`  
Memory fill| `stress-ng --vm 1 --vm-bytes 80%`| Chaos Mesh, Litmus `pod-memory-hog`  
Disk I/O saturation| `dd if=/dev/zero of=/tmp/file bs=1M`| Chaos Mesh `IOChaos`  
Disk fill| Fill volume to 95%| Litmus `disk-fill`  
File descriptor exhaustion| Open N fds| Custom script  
  
### 3.3 Application faults

Fault| Mechanism| Tool  
---|---|---  
Pod/container kill| `docker kill`, `kubectl delete pod`| Chaos Monkey, Pumba `kill`, Litmus `pod-delete`  
Pause (SIGSTOP)| Process freeze without crash| Pumba `pause`  
HTTP error inject| Proxy injects 5xx response| Toxiproxy, Chaos Mesh `HTTPChaos`  
HTTP slow response| Proxy delays response| Toxiproxy  
Exception injection| Bytecode rewrite| Byteman (JVM), Failify  
  
### 3.4 State faults

Fault| Mechanism| Tool  
---|---|---  
Clock skew| `libfaketime`, `chrony` manipulation| Chaos Mesh `TimeChaos`  
Time jump (forward/backward)| `date -s`| Chaos Mesh `TimeChaos`  
Config corruption| Replace config file| Custom  
Cache poisoning| Inject bad data into Redis| Custom  
  
* * *

## 4. Tool landscape

Tool| Vendor| Scope| License| Strengths| Limits  
---|---|---|---|---|---  
**Chaos Monkey**|  Netflix| EC2/cloud instance| Apache 2.0| Pioneer, simple kill| Instance-only  
**Pumba**|  Alexei Ledenev| Docker| MIT| Simple CLI, no infra| Docker only, no K8s  
**Chaos Mesh**|  PingCAP / CNCF (incubating)| Kubernetes| Apache 2.0| CRD-driven, dashboard, broad fault types| K8s only  
**LitmusChaos**|  MayaData / CNCF (incubating)| Kubernetes| Apache 2.0| ChaosHub experiment library, CI/CD integration| K8s only  
**Toxiproxy**|  Shopify| Network proxy| MIT| Deterministic, framework-agnostic, test-friendly| Network layer only  
**Gremlin**|  Gremlin Inc| Multi-platform| Commercial| Enterprise UI, safety controls, ALFI (app-level)| Closed-source, paid  
**AWS FIS**|  AWS| AWS workloads| AWS service| Integrated với AWS console + IAM| AWS only  
**Azure Chaos Studio**|  Azure| Azure workloads| Azure service| Same Azure-only| Azure only  
  
Decision tree pick tool:
    
    
    Env là gì?
    ├── Docker only (dev/local) → Pumba
    ├── Kubernetes
    │   ├── Cần CI/CD integration → LitmusChaos
    │   ├── Cần dashboard + broad fault → Chaos Mesh
    │   └── Đơn giản nhất → Chaos Monkey for K8s
    ├── Network test deterministic → Toxiproxy
    ├── Cloud-managed
    │   ├── AWS → FIS
    │   └── Azure → Chaos Studio
    └── Enterprise, có budget → Gremlin
    

Sources:

  * Pumba: [github.com/alexei-led/pumba](https://github.com/alexei-led/pumba)
  * Chaos Mesh: [chaos-mesh.org](https://chaos-mesh.org/)
  * LitmusChaos: [litmuschaos.io](https://litmuschaos.io/)
  * Toxiproxy: [github.com/Shopify/toxiproxy](https://github.com/Shopify/toxiproxy)
  * AWS FIS: [aws.amazon.com/fis](https://aws.amazon.com/fis/)



* * *

## 5. Experiment design template

5 field bắt buộc theo Rosenthal & Jones, _Chaos Engineering_ , O'Reilly 2020:
    
    
    experiment:
      name: "Payment service network partition under load"
      hypothesis: |
        Steady-state: order_success_rate ≥ 99.5%, checkout_p99 ≤ 800ms.
        Khi payment-svc bị partition từ checkout-svc, retry logic
        sẽ failover to backup payment provider trong < 30s, 
        order_success_rate sẽ giảm không quá 5% trong 60s.    
      blast_radius:
        target: 1 instance of payment-svc
        traffic: 10% of production traffic (canary cell)
        duration: 60 seconds
      rollback:
        automatic: true
        trigger_when: order_success_rate < 90% OR checkout_p99 > 3s
        method: iptables flush, restart sidecar
      measurement:
        metrics: [order_success_rate, checkout_p99, payment_retry_count, error_log_rate]
        capture_window: t-5min to t+10min
      abort_conditions:
        - any SLO breach beyond budget for 30s
        - alert tier-1 fires
    

### 5.1 Hypothesis viết đúng

Sai (vague): "system should still work."

Đúng (testable): "order_success_rate ≥ 99.5%, p99 latency ≤ 800ms during 60s partition."

### 5.2 Blast radius escalation

Khi experiment pass, mở rộng từng bước:

Stage| Target| Traffic  
---|---|---  
1 — Dev| Single dev container| 0% (synthetic)  
2 — Staging| Full staging stack| 0% (load test)  
3 — Prod canary| 1 instance| 1-10%  
4 — Prod region| 1 region| 25-100%  
5 — Prod global| All regions| 100% (game day)  
  
Không skip stage. Stage trước fail → stop, fix, retry.

* * *

## 6. Measurement framework cho AIOps pipeline

Mục tiêu chaos của lab này: validate pipeline W1+W2 (detector, correlator, RCA) có catch được injected fault không.

### 6.1 Confusion matrix per experiment

| Pipeline reported incident| Pipeline silent  
---|---|---  
**Fault injected (ground truth)**|  TP (detected)| FN (miss)  
**No fault** (baseline window)| FP (false alarm)| TN (correct silence)  
  
Tính metric cho pipeline:

**precision** = TP / (TP + FP)
**recall** = TP / (TP + FN)

**MTTD** = mean(alert_fire_time - fault_inject_time)

### 6.2 RCA accuracy

Beyond detection, kiểm tra RCA pick đúng service không:

| RCA pick correct root| RCA pick wrong root| RCA no output  
---|---|---|---  
Fault → service A| RCA_correct| RCA_wrong (e.g., picked loudest downstream)| RCA_miss  
  
**rca_accuracy** = RCA_correct / TP

### 6.3 Scoreboard sau N experiment
    
    
    | Experiment              | Detected | MTTD | RCA correct | False alarms |
    |-------------------------|----------|------|-------------|--------------|
    | payment latency +500ms  | Y        | 47s  | Y           | 0            |
    | db kill                 | Y        | 12s  | N (picked api)| 0          |
    | cache cpu 90%           | N        | —    | —           | —            |
    | network partition       | Y        | 23s  | Y           | 1            |
    | ...                                                                  |
    | TOTAL: 8/10 detected, precision 0.89, recall 0.80, RCA_acc 0.75       |
    

### 6.4 External steady-state signal — synthetic probes

§6.1 đo TP/FN dựa trên "pipeline có fire alert không". Câu hỏi sâu hơn của chaos là **" user có cảm nhận được fault không"** — và signal sạch nhất cho câu đó là **external blackbox probe** : 1 process chạy ngoài cluster, gọi endpoint user dùng, ghi pass/fail. Probe pass-rate = canonical steady-state signal, không phụ thuộc metric nội bộ pipeline.

**Vì sao external > internal cho chaos steady-state:**

Aspect| Internal metric (Prom scrape)| External synthetic probe  
---|---|---  
Đo gì| System claims OK| User-visible OK  
Bị "fooled" bởi| 200 với body sai, cache stale, partial degrade| Khó — đo đúng cái user thấy  
Chứng minh user impact| Gián tiếp (phải infer)| Trực tiếp (probe = user proxy)  
Catch được| Service crash, slow query| Cộng thêm: DNS, TLS, ingress, LB, WAF misconfig  
  
Chaos principle #1 (build hypothesis around steady-state) cần signal đo được user experience — không phải metric nội bộ. Probe ngoài cluster là implementation gần nhất với "user thật".

**Minimal example — 20-line shell probe:**
    
    
     #!/usr/bin/env bash
    # synthetic_probe.sh — log pass/fail mỗi 5s, dùng làm steady-state signal
    ENDPOINT="${1:-http://localhost:8080/checkout/health}"
    LOG="${2:-probe.log}"
    while true; do
      ts=$(date -u +%s)
      start=$(date +%s%N)
      code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$ENDPOINT")
      end=$(date +%s%N)
      latency_ms=$(( (end - start) / 1000000 ))
      if [[ "$code" == "200" && "$latency_ms" -lt 500 ]]; then
        echo "$ts pass $latency_ms" >> "$LOG"
      else
        echo "$ts fail $code $latency_ms" >> "$LOG"
      fi
      sleep 5
    done
    

Steady-state = "≥ 99% pass trong window 60s". Trong chaos run:

  * Before inject: probe chạy 5 phút → confirm steady-state.
  * During inject: pass-rate drop → quantify user impact (không cần Prom).
  * After rollback: pass-rate phải về ≥ 99% trong 2 phút → định nghĩa "system recovered".



**Gotcha — probe location quyết định bắt được gì:**

Probe từ đâu| Bắt được fault gì| Miss gì  
---|---|---  
Cùng pod| Pod logic crash| Network, LB, ingress, DNS  
Cùng cluster| \+ kube-dns, internal LB| External LB, CDN, WAN  
Ngoài cluster, cùng region| \+ ingress, cert, public DNS| Inter-region routing, CDN edge  
Multi-region external| Gần nhất với user thật| Cost cao hơn, FP do internet flap  
  
Cho lab này: probe chạy từ máy host (ngoài docker compose network) đủ — bắt được fault ở api-gateway, ingress, internal LB. Production thật cần multi-region tool (k6 Cloud, Grafana Synthetic Monitoring, Datadog Synthetics).

**References:**

  * Google SRE Workbook ch.5 — "black-box monitoring" pattern
  * [k6.io](https://k6.io/) — open-source load + synthetic
  * [Grafana Synthetic Monitoring](https://grafana.com/products/cloud/synthetic-monitoring/) — managed external probe



* * *

## 7. Pipeline failure modes — observed in real incidents

### 7.1 Detector miss: anomaly chìm dưới noise floor

Roblox October 2021 (73-hour outage): Consul streaming feature contention không trip latency threshold vì baseline Consul đã variable. Anomaly detection 3σ trên Consul read latency: noise floor lớn → 3σ bound ≈ 50× normal → real anomaly chỉ 5× → silent.

**Counter:** percentile-based anomaly trên p99, không trên mean. Hoặc segmented baseline (peak vs off-peak).

Source: [about.roblox.com/newsroom/2022/01/roblox-return-to-service-10-28-10-31-2021](https://about.roblox.com/newsroom/2022/01/roblox-return-to-service-10-28-10-31-2021)

### 7.2 Correlator false positive: gộp fault độc lập thành 1 incident

Khi 2 fault không liên quan xảy ra cùng 5 phút (deploy bug A + Network blip B), correlator dựa time + service → cluster chung. RCA pick 1 service làm root → wrong.

**Counter:** topology-aware correlation (dùng dependency graph), không chỉ temporal.

### 7.3 RCA wrong root: pick service ồn nhất, không phải gốc

Retry-storm pattern: payment-svc fail → checkout-svc retry 10× → checkout fires 10× alert. Naive RCA: rank by alert count → pick checkout. Đúng root: payment.

**Counter:** topology-aware (root upstream of leaves) + temporal-causal (root drift before downstream) — Granger causality, cross-correlation lag analysis.

### 7.4 LLM hallucination với confidence cao

LLM-augmented RCA (W2-D2) đôi khi sinh root cause plausible nhưng sai, confidence 0.9+. Engineer trust → fix nhầm service → 30 phút phí.

**Counter:** grounded confidence — chỉ cao khi có evidence link (metric anomaly + log signature + topology distance). Reject output nếu citation rỗng.

### 7.5 Monitoring dependency loop

Roblox 2021: monitoring stack sống trên Consul. Consul sập → monitoring không alert → AIOps không có input → silent black-out.

**Counter:** AIOps platform có observability stack riêng, không depend on monitored services.

* * *

## 8. Bài tập

### 8.1 Setup được cung cấp

Download **starter pack** (skeleton — không phải full stack):
    
    
    wget https://learning-notes-dz2.pages.dev/aiops-w3/lab/w3-d2-pack.zip
    unzip w3-d2-pack.zip -d w3-d2-pack/
    cd w3-d2-pack/
    cat README.md   # đọc trước
    

Pack ship sẵn:
    
    
    README.md                         hướng dẫn integrate với stack của bạn
    experiments_template.yaml         10-entry YAML — fill 2-9 yourself
    synthetic_probe.sh                external steady-state probe (§6.4)
    pipeline/chaos_runner_skeleton.py runner với 2 TODO functions (§8.5)
    configs/prometheus_targets.yml    example scrape targets — adapt to your stack
    scripts/
    ├── start_stack.sh                stub — wire to your docker-compose
    ├── capture_baseline.py           N-min Prometheus snapshot → baseline.json
    ├── query_pipeline.py             call /alerts + /correlate + /rca
    └── score_run.py                  scoreboard from chaos_results.json
    

Pack KHÔNG ship (bạn tự dựng hoặc lấy lại từ W2 Lab C):

  * `docker-compose.yml` cho 10-service stack
  * Source code của 10 mock services (frontend, api-gateway, payment-svc, inventory-svc, notification-svc, checkout-svc, auth-svc, log-collector, dns-resolver, cache-svc)
  * AIOps pipeline FastAPI exposing `/alerts`, `/correlate`, `/rca`
  * Pumba + Toxiproxy binaries (cài riêng — xem §4)



Khuyến nghị: clone stack từ W2 Lab C của group bạn, mở rộng thêm 5-7 service nếu chưa đủ 10, rồi sửa `scripts/start_stack.sh` để gọi `docker compose up -d` từ stack đó.

Topology target (stack bạn dựng nên match được hình này):
    
    
    frontend → api-gateway → ┬→ payment-svc → payment-db
                             ├→ inventory-svc → inventory-db
                             ├→ notification-svc → kafka
                             └→ checkout-svc → ┬→ payment-svc
                                               └→ inventory-svc
    + auth-svc, log-collector, dns-resolver, cache-svc
    + prometheus 2.50, grafana 10.4, alertmanager 0.27
    + AIOps pipeline (FastAPI on port 8000):
       - GET  /alerts?since=<ts>       → list alert đã fire
       - POST /correlate {window}      → cluster
       - POST /rca {cluster}           → {root_service, confidence, evidence}
    

### 8.2 Bước 1 — Capture baseline + start synthetic probe
    
    
    bash scripts/start_stack.sh                     # đợi tất cả service healthcheck OK
    python scripts/capture_baseline.py --duration 300 --out baseline.json
    
    # canonical steady-state signal — chạy nền suốt 10 experiment (xem §6.4)
    nohup bash synthetic_probe.sh http://localhost:8080/checkout/health probe.log &
    echo $! > probe.pid
    

`baseline.json` chứa steady-state mean + p99 cho mỗi (service, metric) — dùng để xác định "back to normal" sau experiment trên metric nội bộ. `probe.log` cung cấp signal độc lập (external user-visible) — pass-rate phải ≥ 99% trong 60s window trước khi bắt đầu Bước 2; nếu chưa đạt là stack chưa healthy thật, không phải lỗi probe.

### 8.3 Bước 2 — Experiment catalog

#| Target| Fault| Expected pipeline response  
---|---|---|---  
1| payment-svc| netem delay +500ms| detect latency anomaly, RCA pick payment  
2| payment-svc| netem loss 30%| detect error_rate, RCA pick payment  
3| inventory-svc| pod kill every 60s| detect availability, RCA pick inventory  
4| api-gateway| stress CPU 90%| detect latency cascade across all downstream  
5| payment-db| memory fill 95%| detect connection pool, RCA pick payment-db  
6| auth-svc (lateral)| clock skew +60s| detect cert/JWT fail, RCA pick auth  
7| log-collector| disk fill 95%| detect log ingestion lag (meta-monitoring catch?)  
8| frontend ↔ api-gateway| full partition 30s| detect all-downstream timeout, RCA pick edge  
9| dns resolver| slow lookup +2s| detect intermittent error, RCA depends on topology  
10| checkout-svc| HTTP 500 inject 20%| retry storm scenario, RCA must NOT pick checkout  
  
10 experiment phải chạy đủ. Trật tự không quan trọng nhưng phải có **120s cooldown giữa mỗi cái** (chờ system về baseline).

### 8.4 Bước 3 — Fill `experiments.yaml`

Copy `experiments_template.yaml → experiments.yaml`. Field structure theo §5 (5 field: name, hypothesis, blast_radius, rollback, measurement, ground_truth). Entry #1 + #10 đã fill làm reference; #2-9 còn TODO. 10 entry phải đầy đủ trước khi chạy runner. Catalog ở §8.3.

### 8.5 Bước 4 — Implement `chaos_runner.py`

Copy `pipeline/chaos_runner_skeleton.py → chaos_runner.py`. Implement 2 function được mark TODO trong skeleton:

  * `build_inject_cmd(exp)` — dispatcher theo `fault_type`, return command list cho `subprocess.run`. Phủ 10 fault type ở §3 (latency, network_loss, availability, cpu_saturation, memory, disk_fill, time_skew, network_partition, dns_latency, cascade_retry).
  * `print_scoreboard(results)` — print confusion matrix theo format ở §8.6.



### 8.6 Bước 5 — Chạy 10 experiment + score
    
    
    python chaos_runner.py
    # → chaos_results.json + stdout scoreboard
    

Scoreboard format bắt buộc:
    
    
    ==== Chaos Run ====
    Total: 10
    Detected: <N>/10
    RCA correct: <N>/<detected>
    False alarms in baseline windows: <N>
    Precision: <float>
    Recall: <float>
    MTTD p50: <s>, p95: <s>
    
    Per-experiment:
    | # | name              | detected | mttd  | rca_service  | rca_correct |
    |---|-------------------|----------|-------|--------------|-------------|
    | 1 | payment_latency   | Y        | 28s   | payment-svc  | Y           |
    | 2 | ...               | ...      | ...   | ...          | ...         |
    
    Gaps identified:
    - <experiment id>: <symptom> → <suspected root cause in pipeline>
    

**Acceptance:**

  * Detected ≥ 7/10 (70% recall)
  * RCA correct ≥ 5/7 trên những cái detected (≈70% RCA accuracy)
  * False alarm trong 5-min baseline window ≤ 1



Nếu fail acceptance: log gap vào §8.7, không tune pipeline để force pass (đó là dishonest).

### 8.7 Bước 6 — Viết `chaos_report.md`

Sections bắt buộc:
    
    
    # Chaos Engineering Report — <your name>
    
    ## 1. Setup
    - Stack version + commit hash
    - Pipeline version + commit hash
    - Baseline window: <start> → <end>
    - Total experiments run: 10
    
    ## 2. Results table
    [paste scoreboard từ §8.6]
    
    ## 3. Detailed per-experiment analysis
    Cho MỖI experiment, 80-150 từ:
    - Hypothesis (copy từ experiments.yaml)
    - Observed: detected hay không, MTTD, RCA service
    - Match expected? Nếu không, lý do (data evidence)
    
    ## 4. Gap analysis — top 3 pipeline weakness
    Mỗi gap:
    - Symptom: <quan sát cụ thể, experiment nào, số gì>
    - Likely cause in pipeline: <detector? correlator? RCA?>
    - Recommended fix: <concrete, có tham chiếu §7 failure modes>
    
    ## 5. Hypothesis cho gap chưa khẳng định
    [Optional but encouraged] Gap nào cần experiment thêm để xác định?
    

### 8.8 Bước 7 — `SUBMIT.md`
    
    
    # W3-D2 Submission — <your name>
    
    ## 3 thứ tôi học được về AIOps pipeline của mình
    1. ...
    2. ...
    3. ...
    
    ## 1 fault mà tôi mong pipeline catch nhưng nó miss
    - Experiment: ...
    - Why I expected detection: ...
    - Why pipeline missed (hypothesis): ...
    
    ## 1 trade-off trong design pipeline mà tôi muốn rethink
    ...
    
    ## Scoreboard summary
    - detected: __/10
    - rca_correct: __/__
    - mttd_p50: __s
    - false_alarms: __
    - verdict: __
    

### 8.9 Acceptance checklist

  * `experiments.yaml` có đủ 10 entry, mỗi cái có cả 5 field (hypothesis, blast_radius, rollback, measurement, ground_truth)
  * `chaos_runner.py` chạy được, không hard-code experiment
  * `chaos_results.json` có đủ 10 entry
  * `probe.log` chạy xuyên suốt 10 experiment, attach vào submission (chứng minh external steady-state signal)
  * Scoreboard print đúng format §8.6
  * Đạt acceptance §8.6: detected ≥ 7/10, RCA correct ≥ 5/detected, FA ≤ 1
  * `chaos_report.md` có cả 4 section bắt buộc (5 là optional)
  * `SUBMIT.md` đủ 4 section



* * *

## 9. Anti-patterns

Anti-pattern| Hậu quả  
---|---  
Inject fault không có hypothesis| Phá system, không học gì  
Inject vào prod trước khi pass staging| Outage thật, không phải chaos  
Quên rollback script| Fault dính sau experiment, ops phải fix  
Measurement chỉ "system còn sống"| Bỏ qua silent failure, partial degradation  
Skip blast radius escalation| Stage 1 fail → stage 5 destroys prod  
Chaos monthly, không continuous| 30 ngày drift giữa các run → bug đã in production trước khi chaos catch  
Inject 1 service, không inject combination| Real outage thường multi-fault (Roblox: streaming + BoltDB)  
Không version experiment config| Reproducibility = 0, không debug được flaky  
  
* * *

## 10. References

Source| Topic| URL  
---|---|---  
Rosenthal et al.| Principles of Chaos Engineering (canonical, 5 principles)| <https://principlesofchaos.org/>  
Rosenthal & Jones|  _Chaos Engineering: System Resiliency in Practice_ , O'Reilly 2020| <https://www.oreilly.com/library/view/chaos-engineering/9781492043860/>  
Basiri et al.| "Chaos Engineering" IEEE Software 2016| <https://ieeexplore.ieee.org/document/7471636>  
Netflix Tech Blog| "ChAP: Chaos Automation Platform"| <https://netflixtechblog.com/chap-chaos-automation-platform-53e6d528371f>  
Roblox postmortem| Real cascading failure (Consul + BoltDB)| <https://about.roblox.com/newsroom/2022/01/roblox-return-to-service-10-28-10-31-2021>  
Pumba| Docker chaos tool| <https://github.com/alexei-led/pumba>  
Chaos Mesh| K8s chaos (CNCF)| <https://chaos-mesh.org/>  
LitmusChaos| K8s chaos + CI/CD (CNCF)| <https://litmuschaos.io/>  
Toxiproxy| Network chaos| <https://github.com/Shopify/toxiproxy>  
AWS Fault Injection Simulator| AWS-managed| <https://aws.amazon.com/fis/>  
Container Solutions blog| Chaos tool comparison| <https://blog.container-solutions.com/comparing-chaos-engineering-tools>  
Adrian Cockcroft talk| Failure modes in microservices (re:Invent 2019)| <https://www.youtube.com/watch?v=NXSXMAxJSWE>  
  
(C) 2026 [My Learning Notes](https://learning-notes-dz2.pages.dev/) · Powered by [Hugo](https://gohugo.io/) & [PaperMod](https://github.com/adityatelange/hugo-PaperMod/)
