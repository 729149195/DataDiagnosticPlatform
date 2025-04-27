"""
该模块用于批量读取MDSplus数据库中的实验数据，自动调用各类异常检测算法，对指定通道和炮号的数据进行异常诊断，并将检测结果存储到MongoDB中，便于后续分析和可视化。
"""
import re
import time
from datetime import datetime
import importlib
import json
import multiprocessing as mp
from functools import partial
import importlib.util
import random
import os
import logging
import traceback

import MDSplus # type: ignore
import numpy as np
from pymongo import MongoClient, IndexModel, ASCENDING, UpdateMany
from tqdm import tqdm

from mdsConn import MdsTree, formChaPool

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
    delay = random.uniform(0.01, 0.2)
    time.sleep(delay)
    
    # 创建独立的MdsTree连接，添加重试机制
    tree = None
    max_retries = 3
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
            return None, None
        
    channel_type = remove_digits(channel_name).upper()
    if channel_type == 'MIR':
        channel_type = 'Mirnov'

    temp = {
        "shot_number": str(shot_num),
        "channel_type": channel_type,
        "channel_name": channel_name,
        'db_name': DB,
        'error_name': []
    }
    
    # 为批量插入准备的数据
    error_data_list = []
    
    try:
        detect_type = channel_type
        if detect_type in ['MP', 'FLUX', 'IPF']:
            detect_type = 'MP'
            
        if detect_type in algorithm_channel_map:
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
                    if tree is not None:
                        tree.close()
                    return None, None
                
            if X_value is None or Y_value is None or len(Y_value) == 0:
                if tree is not None:
                    tree.close()
                return None, None
                
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
            
            # 动态导入算法模块
            for error in error_type_list:
                if channel_name in error_channel_map[error]:
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
    except Exception as e:
        logger.warning(f"处理通道 {channel_name} 时发生异常: {traceback.format_exc()}")
    
    # 确保关闭连接
    if tree is not None:
        try:
            tree.close()
        except:
            pass
            
    return temp, error_data_list

def RUN(shot_list, channel_list):
    # 连接MongoDB
    client = MongoClient("mongodb://localhost:27017")
    db = client["DataDiagnosticPlatform"]
    errors_collection = db["errors_data"]
    struct_trees_collection = db["struct_trees"]
    
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
    shot_range = list(range(*shot_list))
    read_time = 0
    
    # 计算总通道数用于进度显示
    total_channels = 0
    print("正在统计处理总量...")
    for DB in DB_list:
        for shot_num in tqdm(shot_range, desc=f"统计 {DB} 数据库的炮号"):
            try:
                tree = MdsTree(shot_num, dbname=DB, path=DBS[DB]['path'], subtrees=DBS[DB]['subtrees'])
                pool = tree.formChannelPool()
                if len(channel_list) == 0:
                    total_channels += len(pool)
                else:
                    total_channels += len([c for c in pool if c in channel_list])
                tree.close()
            except Exception as e:
                logger.warning(f"统计炮号{str(shot_num)}时发生异常: {e}")
    
    print(f"总计需要处理 {len(shot_range)} 个炮号, {total_channels} 个通道")
    processed_channels = 0
    
    # 获取可用CPU核心数，合理限制进程数
    num_processes = min(32, max(1, mp.cpu_count() - 1))
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
            try:
                tree = MdsTree(shot_num, dbname=DB, path=DBS[DB]['path'], subtrees=DBS[DB]['subtrees'])
                channel_pool = tree.formChannelPool()
                if len(channel_list) == 0:
                    channels_to_process = channel_pool
                else:
                    channels_to_process = [c for c in channel_pool if c in channel_list]
                
                tree.close()  # 关闭主连接，每个进程将创建自己的连接
                print(f"  炮号 {shot_num} 在 {DB} 数据库共有 {len(channels_to_process)} 个通道需要处理")
            except Exception as e:
                logger.warning(f"获取炮号 {shot_num} 的 {DB} 数据库通道列表时发生异常: {e}")
                continue  # 跳过当前数据库，继续处理下一个数据库
            
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
            
            # 收集当前数据库的结果
            for result in db_results:
                processed_channels += 1
                if result[0] is not None:
                    combined_shot_struct_tree.append(result[0])
                    all_struct_tree.append(result[0])
                
                if result[1] is not None:
                    combined_error_data.extend(result[1])
            
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
        except Exception as e:
            logger.error(f"保存炮号 {shot_num} 的结构树到MongoDB时发生异常: {e}")
        
        shot_end = time.time()
        print(f'已完成炮号 {shot_num} 的全部处理，总运行时间: {round(shot_end-shot_start, 2)}s')
    
    # 将完整的结构树存入MongoDB作为备份
    try:
        struct_trees_collection.update_one(
            {"shot_list": f"{shot_range[0]}_{shot_range[-1]}"},
            {"$set": {"struct_tree": all_struct_tree}},
            upsert=True
        )
        print(f"已将完整结构树（{shot_range[0]}-{shot_range[-1]}）保存到MongoDB")
    except Exception as e:
        logger.error(f"保存完整结构树到MongoDB时发生异常: {e}")
    
    print(f"总处理通道数: {processed_channels}/{total_channels}")

with open('RunDetectAlgorithm/algorithmChannelMap.json', encoding='utf-8') as f:
    algorithm_channel_map = json.load(f)
shot_list = [4571, 4572]
channel_list = []
RUN(shot_list, channel_list)





