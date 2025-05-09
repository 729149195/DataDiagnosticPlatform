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
import signal
from typing import Dict
from MDSplus import Tree, mdsExceptions, Connection # type: ignore
from rich.live import Live
from rich import box

class MdsTree:
    """ 构建MDSplus.Tree的一些常用方法 """
    def __init__(self, shot, dbname, path, subtrees):
        self.shot = shot
        self.dbname = dbname
        self.subtrees = subtrees
        self.tree = Tree(self.dbname, self.shot, path=path)

    def formChannelPool(self):
        """ 构建一个通道池 """
        channels = []
        for subTree in self.subtrees:
            sub_nodes = self.tree.getNode(r'\TOP.{}'.format(subTree)).getNodeWild("***")
            channels += [node.name.strip() for node in sub_nodes if str(node.usage) == 'SIGNAL' and len(node.tags) > 0]

        return channels

    def close(self):
        self.tree.close()

    def getCurrentShot(self):
        """ 获取当前炮号 """
        try:
            shot_num = self.tree.getCurrent()
        except mdsExceptions.TreeNOCURRENT:
            shot_num = ''
        return shot_num

    def renameChaName(self, channel_name):
        """ 通道名加r'\'是通道的tags, 不在使用'子树:通道名'方式进行索引"""
        return '\\' + channel_name.upper()

    def isHaveData(self, channel_name):
        """ 返回储存内容长度, 当里面不是数据是公式的时候也有长度(此时如果公式索引的通道没数据同样没有数据) """
        length = self.tree.getNode(self.renameChaName(channel_name)).getLength()
        return length

    def getWrittenTime(self, channel_name):
        """ 获得数据写入时间 """
        return self.tree.getNode(self.renameChaName(channel_name)).getTimeInserted().date

    def setTimeContext(self, begin, end, delta):
        """ 设置起止时间及采样率，参数单位s """
        self.tree.setTimeContext(begin, end, delta)

    def getData(self, channel_name, begin=-2, end=5, delta=None, isSetTime=True):
        """ 
        返回x, y, unit数据
        """
        if isSetTime:
            self.setTimeContext(begin, end, delta)
        channel_name = self.renameChaName(channel_name)
        try:
            node = self.tree.getNode(channel_name)
            data_x = node.dim_of().data() #*1000.0
            data_y = node.data()
            # unit = node.units_of()
            # unit = '' if unit == ' ' else unit
        except mdsExceptions.TreeNODATA:
            # MDSplus.mdsExceptions.TreeNODATA: %TREE-E-NODATA, No data available for this node
            data_x, data_y, unit = [], [], ''
        except mdsExceptions.TreeNNF:
            # MDSplus.mdsExceptions.TreeNNF: %TREE-W-NNF, Node Not Found
            data_x, data_y, unit = [], [], ''
        except Exception as e:
            # print('Check {} find that {}'.format(channel_name, str(e)))
            data_x, data_y, unit = [], [], ''

        return data_x, data_y #, data_y, unit


# DBS配置要和主控、检测脚本保持一致
DBS = {
    'exl50u': {
        'name': 'exl50u',
        'addr': '192.168.20.11',
        'path': '192.168.20.11::/media/ennfusion/trees/exl50u',
        'subtrees': ['FBC', 'PAI', 'PMNT']
    },
    'eng50u': {
        'name': 'eng50u',
        'addr': '192.168.20.41',
        'path': '192.168.20.41::/media/ennfusion/ENNMNT/trees/eng50u',
        'subtrees': ['PMNT']
    }
}

def count_channels_for_shots(start_shot: int, end_shot: int) -> Dict[str, int]:
    """
    统计每个shot的通道总数，返回字典：{shot_number: channel_count}
    """
    result = {}
    for shot in tqdm(range(start_shot, end_shot + 1), desc=f"统计{end_shot}个炮号通道总数"):
        total_channels = 0
        for db in DBS:
            try:
                tree = MdsTree(shot, dbname=db, path=DBS[db]['path'], subtrees=DBS[db]['subtrees'])
                pool = tree.formChannelPool()
                total_channels += len(pool)
                tree.close()
            except Exception as e:
                # 可以加日志
                pass
        result[str(shot)] = total_channels
    return result

def count_total_channels(start_shot: int, end_shot: int) -> int:
    """
    统计所有shot的通道总数
    """
    shot_map = count_channels_for_shots(start_shot, end_shot)
    return sum(shot_map.values()) 


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
    
    def __init__(self, process_id, start_shot, end_shot, working_dir, script_path, conda_env, global_expected_channels_map, db_name=None):
        self.process_id = process_id
        self.start_shot = start_shot
        self.end_shot = end_shot
        self.working_dir = os.path.expanduser(working_dir)
        self.script_path = script_path
        self.conda_env = conda_env
        self.process = None
        if db_name:
            self.db_name = db_name
        else:
            self.db_name = f"DataDiagnosticPlatform_[{start_shot}_{end_shot}]"
        self.start_time = None
        self.status = "等待中"  # 等待中, 运行中, 已完成
        self.current_shot = "N/A"
        self.channels_total = 0
        self.channels_processed = 0
        self.lock = threading.Lock()
        self.expected_channels_map = {}
        # 从全局map切片出自己负责的shot范围
        for shot in range(self.start_shot, self.end_shot + 1):
            self.expected_channels_map[str(shot)] = global_expected_channels_map.get(str(shot), 0)
            self.channels_total += self.expected_channels_map[str(shot)]
    
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
            cmd = f"cd {self.working_dir} && conda run -n {self.conda_env} python {self.script_path} {self.start_shot} {self.end_shot} {self.db_name}"
            self.process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                preexec_fn=os.setsid  # 关键：新建进程组
            )
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
                                if latest_shot is None or (latest_shot.isdigit() and int(shot_num) > int(latest_shot)):
                                    latest_shot = shot_num
                                    
                    if latest_shot:
                        self.current_shot = latest_shot
                
                # 获取结构树中记录的通道总数和处理情况
                struct_trees = db["struct_trees"]
                all_channels = 0
                processed_channels = 0
                
                # 实时统计所有 struct_tree 的通道数之和，进度实时反映 MongoDB
                for shot in range(self.start_shot, self.end_shot + 1):
                    shot_doc = struct_trees.find_one({"shot_number": str(shot)})
                    if shot_doc and "struct_tree" in shot_doc:
                        channels_in_shot = len(shot_doc["struct_tree"])
                        all_channels += channels_in_shot
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
                elif isinstance(self.current_shot, str) and self.current_shot.isdigit() and int(self.current_shot) > self.start_shot:
                    # 基于炮号进度和平均处理时间估计
                    shots_done = int(self.current_shot) - self.start_shot
                    total_shots = self.end_shot - self.start_shot + 1
                    remaining_shots = total_shots - shots_done
                    self.estimated_end_time = (datetime.now() + timedelta(seconds=remaining_shots * SHOT_PROCESS_TIME)).strftime("%H:%M:%S")
                else:
                    total_shots = self.end_shot - self.start_shot + 1
                    self.estimated_end_time = (datetime.now() + timedelta(seconds=total_shots * SHOT_PROCESS_TIME)).strftime("%H:%M:%S")
                    
                # 如果通道进度已满，且状态为运行中，且已用时间超过60秒，则自动标记为已完成，并尝试终止子进程
                elapsed_seconds = 0
                if self.start_time is not None:
                    elapsed_seconds = int((datetime.now() - self.start_time).total_seconds())
                if self.status == "运行中" and self.channels_total > 0 and self.channels_processed >= self.channels_total and elapsed_seconds > 60:
                    self.status = "已完成"
                    if self.process and self.process.poll() is None:
                        try:
                            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                        except Exception as e:
                            print(f"进程 {self.process_id} 终止子进程失败: {e}")
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
                "ID": self.process_id,
                "范围": f"{self.start_shot}-{self.end_shot}",
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
                 working_dir, script_path, conda_env, db_name=None):
        self.start_shot = start_shot
        self.end_shot = end_shot
        self.batch_size = batch_size
        self.concurrent_processes = concurrent_processes
        self.working_dir = working_dir
        self.script_path = script_path
        self.conda_env = conda_env
        self.db_name = db_name
        
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
        # === 全局统计所有shot所有db的通道池长度 ===
        self.global_expected_channels_map = count_channels_for_shots(start_shot, end_shot)
        for shot in range(start_shot, end_shot + 1):
            if self.global_expected_channels_map[str(shot)] == 0:
                print(f"\033[91m警告：shot {shot} 所有数据库通道池都为0\033[0m")
    
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
                        os.killpg(os.getpgid(proc.process.pid), signal.SIGKILL)
                    except Exception as e:
                        print(f"杀进程组失败: {e}")
        
        print("\n所有炮号处理完成！")
    
    def _start_next_batch(self):
        """启动下一个批次的处理"""
        if self.current_batch_index >= self.total_batches:
            return
            
        batch = self.batches[self.current_batch_index]
        start_shot, end_shot = batch
        # 生成本批次db_name
        if self.db_name:
            batch_db_name = self.db_name
        else:
            batch_db_name = f"DataDiagnosticPlatform_[{start_shot}_{end_shot}]"
        # 创建并启动新进程
        proc = ProcessRunner(
            process_id=self.current_batch_index + 1,
            start_shot=start_shot,
            end_shot=end_shot,
            working_dir=self.working_dir,
            script_path=self.script_path,
            conda_env=self.conda_env,
            global_expected_channels_map=self.global_expected_channels_map,
            db_name=batch_db_name
        )
        self.processes.append(proc)
        proc.run()
        with self.progress_lock:
            self.current_batch_index += 1
    
    def _update_progress_display(self):
        """更新并显示进度信息"""
        last_display_time = 0
        console = Console()
        with Live(refresh_per_second=5, console=console, screen=False) as live:
            while self.running:
                current_time = time.time()
                if current_time - last_display_time < REFRESH_INTERVAL:
                    time.sleep(0.1)
                    continue
                last_display_time = current_time
                for proc in self.processes:
                    proc.update_progress(self.mongo_client)
                with self.progress_lock:
                    total_channels_processed = sum(proc.channels_processed for proc in self.processes)
                    total_channels_expected = sum(self.global_expected_channels_map.values())
                    if total_channels_expected == 0:
                        console.print("\033[91m警告：全局通道总数为0，统计异常！请检查MDS数据库连接和通道池统计逻辑。\033[0m")
                        total_channels_expected = 1
                    overall_progress = f"{total_channels_processed}/{total_channels_expected}"
                    # 新建极简现代风格表格
                    table = Table(
                        show_header=True,
                        header_style="bold white on #222244",
                        box=box.MINIMAL_DOUBLE_HEAD,
                        expand=True,
                        border_style="#444466",
                        padding=(0, 1)
                    )
                    table.add_column("进程ID", justify="center", style="bold cyan", no_wrap=True)
                    table.add_column("炮号范围", justify="center", style="white")
                    table.add_column("当前炮号", justify="center", style="bold yellow")
                    table.add_column("处理状态", justify="center", style="bold")
                    table.add_column("通道进度", justify="right", style="white")
                    table.add_column("通道百分比", justify="right", style="bold")
                    table.add_column("炮号进度", justify="right", style="white")
                    table.add_column("已用时间", justify="center", style="dim")
                    for proc in self.processes:
                        db = self.mongo_client[proc.db_name]
                        struct_trees = db["struct_trees"]
                        all_shots = [doc for doc in struct_trees.find({}, {"shot_number": 1}) if doc.get("shot_number", "").isdigit()]
                        if all_shots:
                            current_shot = max(int(doc["shot_number"]) for doc in all_shots if doc.get("shot_number", "").isdigit())
                            proc.current_shot = str(current_shot)
                        else:
                            proc.current_shot = "N/A"
                        processed_channels = proc.channels_processed
                        expected_channels = proc.channels_total if proc.channels_total > 0 else 1
                        percent = f"{processed_channels / expected_channels * 100:.1f}%"
                        status_color = "#00ff99" if proc.status == "运行中" else "#ffcc00" if proc.status == "等待中" else "#3399ff" if proc.status == "已完成" else "white"
                        status = f"[bold {status_color}]{proc.status}[/bold {status_color}]"
                        current = f"[bright_black]N/A[/bright_black]" if proc.current_shot == "N/A" else f"[yellow]{proc.current_shot}[/yellow]"
                        channel = f"{processed_channels}/{expected_channels}"
                        try:
                            percent_value = float(percent.rstrip('%'))
                        except:
                            percent_value = 0
                        percent_color = "#ff5555" if percent_value < 30 else "#ffaa00" if percent_value < 70 else "#00ff99"
                        percent_disp = f"[bold {percent_color}]{percent}[/bold {percent_color}]"
                        total_shots = proc.end_shot - proc.start_shot + 1
                        # 修正 shots_completed 计算，避免 int('N/A')
                        if isinstance(proc.current_shot, str) and proc.current_shot.isdigit():
                            shots_completed = max(0, int(proc.current_shot) - proc.start_shot)
                        else:
                            shots_completed = 0
                        for shot in range(proc.start_shot, proc.end_shot + 1):
                            doc = struct_trees.find_one({"shot_number": str(shot)})
                            expected = proc.expected_channels_map.get(str(shot), 0)
                            if doc and "struct_tree" in doc and len(doc["struct_tree"]) == expected and expected > 0:
                                shots_completed += 1
                        shot_progress = f"{shots_completed}/{total_shots}"
                        elapsed = proc.get_elapsed_time()
                        table.add_row(
                            f"[cyan]{proc.process_id}[/cyan]",
                            f"{proc.start_shot}-{proc.end_shot}",
                            current,
                            status,
                            channel,
                            percent_disp,
                            shot_progress,
                            elapsed
                        )
                    # 用 live.update 刷新表格
                    live.update(table)
                    # 表格上方加简约标题
                    if self.current_batch_index == 1:
                        console.print("[b white on #222244] 数据诊断平台批量处理进度 [/b white on #222244]\n")
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
    parser.add_argument('--db-name', type=str, default=None, help='自定义数据库名（可选），如未指定则自动生成（默认：DataDiagnosticPlatform_[start_shot_end_shot]）')
    
    args = parser.parse_args()
    
    processor = BatchProcessor(
        start_shot=args.start,
        end_shot=args.end,
        batch_size=args.batch_size,
        concurrent_processes=args.concurrent,
        working_dir=args.working_dir,
        script_path=args.script,
        conda_env=args.conda_env,
        db_name=args.db_name
    )
    
    processor.start()

if __name__ == "__main__":
    main() 