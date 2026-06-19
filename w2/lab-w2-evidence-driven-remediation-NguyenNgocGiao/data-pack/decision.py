import yaml

def load_actions(filepath: str) -> dict:
    """Load actions definitions from YAML file."""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def get_action_details(actions_list: list, action_name: str) -> dict:
    """Find the details of a specific action."""
    for act in actions_list:
        if act.get("name") == action_name:
            return act
    return {}

def evaluate_decision(retrieval_output: dict, actions_dict: dict) -> dict:
    """
    Evaluate the proposed action against safety gates (blast radius).
    Returns a dict with final action, target, and reasoning.
    """
    if not retrieval_output.get("confident", False):
        return {
            "action": "page_oncall",
            "target": None,
            "reason": retrieval_output.get("reason", "Not confident in retrieval")
        }
        
    best_action = retrieval_output["best_action"]
    best_target = retrieval_output["best_target"]
    action_scores = retrieval_output.get("action_scores", {})
    best_score = action_scores.get((best_action, best_target), 0)
    
    # Calculate Reliability (pseudo-probability)
    # Since our max score per match is around 1.0, and k=3, max score is ~3.0.
    # We normalize to somewhat represent probability [0, 1]
    reliability = min(best_score / 1.5, 1.0)
    if reliability < 0:
        reliability = 0.0
    
    if best_action == "page_oncall":
        return {"action": "page_oncall", "target": None, "reason": "Retrieved action was explicitly page_oncall"}
        
    action_details = get_action_details(actions_dict, best_action)
    if not action_details:
        return {"action": "page_oncall", "target": None, "reason": f"Proposed action '{best_action}' unknown"}
        
    blast_radius = action_details.get("blast_radius_services", 5)
    
    # Safety Gating logic
    if blast_radius <= 1:
        threshold = 0.3
        penalty = 0.1
    elif blast_radius <= 2:
        threshold = 0.5
        penalty = 0.3
    else: # high
        threshold = 0.7
        penalty = 0.6
        
    expected_utility = reliability - penalty
    
    if expected_utility <= 0 or reliability < threshold:
        return {
            "action": "page_oncall",
            "target": None,
            "reason": f"Failed safety gate. Blast radius: {blast_radius}, Reliability: {reliability:.2f}, Threshold: {threshold}"
        }
        
    return {
        "action": best_action,
        "target": best_target,
        "reason": f"Passed safety gate. Blast radius: {blast_radius}, Reliability: {reliability:.2f}, EU: {expected_utility:.2f}"
    }
