#!/usr/bin/env python3
"""
Log Analyzer Script
Usage: python log_analyzer.py <logfile>
"""

import sys
import re
from datetime import datetime
from collections import defaultdict
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

def parse_timestamp(line):
    """Trích xuất timestamp từ dòng log"""
    # HDFS format: yymmdd hhmmss
    hdfs_pattern = re.compile(r'^(\d{6}\s+\d{6})')
    match = hdfs_pattern.search(line)
    if match:
        try:
            time_str = match.group(1)
            return datetime.strptime(time_str, '%y%m%d %H%M%S')
        except:
            return None
    return None

def analyze_log(logfile):
    """Phân tích log file"""
    
    print("="*80)
    print(f"LOG ANALYZER - {logfile}")
    print("="*80)
    
    # Đọc file
    try:
        with open(logfile, 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
    except FileNotFoundError:
        print(f"ERROR: File '{logfile}' not found!")
        sys.exit(1)
    
    total_lines = len(log_lines)
    print(f"\n✓ Tổng số dòng: {total_lines}")
    
    # Setup Drain3
    config = TemplateMinerConfig()
    config.drain_sim_th = 0.4
    config.drain_depth = 4
    miner = TemplateMiner(config=config)
    
    # Parse logs
    print("\n⏳ Đang parse logs...")
    template_counts = defaultdict(int)
    template_by_time = defaultdict(lambda: defaultdict(int))
    timestamps = []
    
    for line in log_lines:
        line = line.strip()
        if not line:
            continue
        
        # Parse template
        result = miner.add_log_message(line)
        template_id = result['cluster_id']
        template_counts[template_id] += 1
        
        # Parse timestamp
        ts = parse_timestamp(line)
        if ts:
            timestamps.append(ts)
            hour = ts.replace(minute=0, second=0, microsecond=0)
            template_by_time[hour][template_id] += 1
    
    # Số template unique
    unique_templates = len(miner.drain.clusters)
    print(f"✓ Số templates unique: {unique_templates}")
    
    # Top-5 templates
    print("\n" + "-"*80)
    print("TOP 5 TEMPLATES:")
    print("-"*80)
    
    sorted_clusters = sorted(miner.drain.clusters, key=lambda c: c.size, reverse=True)
    
    for i, cluster in enumerate(sorted_clusters[:5], 1):
        count = cluster.size
        percentage = (count / total_lines) * 100
        template = cluster.get_template()
        template_preview = template[:70] + "..." if len(template) > 70 else template
        
        print(f"\n{i}. T-{cluster.cluster_id:03d} (count: {count}, {percentage:.2f}%)")
        print(f"   {template_preview}")
    
    # Template tăng đột biến trong giờ gần nhất
    print("\n" + "-"*80)
    print("TEMPLATES TĂNG ĐỘT BIẾN (Giờ gần nhất vs Trung bình):")
    print("-"*80)
    
    if len(template_by_time) >= 2:
        hours = sorted(template_by_time.keys())
        last_hour = hours[-1]
        
        # Tính trung bình các giờ trước
        template_avg = defaultdict(float)
        for hour in hours[:-1]:
            for tid, count in template_by_time[hour].items():
                template_avg[tid] += count
        
        for tid in template_avg:
            template_avg[tid] /= len(hours) - 1
        
        # So sánh giờ cuối với trung bình
        spikes = []
        for tid, last_count in template_by_time[last_hour].items():
            avg_count = template_avg.get(tid, 0)
            if avg_count > 0:
                spike_ratio = last_count / avg_count
                if spike_ratio > 2:  # Tăng hơn 2x
                    spikes.append((tid, last_count, avg_count, spike_ratio))
        
        spikes.sort(key=lambda x: x[3], reverse=True)
        
        if spikes:
            print(f"\nGiờ gần nhất: {last_hour}")
            for tid, last_count, avg_count, ratio in spikes[:5]:
                for cluster in miner.drain.clusters:
                    if cluster.cluster_id == tid:
                        template = cluster.get_template()[:60] + "..."
                        print(f"\n  T-{tid:03d}: {int(last_count)} logs (avg: {avg_count:.1f}, tỷ lệ: {ratio:.2f}x)")
                        print(f"  → {template}")
                        break
        else:
            print("\n✗ Không phát hiện template nào tăng đột biến")
    else:
        print("\n✗ Không đủ dữ liệu theo giờ để phân tích")
    
    # New templates (chưa xuất hiện trước giờ gần nhất)
    print("\n" + "-"*80)
    print("NEW TEMPLATES (Xuất hiện trong giờ gần nhất):")
    print("-"*80)
    
    if len(template_by_time) >= 2:
        hours = sorted(template_by_time.keys())
        last_hour = hours[-1]
        
        # Templates đã xuất hiện trước giờ cuối
        old_templates = set()
        for hour in hours[:-1]:
            old_templates.update(template_by_time[hour].keys())
        
        # Templates mới trong giờ cuối
        new_templates = set(template_by_time[last_hour].keys()) - old_templates
        
        if new_templates:
            print(f"\n✓ Phát hiện {len(new_templates)} template(s) mới:")
            for tid in sorted(new_templates):
                for cluster in miner.drain.clusters:
                    if cluster.cluster_id == tid:
                        template = cluster.get_template()[:70] + "..."
                        count = template_by_time[last_hour][tid]
                        print(f"\n  T-{tid:03d} ({count} logs)")
                        print(f"  → {template}")
                        break
        else:
            print("\n✗ Không có template mới trong giờ gần nhất")
    else:
        print("\n✗ Không đủ dữ liệu theo giờ để phân tích")
    
    print("\n" + "="*80)
    print("HOÀN THÀNH!")
    print("="*80)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python log_analyzer.py <logfile>")
        sys.exit(1)
    
    logfile = sys.argv[1]
    analyze_log(logfile)
