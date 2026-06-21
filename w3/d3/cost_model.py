def is_worth_it(
    num_services: int,
    incidents_per_month: int,
    avg_incident_duration_hours: float,
    downtime_cost_per_hour: float,
    expected_mttr_reduction_pct: float = 0.4,
    aiops_monthly_cost: float = 15_000,
) -> dict:
    """
    Tính toán hiệu quả kinh tế (ROI) của hệ thống AIOps.
    """
    # Chi phí thiệt hại hiện tại mỗi tháng (khi chưa có AIOps)
    current_monthly_loss = incidents_per_month * avg_incident_duration_hours * downtime_cost_per_hour
    
    # Số tiền cứu vớt được mỗi tháng nhờ AIOps giảm thời gian chết (MTTR)
    monthly_value = current_monthly_loss * expected_mttr_reduction_pct
    
    # Tính lợi nhuận thuần và ROI
    net_profit = monthly_value - aiops_monthly_cost
    roi = monthly_value / aiops_monthly_cost if aiops_monthly_cost > 0 else float('inf')
    
    # Tính số tháng hoàn vốn
    payback_months = aiops_monthly_cost / net_profit if net_profit > 0 else float('inf')
    
    # Phán quyết
    if roi > 1.5:
        verdict = "worth_it"
    elif 1.0 < roi <= 1.5:
        verdict = "marginal"
    else:
        verdict = "not_worth_it"
        
    return {
        "monthly_value": round(monthly_value, 2),
        "monthly_cost": round(aiops_monthly_cost, 2),
        "roi": round(roi, 2),
        "payback_months": round(payback_months, 2) if payback_months != float('inf') else float('inf'),
        "verdict": verdict
    }

if __name__ == "__main__":
    print("--- Scenario 1: Small Startup ---")
    print(is_worth_it(num_services=20, incidents_per_month=2,
                      avg_incident_duration_hours=1, downtime_cost_per_hour=10_000,
                      aiops_monthly_cost=15_000))
                      
    print("\n--- Scenario 2: Mid-size E-commerce ---")
    print(is_worth_it(num_services=100, incidents_per_month=5,
                      avg_incident_duration_hours=2, downtime_cost_per_hour=20_000,
                      aiops_monthly_cost=25_000))
                      
    print("\n--- Scenario 3: GeekShop Production (Our App) ---")
    # Lập luận cho downtime_cost_per_hour: 
    # GeekShop là nền tảng thương mại điện tử, 1 giờ downtime không chỉ làm mất doanh thu trực tiếp 
    # (khoảng $50,000/hr vào giờ cao điểm) mà còn làm giảm uy tín thương hiệu và tốn chi phí đền bù (SLA penalty).
    # Việc rút ngắn 40% thời gian downtime là cực kỳ sống còn.
    print(is_worth_it(num_services=35, incidents_per_month=4,
                      avg_incident_duration_hours=1.5, downtime_cost_per_hour=50_000,
                      aiops_monthly_cost=20_000))
