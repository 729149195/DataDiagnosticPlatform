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
CONCURRENT = 5
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
            # 单炮补齐，db_name动态扩展
            print_progress(mg_latest, md_latest, "单炮补齐")
            current_start = mg_latest + 1
            current_end = mg_latest + 1
            for shot in range(current_start, md_latest + 1):
                run_batch(shot, shot, batch_size=1, concurrent=1)
                current_end = shot
                # 可选：这里可以实现db_name动态扩展逻辑（如需手动管理db_name）
        print("[等待] 休眠60秒后继续监控...")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main_loop() 