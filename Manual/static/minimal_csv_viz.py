#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版CSV数据可视化工具 - 只显示3个核心图表
"""

import matplotlib.pyplot as plt
import numpy as np
import csv
import glob
import os
from datetime import datetime

# 强制设置Windows中文字体
import matplotlib
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'KaiTi', 'FangSong', 'STSong', 'STKaiti']
matplotlib.rcParams['axes.unicode_minus'] = False

# 尝试设置中文字体
try:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
    # 测试中文显示
    fig_test = plt.figure()
    plt.text(0.5, 0.5, '测试中文', ha='center')
    plt.close(fig_test)
    print("使用字体: Microsoft YaHei")
except:
    try:
        plt.rcParams['font.sans-serif'] = ['SimHei']
        print("使用字体: SimHei")
    except:
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        print("警告: 使用默认字体，中文可能显示为方框")

plt.rcParams['axes.unicode_minus'] = False

def load_csv_data():
    """加载CSV数据"""
    # 查找最新的CSV文件
    db_files = glob.glob("database_statistics_*.csv")
    channel_files = glob.glob("channel_type_statistics_*.csv") 
    error_files = glob.glob("error_type_statistics_*.csv")
    
    if not db_files or not channel_files or not error_files:
        print("错误：未找到必要的CSV文件！")
        return None, None, None
        
    # 获取最新文件
    latest_db = max(db_files, key=os.path.getctime)
    latest_channel = max(channel_files, key=os.path.getctime)
    latest_error = max(error_files, key=os.path.getctime)
    
    print(f"加载: {latest_db}")
    print(f"加载: {latest_channel}")
    print(f"加载: {latest_error}")
    
    # 读取CSV文件
    db_data = []
    with open(latest_db, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            db_data.append(row)
    
    channel_data = []
    with open(latest_channel, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            channel_data.append(row)
    
    error_data = []
    with open(latest_error, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            error_data.append(row)
    
    return db_data, channel_data, error_data

def create_visualization():
    """创建3个核心可视化图表"""
    db_data, channel_data, error_data = load_csv_data()
    if not db_data:
        return
    
    # 创建1行3列的子图
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle('数据诊断平台核心统计分析', fontsize=18, fontweight='bold')
    
    # 1. 前15个通道类型分布
    ax1 = axes[0]
    top_channels = channel_data[:15]
    names = [ch['Channel Type'] for ch in top_channels]
    counts = [int(ch['Count'])/1000000 for ch in top_channels]  # 转换为百万
    
    y_pos = np.arange(len(names))
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(names)))
    bars = ax1.barh(y_pos, counts, color=colors, alpha=0.8, edgecolor='darkblue', linewidth=0.8)
    
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(names, fontsize=11)
    ax1.set_title('前15个通道类型分布', fontweight='bold', fontsize=14)
    ax1.set_xlabel('通道数量 (百万)', fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)
    
    # 添加数值标签
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax1.text(width + 0.05, bar.get_y() + bar.get_height()/2, 
                f'{counts[i]:.1f}M', va='center', fontweight='bold', fontsize=10)
    
    # 2. 前12个异常类型分布
    ax2 = axes[1]
    # 过滤掉测试数据
    filtered_errors = [err for err in error_data if err['Error Type'] not in ['test', '34']][:12]
    error_names = [err['Error Type'].replace('error_', '') for err in filtered_errors]
    error_counts = [int(err['Count'])/1000 for err in filtered_errors]  # 转换为千
    
    y_pos = np.arange(len(error_names))
    colors = plt.cm.plasma(np.linspace(0.2, 0.8, len(error_names)))
    bars = ax2.barh(y_pos, error_counts, color=colors, alpha=0.8, edgecolor='black', linewidth=0.8)
    
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(error_names, fontsize=11)
    ax2.set_title('前12个异常类型分布', fontweight='bold', fontsize=14)
    ax2.set_xlabel('异常数量 (千)', fontweight='bold')
    ax2.grid(axis='x', alpha=0.3)
    
    # 添加数值标签
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax2.text(width + max(error_counts)*0.02, bar.get_y() + bar.get_height()/2, 
                f'{error_counts[i]:.0f}K', va='center', fontweight='bold', fontsize=10)
    
    # 3. 统计摘要
    ax3 = axes[2]
    ax3.axis('off')
    
    total_shots = sum(int(db['shots']) for db in db_data)
    total_channels = sum(int(db['channels']) for db in db_data)
    total_errors = sum(int(db['errors']) for db in db_data)
    error_rate = (total_errors / total_channels * 100) if total_channels > 0 else 0
    
    stats_text = f""" 总体统计摘要
═══════════════════

总炮号数:     {total_shots:,}
总通道数:     {total_channels:,}
总异常数:     {total_errors:,}
异常率:       {error_rate:.2f}%

数据库数量:   {len(db_data)}
通道类型数:   {len(channel_data)}
异常类型数:   {len(error_data)-2}

主要通道类型:
• {channel_data[0]['Channel Type']}: {int(channel_data[0]['Count'])/1000000:.1f}M
• {channel_data[1]['Channel Type']}: {int(channel_data[1]['Count'])/1000000:.1f}M
• {channel_data[2]['Channel Type']}: {int(channel_data[2]['Count'])/1000000:.1f}M

主要异常类型:
• {error_data[0]['Error Type'].replace('error_', '')}: {int(error_data[0]['Count'])/1000:.0f}K
• {error_data[1]['Error Type'].replace('error_', '')}: {int(error_data[1]['Count'])/1000:.0f}K

"""
    
    ax3.text(0.05, 0.95, stats_text, transform=ax3.transAxes, fontsize=12,
            verticalalignment='top',
            bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.8))
    
    plt.tight_layout()
    
    # 保存图表
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"数据诊断核心报告_{timestamp}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"\n核心报告已保存为: {filename}")
    
    plt.show()

def main():
    """主函数"""
    print("数据诊断平台核心可视化工具")
    print("=" * 40)
    
    try:
        create_visualization()
        print("可视化完成！")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 