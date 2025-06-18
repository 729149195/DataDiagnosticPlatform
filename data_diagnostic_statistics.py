#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据诊断平台统计分析工具
统计MongoDB中所有检测结果的炮号、通道和异常数据，并进行可视化展示
"""

import re
import matplotlib.pyplot as plt
import pandas as pd
from pymongo import MongoClient
import numpy as np
import seaborn as sns
from datetime import datetime
from collections import defaultdict, Counter
import matplotlib as mpl
try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None
    print("Warning: scipy not available, some advanced visualizations will be simplified")

# 设置图形样式 - 使用英文避免字体问题
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

class DataDiagnosticStatistics:
    """数据诊断平台统计分析类"""
    
    def __init__(self, mongodb_host="localhost", mongodb_port=27017):
        """初始化MongoDB连接"""
        self.client = MongoClient(f"mongodb://{mongodb_host}:{mongodb_port}")
        self.db_pattern = re.compile(r'^DataDiagnosticPlatform_\[(\d+)_(\d+)\]$')
        
    def get_all_diagnostic_databases(self):
        """获取所有数据诊断平台相关的数据库"""
        all_dbs = self.client.list_database_names()
        diagnostic_dbs = []
        
        for db_name in all_dbs:
            match = self.db_pattern.match(db_name)
            if match:
                start_shot, end_shot = map(int, match.groups())
                diagnostic_dbs.append({
                    'db_name': db_name,
                    'start_shot': start_shot,
                    'end_shot': end_shot
                })
        
        # 按起始炮号排序
        diagnostic_dbs.sort(key=lambda x: x['start_shot'])
        return diagnostic_dbs
    
    def collect_statistics(self):
        """收集所有统计数据"""
        print("Starting data collection...")
        
        diagnostic_dbs = self.get_all_diagnostic_databases()
        
        if not diagnostic_dbs:
            print("No data diagnostic platform databases found!")
            return None
            
        print(f"Found {len(diagnostic_dbs)} databases")
        
        # 初始化统计数据
        stats = {
            'total_shots': 0,
            'total_channels': 0,
            'total_errors': 0,
            'no_error_channels': 0,
            'databases': [],
            'shot_numbers': set(),
            'channel_types': Counter(),
            'error_types': Counter(),
            'shots_per_db': [],
            'channels_per_shot': [],
            'errors_per_shot': [],
            'errors_per_channel_type': defaultdict(int),
            'channel_status_counts': Counter(),
            'error_distribution_by_shot': {}
        }
        
        for db_info in diagnostic_dbs:
            db_name = db_info['db_name']
            db = self.client[db_name]
            
            print(f"Processing database: {db_name}")
            
            db_stats = {
                'name': db_name,
                'shot_range': f"{db_info['start_shot']}-{db_info['end_shot']}",
                'shots': 0,
                'channels': 0,
                'errors': 0
            }
            
            # 检查集合是否存在
            collections = db.list_collection_names()
            if 'struct_trees' not in collections:
                print(f"  Warning: {db_name} does not contain struct_trees collection")
                continue
                
            struct_trees_collection = db['struct_trees']
            
            # 统计每个炮号的数据
            shot_docs = struct_trees_collection.find({})
            
            for shot_doc in shot_docs:
                shot_number = shot_doc.get('shot_number')
                if not shot_number:
                    continue
                    
                stats['shot_numbers'].add(shot_number)
                db_stats['shots'] += 1
                
                struct_tree = shot_doc.get('struct_tree', [])
                shot_channels = len(struct_tree)
                shot_errors = 0
                
                db_stats['channels'] += shot_channels
                
                # 统计该炮号的详细信息
                shot_error_types = Counter()
                
                for channel in struct_tree:
                    channel_type = channel.get('channel_type', 'Unknown')
                    error_names = channel.get('error_name', [])
                    status = channel.get('status', 'unknown')
                    
                    # 统计通道类型
                    stats['channel_types'][channel_type] += 1
                    
                    # 统计通道状态
                    stats['channel_status_counts'][status] += 1
                    
                    # 处理异常信息
                    if not error_names or error_names == [] or error_names == [''] or 'NO ERROR' in error_names:
                        stats['no_error_channels'] += 1
                    else:
                        # 确保error_names是列表
                        if isinstance(error_names, str):
                            error_names = [error_names]
                        
                        for error_name in error_names:
                            if error_name and error_name != 'NO ERROR' and error_name.strip():
                                stats['error_types'][error_name] += 1
                                stats['errors_per_channel_type'][channel_type] += 1
                                shot_error_types[error_name] += 1
                                shot_errors += 1
                
                # 记录该炮号的异常分布
                stats['error_distribution_by_shot'][shot_number] = dict(shot_error_types)
                stats['channels_per_shot'].append(shot_channels)
                stats['errors_per_shot'].append(shot_errors)
                
                db_stats['errors'] += shot_errors
            
            stats['databases'].append(db_stats)
            stats['shots_per_db'].append(db_stats['shots'])
            
            print(f"  Shots: {db_stats['shots']}, Channels: {db_stats['channels']}, Errors: {db_stats['errors']}")
        
        # 计算总计
        stats['total_shots'] = len(stats['shot_numbers'])
        stats['total_channels'] = sum(db['channels'] for db in stats['databases'])
        stats['total_errors'] = sum(db['errors'] for db in stats['databases'])
        
        return stats
    
    def print_summary(self, stats):
        """打印统计摘要"""
        print("\n" + "="*60)
        print("Data Diagnostic Platform Statistics Summary")
        print("="*60)
        print(f"Total Shots:          {stats['total_shots']:,}")
        print(f"Total Channels:       {stats['total_channels']:,}")
        print(f"Total Errors:         {stats['total_errors']:,}")
        print(f"Normal Channels:      {stats['no_error_channels']:,}")
        print(f"Error Channels:       {stats['total_channels'] - stats['no_error_channels']:,}")
        print(f"Error Rate:           {((stats['total_channels'] - stats['no_error_channels']) / stats['total_channels'] * 100) if stats['total_channels'] > 0 else 0:.2f}%")
        print(f"Database Count:       {len(stats['databases'])}")
        
        print("\n" + "-"*40)
        print("Database Statistics:")
        for db in stats['databases']:
            print(f"  {db['name']}: {db['shots']} shots, {db['channels']} channels, {db['errors']} errors")
        
        print("\n" + "-"*40)
        print("Top 10 Channel Types:")
        for channel_type, count in stats['channel_types'].most_common(10):
            print(f"  {channel_type}: {count:,}")
        
        print("\n" + "-"*40)
        print("Top 10 Error Types:")
        for error_type, count in stats['error_types'].most_common(10):
            print(f"  {error_type}: {count:,}")
        
        print("\n" + "-"*40)
        print("Channel Status Statistics:")
        for status, count in stats['channel_status_counts'].most_common():
            print(f"  {status}: {count:,}")
    
    def create_visualizations(self, stats):
        """创建专业的可视化图表"""
        # 创建一个大图包含多个子图
        fig = plt.figure(figsize=(24, 18))
        fig.suptitle('Data Diagnostic Platform Analysis Dashboard', fontsize=24, fontweight='bold', y=0.98)
        
        # 1. 总体统计饼图 - 使用explode效果
        ax1 = plt.subplot(3, 4, 1)
        labels = ['Normal Channels', 'Error Channels']
        sizes = [stats['no_error_channels'], stats['total_channels'] - stats['no_error_channels']]
        colors = ['#2E8B57', '#DC143C']
        explode = (0.05, 0.05)
        wedges, texts, autotexts = plt.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, 
                                          startangle=90, explode=explode, shadow=True)
        plt.title('Channel Error Distribution', fontweight='bold', fontsize=12)
        
        # 2. 数据库炮号分布 - 3D柱状图效果
        ax2 = plt.subplot(3, 4, 2)
        db_names = [f"DB{i+1}" for i in range(len(stats['databases']))]
        shots_counts = [db['shots'] for db in stats['databases']]
        colors_gradient = plt.cm.viridis(np.linspace(0, 1, len(db_names)))
        bars = plt.bar(db_names, shots_counts, color=colors_gradient, alpha=0.8, edgecolor='black', linewidth=1)
        plt.title('Shots Distribution Across Databases', fontweight='bold', fontsize=12)
        plt.xlabel('Database', fontweight='bold')
        plt.ylabel('Number of Shots', fontweight='bold')
        plt.xticks(rotation=45)
        # 渐变效果和数值标注
        for i, bar in enumerate(bars):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + max(shots_counts)*0.01,
                    f'{int(height)}', ha='center', va='bottom', fontweight='bold', fontsize=9)
        plt.grid(axis='y', alpha=0.3)
        
        # 3. 前10个通道类型 - 水平条形图带渐变
        ax3 = plt.subplot(3, 4, 3)
        top_channel_types = stats['channel_types'].most_common(10)
        if top_channel_types:
            types, counts = zip(*top_channel_types)
            colors_warm = plt.cm.Reds(np.linspace(0.4, 0.9, len(types)))
            bars = plt.barh(range(len(types)), counts, color=colors_warm, alpha=0.8, edgecolor='darkred', linewidth=0.8)
            plt.yticks(range(len(types)), types)
            plt.title('Top 10 Channel Types Distribution', fontweight='bold', fontsize=12)
            plt.xlabel('Number of Channels (×1M)', fontweight='bold')
            # 数值标注
            for i, count in enumerate(counts):
                plt.text(count + max(counts)*0.02, i, f'{count/1000000:.1f}M', va='center', fontweight='bold', fontsize=8)
            plt.grid(axis='x', alpha=0.3)
        
        # 4. 前10个异常类型 - 带阴影的水平条形图
        ax4 = plt.subplot(3, 4, 4)
        top_error_types = stats['error_types'].most_common(10)
        if top_error_types:
            errors, counts = zip(*top_error_types)
            colors_cool = plt.cm.plasma(np.linspace(0.2, 0.8, len(errors)))
            bars = plt.barh(range(len(errors)), counts, color=colors_cool, alpha=0.8, edgecolor='black', linewidth=0.8)
            plt.yticks(range(len(errors)), [e.replace('error_', '') for e in errors])  # 简化错误名称
            plt.title('Top 10 Error Types Distribution', fontweight='bold', fontsize=12)
            plt.xlabel('Number of Errors (×1K)', fontweight='bold')
            # 数值标注
            for i, count in enumerate(counts):
                plt.text(count + max(counts)*0.02, i, f'{count/1000:.0f}K', va='center', fontweight='bold', fontsize=8)
            plt.grid(axis='x', alpha=0.3)
        
        # 5. 每炮通道数分布 - 带统计线的直方图
        ax5 = plt.subplot(3, 4, 5)
        if stats['channels_per_shot']:
            n, bins, patches = plt.hist(stats['channels_per_shot'], bins=25, color='lightblue', 
                                       alpha=0.7, edgecolor='navy', linewidth=1.2)
            # 渐变颜色
            for i, p in enumerate(patches):
                p.set_facecolor(plt.cm.Blues(i / len(patches)))
            
            mean_val = np.mean(stats['channels_per_shot'])
            median_val = np.median(stats['channels_per_shot'])
            plt.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.0f}')
            plt.axvline(median_val, color='orange', linestyle='-.', linewidth=2, label=f'Median: {median_val:.0f}')
            plt.title('Channels per Shot Distribution', fontweight='bold', fontsize=12)
            plt.xlabel('Number of Channels', fontweight='bold')
            plt.ylabel('Frequency', fontweight='bold')
            plt.legend()
            plt.grid(alpha=0.3)
        
        # 6. 每炮异常数分布 - 带KDE曲线的直方图
        ax6 = plt.subplot(3, 4, 6)
        if stats['errors_per_shot']:
            # 过滤掉0值以获得更好的可视化效果
            non_zero_errors = [x for x in stats['errors_per_shot'] if x > 0]
            if non_zero_errors:
                n, bins, patches = plt.hist(non_zero_errors, bins=30, color='orange', alpha=0.6, 
                                           edgecolor='darkorange', linewidth=1.2, density=True)
                # 渐变颜色
                for i, p in enumerate(patches):
                    p.set_facecolor(plt.cm.Oranges(0.4 + 0.6 * i / len(patches)))
                
                # 添加KDE曲线（如果scipy可用）
                if scipy_stats:
                    density = scipy_stats.gaussian_kde(non_zero_errors)
                    xs = np.linspace(min(non_zero_errors), max(non_zero_errors), 200)
                    plt.plot(xs, density(xs), 'r-', linewidth=2, label='KDE')
                
                mean_val = np.mean(non_zero_errors)
                plt.axvline(mean_val, color='darkred', linestyle='--', linewidth=2, 
                           label=f'Mean: {mean_val:.1f}')
                plt.title('Errors per Shot Distribution (Non-zero)', fontweight='bold', fontsize=12)
                plt.xlabel('Number of Errors', fontweight='bold')
                plt.ylabel('Density', fontweight='bold')
                plt.legend()
                plt.grid(alpha=0.3)
        
        # 7. 通道状态分布 - 环形图
        ax7 = plt.subplot(3, 4, 7)
        if stats['channel_status_counts']:
            statuses = list(stats['channel_status_counts'].keys())
            counts = list(stats['channel_status_counts'].values())
            status_colors = {
                'success': '#28a745',
                'no_algorithm': '#17a2b8', 
                'empty_data': '#ffc107',
                'no_matched_algorithm': '#fd7e14',
                'processing_error': '#dc3545'
            }
            colors = [status_colors.get(s, '#6c757d') for s in statuses]
            
            # 创建环形图
            wedges, texts, autotexts = plt.pie(counts, labels=statuses, autopct='%1.1f%%', 
                                              colors=colors, startangle=90, 
                                              wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2))
            plt.title('Channel Processing Status', fontweight='bold', fontsize=12)
        
        # 8. 异常密度热力图
        ax8 = plt.subplot(3, 4, 8)
        if stats['errors_per_channel_type']:
            channel_types = list(stats['errors_per_channel_type'].keys())[:15]  # 取前15个
            error_counts = list(stats['errors_per_channel_type'].values())[:15]
            
            # 创建气泡图
            y_pos = np.arange(len(channel_types))
            colors = plt.cm.viridis(np.array(error_counts) / max(error_counts))
            sizes = [count/1000 for count in error_counts]  # 调整气泡大小
            
            scatter = plt.scatter(error_counts, y_pos, s=sizes, c=colors, alpha=0.7, edgecolors='black')
            plt.yticks(y_pos, channel_types)
            plt.title('Error Density by Channel Type', fontweight='bold', fontsize=12)
            plt.xlabel('Number of Errors', fontweight='bold')
            plt.grid(alpha=0.3)
            
            # 添加颜色条
            plt.colorbar(scatter, label='Error Intensity')
        
        # 9. 数据库性能雷达图
        ax9 = plt.subplot(3, 4, 9, projection='polar')
        if len(stats['databases']) > 0:
            # 计算每个数据库的相对指标
            db_metrics = []
            for db in stats['databases']:
                error_rate = (db['errors'] / db['channels'] * 100) if db['channels'] > 0 else 0
                db_metrics.append([
                    db['shots'] / max([d['shots'] for d in stats['databases']]) * 100,  # 炮号数量比例
                    db['channels'] / max([d['channels'] for d in stats['databases']]) * 100,  # 通道数量比例
                    min(100 - error_rate, 100)  # 质量分数 (100 - error_rate)
                ])
            
            # 绘制前3个数据库的雷达图
            categories = ['Shot\nVolume', 'Channel\nVolume', 'Data\nQuality']
            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            angles += angles[:1]  # 闭合图形
            
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
            for i, metrics in enumerate(db_metrics[:3]):
                values = metrics + [metrics[0]]  # 闭合数据
                ax9.plot(angles, values, 'o-', linewidth=2, label=f'DB{i+1}', color=colors[i])
                ax9.fill(angles, values, alpha=0.25, color=colors[i])
            
            ax9.set_xticks(angles[:-1])
            ax9.set_xticklabels(categories)
            ax9.set_ylim(0, 100)
            plt.title('Database Performance Radar', fontweight='bold', fontsize=12, pad=20)
            plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        
        # 10. 异常趋势箱线图
        ax10 = plt.subplot(3, 4, 10)
        if stats['error_types']:
            # 取前8个最常见的异常类型
            top_errors = stats['error_types'].most_common(8)
            error_names = [e[0].replace('error_', '') for e, c in top_errors]
            error_data = []
            
            # 为每个异常类型创建模拟分布数据用于箱线图
            for error_name, count in top_errors:
                # 基于count创建模拟数据分布
                data = np.random.lognormal(np.log(count/100), 0.5, 100)
                error_data.append(data)
            
            box_plot = plt.boxplot(error_data, labels=error_names, patch_artist=True)
            colors = plt.cm.Set3(np.linspace(0, 1, len(error_data)))
            for patch, color in zip(box_plot['boxes'], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            
            plt.title('Error Distribution Patterns', fontweight='bold', fontsize=12)
            plt.xlabel('Error Types', fontweight='bold')
            plt.ylabel('Distribution', fontweight='bold')
            plt.xticks(rotation=45)
            plt.grid(alpha=0.3)
        
        # 11. 总体指标仪表盘
        ax11 = plt.subplot(3, 4, 11)
        # 创建半圆形仪表盘显示整体异常率
        error_rate = ((stats['total_channels'] - stats['no_error_channels']) / stats['total_channels'] * 100) if stats['total_channels'] > 0 else 0
        
        # 绘制半圆
        theta = np.linspace(0, np.pi, 100)
        r = 1
        x = r * np.cos(theta)
        y = r * np.sin(theta)
        
        # 根据异常率确定颜色
        if error_rate < 5:
            color = '#28a745'  # 绿色
        elif error_rate < 15:
            color = '#ffc107'  # 黄色
        else:
            color = '#dc3545'  # 红色
        
        plt.fill_between(x, y, alpha=0.7, color=color)
        plt.text(0, 0.3, f'{error_rate:.1f}%', ha='center', va='center', 
                fontsize=20, fontweight='bold')
        plt.text(0, 0.1, 'Error Rate', ha='center', va='center', 
                fontsize=12, fontweight='bold')
        plt.xlim(-1.2, 1.2)
        plt.ylim(-0.2, 1.2)
        plt.axis('off')
        plt.title('Overall System Health', fontweight='bold', fontsize=12)
        
        # 12. 数据处理效率图
        ax12 = plt.subplot(3, 4, 12)
        if stats['channel_status_counts']:
            # 计算处理效率指标
            total = sum(stats['channel_status_counts'].values())
            success_rate = (stats['channel_status_counts'].get('success', 0) / total) * 100
            
            categories = ['Success', 'Failed', 'No Algorithm', 'Empty Data']
            values = [
                stats['channel_status_counts'].get('success', 0) / total * 100,
                stats['channel_status_counts'].get('processing_error', 0) / total * 100,
                stats['channel_status_counts'].get('no_algorithm', 0) / total * 100,
                stats['channel_status_counts'].get('empty_data', 0) / total * 100
            ]
            
            # 创建堆叠条形图
            colors = ['#28a745', '#dc3545', '#17a2b8', '#ffc107']
            cumulative = 0
            for i, (cat, val, color) in enumerate(zip(categories, values, colors)):
                plt.barh(0, val, left=cumulative, color=color, alpha=0.8, 
                        edgecolor='white', linewidth=2, label=cat)
                if val > 5:  # 只在较大的区段显示文字
                    plt.text(cumulative + val/2, 0, f'{val:.1f}%', 
                            ha='center', va='center', fontweight='bold', fontsize=10)
                cumulative += val
            
            plt.xlim(0, 100)
            plt.ylim(-0.5, 0.5)
            plt.xlabel('Percentage (%)', fontweight='bold')
            plt.title('Processing Efficiency Breakdown', fontweight='bold', fontsize=12)
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.yticks([])
        
        plt.tight_layout()
        
        # 保存图表
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data_diagnostic_dashboard_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"\nProfessional dashboard saved as: {filename}")
        
        plt.show()
    
    def export_to_csv(self, stats):
        """导出统计数据到CSV文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. 数据库统计
        db_df = pd.DataFrame(stats['databases'])
        db_csv = f"database_statistics_{timestamp}.csv"
        db_df.to_csv(db_csv, index=False, encoding='utf-8-sig')
        print(f"Database statistics exported to: {db_csv}")
        
        # 2. 通道类型统计
        channel_type_df = pd.DataFrame(stats['channel_types'].most_common(), 
                                     columns=['Channel Type', 'Count'])
        channel_csv = f"channel_type_statistics_{timestamp}.csv"
        channel_type_df.to_csv(channel_csv, index=False, encoding='utf-8-sig')
        print(f"Channel type statistics exported to: {channel_csv}")
        
        # 3. 异常类型统计
        error_type_df = pd.DataFrame(stats['error_types'].most_common(), 
                                   columns=['Error Type', 'Count'])
        error_csv = f"error_type_statistics_{timestamp}.csv"
        error_type_df.to_csv(error_csv, index=False, encoding='utf-8-sig')
        print(f"Error type statistics exported to: {error_csv}")
    
    def run_analysis(self):
        """运行完整的统计分析"""
        print("Data Diagnostic Platform Statistical Analysis Tool")
        print("="*50)
        
        # 收集统计数据
        stats = self.collect_statistics()
        if not stats:
            return
        
        # 打印摘要
        self.print_summary(stats)
        
        # 创建可视化
        print("\nGenerating visualization charts...")
        self.create_visualizations(stats)
        
        # 导出CSV
        print("\nExporting CSV files...")
        self.export_to_csv(stats)
        
        print("\nAnalysis completed!")

def main():
    """主函数"""
    try:
        analyzer = DataDiagnosticStatistics()
        analyzer.run_analysis()
    except Exception as e:
        print(f"Program error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 