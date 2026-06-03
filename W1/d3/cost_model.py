import pandas as pd
BUILD_RATES = {
    "metric_per_eps": 0.002,      
    "log_per_gb_day": 0.15,       
    "trace_per_service": 15.0,    
    "kafka_per_msg_sec": 0.0025,  
    "compute_per_eps": 0.0012     
}
MIN_KAFKA_COST = 250             

BUY_RATES = {
    "infra_apm_per_service": 46.0, 
    "log_per_gb_day": 1.50        
}

tiers = {
    "Small": {
        "services": 10,
        "log_gb_day": 50,
        "metric_eps": 100_000,
        "kafka_msg_sec": 10_000
    },
    "Medium": {
        "services": 100,
        "log_gb_day": 500,
        "metric_eps": 1_000_000,
        "kafka_msg_sec": 100_000
    },
    "Large": {
        "services": 1000,
        "log_gb_day": 5000,
        "metric_eps": 10_000_000,
        "kafka_msg_sec": 1_000_000
    }
}


results = []

for tier_name, specs in tiers.items():
    
    # Tính chi phí tự build
    # Storage
    metric_cost = specs["metric_eps"] * BUILD_RATES["metric_per_eps"]
    log_cost = specs["log_gb_day"] * BUILD_RATES["log_per_gb_day"]
    trace_cost = specs["services"] * BUILD_RATES["trace_per_service"]
    storage_total = metric_cost + log_cost + trace_cost
    
    # Network
    network_total = specs["kafka_msg_sec"] * BUILD_RATES["kafka_per_msg_sec"]
    network_total = max(network_total, MIN_KAFKA_COST) # Không thể rẻ hơn chi phí duy trì cụm server thấp nhất
        
    # Compute Cost
    compute_total = specs["metric_eps"] * BUILD_RATES["compute_per_eps"]
    
    build_total = storage_total + network_total + compute_total
    
    # chi phí tự mua
    # Bao gồm tiền APM/Infra gộp theo service + Tiền dung lượng Log 
    buy_total = (specs["services"] * BUY_RATES["infra_apm_per_service"]) + \
                (specs["log_gb_day"] * BUY_RATES["log_per_gb_day"] * 30) # Tính theo 30 ngày/tháng
    
    # hiển thị kết quả
    results.append({
        "Tier": tier_name,
        "Services": specs["services"],
        "Storage ($)": f"${storage_total:,.0f}",
        "Compute ($)": f"${compute_total:,.0f}",
        "Kafka ($)": f"${network_total:,.0f}",
        "TOTAL BUILD ($)": f"${build_total:,.0f}",
        "TOTAL SaaS ($)": f"${buy_total:,.0f}",
        "Diff": f"{buy_total/build_total:.1f}x"
    })


df = pd.DataFrame(results)

print("="*90)
print("BẢNG ƯỚC TÍNH CHI PHÍ OBSERVABILITY HÀNG THÁNG")
print("="*90)
print(df.to_string(index=False))
print("="*90)