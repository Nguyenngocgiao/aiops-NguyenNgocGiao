import json
import os
from collections import defaultdict
from datetime import datetime, timezone
import networkx as nx

# Global paths
SERVICES_PATH = os.path.join(os.path.dirname(__file__), "..", "d2", "dataset", "services.json")
INCIDENTS_PATH = os.path.join(os.path.dirname(__file__), "..", "d2", "dataset", "incidents_history.json")

def build_graph(services_json_path: str) -> nx.DiGraph:
    g = nx.DiGraph()
    with open(services_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for svc in data['services']:
        g.add_node(svc['name'], **{k: v for k, v in svc.items() if k != 'name'})
    for store in data['stores']:
        g.add_node(store['name'], **{k: v for k, v in store.items() if k != 'name'})
    for edge in data['edges']:
        g.add_edge(edge['from'], edge['to'], type=edge['type'])
    return g

def load_history(incidents_path: str):
    with open(incidents_path, 'r', encoding='utf-8') as f:
        return json.load(f)['incidents']

# Module level globals
try:
    GRAPH = build_graph(SERVICES_PATH)
    GRAPH_LOADED_AT = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
except Exception as e:
    print(f"Error loading graph: {e}")
    GRAPH = nx.DiGraph()
    
try:
    HISTORY = load_history(INCIDENTS_PATH)
except Exception as e:
    print(f"Error loading history: {e}")
    HISTORY = []

# --- Layer 1 functions ---
def fingerprint(alert: dict) -> str:
    return f"{alert['service']}|{alert['metric']}|{alert['severity']}"

def session_groups(alerts, gap_sec) -> list[list[dict]]:
    if not alerts: return []
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

def topology_group(alerts, graph, max_hop=2) -> list[list[dict]]:
    if not alerts: return []
    undirected = graph.to_undirected()
    by_service = defaultdict(list)
    for a in alerts:
        by_service[a['service']].append(a)

    services_with_alerts = list(by_service.keys())
    parent = {s: s for s in services_with_alerts}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        parent[find(x)] = find(y)

    for i, s1 in enumerate(services_with_alerts):
        for s2 in services_with_alerts[i+1:]:
            try:
                dist = nx.shortest_path_length(undirected, s1, s2)
                if dist <= max_hop:
                    union(s1, s2)
            except nx.NetworkXNoPath:
                continue

    groups_dict = defaultdict(list)
    for s in services_with_alerts:
        groups_dict[find(s)].extend(by_service[s])

    return list(groups_dict.values())

def correlate(alerts, graph, gap_sec, max_hop):
    sessions = session_groups(alerts, gap_sec=gap_sec)
    all_clusters = []
    for session_idx, session_alerts in enumerate(sessions):
        topo_groups = topology_group(session_alerts, graph, max_hop=max_hop)
        for group_idx, group in enumerate(topo_groups):
            all_clusters.append({
                'cluster_id': f'c-{session_idx:03d}-{group_idx:03d}',
                'alert_count': len(group),
                'services': sorted(set(a['service'] for a in group)),
                'alert_ids': [a['id'] for a in group],
                'time_range': [min(a['ts'] for a in group), max(a['ts'] for a in group)],
                'max_severity': max(a['severity'] for a in group),
                'fingerprints': sorted(set(fingerprint(a) for a in group)),
            })
    return all_clusters

# --- Layer 2 functions ---
def calculate_graph_temporal_candidates(cluster, alerts, G):
    cluster_services = cluster['services']
    subgraph = G.subgraph(cluster_services)
    if len(subgraph) == 0: return []
    try:
        rev_subgraph = subgraph.reverse(copy=True)
        pagerank_scores = nx.pagerank(rev_subgraph, alpha=0.85)
    except Exception:
        pagerank_scores = {node: 1.0/len(subgraph) for node in subgraph.nodes()}

    max_pr = max(pagerank_scores.values()) if pagerank_scores else 1.0
    pagerank_norm = {node: (score / max_pr if max_pr > 0 else 0.0) for node, score in pagerank_scores.items()}

    cluster_alert_ids = set(cluster['alert_ids'])
    cluster_alerts = [a for a in alerts if a['id'] in cluster_alert_ids]

    service_earliest_ts = {}
    for a in cluster_alerts:
        svc = a['service']
        ts = datetime.fromisoformat(a['ts'].replace('Z', '+00:00'))
        if svc not in service_earliest_ts or ts < service_earliest_ts[svc]:
            service_earliest_ts[svc] = ts

    if service_earliest_ts:
        timestamps = list(service_earliest_ts.values())
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        time_diff = (max_ts - min_ts).total_seconds()
    else:
        time_diff = 0

    temporal_scores = {}
    for svc in cluster_services:
        if svc not in service_earliest_ts:
            temporal_scores[svc] = 0.0
            continue
        if time_diff == 0:
            temporal_scores[svc] = 1.0
        else:
            svc_ts = service_earliest_ts[svc]
            delay = (svc_ts - min_ts).total_seconds()
            temporal_scores[svc] = 1.0 - (delay / time_diff)

    candidates = []
    for svc in cluster_services:
        pr = pagerank_norm.get(svc, 0.0)
        temp = temporal_scores.get(svc, 0.0)
        final_score = 0.6 * pr + 0.4 * temp
        candidates.append((svc, final_score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates

def retrieve_similar_incidents(cluster, incidents, k=3):
    cluster_services = set(cluster['services'])
    max_severity = cluster.get('max_severity', 'warn').lower()
    scored_incidents = []
    for inc in incidents:
        score = 0.0
        if inc.get('root_cause_service') in cluster_services:
            score += 0.4
        inc_services = set(inc.get('services_involved', []))
        overlap = cluster_services.intersection(inc_services)
        score += min(0.2 * len(overlap), 0.4)
        if inc.get('severity', '').lower() == max_severity:
            score += 0.2
        scored_incidents.append((inc, score))
    scored_incidents.sort(key=lambda x: x[1], reverse=True)
    return [(inc, score) for inc, score in scored_incidents if score >= 0.2][:k]

def classify_rca(cluster, candidates, similar_incidents, incidents_dict):
    if not similar_incidents or similar_incidents[0][1] < 0.2:
        top_candidate = candidates[0][0] if candidates else "unknown"
        confidence = candidates[0][1] if candidates else 0.5
        return {
            "root_cause": top_candidate,
            "class": "other",
            "confidence": round(float(confidence), 2),
            "actions": ["Investigate manually"],
            "reasoning": "No similar past incidents found. Fallback to top candidate from graph topology and temporal analysis.",
            "similar_incidents": [],
            "method": "graph-only-fallback"
        }
    top_inc, similarity = similar_incidents[0]
    root_cause_service = top_inc['root_cause_service']
    root_cause_class = top_inc['root_cause_class']
    remediation = top_inc['remediation']
    if root_cause_service not in cluster['services']:
        root_cause = candidates[0][0] if candidates else "unknown"
    else:
        root_cause = root_cause_service
    return {
        "root_cause": root_cause,
        "class": root_cause_class,
        "confidence": round(float(similarity), 2),
        "actions": [remediation] if isinstance(remediation, str) else remediation,
        "reasoning": f"Matched with historical incident {top_inc['id']} (similarity: {similarity:.2f}). Summary: {top_inc['summary']}",
        "similar_incidents": [inc['id'] for inc, _ in similar_incidents],
        "method": "graph+retrieval"
    }

def run_rca(cluster, alerts, graph, history):
    candidates = calculate_graph_temporal_candidates(cluster, alerts, graph)
    similar_incidents = retrieve_similar_incidents(cluster, history)
    inc_lookup = {inc['id']: inc for inc in history}
    
    use_llm = os.getenv('AIOPS_USE_LLM', 'true').lower() == 'true'
    if not use_llm:
        top_candidate = candidates[0][0] if candidates else "unknown"
        return {
            "root_cause": top_candidate,
            "class": "other",
            "confidence": round(float(candidates[0][1]), 2) if candidates else 0.5,
            "actions": ["Investigate manually"],
            "reasoning": "LLM bypassed by feature flag.",
            "similar_incidents": [],
            "method": "graph-only-flag-off"
        }
        
    return classify_rca(cluster, candidates, similar_incidents, inc_lookup)

def process_batch(alerts):
    if not alerts:
        return {"clusters": [], "root_cause": "unknown", "recommended_actions": [], "similar_incidents": []}
    
    clusters = correlate(alerts, GRAPH, gap_sec=120, max_hop=2)
    if not clusters:
        return {"clusters": [], "root_cause": "unknown", "recommended_actions": [], "similar_incidents": []}
        
    primary_cluster = max(clusters, key=lambda c: c['alert_count'])
    rca_res = run_rca(primary_cluster, alerts, GRAPH, HISTORY)
    
    return {
        "clusters": clusters,
        "root_cause": {"service": rca_res["root_cause"], "class": rca_res["class"], "confidence": rca_res["confidence"]},
        "recommended_actions": rca_res["actions"],
        "similar_incidents": rca_res["similar_incidents"]
    }
