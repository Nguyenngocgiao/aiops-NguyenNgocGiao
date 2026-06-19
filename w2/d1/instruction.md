# W2-D1: Alert Correlation — Từ Noise Sang Signal

> **Thời gian đọc:** 18 phút | **Độ dài:** 3793 từ

---

## Mục Lục

1. [Mở đầu: Đêm pager kêu](#1-mở-đầu-đêm-pager-kêu)
2. [Vấn đề: Vì sao alert flood là cơn ác mộng?](#2-vấn-đề-vì-sao-alert-flood-là-cơn-ác-mộng)
3. [Layer 1 — Dedup (gộp alert trùng lặp)](#3-layer-1--dedup-gộp-alert-trùng-lặp)
4. [Layer 2 — Time-Window](#4-layer-2--time-window-gom-alert-gần-nhau-về-thời-gian)
5. [Layer 3 — Topology-Aware Correlation](#5-layer-3--topology-aware-correlation)
6. [Layer 4 (Bonus) — Semantic / Similarity Correlation](#6-layer-4-bonus--semantic--similarity-correlation)
7. [Production Patterns](#7-production-patterns)
8. [Embedded Exercise — Build correlator của bạn](#8-embedded-exercise--build-correlator-của-bạn)
9. [EOD Checkpoint](#9-eod-checkpoint)
10. [Resources](#10-resources)
11. [Sang ngày mai](#11-sang-ngày-mai)

---

## 1. Mở đầu: Đêm pager kêu

Tưởng tượng bạn vừa thiu thiu ngủ. 02:14 sáng. Điện thoại rung — pager báo. Bạn dụi mắt, mở laptop ra.

Trên dashboard hiện ra cảnh này:

```
┌──────────────────────────────────────────────────────────────┐
│ MONITORING DASHBOARD — incident in progress                  │
├──────────────────────────────────────────────────────────────┤
│ 02:14:03  🔴 payment-svc      latency_p99 = 3.2s            │
│ 02:14:05  🔴 payment-svc      error_rate  = 12%             │
│ 02:14:07  🔴 checkout-svc     5xx_rate    = 8%              │
│ 02:14:08  🔴 checkout-svc     latency_p99 = 4.1s            │
│ 02:14:09  🔴 edge-lb          p99 > 3s                       │
│ 02:14:11  🔴 cart-redis       evict_rate  = 850/s           │
│ 02:14:12  🔴 notif-queue      lag         = 12,000          │
│ 02:14:15  🔴 payments-db      cpu         = 95%             │
│ 02:14:17  🔴 recommender      oom_kill    = 3               │
│ 02:14:19  🔴 payment-svc      timeout     = 23%             │
│ 02:14:22  🔴 checkout-svc     error_rate  = 15%             │
│ ... còn 36 alert nữa trong 90 giây tiếp theo                │
└──────────────────────────────────────────────────────────────┘
```

47 alert đỏ rực trong 90 giây. 7 service khác nhau cùng kêu một lúc. Bạn còn chưa kịp uống ngụm nước.

**Câu hỏi đầu tiên trong đầu:** *"Cái nào là gốc? Cái nào chỉ là hệ quả?"*

### Vấn đề ở đây không phải KHÓ. Là QUÁ NHIỀU

Nếu chỉ có 1 alert ("payment-svc bị crash"), bạn biết phải làm gì. Vào log, đọc metric, tìm cause. Xong trong 15 phút.

Nhưng 47 alert một lúc thì khác. Bạn không thể đọc 47 thứ song song — não bị quá tải. Bạn rơi vào trạng thái "everything is broken" và mất 10 phút chỉ để đọc hết alert list — chưa kịp bắt đầu fix.

**Bài hôm nay:** học cách gộp 47 alert thành 3 nhóm (cluster) có nghĩa, để não bạn chỉ phải đối mặt với 3 thứ thay vì 47. Ngày mai (D2) chúng ta dùng 3 cluster đó để tìm root cause — nhưng đó là chuyện mai.

### Một analogy cho dễ hình dung

Hãy tưởng tượng bạn đang đứng giữa vụ tắc đường nghiêm trọng:

```
Trước correlation:                  Sau correlation:
─────────────────────               ──────────────────────────
🚨 Còi xe (47 cái cùng kêu)         🟡 Nhóm 1: tai nạn ở km 5
🚨 Đèn brake đỏ rực                          (← cái này là GỐC)
🚨 Người đi bộ la                   🟡 Nhóm 2: đường ngập cách
🚨 Còi cứu thương                            đó 2km (riêng)
🚨 Tiếng còi inh ỏi                 🟡 Nhóm 3: xe hỏng lẻ tẻ
🚨 ... 42 cái nữa                            (không liên quan)
```

Mỗi tiếng còi đều "đúng" — chúng phản ánh hiện tượng thật sự. Nhưng phần lớn là hệ quả của 1–2 sự kiện gốc. Correlation = gom các tiếng còi liên quan vào cùng nhóm, để bạn biết chỉ cần xử lý nhóm-gốc.

> 💡 **Quy tắc vàng:** Correlation KHÔNG tìm root cause. Nó chỉ rút gọn số việc cần làm RCA. Đừng nhầm 2 cái này — D1 (hôm nay) làm correlation, D2 (mai) làm RCA.

---

## 2. Vấn đề: Vì sao alert flood là cơn ác mộng?

### 2.1 Alert fatigue — bệnh nghề nghiệp của on-call

Bạn có biết một engineer on-call ở 1 công ty mid-size nhận bao nhiêu alert mỗi ngày không?

**20–50 cái. Mỗi cái đều "khẩn cấp". Mỗi ngày.**

Khảo sát của VictorOps 2023 (800 engineer) chỉ ra điều đáng buồn:

```
67% engineer nhận > 10 alert mỗi ca trực
   ████████████████████░░░░░░░░░░

45% engineer thừa nhận: đã từng TẮT notification của 1 alert vì nó noisy quá
   █████████████░░░░░░░░░░░░░░░░░

MTTR (thời gian fix sự cố) tăng 2.4× khi alert flood:
   Bình thường: ████░░░░░░          ~10 phút
   Khi flood:   ██████████████░░    ~24 phút
```

Hệ quả? Engineer mất niềm tin vào hệ thống. Họ bắt đầu ignore alert. Đến khi có 1 alert thật sự nguy hiểm, không ai nhìn — vì đã tê liệt.

### 2.2 Khi 1 service hỏng, không bao giờ chỉ mình nó

Sự thật về production: mọi thứ đều dependency với mọi thứ khác.

```
                    ┌──────────────────────────┐
                    │   1 cause → 5+ symptoms  │
                    └──────────────────────────┘

     edge-lb  ←  bị chậm vì checkout chậm  (symptom 3)
        │
        ▼
    checkout-svc  ←  bị chậm vì payment chậm  (symptom 2)
        │
        ├────► cart-svc → cart-redis
        │
        └────► payment-svc  ←  GỐC: pool DB cạn  (CAUSE)
                   │
                   ▼
              payments-db  ←  CPU cao do query tăng  (symptom 4)
                   
    notif-queue  ←  không nhận "order paid", backlog  (symptom 5)
```

Khi `payment-svc` chậm:
- `checkout-svc` đợi nó → cũng chậm → alert
- `edge-lb` thấy `checkout-svc` chậm → alert
- `notif-queue` không có "order paid" event → backlog → alert
- `payments-db` bị query nhiều → CPU 95% → alert

→ **1 cause, 5 symptoms.** Mỗi symptom tự nó "đúng" — nó phản ánh hiện tượng thật. Nhưng bạn cần biết: chỉ 1 cái là gốc, còn lại là tiếng vang.

### 2.3 4 loại alert flood bạn sẽ gặp

47 alert đêm qua không phải 47 loại khác nhau. Thực ra chỉ là tổ hợp của 4 dạng:

| Dạng | Ví dụ trong đời thật | Hình dung |
|------|----------------------|-----------|
| **Duplicate** — cùng 1 alert lặp đi lặp lại | Latency alert fire mỗi 30s suốt 10 phút | 🔄 🔄 🔄 🔄 🔄 (20 cái giống hệt) |
| **Cascade** — 1 service hỏng kéo cả chuỗi | payment hỏng → checkout hỏng → edge hỏng | 🔻 🔻 🔻 (gốc → ngọn) |
| **Flapping** — metric dao động quanh ngưỡng | CPU: 79 → 81 → 79 → 81 → 79 → 81 % | 📈📉📈📉📈 (jitter) |
| **Cùng service, nhiều metric** | payment-svc: latency + error + CPU cùng tăng | 🔴🔴🔴 (1 nguồn, 3 góc nhìn) |

Mỗi dạng cần kỹ thuật correlation khác nhau. Hôm nay đi qua tất cả.

### 2.4 Mục tiêu cụ thể cuối ngày

Cho 200 alert đầu vào (`alerts.jsonl` từ lab dataset), output **3–7 cluster** trong đó:

- Mỗi cluster có ít nhất 2 alert nguồn gốc chung (cùng dedup key, cùng thời gian, cùng đường đi trong service graph)
- Cluster có metadata: `cluster_id`, `alert_count`, `services` (list), `time_range`, `severity` (max)
- Có 0 alert orphan (nếu 1 alert không match cluster nào, vẫn output thành cluster size=1)

**200 → 3–7 cluster** có nghĩa là giảm 96–98% items mà RCA cần xử lý. Đây là cách đo correlation work hay không.

---

## 3. Layer 1 — Dedup (gộp alert trùng lặp)

Layer đơn giản nhất. Ý tưởng: cùng 1 alert fire đi fire lại → không cần tạo nhiều cluster, chỉ cần đếm số lần.

### 3.1 Fingerprint — "vân tay" của alert

Hãy nghĩ về vân tay con người. Mỗi người có vân tay riêng, không đổi. Nếu cùng 1 người chạm vào cốc 5 lần, ta thấy 5 dấu — nhưng đó là 1 người duy nhất.

Alert cũng vậy. Mỗi alert có 10–20 field. Hầu hết field thay đổi mỗi lần fire (timestamp, value), nhưng một subset không đổi — đó là **fingerprint**.

```
Alert lúc 02:14:03              Alert lúc 02:14:33
───────────────────             ───────────────────
service:   payment-svc          service:   payment-svc    ← giống
metric:    latency_p99_ms       metric:    latency_p99_ms ← giống
severity:  crit                 severity:  crit           ← giống
───────────────────             ───────────────────
value:     3.2s                 value:     3.8s            ← khác (không quan trọng)
ts:        02:14:03             ts:        02:14:33        ← khác (không quan trọng)

  Fingerprint của cả 2 = "payment-svc | latency_p99_ms | crit"
  → Cùng vân tay → cùng 1 "thứ" → gom thành 1 cluster, count = 2
```

Fingerprint = subset field định danh "đây cùng 1 loại alert".

```python
def fingerprint(alert: dict) -> str:
    """
    Tạo unique key cho alert. 2 alert có cùng fingerprint = duplicate.
    
    Chọn field nào vào fingerprint?
    - PHẢI có: service, metric, severity (cùng service báo cùng metric ở cùng severity = duplicate)
    - KHÔNG nên có: timestamp, value (vì chúng thay đổi mỗi lần fire — nếu include thì
      không alert nào duplicate alert nào → dedup vô dụng)
    - Tùy chọn: labels.env, labels.region (nếu bạn muốn alert ở env=prod khác alert ở env=staging)
    """
    return f"{alert['service']}|{alert['metric']}|{alert['severity']}"
```

> **Câu hỏi tự kiểm tra:** Vì sao không include `labels.host`? — Vì trong K8s, mỗi pod là 1 host khác nhau, nhưng cùng service mà 3 pod alert thì bạn coi như cùng vấn đề. Include host → 3 alert khác fingerprint → dedup mất tác dụng.

### 3.2 Dedup with state

Dedup không phải là 1 hàm pure. Bạn cần **state**: một dictionary lưu `fingerprint → cluster`. Khi alert mới đến, check fingerprint trong dict; nếu có → update; nếu không → tạo entry mới.

```python
from collections import defaultdict
from datetime import datetime

class Deduper:
    def __init__(self):
        self.store: dict[str, dict] = {}  # fingerprint → cluster info
    
    def push(self, alert: dict) -> str:
        """
        Add alert vào store. Return cluster_id (fingerprint đóng vai trò cluster_id ở layer này).
        """
        fp = fingerprint(alert)
        ts = datetime.fromisoformat(alert['ts'].replace('Z', '+00:00'))
        
        if fp not in self.store:
            self.store[fp] = {
                'cluster_id': fp,
                'count': 1,
                'first_seen': ts,
                'last_seen': ts,
                'alerts': [alert['id']],
                'max_value': alert['value'],
            }
        else:
            c = self.store[fp]
            c['count'] += 1
            c['last_seen'] = ts
            c['alerts'].append(alert['id'])
            c['max_value'] = max(c['max_value'], alert['value'])
        
        return fp
    
    def clusters(self) -> list[dict]:
        return list(self.store.values())
```

> ⚠️ **Cảnh báo về memory:** `self.store` không có giới hạn — nó grow vô tận. Trên production, sau 24h bạn có 100k+ entries. Cần TTL eviction: nếu fingerprint không thấy trong N phút → xoá. Sẽ bàn ở section 7.

### 3.3 Khi dedup không đủ

Dedup chỉ gom alert giống hệt nhau. Nó **không** gom:
- `Payment latency alert` + `Payment error_rate alert` (cùng service, khác metric) → 2 cluster khác nhau
- `Payment alert` + `Checkout alert` (khác service, cùng cause) → 2 cluster khác nhau

Cần thêm 2 layer nữa.

---

## 4. Layer 2 — Time-Window (gom alert gần nhau về thời gian)

### 4.1 Insight chính: thời gian là tín hiệu

Hãy nghĩ thế này: nếu 5 service cùng kêu trong 2 phút, khả năng chúng có cùng cause là **RẤT cao**. Nếu 5 service kêu spread ra 2 giờ, có thể chúng chẳng liên quan gì nhau.

```
Case 1: cùng cluster (high signal)        Case 2: không cùng cluster
─────────────────────────────────         ─────────────────────────────────
02:14:03  🔴 payment                       02:14:03  🔴 payment
02:14:09  🔴 checkout                      03:47:21  🔴 checkout    (1h33 sau)
02:14:15  🔴 edge-lb                       05:12:08  🔴 edge-lb     (1h25 sau)
02:14:22  🔴 cart-redis                    07:33:55  🔴 cart-redis  (2h21 sau)

  Span: 19 giây → SAME incident               Span: 5h30 → unrelated
```

Layer này chỉ làm 1 việc: gom alert nào đến gần nhau về thời gian thành 1 nhóm.

### 4.2 Sliding window cơ bản

```python
from collections import deque
from datetime import datetime, timedelta

def time_window_groups(alerts: list[dict], window_sec: int = 300) -> list[list[dict]]:
    """
    Group alerts arriving within window_sec của nhau.
    
    Args:
        alerts: list alert đã sort theo timestamp tăng dần
        window_sec: cửa sổ thời gian (e.g. 300 = 5 phút)
    
    Returns:
        list of groups, mỗi group là list alert
    
    Logic: dùng deque buffer 5 phút last. Mỗi alert mới đến:
      1. Pop từ buffer những alert cũ hơn (now - window_sec)
      2. Còn lại trong buffer là alert "cùng window" với alert hiện tại
    """
    groups = []
    buffer = deque()  # (ts, alert)
    
    for alert in alerts:
        ts = datetime.fromisoformat(alert['ts'].replace('Z', '+00:00'))
        cutoff = ts - timedelta(seconds=window_sec)
        
        # Pop alert cũ
        while buffer and buffer[0][0] < cutoff:
            buffer.popleft()
        
        buffer.append((ts, alert))
        groups.append([a for _, a in buffer])
    
    return groups
```

> **Vấn đề:** code trên trả về 1 group cho mỗi alert (overlapping groups). Trong thực tế, bạn cần non-overlapping groups — mỗi alert thuộc đúng 1 group.

### 4.3 Tumbling window vs Sliding window

| Window type | Mô tả | Khi nào dùng |
|-------------|-------|--------------|
| **Tumbling** | Fixed-size, non-overlapping. E.g. 0–5, 5–10, 10–15 | Khi cần group rõ ràng, mỗi alert thuộc đúng 1 window. Default choice. |
| **Sliding** | Mỗi alert tạo 1 window backward. Overlapping. | Khi cần "có alert nào gần đây" — e.g. live alerting |
| **Session** | Window kết thúc khi không có alert mới trong N giây | Khi incident có "burst" rõ ràng — dynamic length |

Cho lab này, dùng **session window** thông minh hơn tumbling:

```python
def session_groups(alerts: list[dict], gap_sec: int = 120) -> list[list[dict]]:
    """
    Mỗi group là 1 'session' alert. Session kết thúc khi không alert nào trong gap_sec giây.
    
    Vì sao session tốt hơn tumbling cho incident:
    - Incident burst: 30 alert trong 90 giây → 1 session tự nhiên
    - Tumbling 5min: nếu incident span 4 phút 30 - 5 phút 30 → bị cắt thành 2 window
    - Session tự adapt kích thước theo burst pattern
    """
    if not alerts:
        return []
    
    sorted_alerts = sorted(alerts, key=lambda a: a['ts'])
    groups = [[sorted_alerts[0]]]
    
    for alert in sorted_alerts[1:]:
        ts = datetime.fromisoformat(alert['ts'].replace('Z', '+00:00'))
        last_ts = datetime.fromisoformat(groups[-1][-1]['ts'].replace('Z', '+00:00'))
        
        if (ts - last_ts).total_seconds() <= gap_sec:
            groups[-1].append(alert)
        else:
            groups.append([alert])
    
    return groups
```

### 4.4 Chọn `gap_sec` thế nào

Đây là parameter quan trọng nhất của layer này:

| `gap_sec` | Hậu quả | Khi nào dùng |
|-----------|---------|--------------|
| 30s | Group rất nhỏ. Incident dài bị tách | Nếu alert flood thực sự < 30s spread |
| **120s (2 phút)** | **Sweet spot cho hầu hết production system** | **Default cho W2 lab** |
| 300s (5 phút) | Group lớn hơn. Có thể merge 2 incident không liên quan | Khi service degrade chậm |
| 600s+ | Bắt incident kéo dài | Cảnh giác false correlation |

> **Production wisdom:** Đo `gap_sec` bằng cách nhìn histogram của `time_since_last_alert` trong 30 ngày qua. Chọn `gap_sec` ở mức 95th percentile của intra-incident gap.

---

## 5. Layer 3 — Topology-Aware Correlation

Time-window gom alert theo **khi nào**. Topology gom theo **chúng có connected không**.

### 5.1 Service graph là gì

Service graph là **directed graph**:
- **Node** = service
- **Edge** A → B = service A gọi service B (depend on)

Trong lab `services.json` của bạn:

```
edge-lb → checkout-svc
checkout-svc → payment-svc
checkout-svc → cart-svc
checkout-svc → inventory-svc
cart-svc → cart-redis
payment-svc → payments-db
```

Khi `payment-svc` hỏng, ai bị ảnh hưởng?
- **Downstream** của `payment-svc` (`payments-db`) — không, payments-db OK, payment-svc dùng nó
- **Upstream** của `payment-svc` (`checkout-svc`) — có, vì checkout depend on payment
- **Upstream** của `checkout-svc` (`edge-lb`) — có, transitive cascade

Đây là **propagation pattern**: hỏng ở 1 node lan upstream (về phía caller).

### 5.2 Build graph với networkx

```python
import networkx as nx
import json

def build_graph(services_json_path: str) -> nx.DiGraph:
    """
    Build directed graph: A → B nghĩa là A gọi B.
    
    Khi RCA traverse, bạn sẽ đi NGƯỢC edge (từ A về B) — vì nếu A alert
    thì có thể B là root cause.
    """
    g = nx.DiGraph()
    data = json.loads(open(services_json_path).read())
    
    # Add service nodes
    for svc in data['services']:
        g.add_node(svc['name'], **{k: v for k, v in svc.items() if k != 'name'})
    
    # Add store nodes
    for store in data['stores']:
        g.add_node(store['name'], **{k: v for k, v in store.items() if k != 'name'})
    
    # Add edges
    for edge in data['edges']:
        g.add_edge(edge['from'], edge['to'], type=edge['type'])
    
    return g
```

### 5.3 Topology grouping logic

Cho 1 set alert, gom chúng nếu các service alert "gần nhau" trên graph.

- **Cách 1 — Connected component:** Lấy subgraph chỉ chứa service có alert. Mỗi connected component = 1 cluster. Đơn giản nhưng có thể quá rộng (1 hop ≈ 1 service apart).
- **Cách 2 — Path-based:** Hai alert cùng cluster nếu có path ≤ N hop nối chúng. **N = 2** thường tốt.

```python
def topology_group(alerts: list[dict], graph: nx.DiGraph, max_hop: int = 2) -> list[list[dict]]:
    """
    Group alerts nếu service của chúng cách nhau ≤ max_hop trên service graph.
    
    Lưu ý: dùng undirected version của graph cho khoảng cách — vì cascade
    có thể đi cả 2 chiều (upstream effect, downstream propagation tùy case).
    """
    if not alerts:
        return []
    
    undirected = graph.to_undirected()
    
    # Build mapping service → alerts ở service đó
    by_service = defaultdict(list)
    for a in alerts:
        by_service[a['service']].append(a)
    
    services_with_alerts = list(by_service.keys())
    
    # Union-Find
    parent = {s: s for s in services_with_alerts}
    
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    
    def union(x, y):
        parent[find(x)] = find(y)
    
    # Two services cùng group nếu khoảng cách ≤ max_hop trên graph
    for i, s1 in enumerate(services_with_alerts):
        for s2 in services_with_alerts[i+1:]:
            try:
                dist = nx.shortest_path_length(undirected, s1, s2)
                if dist <= max_hop:
                    union(s1, s2)
            except nx.NetworkXNoPath:
                continue  # 2 service không connected → không group
    
    # Collect groups
    groups_dict = defaultdict(list)
    for s in services_with_alerts:
        groups_dict[find(s)].extend(by_service[s])
    
    return list(groups_dict.values())
```

**Test mental model trước khi chạy code:**
1. 47 alert, có 8 service distinct trong đó
2. Build subgraph chỉ với 8 service đó
3. `payment-svc`, `checkout-svc`, `edge-lb` thuộc connected component A (cascade chain)
4. `recommender-svc` đứng riêng (component B)
5. `search-svc` đứng riêng (component C)
6. Output: **3 group**

### 5.4 Kết hợp Time-Window + Topology

Mỗi alone không đủ:
- **Time-window only:** gom alert cùng giờ nhưng có thể chúng không liên quan (recommender retrain + payment crash trùng giờ)
- **Topology only:** gom alert cùng cascade chain nhưng có thể chúng cách nhau 6 giờ (không phải cùng incident)
- **Combined logic:** 2 alert cùng cluster nếu vừa **cùng time-window** vừa **cùng topology component**.

```python
def correlate(alerts: list[dict], graph: nx.DiGraph, gap_sec: int = 120, max_hop: int = 2):
    """
    Pipeline:
      1. Sort alert by timestamp
      2. Cho mỗi session (time-window), apply topology grouping
      3. Output clusters
    """
    sessions = session_groups(alerts, gap_sec=gap_sec)
    
    all_clusters = []
    for session_idx, session_alerts in enumerate(sessions):
        # Trong mỗi session, topology-group
        topo_groups = topology_group(session_alerts, graph, max_hop=max_hop)
        for group_idx, group in enumerate(topo_groups):
            all_clusters.append({
                'cluster_id': f'c-{session_idx:03d}-{group_idx:03d}',
                'alert_count': len(group),
                'services': sorted(set(a['service'] for a in group)),
                'alert_ids': [a['id'] for a in group],
                'time_range': [min(a['ts'] for a in group), max(a['ts'] for a in group)],
                'max_severity': max(a['severity'] for a in group),
            })
    
    return all_clusters
```

---

## 6. Layer 4 (Bonus) — Semantic / Similarity Correlation

Đến đây bạn đã đủ pass lab. Nhưng trong production hệ thống tốt còn có 1 layer nữa: **semantic similarity**.

### 6.1 Insight

Đôi khi 2 alert có fingerprint khác nhau nhưng nội dung tương tự:

```
payment-svc  db_pool_used_ratio = 0.95         (warn)
payment-svc  db_connection_count = 49 / 50     (crit)
```

Chúng đo cùng 1 hiện tượng (DB pool gần cạn) nhưng metric name khác. Dedup miss. Time-window + topology gom được (cùng service, cùng thời gian) nhưng không biết chúng "cùng nói 1 chuyện".

### 6.2 Approach đơn giản — keyword overlap

```python
def text_similarity(alert_a: dict, alert_b: dict) -> float:
    """Jaccard similarity trên tokenized metric name + labels.note (nếu có)."""
    def tokens(a):
        text = f"{a['metric']} {a.get('labels', {}).get('note', '')}"
        return set(text.lower().replace('_', ' ').split())
    
    ta, tb = tokens(alert_a), tokens(alert_b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
```

### 6.3 Approach nâng cao — embedding

Dùng `sentence-transformer` encode `metric + labels.note + service.team` thành vector. Cosine similarity > 0.8 → "semantically related".

> **Không bắt buộc cho lab.** Đề cập để biết direction.

---

## 7. Production Patterns

### 7.1 Alertmanager (Prometheus ecosystem)

Alertmanager có routing tree + grouping rules:

```yaml
route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s          # Đợi 30s gom thêm alert giống nhau
  group_interval: 5m       # Gom alert vào group cũ trong 5 phút
  repeat_interval: 4h      # Re-fire group đã active sau 4h
```

Đây là dedup + time-window + simple grouping ở mức infrastructure. **Không có topology** — bạn phải tự build.

### 7.2 Vì sao bạn vẫn cần code layer của bạn

Alertmanager grouping work ở mỗi route, không cross-route. Topology-aware correlation ở mức platform-wide. Đây là việc của alert correlator layer riêng — có sản phẩm thương mại (BigPanda, Moogsoft), nhưng cốt lõi không khác gì bạn vừa build.

### 7.3 Memory + TTL

Trên production:
- **Dedup store:** TTL theo `last_seen` — xoá entry > 1 giờ không update
- **Session groups:** chỉ giữ session active (chưa close) — đã close + emit thì gửi đi và xoá
- **Topology graph:** load 1 lần, reload mỗi N phút từ service registry

```python
def evict_stale(store: dict, ttl_sec: int = 3600):
    """Xoá entries cũ. Gọi mỗi 5 phút bằng scheduler."""
    now = datetime.now(timezone.utc)
    stale = [k for k, v in store.items() 
             if (now - v['last_seen']).total_seconds() > ttl_sec]
    for k in stale:
        del store[k]
```

### 7.4 Flapping suppression

Một alert "flap" = liên tục fire/clear (CPU dao động quanh 80%). Đếm số lần fire trong window, nếu > threshold → suppress:

```python
def is_flapping(events: list[str], window: int = 10) -> bool:
    """events = ['fire', 'clear', 'fire', 'clear', ...] in last 10 minutes."""
    return events[-window:].count('fire') >= 5  # ≥ 5 fire trong 10 phút
```

---

## 8. Embedded Exercise — Build correlator của bạn

**Task:** Code `correlate.py` cho lab dataset.

### Quy ước nộp bài (auto-grader rất chặt)

> ⚠️ **QUAN TRỌNG:** Sai 1 trong 4 thứ dưới → điểm tự động = 1.

- Branch `main` (không phải feature branch)
- Path: `aiops-<tên>/w2/d1/` — `w2` và `d1` đều **lowercase**
- File: `assignment.ipynb` (chính xác tên này) + `SUBMIT.md` (HOA) + `results/cluster_summary.json`

### 8.1 Input

Tải về 2 file dataset:
- **Alert sample (20 alert):** `alerts_sample.jsonl`
- **Service graph:** `services.json`

Lưu vào `aiops-<tên>/w2/d1/dataset/` (cùng folder với notebook).

### 8.2 Output

`results/cluster_summary.json` với format:

```json
{
  "input_alerts": 20,
  "output_clusters": 3,
  "reduction_ratio": 0.85,
  "clusters": [
    {
      "cluster_id": "c-001-000",
      "alert_count": 14,
      "services": ["payment-svc", "checkout-svc", "edge-lb"],
      "time_range": ["2026-06-12T09:42:01Z", "2026-06-12T09:48:30Z"],
      "max_severity": "crit",
      "fingerprints": ["payment-svc|latency_p99_ms|crit", "..."]
    }
  ]
}
```

### 8.3 Steps

1. Tạo folder `aiops-<your-name>/w2/d1/`
2. Tạo notebook `assignment.ipynb` import các function trên
3. Load `services.json` + `alerts_sample.jsonl`
4. Run `correlate()` pipeline
5. Write output JSON to `results/cluster_summary.json`
6. Write `SUBMIT.md` với:
   - Bạn chọn `gap_sec` bao nhiêu, vì sao
   - Bạn chọn `max_hop` bao nhiêu, vì sao
   - 1 alert ID đã bị "miss" (không match cluster nào) — tại sao?
   - Nếu có 10000 alert thay vì 200, code của bạn sẽ chậm ở đâu?

### 8.4 Acceptance criteria

- [ ] Notebook chạy được, có ≥ 3 cell với output
- [ ] `results/cluster_summary.json` exist + valid JSON
- [ ] Cluster có cả `services` list và `time_range`
- [ ] `reduction_ratio = 1 - output_clusters / input_alerts` ≥ 0.5 (giảm tối thiểu 50%)
- [ ] `SUBMIT.md` ≥ 100 từ, có ít nhất 1 design trade-off discuss

> 📌 Đây là Layer 1 của lab Friday. Code bạn viết hôm nay sẽ trở thành `correlate.py` của nhóm. Học chắc — vì trainer sẽ hỏi cá nhân về dedup logic + window choice ở vấn đáp.

---

## 9. EOD Checkpoint

Trả lời ngắn (~50–100 từ mỗi câu) trong file `SUBMIT.md`:

1. **[Dedup fingerprint]** Vì sao fingerprint cho dedup không include `timestamp` hay `value`? Cho ví dụ nếu include thì hệ thống behave ra sao.

2. **[Duplicate vs Correlated]** Sự khác biệt giữa "duplicate" và "correlated" alert là gì? Ví dụ cụ thể từ lab dataset.

3. **[gap_sec tradeoff]** `gap_sec = 30` (rất ngắn) vs `gap_sec = 600` (rất dài) — mỗi cái sẽ ảnh hưởng output thế nào? 1 dòng cho mỗi case.

4. **⭐ [Topology test]** Trong scenario chính (payment-svc pool exhaustion), `recommender-svc` cũng alert (batch retrain). Correlator của bạn có gom `recommender` vào cluster chính không? Vì sao có / không?

5. **[Topology limitation]** Limitation lớn nhất của topology grouping mà bạn nhận ra? Suggest 1 cách khắc phục.

> ⭐ **Câu 4 là câu "soul" của bài** — nếu trả lời được mạch lạc → bạn hiểu topology-aware correlation. Nếu vẫn confused → đọc lại section 5 + thử với `alerts_sample.jsonl` để observe.

---

## 10. Resources

- **Prometheus Alertmanager docs** — routing + grouping reference: https://prometheus.io/docs/alerting/latest/alertmanager/
- **"You're About To Get Paged"** — Charity Majors blog series. Honest về alert fatigue.
- **Drain3 (W1-D2)** — Drain3 và alert correlation rất giống về tinh thần — đều là "gom many → few có ý nghĩa". Ý tưởng giống, domain khác.
- **BigPanda blog** — vendor nhưng case study về alert correlation industry: https://www.bigpanda.io/blog/

---

## 11. Sang ngày mai

Mai (D2) bạn nhận clusters output từ hôm nay làm input. Câu hỏi sẽ là: *"Cluster này gây ra bởi service nào?"* Bạn sẽ học:

- Service dependency graph traversal cho RCA
- Centrality scoring (PageRank-style)
- Causal inference (Granger / PC algorithm)
- LLM-augmented RCA (retrieve incident history, hỏi LLM)

Đến cuối D2, bạn có thể trả lời câu hỏi từ scenario chính: **"payment-svc, hay checkout-svc, hay edge-lb là root cause của cluster lúc 09:42?"**

---

*© 2026 AIOps Learning Notes · W2-D1 Alert Correlation*
