import threading
import time
from datetime import datetime, timedelta
from pymongo import MongoClient
import re
import sys
import os
import json

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 导入MDS+相关模块
from RunDetectAlgorithm.mdsConn import currentShot, MdsTree
print("成功导入 currentShot 和 MdsTree 函数")

# 全局监控状态
monitor_status = {
    'mds_latest_shot': 0,
    'mongo_processing_shot': 0,
    'mongo_latest_shot': 0,
    'last_update': None,
    'next_update': None,
    'is_running': False,
    'processing_progress': {
        'current_shot': 0,
        'total_channels': 0,
        'processed_channels': 0,
        'progress_percent': 0.0,
        'is_processing': False
    }
}

# 监控锁
monitor_lock = threading.Lock()

# MDS+配置
MDSPLUS_TREE = 'exl50u'
MDSPLUS_PATH = '192.168.20.11::/media/ennfusion/trees/exl50u'

# MongoDB配置
MONGO_CLIENT = MongoClient("mongodb://localhost:27017")
MG_DB_PATTERN = re.compile(r"DataDiagnosticPlatform_\[(\d+)_(\d+)\]")

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

STATUS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_status.json")

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

def get_processing_progress(processing_shot, latest_db_name):
    """获取正在处理炮号的进度信息"""
    if not processing_shot or not latest_db_name:
        return {
            'current_shot': 0,
            'total_channels': 0,
            'processed_channels': 0,
            'progress_percent': 0.0,
            'is_processing': False
        }
    
    try:
        # 获取该炮号的期望总通道数
        total_channels = get_shot_channel_count(processing_shot)
        
        # 获取MongoDB中已处理的通道数
        db = MONGO_CLIENT[latest_db_name]
        struct_trees_collection = db["struct_trees"]
        
        # 查找该炮号的struct_tree记录
        struct_doc = struct_trees_collection.find_one({"shot_number": str(processing_shot)})
        processed_channels = 0
        
        if struct_doc and "struct_tree" in struct_doc:
            processed_channels = len(struct_doc["struct_tree"])
        
        # 计算进度百分比
        progress_percent = 0.0
        if total_channels > 0:
            progress_percent = (processed_channels / total_channels) * 100.0
        
        # 判断是否正在处理（有总通道数但未完成）
        is_processing = total_channels > 0 and processed_channels < total_channels
        
        return {
            'current_shot': processing_shot,
            'total_channels': total_channels,
            'processed_channels': processed_channels,
            'progress_percent': round(progress_percent, 1),
            'is_processing': is_processing
        }
        
    except Exception as e:
        print(f"获取处理进度失败: {e}")
        return {
            'current_shot': processing_shot,
            'total_channels': 0,
            'processed_channels': 0,
            'progress_percent': 0.0,
            'is_processing': False
        }

def get_latest_mongo_db_info():
    """获取最新的MongoDB数据库信息"""
    try:
        db_names = MONGO_CLIENT.list_database_names()
        ddp_dbs = [name for name in db_names if name.startswith("DataDiagnosticPlatform")]
        
        if not ddp_dbs:
            return None, 0, 0, 0  # 新增返回processing_shot
            
        # 解析数据库名称获取范围
        db_ranges = []
        for name in ddp_dbs:
            # 处理新格式 DataDiagnosticPlatform_[start_end] 和旧格式 DataDiagnosticPlatform_start_end
            if '[' in name and ']' in name:
                # 新格式
                match = re.search(r'DataDiagnosticPlatform_\[(\d+)_(\d+)\]', name)
            else:
                # 旧格式
                match = re.search(r'DataDiagnosticPlatform_(\d+)_(\d+)', name)
            
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                db_ranges.append((name, start, end))
        
        if not db_ranges:
            return None, 0, 0, 0
            
        # 按结束炮号排序，获取最新的数据库
        db_ranges.sort(key=lambda x: x[2], reverse=True)
        latest_db_name, db_start, db_end = db_ranges[0]
        db = MONGO_CLIENT[latest_db_name]
        
        # 获取struct_trees中所有shot_number，取最大，作为processing_shot
        processing_shot = db_start
        if 'struct_trees' in db.list_collection_names():
            struct_trees = db['struct_trees']
            shot_numbers = []
            for doc in struct_trees.find({}, {'shot_number': 1}):
                try:
                    shot_num = int(doc.get('shot_number', 0))
                    if shot_num > 0:
                        shot_numbers.append(shot_num)
                except (ValueError, TypeError):
                    continue
            if shot_numbers:
                processing_shot = max(shot_numbers)
        
        # 获取index集合中key为shot_number的文档，index_data所有key的最大值，作为mongo_latest_shot
        mongo_latest_shot = db_start
        if 'index' in db.list_collection_names():
            index_col = db['index']
            index_doc = index_col.find_one({"key": "shot_number"})
            if index_doc and "index_data" in index_doc:
                shot_keys = list(index_doc["index_data"].keys())
                # 过滤掉非数字key
                shot_keys = [int(k) for k in shot_keys if str(k).isdigit()]
                if shot_keys:
                    mongo_latest_shot = max(shot_keys)
        
        return latest_db_name, mongo_latest_shot, db_end, processing_shot
        
    except Exception as e:
        print(f"获取MongoDB信息失败: {e}")
        return None, 0, 0, 0

def get_mds_latest_shot():
    """获取MDS+最新炮号"""
    try:
        shot = currentShot(MDSPLUS_TREE, MDSPLUS_PATH)
        return int(shot) if shot else 0
    except Exception as e:
        print(f"获取MDS+最新炮号失败: {e}")
        return 0

def write_status_to_file(status):
    try:
        with open(STATUS_FILE_PATH, "w") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"写入监控状态文件失败: {e}")

def read_status_from_file():
    try:
        with open(STATUS_FILE_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取监控状态文件失败: {e}")
        return {}

def monitor_loop():
    """监控循环"""
    global monitor_status
    
    while True:
        try:
            current_time = datetime.now()
            
            # 获取MDS+最新炮号
            mds_latest = get_mds_latest_shot()
            
            # 获取MongoDB信息
            latest_db_name, mongo_latest, db_end, processing_shot = get_latest_mongo_db_info()
            
            # 计算正在处理的炮号（processing_shot+1，但不超过MDS+最新炮号）
            if processing_shot < mds_latest:
                processing_shot_display = processing_shot
            else:
                processing_shot_display = processing_shot
            
            # 获取处理进度信息
            progress_info = get_processing_progress(processing_shot_display, latest_db_name)
                
            # 更新全局状态
            with monitor_lock:
                monitor_status.update({
                    'mds_latest_shot': mds_latest,
                    'mongo_processing_shot': processing_shot_display,
                    'mongo_latest_shot': mongo_latest,
                    'last_update': current_time.isoformat(),
                    'next_update': (current_time + timedelta(seconds=10)).isoformat(),
                    'is_running': True,
                    'latest_db_name': latest_db_name,
                    'db_end_range': db_end,
                    'processing_progress': progress_info
                })
                # 每次更新后写入文件
                write_status_to_file(monitor_status)
            
            print(f"[监控更新] MDS+最新: {mds_latest}, MongoDB已完成: {mongo_latest}, 正在处理: {processing_shot_display}")
            if progress_info['is_processing']:
                print(f"[处理进度] 炮号 {processing_shot_display}: {progress_info['processed_channels']}/{progress_info['total_channels']} ({progress_info['progress_percent']}%)")
            
        except Exception as e:
            print(f"监控循环出错: {e}")
            with monitor_lock:
                monitor_status['is_running'] = False
                write_status_to_file(monitor_status)
            
        # 等待10秒
        time.sleep(10)

def start_monitor():
    """启动监控线程"""
    global monitor_status
    
    with monitor_lock:
        if monitor_status['is_running']:
            print("监控程序已在运行中，跳过启动")
            return False  # 已经在运行
            
    # 创建并启动监控线程
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    
    print("监控程序已启动")
    
    # 等待监控线程初始化并获取第一次数据
    time.sleep(2)
    
    # 立即执行一次监控更新
    try:
        current_time = datetime.now()
        
        # 获取MDS+最新炮号
        mds_latest = get_mds_latest_shot()
        
        # 获取MongoDB信息
        latest_db_name, mongo_latest, db_end, processing_shot = get_latest_mongo_db_info()
        
        # 计算正在处理的炮号
        if processing_shot < mds_latest:
            processing_shot_display = processing_shot + 1
        else:
            processing_shot_display = processing_shot
        
        # 获取处理进度信息
        progress_info = get_processing_progress(processing_shot_display, latest_db_name)
            
        # 更新全局状态
        with monitor_lock:
            monitor_status.update({
                'mds_latest_shot': mds_latest,
                'mongo_processing_shot': processing_shot_display,
                'mongo_latest_shot': mongo_latest,
                'last_update': current_time.isoformat(),
                'next_update': (current_time + timedelta(seconds=10)).isoformat(),
                'is_running': True,
                'latest_db_name': latest_db_name,
                'db_end_range': db_end,
                'processing_progress': progress_info
            })
            write_status_to_file(monitor_status)
        
        print(f"[立即更新] MDS+最新: {mds_latest}, MongoDB已完成: {mongo_latest}, 正在处理: {processing_shot_display}")
        if progress_info['is_processing']:
            print(f"[处理进度] 炮号 {processing_shot_display}: {progress_info['processed_channels']}/{progress_info['total_channels']} ({progress_info['progress_percent']}%)")
        
    except Exception as e:
        print(f"立即更新监控状态出错: {e}")
    
    return True

def get_monitor_status():
    """获取当前监控状态"""
    with monitor_lock:
        current_status = monitor_status.copy()
        print(f"[状态查询] 返回监控状态: is_running={current_status.get('is_running', False)}, mds={current_status.get('mds_latest_shot', 'N/A')}, mongo={current_status.get('mongo_latest_shot', 'N/A')}")
        return current_status

def stop_monitor():
    """停止监控（通过设置标志）"""
    global monitor_status
    with monitor_lock:
        monitor_status['is_running'] = False

# 自动启动监控
# if __name__ != "__main__":
#     # 当模块被导入时自动启动监控
#     start_monitor() 