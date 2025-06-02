import threading
import time
import json
from datetime import datetime, timedelta
from pymongo import MongoClient
import re
import sys
import os
import fcntl

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 状态文件路径
STATUS_FILE_PATH = os.path.join(current_dir, 'monitor_status.json')

# 导入MDS+相关模块
try:
    from RunDetectAlgorithm.mdsConn import currentShot
    print("成功导入 currentShot 函数")
except ImportError as e:
    print(f"导入 currentShot 失败: {e}")
    # 备用导入方式
    try:
        sys.path.append(os.path.join(project_root, 'RunDetectAlgorithm'))
        from mdsConn import currentShot
        print("通过备用方式成功导入 currentShot 函数")
    except ImportError as e2:
        print(f"备用导入方式也失败: {e2}")
        # 定义一个备用函数
        def currentShot(dbname, path):
            print(f"警告: 无法连接MDS+，返回模拟炮号")
            return 5000  # 返回一个模拟的炮号
        print("使用备用 currentShot 函数")

# 全局监控状态（仅用于内存缓存）
monitor_status = {
    'mds_latest_shot': 0,
    'mongo_processing_shot': 0,
    'mongo_latest_shot': 0,
    'last_update': None,
    'next_update': None,
    'is_running': False
}

# 监控锁
monitor_lock = threading.Lock()

# MDS+配置
MDSPLUS_TREE = 'exl50u'
MDSPLUS_PATH = '192.168.20.11::/media/ennfusion/trees/exl50u'

# MongoDB配置
MONGO_CLIENT = MongoClient("mongodb://localhost:27017")
MG_DB_PATTERN = re.compile(r"DataDiagnosticPlatform_\[(\d+)_(\d+)\]")

def write_status_to_file(status_data):
    """将状态写入文件"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(STATUS_FILE_PATH), exist_ok=True)
        
        # 写入临时文件，然后原子性移动
        temp_file = STATUS_FILE_PATH + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, ensure_ascii=False, indent=2)
        
        # 原子性移动
        if os.path.exists(STATUS_FILE_PATH):
            os.remove(STATUS_FILE_PATH)
        os.rename(temp_file, STATUS_FILE_PATH)
        
    except Exception as e:
        print(f"写入状态文件失败: {e}")

def read_status_from_file():
    """从文件读取状态"""
    try:
        if not os.path.exists(STATUS_FILE_PATH):
            return {
                'mds_latest_shot': 0,
                'mongo_processing_shot': 0,
                'mongo_latest_shot': 0,
                'last_update': None,
                'next_update': None,
                'is_running': False
            }
        
        with open(STATUS_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        print(f"读取状态文件失败: {e}")
        return {
            'mds_latest_shot': 0,
            'mongo_processing_shot': 0,
            'mongo_latest_shot': 0,
            'last_update': None,
            'next_update': None,
            'is_running': False
        }

def get_latest_mongo_db_info():
    """获取最新的MongoDB数据库信息"""
    try:
        db_names = MONGO_CLIENT.list_database_names()
        ddp_dbs = [name for name in db_names if name.startswith("DataDiagnosticPlatform")]
        
        if not ddp_dbs:
            return None, 0, 0
            
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
            return None, 0, 0
            
        # 按结束炮号排序，获取最新的数据库
        db_ranges.sort(key=lambda x: x[2], reverse=True)
        latest_db_name, db_start, db_end = db_ranges[0]
        
        # 获取该数据库中实际存在的最大炮号
        db = MONGO_CLIENT[latest_db_name]
        if 'struct_trees' in db.list_collection_names():
            struct_trees = db['struct_trees']
            # 获取所有炮号并转换为整数
            shot_numbers = []
            for doc in struct_trees.find({}, {'shot_number': 1}):
                try:
                    shot_num = int(doc.get('shot_number', 0))
                    if shot_num > 0:
                        shot_numbers.append(shot_num)
                except (ValueError, TypeError):
                    continue
            
            mongo_latest_shot = max(shot_numbers) if shot_numbers else db_start
        else:
            mongo_latest_shot = db_start
            
        return latest_db_name, mongo_latest_shot, db_end
        
    except Exception as e:
        print(f"获取MongoDB信息失败: {e}")
        return None, 0, 0

def get_mds_latest_shot():
    """获取MDS+最新炮号"""
    try:
        shot = currentShot(MDSPLUS_TREE, MDSPLUS_PATH)
        return int(shot) if shot else 0
    except Exception as e:
        print(f"获取MDS+最新炮号失败: {e}")
        return 0

def monitor_loop():
    """监控循环"""
    print("监控循环开始")
    
    while True:
        try:
            current_time = datetime.now()
            
            # 获取MDS+最新炮号
            mds_latest = get_mds_latest_shot()
            
            # 获取MongoDB信息
            latest_db_name, mongo_latest, db_end = get_latest_mongo_db_info()
            
            # 计算正在处理的炮号（MongoDB最新炮号+1，但不超过MDS+最新炮号）
            if mongo_latest < mds_latest:
                processing_shot = mongo_latest + 1
            else:
                processing_shot = mongo_latest
                
            # 创建状态数据
            status_data = {
                'mds_latest_shot': mds_latest,
                'mongo_processing_shot': processing_shot,
                'mongo_latest_shot': mongo_latest,
                'last_update': current_time.isoformat(),
                'next_update': (current_time + timedelta(seconds=10)).isoformat(),
                'is_running': True,
                'latest_db_name': latest_db_name,
                'db_end_range': db_end
            }
            
            # 写入文件
            write_status_to_file(status_data)
            
            # 更新内存状态
            with monitor_lock:
                monitor_status.update(status_data)
                
            print(f"[监控更新] MDS+最新: {mds_latest}, MongoDB最新: {mongo_latest}, 正在处理: {processing_shot}")
            
        except Exception as e:
            print(f"监控循环出错: {e}")
            # 标记服务停止
            error_status = read_status_from_file()
            error_status['is_running'] = False
            write_status_to_file(error_status)
            
        # 等待10秒
        time.sleep(10)

def start_monitor():
    """启动监控线程"""
    global monitor_status
    
    # 检查是否已有监控进程在运行
    current_status = read_status_from_file()
    if current_status.get('is_running', False):
        # 检查最后更新时间，如果超过30秒则认为进程已死
        last_update = current_status.get('last_update')
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update)
                if (datetime.now() - last_time).total_seconds() < 30:
                    print("监控服务已在运行中")
                    return False
            except:
                pass
    
    print("启动新的监控服务")
    
    # 立即更新一次状态
    try:
        current_time = datetime.now()
        mds_latest = get_mds_latest_shot()
        latest_db_name, mongo_latest, db_end = get_latest_mongo_db_info()
        
        if mongo_latest < mds_latest:
            processing_shot = mongo_latest + 1
        else:
            processing_shot = mongo_latest
            
        initial_status = {
            'mds_latest_shot': mds_latest,
            'mongo_processing_shot': processing_shot,
            'mongo_latest_shot': mongo_latest,
            'last_update': current_time.isoformat(),
            'next_update': (current_time + timedelta(seconds=10)).isoformat(),
            'is_running': True,
            'latest_db_name': latest_db_name,
            'db_end_range': db_end
        }
        
        write_status_to_file(initial_status)
        
        with monitor_lock:
            monitor_status.update(initial_status)
            
        print(f"[立即更新] MDS+最新: {mds_latest}, MongoDB最新: {mongo_latest}, 正在处理: {processing_shot}")
        
    except Exception as e:
        print(f"立即更新监控状态出错: {e}")
    
    # 创建并启动监控线程
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    
    print("监控程序已启动")
    return True

def get_monitor_status():
    """获取当前监控状态"""
    # 从文件读取最新状态
    status = read_status_from_file()
    print(f"[状态查询] 从文件读取监控状态: is_running={status.get('is_running', False)}, mds={status.get('mds_latest_shot', 'N/A')}, mongo={status.get('mongo_latest_shot', 'N/A')}")
    return status

def stop_monitor():
    """停止监控（通过设置标志）"""
    status = read_status_from_file()
    status['is_running'] = False
    write_status_to_file(status)
    
    with monitor_lock:
        monitor_status['is_running'] = False

# 自动启动监控（仅在直接运行时）
if __name__ == "__main__":
    # 作为独立服务运行
    print("作为独立监控服务启动")
    start_monitor()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("停止监控服务")
        stop_monitor()
else:
    # 被导入时不自动启动，让API手动控制
    print("监控模块已加载（未自动启动）") 