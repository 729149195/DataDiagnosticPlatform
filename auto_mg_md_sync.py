import re
import time
import subprocess
from pymongo import MongoClient
from MDSplus import Tree, mdsExceptions # type: ignore
from RunDetectAlgorithm.mdsConn import currentShot
from datetime import datetime
import threading

MG_DB_PREFIX = "DataDiagnosticPlatform_"
MG_DB_PATTERN = re.compile(r"DataDiagnosticPlatform_\[(\d+)_(\d+)\]")
MDSPLUS_TREE = 'exl50u'
MDSPLUS_PATH = '192.168.20.11::/media/ennfusion/trees/exl50u'
BATCH_SIZE = 100
CONCURRENT = 1
CHECK_INTERVAL = 60  # 秒
CHANNEL_STABILITY_CHECK_DURATION = 60  # 通道数稳定性检查时长(秒)
CHANNEL_STABILITY_WAIT_DURATION = 30   # 通道数稳定后额外等待时长(秒)

# DBS配置，与检测脚本保持一致
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

class MdsTree:
    """用于获取通道数的简化MdsTree类"""
    def __init__(self, shot, dbname, path, subtrees):
        self.shot = shot
        self.dbname = dbname
        self.subtrees = subtrees
        self.tree = Tree(self.dbname, self.shot, path=path)

    def formChannelPool(self):
        """构建通道池"""
        channels = []
        for subTree in self.subtrees:
            try:
                sub_nodes = self.tree.getNode(r'\TOP.{}'.format(subTree)).getNodeWild("***")
                channels += [node.name.strip() for node in sub_nodes if str(node.usage) == 'SIGNAL' and len(node.tags) > 0]
            except Exception as e:
                # 忽略获取失败的子树
                pass
        return channels

    def close(self):
        self.tree.close()

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

def get_shot_channel_count(shot_num):
    """获取指定炮号的总通道数"""
    total_channels = 0
    for db_name, db_config in DBS.items():
        try:
            tree = MdsTree(shot_num, dbname=db_name, path=db_config['path'], subtrees=db_config['subtrees'])
            channels = tree.formChannelPool()
            total_channels += len(channels)
            tree.close()
        except Exception as e:
            print(f"[警告] 获取炮号 {shot_num} 在数据库 {db_name} 的通道数失败: {e}")
    return total_channels

def check_latest_shot_channel_stability(latest_shot):
    """检查最新炮号的通道数稳定性"""
    print(f"[通道稳定性检查] 开始检查炮号 {latest_shot} 的通道数稳定性...")
    
    channel_counts = []
    start_time = time.time()
    
    # 持续检查60秒
    while time.time() - start_time < CHANNEL_STABILITY_CHECK_DURATION:
        current_count = get_shot_channel_count(latest_shot)
        channel_counts.append((time.time(), current_count))
        print(f"[通道稳定性检查] 炮号 {latest_shot} 当前通道数: {current_count}")
        time.sleep(10)  # 每10秒检查一次
    
    # 检查通道数是否稳定（最后1分钟内没有变化）
    if len(channel_counts) < 2:
        print(f"[通道稳定性检查] 炮号 {latest_shot} 检查数据不足，视为不稳定")
        return False
    
    # 检查最后1分钟内的所有记录是否通道数一致
    last_count = channel_counts[-1][1]
    is_stable = all(count == last_count for _, count in channel_counts[-6:])  # 最后6次检查(60秒)
    
    if is_stable:
        print(f"[通道稳定性检查] 炮号 {latest_shot} 通道数稳定，等待额外 {CHANNEL_STABILITY_WAIT_DURATION} 秒...")
        time.sleep(CHANNEL_STABILITY_WAIT_DURATION)
        # 再次检查确认通道数没有变化
        final_count = get_shot_channel_count(latest_shot)
        if final_count == last_count:
            print(f"[通道稳定性检查] 炮号 {latest_shot} 通道数最终稳定在 {final_count}")
            return True
        else:
            print(f"[通道稳定性检查] 炮号 {latest_shot} 通道数在等待期间发生变化: {last_count} -> {final_count}")
            return False
    else:
        print(f"[通道稳定性检查] 炮号 {latest_shot} 通道数不稳定")
        return False

def merge_databases(mongo_client):
    """合并不满100炮号的数据库"""
    print("[数据库合并] 开始检查和合并不满100炮号的数据库...")
    
    shot_ranges = get_all_mg_shot_ranges(mongo_client)
    if not shot_ranges:
        print("[数据库合并] 没有找到任何数据库，跳过合并")
        return
    
    # 找出需要合并的数据库（炮号范围小于100的）
    databases_to_merge = []
    for start, end in shot_ranges:
        if end - start + 1 < BATCH_SIZE:
            databases_to_merge.append((start, end))
    
    if len(databases_to_merge) < 2:
        print(f"[数据库合并] 找到 {len(databases_to_merge)} 个不满100炮号的数据库，无需合并")
        return
    
    print(f"[数据库合并] 找到 {len(databases_to_merge)} 个不满100炮号的数据库需要合并")
    
    # 按起始炮号排序
    databases_to_merge.sort()
    
    i = 0
    while i < len(databases_to_merge):
        merge_group = [databases_to_merge[i]]
        total_shots = databases_to_merge[i][1] - databases_to_merge[i][0] + 1
        
        # 尝试将连续的数据库合并到100炮号
        j = i + 1
        while j < len(databases_to_merge) and total_shots < BATCH_SIZE:
            next_start, next_end = databases_to_merge[j]
            next_shots = next_end - next_start + 1
            
            # 检查是否连续且合并后不超过100炮号
            if (next_start == merge_group[-1][1] + 1 and 
                total_shots + next_shots <= BATCH_SIZE):
                merge_group.append((next_start, next_end))
                total_shots += next_shots
                j += 1
            else:
                break
        
        # 如果找到了需要合并的组（超过1个数据库）
        if len(merge_group) > 1:
            merge_start = merge_group[0][0]
            merge_end = merge_group[-1][1]
            
            print(f"[数据库合并] 合并数据库组: {[f'[{s}_{e}]' for s, e in merge_group]} -> [{merge_start}_{merge_end}]")
            
            try:
                # 执行合并
                _execute_database_merge(mongo_client, merge_group, merge_start, merge_end)
                print(f"[数据库合并] 成功合并为 DataDiagnosticPlatform_[{merge_start}_{merge_end}]")
                
                # 从待合并列表中移除已合并的数据库
                for k in range(len(merge_group)):
                    databases_to_merge.pop(i)
                    
            except Exception as e:
                print(f"[数据库合并] 合并失败: {e}")
                i += 1
        else:
            i += 1

def _execute_database_merge(mongo_client, merge_group, target_start, target_end):
    """执行具体的数据库合并操作"""
    target_db_name = f"DataDiagnosticPlatform_[{target_start}_{target_end}]"
    target_db = mongo_client[target_db_name]
    
    # 合并所有源数据库的数据
    all_struct_trees = []
    all_errors_data = []
    all_data_statistics = []
    all_index_data = {}
    
    for start, end in merge_group:
        source_db_name = f"DataDiagnosticPlatform_[{start}_{end}]"
        source_db = mongo_client[source_db_name]
        
        print(f"[数据库合并] 正在合并源数据库: {source_db_name}")
        
        # 合并struct_trees集合
        for doc in source_db["struct_trees"].find():
            shot_number = doc.get("shot_number")
            struct_tree = doc.get("struct_tree", [])
            
            # 检查目标数据库中是否已存在该炮号
            existing_doc = target_db["struct_trees"].find_one({"shot_number": shot_number})
            if existing_doc:
                # 合并struct_tree数据
                target_db["struct_trees"].update_one(
                    {"shot_number": shot_number},
                    {"$addToSet": {"struct_tree": {"$each": struct_tree}}}
                )
            else:
                target_db["struct_trees"].insert_one(doc)
        
        # 合并errors_data集合
        for doc in source_db["errors_data"].find():
            # 使用upsert确保不重复插入
            target_db["errors_data"].update_one(
                {
                    "shot_number": doc.get("shot_number"),
                    "channel_number": doc.get("channel_number"),
                    "error_type": doc.get("error_type")
                },
                {"$set": doc},
                upsert=True
            )
        
        # 合并data_statistics集合
        for doc in source_db["data_statistics"].find():
            target_db["data_statistics"].update_one(
                {"shot_number": doc.get("shot_number")},
                {"$set": doc},
                upsert=True
            )
        
        # 合并index集合
        for doc in source_db["index"].find():
            key = doc.get("key")
            index_data = doc.get("index_data", {})
            
            existing_index = target_db["index"].find_one({"key": key})
            if existing_index:
                # 合并索引数据
                existing_index_data = existing_index.get("index_data", {})
                existing_index_data.update(index_data)
                target_db["index"].update_one(
                    {"key": key},
                    {"$set": {"index_data": existing_index_data}}
                )
            else:
                target_db["index"].insert_one(doc)
    
    # 删除源数据库
    for start, end in merge_group:
        source_db_name = f"DataDiagnosticPlatform_[{start}_{end}]"
        print(f"[数据库合并] 删除源数据库: {source_db_name}")
        mongo_client.drop_database(source_db_name)

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
        # 每轮开始前先合并数据库
        print("[主循环] 检查轮次开始，先进行数据库合并...")
        merge_databases(mongo_client)
        
        mg_latest = get_latest_mg_shot(mongo_client)
        md_latest = get_latest_md_shot()
        
        # 如果是最新炮号，需要检查通道数稳定性
        if md_latest > mg_latest:
            print(f"[主循环] 检测到新炮号 {md_latest}，检查通道数稳定性...")
            if not check_latest_shot_channel_stability(md_latest):
                print(f"[主循环] 炮号 {md_latest} 通道数不稳定，跳过本轮处理")
                time.sleep(CHECK_INTERVAL)
                continue
        
        diff = md_latest - mg_latest
        if md_latest <= mg_latest:
            print_progress(mg_latest, md_latest, "已同步")
            # 即使已同步也要进行合并检查
            merge_databases(mongo_client)
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
                    
                    # 对新的最新炮号也要检查稳定性
                    if not check_latest_shot_channel_stability(md_latest):
                        print(f"[主循环] 新炮号 {md_latest} 通道数不稳定，暂停处理等待下轮")
                        break
                
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
        
        # 单轮检测结束后再次合并数据库
        print("[主循环] 单轮检测结束，进行数据库合并...")
        merge_databases(mongo_client)
        
        print("[等待] 休眠60秒后继续监控...")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main_loop() 