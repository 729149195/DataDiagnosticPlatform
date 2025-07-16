#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对指定数据库中的部分炮号进行重跑，并覆盖写入结果。
用法示例：
python rerun_selected_shots.py --db DataDiagnosticPlatform_[1_100] --shots 5-10,15,20 [--reset]
"""
import argparse
from pymongo import MongoClient
import sys
import os
import threading
import time
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box

# 动态导入 RUN
sys.path.append(os.path.join(os.path.dirname(__file__), 'RunDetectAlgorithm'))
from RunDetectAlgorithm.Get_structtrees_errors_indexs import RUN

def parse_shots(shots_str):
    """解析如 5-10,15,20 为 [5,6,7,8,9,10,15,20]"""
    shots = set()
    for part in shots_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            shots.update(range(int(start), int(end) + 1))
        elif part:
            shots.add(int(part))
    return sorted(shots)

def delete_shot_data(db, shot):
    """删除 struct_trees, errors_data, data_statistics, index 中该炮号相关数据"""
    db["struct_trees"].delete_many({"shot_number": str(shot)})
    db["errors_data"].delete_many({"shot_number": str(shot)})
    db["data_statistics"].delete_many({"shot_number": str(shot)})
    # index 结构特殊，需遍历所有文档
    for doc in db["index"].find({}):
        key = doc.get("key")
        if not key:
            continue
        index_data = doc.get("index_data", {})
        if str(shot) in index_data:
            del index_data[str(shot)]
            db["index"].update_one({"key": key}, {"$set": {"index_data": index_data}})

def get_shot_progress(db, shot, start_time, status):
    """从MongoDB获取单个炮号的进度信息"""
    struct_doc = db["struct_trees"].find_one({"shot_number": str(shot)})
    stats_doc = db["data_statistics"].find_one({"shot_number": str(shot)})
    # 通道进度
    processed = 0
    total = 0
    percent = "0.0%"
    if stats_doc:
        processed = stats_doc.get("total_channels_processed", 0)
        total = stats_doc.get("total_channels_expected", 0)
        if total > 0:
            percent = f"{processed/total*100:.1f}%"
        else:
            percent = "0.0%"
    # 状态
    if status == "运行中":
        if stats_doc and stats_doc.get("processing_completed", False):
            status_disp = "已完成"
        else:
            status_disp = "运行中"
    else:
        status_disp = status
    # 当前炮号
    current_shot = str(shot)
    # 已用时间
    elapsed = "00:00:00"
    if start_time:
        elapsed_seconds = int((datetime.now() - start_time).total_seconds())
        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        elapsed = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    # 炮号进度
    shot_progress = f"1/1"
    return {
        "炮号": current_shot,
        "状态": status_disp,
        "通道进度": f"{processed}/{total if total else '未知'}",
        "通道百分比": percent,
        "炮号进度": shot_progress,
        "已用时间": elapsed
    }

def progress_display_thread(db, shots, shot_status_dict, shot_start_time_dict, running_flag):
    console = Console()
    with Live(refresh_per_second=5, console=console, screen=False) as live:
        while running_flag[0]:
            table = Table(
                show_header=True,
                header_style="bold white on #222244",
                box=box.MINIMAL_DOUBLE_HEAD,
                expand=True,
                border_style="#444466",
                padding=(0, 1)
            )
            table.add_column("炮号", justify="center", style="bold cyan", no_wrap=True)
            table.add_column("状态", justify="center", style="bold")
            table.add_column("通道进度", justify="right", style="white")
            table.add_column("通道百分比", justify="right", style="bold")
            table.add_column("炮号进度", justify="right", style="white")
            table.add_column("已用时间", justify="center", style="dim")
            for shot in shots:
                status = shot_status_dict.get(shot, "等待中")
                start_time = shot_start_time_dict.get(shot, None)
                progress = get_shot_progress(db, shot, start_time, status)
                # 颜色
                if progress["状态"] == "运行中":
                    status_color = "#00ff99"
                elif progress["状态"] == "已完成":
                    status_color = "#3399ff"
                elif progress["状态"] == "等待中":
                    status_color = "#ffcc00"
                else:
                    status_color = "white"
                percent_value = 0
                try:
                    percent_value = float(progress["通道百分比"].rstrip('%'))
                except:
                    percent_value = 0
                percent_color = "#ff5555" if percent_value < 30 else "#ffaa00" if percent_value < 70 else "#00ff99"
                percent_disp = f"[bold {percent_color}]{progress['通道百分比']}[/bold {percent_color}]"
                table.add_row(
                    f"[cyan]{progress['炮号']}[/cyan]",
                    f"[bold {status_color}]{progress['状态']}[/bold {status_color}]",
                    progress["通道进度"],
                    percent_disp,
                    progress["炮号进度"],
                    progress["已用时间"]
                )
            live.update(table)
            time.sleep(0.2)

def main():
    parser = argparse.ArgumentParser(description='对指定数据库中的部分炮号进行重跑并覆盖写入')
    parser.add_argument('--db', type=str, required=True, help='数据库名，如 DataDiagnosticPlatform_[1_100]')
    parser.add_argument('--shots', type=str, required=True, help='炮号列表，如 5-10,15,20')
    parser.add_argument('--reset', action='store_true', help='是否重置（删除旧数据后重跑）')
    args = parser.parse_args()

    db_name = args.db
    shots = parse_shots(args.shots)
    reset = args.reset

    print(f"将对数据库 {db_name} 的以下炮号进行重跑: {shots}")
    if reset:
        print("重跑前将删除这些炮号的所有相关数据！")

    client = MongoClient("mongodb://localhost:27017")
    db = client[db_name]

    # 进度可视化相关
    shot_status_dict = {shot: "等待中" for shot in shots}
    shot_start_time_dict = {shot: None for shot in shots}
    running_flag = [True]
    progress_thread = threading.Thread(target=progress_display_thread, args=(db, shots, shot_status_dict, shot_start_time_dict, running_flag))
    progress_thread.daemon = True
    progress_thread.start()

    try:
        for shot in shots:
            shot_status_dict[shot] = "运行中"
            shot_start_time_dict[shot] = datetime.now()
            if reset:
                delete_shot_data(db, shot)
            try:
                RUN([shot, shot], [], db_name, reset=False)
                shot_status_dict[shot] = "已完成"
            except Exception as e:
                shot_status_dict[shot] = f"失败: {e}"
    finally:
        running_flag[0] = False
        progress_thread.join()
    print("\n所有指定炮号处理完成！")

if __name__ == "__main__":
    main() 