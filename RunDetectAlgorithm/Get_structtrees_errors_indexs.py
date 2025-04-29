"""
该模块用于批量读取MDSplus数据库中的实验数据，自动调用各类异常检测算法，对指定通道和炮号的数据进行异常诊断，并将检测结果存储到MongoDB中，便于后续分析和可视化。
(mdsplus) diagdiag-2288H-V7:~/DataDiagnostic/DatapiagnosticPlatforn/RunDetectAlgorithms$ 
python /home/diag/DataDiagnostic/DataDiagnosticPlatform/RunDetectAlgorithm/get_structtrees_errors_indexs.py 1 100
获取处理1-100炮号（包含1和100）的数据，数据会在名为 DataDiagnosticPlatform_[1_100] 的数据库中
"""
import re
import time
from datetime import datetime
import importlib
import json
import multiprocessing as mp
import importlib.util
import random
import logging
import traceback
import sys

import MDSplus # type: ignore
import numpy as np
from pymongo import MongoClient, ASCENDING, UpdateMany
from tqdm import tqdm

from mdsConn import MdsTree

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('detect_algorithm.log')
    ]
)
logger = logging.getLogger('DataDiagnostic')

class JsonEncoder(json.JSONEncoder):
    """Convert numpy classes to JSON serializable objects."""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(JsonEncoder, self).default(obj)
        
def import_module_from_path(module_name, file_path):
    """动态导入指定路径的模块"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def remove_digits(s: str) -> str:
    """去掉字符串中的所有数字"""
    return re.match(r'^[^\d]*', s)[0]


DBS = {
        'exl50':{
            'name':'exl50',
            'addr':'192.168.20.11',
            'path':'192.168.20.11::/media/ennfusion/trees/exl50',
            'subtrees':['FBC','PAI','PMNT']
        },
        'exl50u':{
            'name':'exl50u',
            'addr':'192.168.20.11',
            'path':'192.168.20.11::/media/ennfusion/trees/exl50u',
            'subtrees':['FBC','PAI','PMNT']
        },
        'eng50u':{
            'name':'eng50u',
            'addr':'192.168.20.41',
            'path':'192.168.20.41::/media/ennfusion/ENNMNT/trees/eng50u',
            'subtrees':['PMNT']
        },
        'ecrhlab':{
            'name':'ecrhlab',
            'addr':'192.168.20.32',
            'path':'192.168.20.32::/media/ecrhdb/trees/ecrhlab',
            'subtrees':['PAI']
        },
        'ts':{
            'name':'ts',
            'addr':'192.168.20.28',
            'path':'192.168.20.28::/media/ennts/trees/ts',
            'subtrees':['AI']
        },
    }

# 预加载算法模块
def preload_algorithms(algorithm_channel_map):
    """预加载所有算法模块，避免重复导入"""
    algorithm_modules = {}
    for detect_type, error_channel_map in algorithm_channel_map.items():
        algorithm_modules[detect_type] = {}
        for error in error_channel_map.keys():
            path = f'RunDetectAlgorithm/algorithm/{detect_type}/{error}.py'
            try:
                algorithm_modules[detect_type][error] = import_module_from_path(error, path)
            except Exception as e:
                logger.error(f"预加载算法模块 {error} 失败: {e}")
    return algorithm_modules

# 处理单个通道的函数
def process_channel(channel_args):
    shot_num, DB, channel_name, tree_path, subtrees, algorithm_channel_map, lock_id = channel_args
    
    # 添加随机延迟，避免同时连接
    delay = random.uniform(0.5, 1.5)
    time.sleep(delay)
    
    channel_type = remove_digits(channel_name).upper()
    if channel_type == 'MIR':
        channel_type = 'Mirnov'

    # 创建基本通道信息结构，包括状态信息
    temp = {
        "shot_number": str(shot_num),
        "channel_type": channel_type,
        "channel_name": channel_name,
        'db_name': DB,
        'error_name': [],
        'status': 'success',  # 默认状态为成功
        'status_message': ''  # 状态说明信息
    }
    
    # 创建独立的MdsTree连接，添加重试机制
    tree = None
    max_retries = 10
    for retry in range(max_retries):
        try:
            tree = MdsTree(shot_num, dbname=DB, path=tree_path, subtrees=subtrees)
            break
        except Exception as e:
            if retry < max_retries - 1:
                # 指数退避策略
                wait_time = (2 ** retry) * 0.5 + random.uniform(0, 0.5)
                time.sleep(wait_time)
                continue
            logger.warning(f"创建通道 {channel_name} 的MdsTree连接失败: {e}")
            temp['status'] = 'failed'
            temp['status_message'] = f'MdsTree连接失败: {str(e)}'
            return temp, None
    
    # 为批量插入准备的数据
    error_data_list = []
    
    try:
        detect_type = channel_type
        if detect_type in ['MP', 'FLUX', 'IPF']:
            detect_type = 'MP'
            
        # 检查是否有匹配的算法
        has_matching_algorithm = detect_type in algorithm_channel_map
        if not has_matching_algorithm:
            temp['status'] = 'no_algorithm'
            temp['status_message'] = f'没有匹配的算法类型: {detect_type}'
            if tree is not None:
                tree.close()
            return temp, None
        
        # 读取通道数据，添加重试机制
        X_value, Y_value = None, None
        for retry in range(max_retries):
            try:
                if detect_type == 'MP':
                    X_value, Y_value = tree.getData(channel_name, -7, 5)
                else:
                    X_value, Y_value = tree.getData(channel_name)
                break
            except Exception as e:
                if retry < max_retries - 1:
                    wait_time = (2 ** retry) * 0.5 + random.uniform(0, 0.5)
                    time.sleep(wait_time)
                    continue
                # 最后一次重试失败
                temp['status'] = 'data_read_failed'
                temp['status_message'] = f'数据读取失败: {str(e)}'
                if tree is not None:
                    tree.close()
                return temp, None
            
        if X_value is None or Y_value is None or len(Y_value) == 0:
            temp['status'] = 'empty_data'
            temp['status_message'] = '数据为空或无效'
            if tree is not None:
                tree.close()
            return temp, None
            
        X_unit = 's'
        if channel_type == 'TS':
            X_unit = 'ns'
        
        # 预先获取可能需要的辅助通道数据
        aux_channel_data = {}
        if 'error_axuv_Detector_channel_damage' in algorithm_channel_map.get(detect_type, {}) or 'error_sxr_spectra_saturation' in algorithm_channel_map.get(detect_type, {}):
            for retry in range(max_retries):
                try:
                    if 'error_axuv_Detector_channel_damage' in algorithm_channel_map.get(detect_type, {}):
                        _, aux_data = tree.getData('ECRH0_UA')
                        aux_channel_data['ECRH0_UA'] = aux_data
                    
                    if 'error_sxr_spectra_saturation' in algorithm_channel_map.get(detect_type, {}):
                        _, aux_data = tree.getData('IP')
                        aux_channel_data['IP'] = aux_data
                    break
                except Exception as e:
                    if retry < max_retries - 1:
                        wait_time = (2 ** retry) * 0.5 + random.uniform(0, 0.5)
                        time.sleep(wait_time)
                        continue
        
        error_channel_map = algorithm_channel_map[detect_type]
        error_type_list = error_channel_map.keys()
        algorithm_applied = False
        
        # 动态导入算法模块
        for error in error_type_list:
            if channel_name in error_channel_map[error]:
                algorithm_applied = True
                path = f'RunDetectAlgorithm/algorithm/{detect_type}/{error}.py'
                try:
                    moduleX = import_module_from_path(error, path)
                except Exception as e:
                    logger.warning(f"导入模块 {error} 失败: {e}")
                    continue
                
                # 运行异常检测算法
                try:
                    if error == 'error_axuv_Detector_channel_damage':
                        if 'ECRH0_UA' not in aux_channel_data:
                            continue
                        error_indexes = moduleX.func(Y_value, aux_channel_data['ECRH0_UA'])
                    elif error == 'error_sxr_spectra_saturation':
                        if 'IP' not in aux_channel_data:
                            continue
                        error_indexes = moduleX.func(Y_value, aux_channel_data['IP'])
                    elif channel_type == 'TS':
                        error_indexes = moduleX.func(Y_value, X_value)
                    else:
                        error_indexes = moduleX.func(Y_value)
                except Exception as e:
                    # 算法执行失败，跳过
                    logger.warning(f"执行算法 {error} 失败: {e}")
                    continue
                
                # 处理检测结果
                try:
                    if channel_type != 'TS':
                        X_value_error = [[X_value[indice[0]], X_value[indice[1]]] for indice in error_indexes if indice[0] < len(X_value) and indice[1] < len(X_value)]
                    else:
                        X_value_error = error_indexes
                except Exception as e:
                    logger.warning(f"处理检测结果失败: {e}")
                    continue
                
                # 检测到异常，准备数据
                if len(error_indexes) != 0:
                    error_data = [[], [{
                        'person': "mechine",
                        'diagnostic_name': channel_type,
                        'channel_number': channel_name,
                        'error_type': error,
                        "shot_number": str(shot_num),
                        'X_error': list(X_value_error),
                        'diagonistic_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "error_description": '',
                    }]]
                    
                    # 添加到批量插入列表
                    error_data_list.append({
                        "query": {
                            "shot_number": str(shot_num),
                            "channel_number": channel_name,
                            "error_type": error
                        },
                        "data": error_data
                    })
                    
                    # 添加到结构树
                    temp['error_name'].append(error)
        
        # 如果没有应用任何算法，标记为无匹配算法
        if not algorithm_applied:
            temp['status'] = 'no_matched_algorithm'
            temp['status_message'] = f'通道类型 {detect_type} 有算法，但该通道 {channel_name} 无匹配的具体算法'
    except Exception as e:
        logger.warning(f"处理通道 {channel_name} 时发生异常: {traceback.format_exc()}")
        temp['status'] = 'processing_error'
        temp['status_message'] = f'处理异常: {str(e)}'
    
    # 确保关闭连接
    if tree is not None:
        try:
            tree.close()
        except:
            pass
            
    return temp, error_data_list

def RUN(shot_list, channel_list, db_name):
    # 连接MongoDB
    client = MongoClient("mongodb://localhost:27017")
    db = client[db_name]
    errors_collection = db["errors_data"]
    struct_trees_collection = db["struct_trees"]
    data_stats_collection = db["data_statistics"]  # 新增统计集合
    
    # 清空数据库中已有的数据
    print("正在清空数据库中已有的数据...")
    try:
        errors_collection.delete_many({})
        struct_trees_collection.delete_many({})
        data_stats_collection.delete_many({})
        db["index"].delete_many({})
        print("已成功清空数据库中的所有集合")
    except Exception as e:
        logger.error(f"清空数据库时发生异常: {e}")
        print(f"清空数据库失败: {e}")
    
    # 创建复合索引
    errors_collection.create_index([
        ("shot_number", ASCENDING),
        ("channel_number", ASCENDING),
        ("error_type", ASCENDING)
    ])

    with open('RunDetectAlgorithm/algorithmChannelMap.json', encoding='utf-8') as f:
        algorithm_channel_map = json.load(f)
    detect_channel_type_list = algorithm_channel_map.keys()
    DB_list = ["exl50u", "eng50u"]

    all_struct_tree = []  # 所有炮号的结构树
    shot_range = list(range(shot_list[0], shot_list[1] + 1))
    read_time = 0
    
    # 统计数据
    data_statistics = {
        "shot_range": f"{shot_range[0]}_{shot_range[-1]}",
        "total_channels_expected": 0,
        "total_channels_processed": 0,
        "status_counts": {
            "success": 0,
            "failed": 0,
            "data_read_failed": 0,
            "empty_data": 0,
            "no_algorithm": 0,
            "no_matched_algorithm": 0,
            "processing_error": 0
        },
        "by_shot": {},
        "by_db": {},
        "problem_channels": {
            "failed": [],
            "data_read_failed": [],
            "empty_data": [],
            "no_algorithm": [],
            "no_matched_algorithm": [],
            "processing_error": []
        },
        "connection_failures": []
    }
    
    # 计算总通道数用于进度显示
    total_channels = 0
    print("正在统计处理总量...")
    for DB in DB_list:
        if DB not in data_statistics["by_db"]:
            data_statistics["by_db"][DB] = {
                "total": 0,
                "processed": 0,
                "status_counts": {
                    "success": 0,
                    "failed": 0,
                    "data_read_failed": 0,
                    "empty_data": 0,
                    "no_algorithm": 0,
                    "no_matched_algorithm": 0,
                    "processing_error": 0
                }
            }
            
        for shot_num in tqdm(shot_range, desc=f"统计 {DB} 数据库的炮号"):
            if str(shot_num) not in data_statistics["by_shot"]:
                data_statistics["by_shot"][str(shot_num)] = {
                    "total": 0,
                    "processed": 0,
                    "status_counts": {
                        "success": 0,
                        "failed": 0,
                        "data_read_failed": 0,
                        "empty_data": 0,
                        # no_algorithm 代表该通道类型在算法映射表（algorithm_channel_map）中没有对应的异常检测算法。（比如某种新通道类型还没开发算法）
                        "no_algorithm": 0,  
                        # no_matched_algorithm 代表通道类型在算法映射表中有算法，但该具体通道没有被分配到任何一个具体算法。（比如MP类型有算法，但某个通道名没有被分配到任何一个MP算法）
                        "no_matched_algorithm": 0,
                        "processing_error": 0
                    }
                }
                
            try:
                tree = MdsTree(shot_num, dbname=DB, path=DBS[DB]['path'], subtrees=DBS[DB]['subtrees'])
                pool = tree.formChannelPool()
                channels_count = 0
                
                if len(channel_list) == 0:
                    channels_count = len(pool)
                else:
                    channels_count = len([c for c in pool if c in channel_list])
                    
                total_channels += channels_count
                data_statistics["total_channels_expected"] += channels_count
                data_statistics["by_db"][DB]["total"] += channels_count
                data_statistics["by_shot"][str(shot_num)]["total"] += channels_count
                
                tree.close()
            except Exception as e:
                logger.warning(f"统计炮号{str(shot_num)}时发生异常: {e}")
    
    print(f"总计需要处理 {len(shot_range)} 个炮号, {total_channels} 个通道")
    processed_channels = 0
    
    # 获取可用CPU核心数，合理限制进程数
    num_processes = min(64, max(1, mp.cpu_count() - 1))
    print(f"将使用 {num_processes} 个进程并行处理数据")
    
    # 处理每个炮号
    for shot_num in shot_range:
        shot_start = time.time()
        print(f"\n---- 开始处理炮号: {shot_num} ----")
        
        # 用于存储当前炮号的结构树 (合并所有数据库的结果)
        combined_shot_struct_tree = []
        combined_error_data = []
        
        # 处理每个数据库
        for DB in DB_list:
            print(f"\n  处理数据库: {DB}")
            start = time.time()
            channel_pool = []
            max_db_retries = 10
            
            # 获取通道列表，增加重试机制
            for db_retry in range(max_db_retries):
                try:
                    # 随机延迟以避免同时连接
                    delay = random.uniform(1.0, 3.0)
                    time.sleep(delay)
                    
                    tree = MdsTree(shot_num, dbname=DB, path=DBS[DB]['path'], subtrees=DBS[DB]['subtrees'])
                    channel_pool = tree.formChannelPool()
                    tree.close()  # 关闭主连接，每个进程将创建自己的连接
                    break  # 成功获取通道列表，跳出重试循环
                except Exception as e:
                    error_msg = str(e)
                    if 'Broken pipe' in error_msg or 'TREE-E-FOPENR' in error_msg:
                        logger.warning(f"获取炮号 {shot_num} 的 {DB} 数据库通道列表时发生连接错误: {e}")
                    else:
                        logger.warning(f"获取炮号 {shot_num} 的 {DB} 数据库通道列表时发生异常: {e}")
                    
                    if db_retry < max_db_retries - 1:
                        retry_delay = (2 ** db_retry) * 1.0 + random.uniform(0.5, 2.0)
                        print(f"  连接失败，将在 {round(retry_delay, 2)}s 后重试 ({db_retry+1}/{max_db_retries-1})...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"获取炮号 {shot_num} 的 {DB} 数据库通道列表已达最大重试次数，跳过此数据库")
                        # 记录连接失败的数据库统计
                        if "connection_failures" not in data_statistics:
                            data_statistics["connection_failures"] = []
                        data_statistics["connection_failures"].append({
                            "shot_number": str(shot_num),
                            "db_name": DB,
                            "error": str(e)
                        })
            
            # 如果通道列表为空，跳过当前数据库
            if not channel_pool:
                print(f"  无法获取炮号 {shot_num} 在 {DB} 数据库的通道列表，跳过处理")
                continue
                
            if len(channel_list) == 0:
                channels_to_process = channel_pool
            else:
                channels_to_process = [c for c in channel_pool if c in channel_list]
            
            print(f"  炮号 {shot_num} 在 {DB} 数据库共有 {len(channels_to_process)} 个通道需要处理")
            
            # 批量处理，分组处理通道以限制并发连接数
            batch_size = 100  # 每批处理的通道数
            db_results = []  # 当前数据库的处理结果
            
            for batch_idx in range(0, len(channels_to_process), batch_size):
                batch_channels = channels_to_process[batch_idx:batch_idx + batch_size]
                
                # 准备多进程处理的参数
                channel_args = [(shot_num, DB, channel_name, DBS[DB]['path'], DBS[DB]['subtrees'], algorithm_channel_map, idx) 
                                for idx, channel_name in enumerate(batch_channels)]
                
                # 使用进程池并行处理通道
                with mp.Pool(processes=num_processes) as pool:
                    results = list(tqdm(
                        pool.imap(process_channel, channel_args),
                        total=len(channel_args),
                        desc=f"  处理炮号 {shot_num} 在 {DB} 数据库的通道 ({batch_idx+1}-{min(batch_idx+batch_size, len(channels_to_process))})"
                    ))
                    db_results.extend(results)
            
            # 收集当前数据库的结果和统计数据
            for result in db_results:
                processed_channels += 1
                data_statistics["total_channels_processed"] += 1
                data_statistics["by_db"][DB]["processed"] += 1
                data_statistics["by_shot"][str(shot_num)]["processed"] += 1
                
                channel_data, error_list = result
                
                if channel_data:
                    # 添加到structtree（无论成功与否，只要有通道数据）
                    combined_shot_struct_tree.append(channel_data)
                    all_struct_tree.append(channel_data)
                    
                    # 更新统计数据
                    status = channel_data.get('status', 'unknown')
                    data_statistics["status_counts"][status] += 1
                    data_statistics["by_db"][DB]["status_counts"][status] += 1
                    data_statistics["by_shot"][str(shot_num)]["status_counts"][status] += 1
                    
                    # 记录问题通道的详细信息
                    if status != 'success' and status in data_statistics["problem_channels"]:
                        channel_info = {
                            "shot_number": str(shot_num),
                            "db_name": DB,
                            "channel_name": channel_data.get("channel_name", ""),
                            "channel_type": channel_data.get("channel_type", ""),
                            "message": channel_data.get("status_message", "")
                        }
                        data_statistics["problem_channels"][status].append(channel_info)
                
                if error_list:
                    combined_error_data.extend(error_list)
            
            end = time.time()
            print(f'  已完成 {DB} 数据库处理，运行时间: {round(end-start, 2)}s')
        
        # 在处理完所有数据库后，批量更新MongoDB
        if combined_error_data:
            operations = []
            for item in combined_error_data:
                operations.append(
                    UpdateMany(
                        item["query"],
                        {"$set": {"data": item["data"]}},
                        upsert=True
                    )
                )
            
            if operations:
                # 批量执行操作，每10个一批
                for batch_idx in range(0, len(operations), 10):
                    batch = operations[batch_idx:batch_idx+10]
                    if batch:
                        try:
                            errors_collection.bulk_write(batch)
                        except Exception as e:
                            logger.error(f"批量写入MongoDB失败: {e}")
        
        # 将当前炮号的结构树存入MongoDB (合并了所有数据库的结果)
        try:
            struct_trees_collection.update_one(
                {"shot_number": str(shot_num)},
                {"$set": {"struct_tree": combined_shot_struct_tree}},
                upsert=True
            )
            print(f"已将炮号 {shot_num} 的结构树保存到MongoDB (包含所有数据库的结果)")
            
            # 为当前炮号创建索引数据并存储到MongoDB
            print(f"  为炮号 {shot_num} 创建索引数据...")
            create_shot_index(db, str(shot_num), combined_shot_struct_tree)
            
        except Exception as e:
            logger.error(f"保存炮号 {shot_num} 的结构树到MongoDB时发生异常: {e}")
        
        shot_end = time.time()
        print(f'已完成炮号 {shot_num} 的全部处理，总运行时间: {round(shot_end-shot_start, 2)}s')

        # === 新增：每炮统计信息单独存储 ===
        # 构建当前炮号的统计信息
        shot_statistics = {
            "shot_number": str(shot_num),
            "total_channels_expected": data_statistics["by_shot"][str(shot_num)]["total"],
            "total_channels_processed": data_statistics["by_shot"][str(shot_num)]["processed"],
            "status_counts": data_statistics["by_shot"][str(shot_num)]["status_counts"],
            "problem_channels": {
                status: [
                    c for c in data_statistics["problem_channels"][status]
                    if c["shot_number"] == str(shot_num)
                ]
                for status in data_statistics["problem_channels"]
            },
            # 可以根据需要添加其它字段
        }
        # 存储到MongoDB
        data_stats_collection.update_one(
            {"shot_number": str(shot_num)},
            {"$set": shot_statistics},
            upsert=True
        )
    
    # 打印统计信息
    print("\n---- 数据处理统计 ----")
    print(f"预期处理通道总数: {data_statistics['total_channels_expected']}")
    print(f"实际处理通道总数: {data_statistics['total_channels_processed']}")
    print("\n状态统计:")
    for status, count in data_statistics["status_counts"].items():
        print(f"  {status}: {count}")
        if status != 'success' and count > 0:
            problem_channels = data_statistics["problem_channels"].get(status, [])
            if len(problem_channels) > 0:
                print(f"    问题通道示例(显示前5个):")
                for i, channel in enumerate(problem_channels[:5]):
                    print(f"      {i+1}. 炮号:{channel['shot_number']} 数据库:{channel['db_name']} 通道:{channel['channel_name']} ({channel['channel_type']}) - {channel['message']}")
    
    # 显示连接失败的数据库
    connection_failures = data_statistics.get("connection_failures", [])
    if connection_failures:
        print(f"\n连接失败的数据库: {len(connection_failures)}个")
        for i, failure in enumerate(connection_failures[:5]):  # 只显示前5个
            print(f"  {i+1}. 炮号:{failure['shot_number']} 数据库:{failure['db_name']} - 错误:{failure['error']}")
        if len(connection_failures) > 5:
            print(f"  ...以及其他 {len(connection_failures) - 5} 个连接失败")
    
    print(f"\n总处理通道数: {processed_channels}/{total_channels}")
    print("所有索引数据已成功存储到MongoDB的index集合中")

def create_shot_index(db, shot_number, struct_tree_data):
    """为单个炮号的结构树创建索引数据并存储到MongoDB"""
    index_collection = db["index"]
    
    # 遍历数据，为每个key创建索引
    for key in set([k for item in struct_tree_data for k in item.keys() if k not in ['status', 'status_message']]):
        # 获取或创建此key的索引文档
        index_doc = index_collection.find_one({"key": key}) or {"key": key, "index_data": {}}
        
        # 确保索引文档有正确的结构
        if "index_data" not in index_doc:
            index_doc["index_data"] = {}
            
        # 为当前炮号创建/更新索引
        shot_index_data = {}
        
        # 遍历结构树中的每个条目，为当前炮号创建索引
        for idx, item in enumerate(struct_tree_data):
            if key in item:
                value = item[key]
                
                # 根据值的类型进行不同处理
                if type(value) != list:
                    # 非列表类型值的处理
                    if value not in shot_index_data:
                        shot_index_data[value] = []
                    shot_index_data[value].append(idx)
                else:
                    # 列表类型值的处理
                    if len(value) == 0:
                        shot_index_data.setdefault('NO ERROR', []).append(idx)
                    for v in value:
                        if v not in shot_index_data:
                            shot_index_data[v] = []
                        shot_index_data[v].append(idx)
        
        # 更新索引文档中的炮号索引数据
        index_doc["index_data"][shot_number] = shot_index_data
        
        # 保存回MongoDB
        index_collection.update_one(
            {"key": key},
            {"$set": index_doc},
            upsert=True
        )
    
    print(f"  已成功为炮号 {shot_number} 创建并保存索引数据")
    
    # 确保索引集合有适当的索引以提高查询性能
    index_collection.create_index([("key", ASCENDING)])
    
if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) >= 3:
        # 从命令行获取两个参数，并转为整数
        shot_start = int(sys.argv[1])
        shot_end = int(sys.argv[2])
        shot_list = [shot_start, shot_end]
    else:
        # 默认值
        shot_list = [1, 100]
    channel_list = []
    # 动态设置数据库名
    db_name = f"DataDiagnosticPlatform_[{shot_list[0]}_{shot_list[1]}]"
    RUN(shot_list, channel_list, db_name)





