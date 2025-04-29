#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据诊断平台批量处理主控程序
同时运行多个Get_structtrees_errors_indexs.py进程，处理不同范围的炮号数据
并实时显示处理进度
"""

import os
import time
import subprocess
import threading
import argparse
import shutil  # 用于获取终端大小
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
from tabulate import tabulate
from tqdm import tqdm
import numpy as np
from rich.console import Console
from rich.table import Table

# 终端颜色定义
class Colors:
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

# 配置参数
DEFAULT_CONCURRENT_PROCESSES = 5
DEFAULT_BATCH_SIZE = 2
DEFAULT_START_SHOT = 1
DEFAULT_END_SHOT = 20
PROCESS_SCRIPT = "/home/diag/DataDiagnostic/DataDiagnosticPlatform/RunDetectAlgorithm/Get_structtrees_errors_indexs.py"
WORKING_DIR = "~/DataDiagnostic/DataDiagnosticPlatform"
CONDA_ENV = "mdsplus"
SHOT_PROCESS_TIME = 160  # 每个炮号处理时间约160秒
REFRESH_INTERVAL = 1.0   # 进度更新频率(秒)

class ProcessRunner:
    """处理单个批次的炮号范围的进程管理类"""
    
    def __init__(self, process_id, start_shot, end_shot, working_dir, script_path, conda_env):
        self.process_id = process_id
        self.start_shot = start_shot
        self.end_shot = end_shot
        self.working_dir = os.path.expanduser(working_dir)
        self.script_path = script_path
        self.conda_env = conda_env
        self.process = None
        self.db_name = f"DataDiagnosticPlatform_[{start_shot}_{end_shot}]"
        self.start_time = None
        self.status = "等待中"  # 等待中, 运行中, 已完成
        self.current_shot = "N/A"
        self.channels_total = 0
        self.channels_processed = 0
        self.lock = threading.Lock()
    
    def get_elapsed_time(self):
        """获取进程已运行时间"""
        if self.start_time is None:
            return "00:00:00"
        
        elapsed_seconds = int((datetime.now() - self.start_time).total_seconds())
        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def run(self):
        """启动处理进程"""
        with self.lock:
            self.status = "运行中"
            self.start_time = datetime.now()
            
            # 构建命令
            cmd = f"cd {self.working_dir} && conda run -n {self.conda_env} python {self.script_path} {self.start_shot} {self.end_shot}"
            
            # 启动子进程
            self.process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 启动独立线程监控进程状态
            monitor_thread = threading.Thread(target=self._monitor_process)
            monitor_thread.daemon = True
            monitor_thread.start()
    
    def _monitor_process(self):
        """监控进程执行状态"""
        self.process.wait()
        with self.lock:
            self.status = "已完成"
    
    def update_progress(self, mongo_client):
        """从MongoDB更新进度信息"""
        if self.status != "运行中":
            return
            
        try:
            with self.lock:
                db = mongo_client[self.db_name]
                
                # 获取数据统计
                stats_collection = db["data_statistics"]
                stats_docs = list(stats_collection.find({}))
                
                if stats_docs:
                    # 找出最新的处理中的炮号
                    latest_shot = None
                    max_processed = 0
                    
                    for doc in stats_docs:
                        shot_num = doc.get("shot_number")
                        if shot_num and shot_num.isdigit():
                            processed = doc.get("total_channels_processed", 0)
                            if processed > 0:
                                if latest_shot is None or int(shot_num) > int(latest_shot):
                                    latest_shot = shot_num
                                    
                    if latest_shot:
                        self.current_shot = latest_shot
                
                # 获取结构树中记录的通道总数和处理情况
                struct_trees = db["struct_trees"]
                all_channels = 0
                processed_channels = 0
                
                for shot in range(self.start_shot, self.end_shot + 1):
                    shot_doc = struct_trees.find_one({"shot_number": str(shot)})
                    if shot_doc and "struct_tree" in shot_doc:
                        channels_in_shot = len(shot_doc["struct_tree"])
                        all_channels += channels_in_shot
                        if shot < int(self.current_shot) or (shot == int(self.current_shot) and channels_in_shot > 0):
                            if shot < int(self.current_shot):
                                processed_channels += channels_in_shot
                            else:
                                processed_channels += channels_in_shot
                
                self.channels_processed = processed_channels
                
                # 如果还没有通道总数信息，尝试从索引或其他集合获取
                if self.channels_total == 0 and all_channels > 0:
                    # 已经有一些处理过的通道，可以估算总数
                    shot_range = self.end_shot - self.start_shot + 1
                    shots_with_data = len([s for s in range(self.start_shot, self.end_shot + 1) 
                                          if struct_trees.find_one({"shot_number": str(s)}) is not None])
                    
                    if shots_with_data > 0:
                        avg_channels_per_shot = all_channels / shots_with_data
                        self.channels_total = int(avg_channels_per_shot * shot_range)
                    else:
                        # 假设每个炮号平均200个通道
                        self.channels_total = shot_range * 200
                
                # 计算预计完成时间
                if self.channels_total > 0 and self.channels_processed > 0:
                    progress_ratio = self.channels_processed / self.channels_total
                    if progress_ratio > 0:
                        elapsed = (datetime.now() - self.start_time).total_seconds()
                        estimated_total = elapsed / progress_ratio
                        remaining = estimated_total - elapsed
                        self.estimated_end_time = (datetime.now() + timedelta(seconds=remaining)).strftime("%H:%M:%S")
                elif int(self.current_shot) > self.start_shot:
                    # 基于炮号进度和平均处理时间估计
                    shots_done = int(self.current_shot) - self.start_shot
                    total_shots = self.end_shot - self.start_shot + 1
                    remaining_shots = total_shots - shots_done
                    self.estimated_end_time = (datetime.now() + timedelta(seconds=remaining_shots * SHOT_PROCESS_TIME)).strftime("%H:%M:%S")
                else:
                    # 最简单的估算：每个炮号约160秒
                    total_shots = self.end_shot - self.start_shot + 1
                    self.estimated_end_time = (datetime.now() + timedelta(seconds=total_shots * SHOT_PROCESS_TIME)).strftime("%H:%M:%S")
                    
        except Exception as e:
            print(f"进程 {self.process_id} 更新进度时出错: {e}")
    
    def is_running(self):
        """检查进程是否仍在运行"""
        with self.lock:
            if self.process is None:
                return False
            return self.process.poll() is None
    
    def get_status_info(self):
        """获取当前状态信息"""
        with self.lock:
            # 计算炮号进度
            total_shots = self.end_shot - self.start_shot + 1
            if self.current_shot != "N/A":
                shots_completed = max(0, int(self.current_shot) - self.start_shot)
                shot_progress = f"{shots_completed}/{total_shots}"
            else:
                shot_progress = f"0/{total_shots}"
            
            # 计算通道进度
            if self.channels_total > 0:
                channel_progress = f"{self.channels_processed}/{self.channels_total}"
                channel_percent = f"{self.channels_processed/self.channels_total:.1%}"
            else:
                channel_progress = "等待中"
                channel_percent = "0.0%"
            
            return {
                "进程ID": self.process_id,
                "炮号范围": f"{self.start_shot}-{self.end_shot}",
                "当前炮号": self.current_shot,
                "状态": self.status,
                "通道进度": channel_progress,
                "通道百分比": channel_percent,
                "炮号进度": shot_progress,
                "已用时间": self.get_elapsed_time()
            }

class BatchProcessor:
    """批量处理管理类"""
    
    def __init__(self, start_shot, end_shot, batch_size, concurrent_processes, 
                 working_dir, script_path, conda_env):
        self.start_shot = start_shot
        self.end_shot = end_shot
        self.batch_size = batch_size
        self.concurrent_processes = concurrent_processes
        self.working_dir = working_dir
        self.script_path = script_path
        self.conda_env = conda_env
        
        # 计算批次
        self.batches = []
        for i in range(start_shot, end_shot + 1, batch_size):
            batch_end = min(i + batch_size - 1, end_shot)
            self.batches.append((i, batch_end))
        
        self.total_batches = len(self.batches)
        self.current_batch_index = 0
        self.processes = []
        self.mongo_client = MongoClient("mongodb://localhost:27017")
        self.running = True
        self.progress_lock = threading.Lock()
    
    def start(self):
        """启动批处理"""
        print(f"开始处理炮号范围: {self.start_shot}-{self.end_shot}")
        print(f"共 {self.total_batches} 个批次，每批 {self.batch_size} 个炮号，同时运行 {self.concurrent_processes} 个进程")
        
        # 启动进度显示线程
        progress_thread = threading.Thread(target=self._update_progress_display)
        progress_thread.daemon = True
        progress_thread.start()
        
        # 启动初始进程
        initial_processes = min(self.concurrent_processes, self.total_batches)
        for i in range(initial_processes):
            self._start_next_batch()
        
        try:
            # 主循环：监控进程完成情况，启动新进程
            while self.current_batch_index < self.total_batches or any(p.is_running() for p in self.processes):
                # 检查是否有完成的进程
                for proc in list(self.processes):
                    if not proc.is_running() and proc.status != "已完成":
                        with self.progress_lock:
                            proc.status = "已完成"
                
                # 如果有进程完成，且还有批次未处理，启动新的批次
                if (len([p for p in self.processes if p.is_running()]) < self.concurrent_processes and 
                    self.current_batch_index < self.total_batches):
                    self._start_next_batch()
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n用户中断，正在停止所有进程...")
            self.running = False
            for proc in self.processes:
                if proc.process:
                    try:
                        proc.process.terminate()
                    except:
                        pass
        
        print("\n所有炮号处理完成！")
    
    def _start_next_batch(self):
        """启动下一个批次的处理"""
        if self.current_batch_index >= self.total_batches:
            return
            
        batch = self.batches[self.current_batch_index]
        start_shot, end_shot = batch
        
        # 创建并启动新进程
        proc = ProcessRunner(
            process_id=self.current_batch_index + 1,
            start_shot=start_shot,
            end_shot=end_shot,
            working_dir=self.working_dir,
            script_path=self.script_path,
            conda_env=self.conda_env
        )
        
        self.processes.append(proc)
        proc.run()
        
        with self.progress_lock:
            self.current_batch_index += 1
    
    def _update_progress_display(self):
        """更新并显示进度信息"""
        last_display_time = 0
        console = Console()
        while self.running:
            current_time = time.time()
            if current_time - last_display_time < REFRESH_INTERVAL:
                time.sleep(0.1)
                continue
            last_display_time = current_time
            for proc in self.processes:
                proc.update_progress(self.mongo_client)
            with self.progress_lock:
                table_data = [proc.get_status_info() for proc in self.processes]
                total_completed_batches = sum(1 for p in self.processes if p.status == "已完成")
                overall_progress = f"{total_completed_batches}/{self.total_batches}"
                os.system('clear')
                print(f"\n\033[96m数据诊断平台批量处理\033[0m - 总进度: \033[92m{overall_progress}\033[0m")
                print(f"开始时间: \033[93m{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\033[0m")

                table = Table(show_header=True, header_style="bold white")
                table.add_column("进程ID", justify="center")
                table.add_column("炮号范围", justify="center")
                table.add_column("当前炮号", justify="center")
                table.add_column("处理状态", justify="center")
                table.add_column("通道进度", justify="center")
                table.add_column("通道百分比", justify="center")
                table.add_column("炮号进度", justify="center")
                table.add_column("已用时间", justify="center")

                for item in table_data:
                    proc_id = f"[cyan]{item['进程ID']}[/cyan]"
                    shot_range = item['炮号范围']
                    current = f"[bright_black]N/A[/bright_black]" if item['当前炮号'] == "N/A" else f"[yellow]{item['当前炮号']}[/yellow]"
                    status_color = "bright_green" if item['状态'] == "运行中" else "bright_yellow" if item['状态'] == "等待中" else "bright_cyan" if item['状态'] == "已完成" else "white"
                    status = f"[{status_color}]{item['状态']}[/{status_color}]"
                    channel = item['通道进度']
                    percent_str = str(item['通道百分比'])
                    try:
                        percent_value = float(percent_str.rstrip('%')) if percent_str.endswith('%') else 0
                    except:
                        percent_value = 0
                    percent_color = "red" if percent_value < 30 else "yellow" if percent_value < 70 else "green"
                    percent = f"[{percent_color}]{percent_str}[/{percent_color}]"
                    shot_progress = item['炮号进度']
                    elapsed = item['已用时间']
                    table.add_row(proc_id, shot_range, current, status, channel, percent, shot_progress, elapsed)

                console.print(table)
                print(f"\n\033[93m按 Ctrl+C 中断处理\033[0m")
            time.sleep(REFRESH_INTERVAL)

def main():
    parser = argparse.ArgumentParser(description='数据诊断平台批量处理控制程序')
    parser.add_argument('--start', type=int, default=DEFAULT_START_SHOT, help=f'起始炮号 (默认: {DEFAULT_START_SHOT})')
    parser.add_argument('--end', type=int, default=DEFAULT_END_SHOT, help=f'结束炮号 (默认: {DEFAULT_END_SHOT})')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help=f'每批次处理的炮号数 (默认: {DEFAULT_BATCH_SIZE})')
    parser.add_argument('--concurrent', type=int, default=DEFAULT_CONCURRENT_PROCESSES, help=f'同时运行的进程数 (默认: {DEFAULT_CONCURRENT_PROCESSES})')
    parser.add_argument('--working-dir', type=str, default=WORKING_DIR, help=f'工作目录 (默认: {WORKING_DIR})')
    parser.add_argument('--script', type=str, default=PROCESS_SCRIPT, help=f'处理脚本路径 (默认: {PROCESS_SCRIPT})')
    parser.add_argument('--conda-env', type=str, default=CONDA_ENV, help=f'Conda环境名称 (默认: {CONDA_ENV})')
    
    args = parser.parse_args()
    
    processor = BatchProcessor(
        start_shot=args.start,
        end_shot=args.end,
        batch_size=args.batch_size,
        concurrent_processes=args.concurrent,
        working_dir=args.working_dir,
        script_path=args.script,
        conda_env=args.conda_env
    )
    
    processor.start()

if __name__ == "__main__":
    main() 