def compute_similarity(live_feat: dict, hist_feat: dict) -> float:
    """Compute similarity between live incident and historical incident."""
    score = 0.0
    
    # 1. Log signatures overlap (weight 0.6)
    live_sigs = set(live_feat.get("matched_log_sigs", []))
    hist_sigs = set(hist_feat.get("matched_log_sigs", []))
    
    if live_sigs or hist_sigs:
        intersection = live_sigs.intersection(hist_sigs)
        union = live_sigs.union(hist_sigs)
        score += 0.6 * (len(intersection) / len(union))
        
    # 2. Alert name match (weight 0.2)
    live_alert = live_feat["incident"].get("trigger_alert", {}).get("alert_name")
    hist_alert = hist_feat["incident"].get("trigger_alert", {}).get("alert_name")
    if live_alert and hist_alert and live_alert == hist_alert:
        score += 0.2
        
    # 3. Structural/Affected Services overlap (weight 0.2)
    live_affected = live_feat.get("affected_services", [])
    hist_affected = hist_feat.get("affected_services", [])
    
    if live_affected and hist_affected:
        if live_affected[0] == hist_affected[0]:
            score += 0.2
        else:
            if set(live_affected).intersection(set(hist_affected)):
                score += 0.1
                
    return score

def retrieve_and_vote(live_feat: dict, hist_features_list: list[dict], k=3, threshold=0.4) -> dict:
    """
    Find top-k similar past incidents using outcome-weighted voting.
    Returns a dict with confidence, proposed action, mapped target, and context.
    """
    scored = []
    for hf in hist_features_list:
        sim = compute_similarity(live_feat, hf)
        scored.append((sim, hf))
        
    # Sort descending by similarity
    scored.sort(key=lambda x: x[0], reverse=True)
    top_k = scored[:k]
    
    # Out of distribution (OOD) check
    if not top_k or top_k[0][0] < threshold:
        return {
            "confident": False,
            "reason": "Top match similarity below threshold",
            "best_action": "page_oncall",
            "best_target": None,
            "action_scores": {},
            "top_matches": [(s, h["incident"].get("incident_id")) for s, h in top_k]
        }
        
    action_scores = {}
    action_targets = {} # keep track of targets proposed by history
    
    # Outcome-weighted voting
    for sim, hf in top_k:
        if sim < (threshold * 0.5):
            continue
            
        action = hf["incident"].get("remediation_action")
        target = hf["incident"].get("remediation_target")
        status = hf["incident"].get("status")
        
        # Service mapping: map historical target to live equivalent
        mapped_target = target
        if target and hf.get("affected_services"):
            # If the target was the primary affected service in history
            if target == hf["affected_services"][0]:
                if live_feat.get("affected_services"):
                    # Map to the primary affected service in live
                    mapped_target = live_feat["affected_services"][0]
            elif target in hf["affected_services"]:
                # If it was a secondary service, try to map similarly if possible
                pass 
                
        key = (action, mapped_target)
        weight = sim if status == "resolved" else -sim
        action_scores[key] = action_scores.get(key, 0.0) + weight
        
    if not action_scores:
        return {
            "confident": False,
            "reason": "No valid actions derived from top matches",
            "best_action": "page_oncall",
            "best_target": None,
            "action_scores": action_scores,
            "top_matches": [(s, h["incident"].get("incident_id")) for s, h in top_k]
        }
        
    # Find action with highest score
    best_key = max(action_scores.items(), key=lambda x: x[1])
    best_action, best_target = best_key[0]
    best_score = best_key[1]
    
    # Safety Check: If the aggregate vote tells us the actions FAILED, we escalate
    if best_score <= 0.1:
        return {
            "confident": False,
            "reason": "Top historical matches indicate failure for these actions",
            "best_action": "page_oncall",
            "best_target": None,
            "action_scores": action_scores,
            "top_matches": [(s, h["incident"].get("incident_id")) for s, h in top_k]
        }
        
    return {
        "confident": True,
        "reason": "Found confident match with positive historical outcome",
        "best_action": best_action,
        "best_target": best_target,
        "action_scores": action_scores,
        "top_matches": [(s, h["incident"].get("incident_id")) for s, h in top_k]
    }
