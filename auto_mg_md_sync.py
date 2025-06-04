import re
import time
import subprocess
from pymongo import MongoClient
from MDSplus import Tree # type: ignore
from RunDetectAlgorithm.mdsConn import currentShot

MG_DB_PREFIX = "DataDiagnosticPlatform_"
MG_DB_PATTERN = re.compile(r"DataDiagnosticPlatform_\[(\d+)_(\d+)\]")
MDSPLUS_TREE = 'exl50u'
MDSPLUS_PATH = '192.168.20.11::/media/ennfusion/trees/exl50u'
BATCH_SIZE = 100
CONCURRENT = 1
CHECK_INTERVAL = 60  # 秒


def get_all_mg_shot_ranges(mongo_client):
    db_names = mongo_client.list_database_names()
    shot_ranges = []
    for name in db_names:
        m = MG_DB_PATTERN.match(name)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            shot_ranges.append((start, end))
    return sorted(shot_ranges)

def get_latest_mg_shot(mongo_client):
    shot_ranges = get_all_mg_shot_ranges(mongo_client)
    if not shot_ranges:
        return 0
    return max(end for start, end in shot_ranges)

def get_latest_md_shot():
    try:
        shot = currentShot(MDSPLUS_TREE, MDSPLUS_PATH)
        return int(shot) if shot else 0
    except Exception as e:
        print(f"[警告] 获取md数据库最新炮号失败: {e}")
        return 0

def run_batch(start, end, batch_size=BATCH_SIZE, concurrent=CONCURRENT):
    cmd = [
        "python", "run_batch_processing.py",
        "--start", str(start),
        "--end", str(end),
        "--batch-size", str(batch_size),
        "--concurrent", str(concurrent)
    ]
    print(f"[任务] 运行: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def print_progress(mg_latest, md_latest, mode, batch_start=None, batch_end=None):
    print("\n==================== 进度监控 ====================")
    print(f"mg数据库最新炮号: {mg_latest}")
    print(f"md数据库最新炮号: {md_latest}")
    print(f"当前模式: {mode}")
    if batch_start is not None and batch_end is not None:
        print(f"本次处理区间: {batch_start} - {batch_end}")
    print("================================================\n")

def main_loop():
    mongo_client = MongoClient("mongodb://localhost:27017")
    while True:
        mg_latest = get_latest_mg_shot(mongo_client)
        md_latest = get_latest_md_shot()
        diff = md_latest - mg_latest
        if md_latest <= mg_latest:
            print_progress(mg_latest, md_latest, "已同步")
            time.sleep(CHECK_INTERVAL)
            continue
        if diff >= BATCH_SIZE:
            # 批量补齐
            for batch_start in range(mg_latest + 1, md_latest + 1, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE - 1, md_latest)
                print_progress(mg_latest, md_latest, "批量补齐", batch_start, batch_end)
                run_batch(batch_start, batch_end, batch_size=BATCH_SIZE, concurrent=CONCURRENT)
                mg_latest = batch_end
        else:
            # 单炮聚合补齐，聚合多个炮号直到满100个或处理完所有待补齐炮号
            print_progress(mg_latest, md_latest, "单炮聚合补齐")
            
            while mg_latest < md_latest:
                # 重新获取最新的md炮号，因为可能在处理过程中有新的炮号产生
                current_md_latest = get_latest_md_shot()
                if current_md_latest > md_latest:
                    old_md_latest = md_latest
                    md_latest = current_md_latest
                    print(f"[更新] 检测到新的md炮号，从 {old_md_latest} 更新为: {md_latest}")
                
                # 收集待处理的炮号
                pending_shots = []
                current_shot = mg_latest + 1
                
                # 收集炮号直到达到批次大小或没有更多炮号
                while current_shot <= md_latest and len(pending_shots) < BATCH_SIZE:
                    pending_shots.append(current_shot)
                    current_shot += 1
                
                if pending_shots:
                    batch_start = pending_shots[0]
                    batch_end = pending_shots[-1]
                    batch_count = len(pending_shots)
                    
                    print_progress(mg_latest, md_latest, f"单炮聚合补齐(聚合{batch_count}个炮号)", batch_start, batch_end)
                    run_batch(batch_start, batch_end, batch_size=batch_count, concurrent=CONCURRENT)
                    
                    # 更新mg_latest为已处理的最新炮号
                    mg_latest = batch_end
                    print(f"[完成] 已处理炮号 {batch_start}-{batch_end}，mg数据库最新炮号更新为: {mg_latest}")
                else:
                    # 没有待处理的炮号，退出循环
                    break
        print("[等待] 休眠60秒后继续监控...")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main_loop() 