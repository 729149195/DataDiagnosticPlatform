#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版CSV数据可视化工具 - 只显示3个核心图表（单独输出，每个按降序排列，无bar数值标签）
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
    db_files = glob.glob("./Manual/static/database_statistics_*.csv")
    channel_files = glob.glob("./Manual/static/channel_type_statistics_*.csv") 
    error_files = glob.glob("./Manual/static/error_type_statistics_*.csv")
    
    if not db_files or not channel_files or not error_files:
        print("错误：未找到必要的CSV文件！")
        return None, None, None
        
    latest_db = max(db_files, key=os.path.getctime)
    latest_channel = max(channel_files, key=os.path.getctime)
    latest_error = max(error_files, key=os.path.getctime)
    
    print(f"加载: {latest_db}")
    print(f"加载: {latest_channel}")
    print(f"加载: {latest_error}")
    
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

def plot_top_channel_types(channel_data):
    """输出前10个通道类型分布图，按数量降序（从上到下从大到小，0的不渲染，数据多时用省略号）"""
    # 过滤掉数量为0的通道类型
    filtered_channels = [ch for ch in channel_data if int(ch['Count']) > 0]
    # 如果全部为0，直接返回，不画图
    if not filtered_channels:
        print("没有数量大于0的通道类型，跳过通道类型分布图。")
        return
    # 按数量降序排序
    sorted_channels = sorted(filtered_channels, key=lambda x: int(x['Count']), reverse=True)
    # 只取前10个
    display_limit = 10
    display_channels = sorted_channels[:display_limit]
    names = [ch['Channel Type'] for ch in display_channels]
    counts = [int(ch['Count'])/1000000 for ch in display_channels]  # 单位: 百万

    # 如果数据超过15个，添加省略号
    if len(sorted_channels) > display_limit:
        names.append("……")
        counts.append(0)

    # y轴顺序从上到下是从大到小
    y_pos = np.arange(len(names))
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(names)))
    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.barh(y_pos, counts, color=colors, alpha=0.8, edgecolor='darkblue', linewidth=0.8)
    ax.set_yticks(y_pos)
    # 中文标签
    ax.set_yticklabels(names, fontsize=11)
    ax.set_title('前10个通道类型', fontweight='bold', fontsize=14)
    ax.set_xlabel('通道数量（百万）', fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    # 反转y轴，使最大值在最上面
    ax.invert_yaxis()
    plt.tight_layout()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"top_channel_types_{timestamp}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"通道类型分布图已保存为: {filename}")
    plt.show()

def plot_top_error_types(error_data):
    """输出前12个异常类型分布图，按数量降序（从上到下从大到小，0的不渲染，数据多时用省略号）"""
    # 过滤掉测试数据和数量为0的异常类型
    filtered_errors = [err for err in error_data if err['Error Type'] not in ['test', '34'] and int(err['Count']) > 0]
    # 如果全部为0，直接返回，不画图
    if not filtered_errors:
        print("没有数量大于0的异常类型，跳过异常类型分布图。")
        return
    # 按数量降序排序
    sorted_errors = sorted(filtered_errors, key=lambda x: int(x['Count']), reverse=True)
    # 只取前12个
    display_limit = 10
    display_errors = sorted_errors[:display_limit]
    error_names = [err['Error Type'].replace('error_', '') for err in display_errors]
    error_counts = [int(err['Count'])/1000 for err in display_errors]  # 单位: 千

    # 如果数据超过12个，添加省略号
    if len(sorted_errors) > display_limit:
        error_names.append("……")
        error_counts.append(0)

    y_pos = np.arange(len(error_names))
    colors = plt.cm.plasma(np.linspace(0.2, 0.8, len(error_names)))
    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.barh(y_pos, error_counts, color=colors, alpha=0.8, edgecolor='black', linewidth=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(error_names, fontsize=11)
    ax.set_title('前10个异常类型', fontweight='bold', fontsize=14)
    ax.set_xlabel('异常数量（千）', fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    # 反转y轴，使最大值在最上面
    ax.invert_yaxis()
    plt.tight_layout()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"top_error_types_{timestamp}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"异常类型分布图已保存为: {filename}")
    plt.show()

def plot_summary_stats(db_data, channel_data, error_data):
    """输出统计摘要图"""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis('off')
    total_shots = sum(int(db['shots']) for db in db_data)
    total_channels = sum(int(db['channels']) for db in db_data)
    total_errors = sum(int(db['errors']) for db in db_data)
    error_rate = (total_errors / total_channels * 100) if total_channels > 0 else 0

    # 主要通道类型和异常类型（按降序，且数量大于0）
    sorted_channels = sorted([ch for ch in channel_data if int(ch['Count']) > 0], key=lambda x: int(x['Count']), reverse=True)
    sorted_errors = sorted([err for err in error_data if err['Error Type'] not in ['test', '34'] and int(err['Count']) > 0], key=lambda x: int(x['Count']), reverse=True)

    # 只显示前三个主要通道类型和异常类型，数据多时用省略号
    main_channel_lines = []
    for i in range(min(3, len(sorted_channels))):
        main_channel_lines.append(f"• {sorted_channels[i]['Channel Type']}: {int(sorted_channels[i]['Count'])/1000000:.1f}百万")
    if len(sorted_channels) > 3:
        main_channel_lines.append("• ……")

    main_error_lines = []
    for i in range(min(2, len(sorted_errors))):
        main_error_lines.append(f"• {sorted_errors[i]['Error Type'].replace('error_', '')}: {int(sorted_errors[i]['Count'])/1000:.0f}千")
    if len(sorted_errors) > 2:
        main_error_lines.append("• ……")

    stats_text = f""" 统计摘要
═══════════════════

总实验次数:     {total_shots:,}
总通道数量:     {total_channels:,}
总异常数量:     {total_errors:,}
异常率:         {error_rate:.2f}%

数据库数量:     {len(db_data)}
通道类型数量:   {len([ch for ch in channel_data if int(ch['Count']) > 0])}
异常类型数量:   {len([err for err in error_data if err['Error Type'] not in ['test', '34'] and int(err['Count']) > 0])}

主要通道类型:
""" + "\n".join(main_channel_lines) + """

主要异常类型:
""" + "\n".join(main_error_lines) + "\n"

    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=12,
            verticalalignment='top',
            bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.8))
    plt.tight_layout()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"summary_stats_{timestamp}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"统计摘要图已保存为: {filename}")
    plt.show()

def main():
    """主函数"""
    print("数据诊断平台核心可视化工具")
    print("=" * 40)
    try:
        db_data, channel_data, error_data = load_csv_data()
        if not db_data:
            return
        plot_top_channel_types(channel_data)
        plot_top_error_types(error_data)
        plot_summary_stats(db_data, channel_data, error_data)
        print("可视化已完成！")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()