import ast
import json
import orjson
import os
import re
import time
import gzip
import MDSplus # type: ignore
import numpy as np
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
import uuid
import threading
from django.utils import timezone
from datetime import datetime
import unicodedata  # 添加这一行来导入unicodedata模块
import inspect  # 添加inspect模块导入
import importlib.util  # 添加importlib工具模块导入
from django.views.decorators.csrf import csrf_exempt  # 添加CSRF豁免
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings
import zipfile
from io import BytesIO

from api.self_algorithm_utils import period_condition_anomaly
from api.Mds import MdsTree
from api.verify_user import send_post_request
from api.pattern_matching_Qetch import match_pattern  # 只导入模式匹配函数
from pymongo import MongoClient, ASCENDING, UpdateMany
from collections import defaultdict, Counter
import logging
import pymongo
import csv
import os

# 配置日志
logger = logging.getLogger(__name__)

# 导入科学计算库
try:
    from sklearn.decomposition import PCA
    sklearn_available = True
except ImportError:
    sklearn_available = False
    print("警告：sklearn未安装，PCA功能将不可用")

# 存储计算任务状态的字典
calculation_tasks = {}

# MongoDB 配置：
client = MongoClient("mongodb://localhost:27017")

# 数据库范围缓存，避免重复解析数据库名称（缓存5分钟）
_db_ranges_cache = None
_db_ranges_cache_time = None
_cache_duration = 300  # 5分钟缓存
# 移除固定的db赋值，改为根据请求参数动态选择数据库
# db = client["DataDiagnosticPlatform_4949_5071"]
# 改为在各函数中动态获取数据库参数

# 获取数据库实例的辅助函数
def _get_db_ranges_cached():
    """获取缓存的数据库范围信息"""
    global _db_ranges_cache, _db_ranges_cache_time
    
    current_time = time.time()
    
    # 检查缓存是否过期
    if (_db_ranges_cache is None or 
        _db_ranges_cache_time is None or 
        current_time - _db_ranges_cache_time > _cache_duration):
        
        # 重新解析数据库范围
        db_names = client.list_database_names()
        filtered_db_names = [name for name in db_names if name.startswith("DataDiagnosticPlatform")]
        
        db_ranges = {}  # {(start, end): db_suffix}
        
        for db_name in filtered_db_names:
            # 从数据库名称解析炮号范围
            if '[' in db_name and ']' in db_name:
                # 新格式: DataDiagnosticPlatform_[1201_1300]
                match = re.search(r'DataDiagnosticPlatform_\[(\d+)_(\d+)\]', db_name)
                if match:
                    db_start, db_end = int(match.group(1)), int(match.group(2))
                    db_suffix = f"[{db_start}_{db_end}]"
                    db_ranges[(db_start, db_end)] = db_suffix
            else:
                # 旧格式: DataDiagnosticPlatform_1201_1300
                parts = db_name.replace("DataDiagnosticPlatform_", "").split("_")
                if len(parts) >= 2:
                    try:
                        db_start, db_end = int(parts[0]), int(parts[1])
                        db_suffix = f"{db_start}_{db_end}"
                        db_ranges[(db_start, db_end)] = db_suffix
                    except (ValueError, IndexError):
                        continue
        
        # 更新缓存
        _db_ranges_cache = db_ranges
        _db_ranges_cache_time = current_time
        
        print(f"数据库范围缓存已更新，共找到 {len(db_ranges)} 个数据库")
    
    return _db_ranges_cache

def find_databases_for_shot_numbers(shot_numbers):
    """
    根据炮号列表快速查找包含这些炮号的数据库
    优化算法：基于炮号区间规律，炮号区间都是从100炮的开头开始，如1254炮在[1201_1300]区间
    使用缓存机制避免重复解析数据库名称
    
    Args:
        shot_numbers: 炮号列表
    
    Returns:
        dict: {db_suffix: [matched_shot_numbers]}
    """
    if not shot_numbers:
        return {}
    
    # 将炮号转换为整数进行范围比较
    shot_numbers_int = []
    for shot in shot_numbers:
        try:
            shot_numbers_int.append(int(shot))
        except (ValueError, TypeError):
            continue
    
    if not shot_numbers_int:
        return {}
    
    # 获取缓存的数据库范围信息
    db_ranges = _get_db_ranges_cached()
    
    if not db_ranges:
        return {}
    
    # 快速匹配炮号到数据库
    db_shot_mapping = {}
    
    for shot_int in shot_numbers_int:
        # 快速计算该炮号应该在哪个数据库区间
        # 基于100炮区间规律：1254 -> 应该在 [1201, 1300] 区间
        
        # 计算区间的起始炮号（向下取整到最近的 X01）
        hundred_base = (shot_int // 100) * 100
        expected_start = hundred_base + 1
        
        # 首先尝试直接命中预期区间（最快）
        found_db = None
        for (db_start, db_end), db_suffix in db_ranges.items():
            if db_start == expected_start and db_start <= shot_int <= db_end:
                found_db = db_suffix
                break
        
        # 如果预期区间没找到，尝试相邻区间（处理边界情况）
        if not found_db:
            # 尝试上一个百位区间
            alt_expected_start = hundred_base - 99  # 如 1154 -> 1101
            for (db_start, db_end), db_suffix in db_ranges.items():
                if db_start == alt_expected_start and db_start <= shot_int <= db_end:
                    found_db = db_suffix
                    break
        
        # 最后回退到完全匹配（兜底机制）
        if not found_db:
            for (db_start, db_end), db_suffix in db_ranges.items():
                if db_start <= shot_int <= db_end:
                    found_db = db_suffix
                    break
        
        # 添加到结果中
        if found_db:
            if found_db not in db_shot_mapping:
                db_shot_mapping[found_db] = []
            db_shot_mapping[found_db].append(str(shot_int))
    
    return db_shot_mapping

def get_multi_db_index_data(key, shot_numbers):
    """
    从多个数据库获取索引数据并合并
    
    Args:
        key: 索引键 ('channel_name', 'error_name' 等)
        shot_numbers: 炮号列表
    
    Returns:
        dict: 合并后的索引数据，格式为 {item_name: [(shot_number, db_suffix)]}
    """
    db_shot_mapping = find_databases_for_shot_numbers(shot_numbers)
    
    if not db_shot_mapping:
        return {}
    
    merged_index = {}
    
    for db_suffix, shots_in_db in db_shot_mapping.items():
        try:
            db = get_db(db_suffix)
            index_collection = db["index"]
            
            # 获取该数据库的索引文档
            doc = index_collection.find_one({'key': key})
            if not doc or 'index_data' not in doc:
                continue
            
            index_data = doc['index_data']
            
            # 遍历该数据库中匹配的炮号
            for shot_number in shots_in_db:
                if shot_number in index_data:
                    shot_index = index_data[shot_number]
                    
                    # 根据索引键的不同，处理数据结构
                    if key == 'channel_name':
                        # channel_name索引: {shot: {channel_name: [channel_types]}}
                        for channel_name, channel_types in shot_index.items():
                            if channel_name not in merged_index:
                                merged_index[channel_name] = []
                            # 添加 (shot_number, db_suffix) 作为索引标识
                            merged_index[channel_name].append((shot_number, db_suffix))
                    
                    elif key == 'error_name':
                        # error_name索引: {shot: {error_name: [channel_names]}}
                        for error_name, channel_names in shot_index.items():
                            if error_name not in merged_index:
                                merged_index[error_name] = []
                            # 添加 (shot_number, db_suffix) 作为索引标识
                            merged_index[error_name].append((shot_number, db_suffix))
                    
                    elif key == 'channel_type':
                        # channel_type索引: {shot: {channel_type: [channel_names]}}
                        for channel_type, channel_names in shot_index.items():
                            if channel_type not in merged_index:
                                merged_index[channel_type] = []
                            # 添加 (shot_number, db_suffix) 作为索引标识
                            merged_index[channel_type].append((shot_number, db_suffix))
                            
        except Exception as e:
            print(f"获取数据库 {db_suffix} 的索引数据时出错: {str(e)}")
            continue
    
    return merged_index

def get_db(db_suffix=None):
    """
    根据参数动态获取MongoDB数据库实例
    
    Args:
        db_suffix: 数据库名后缀，如 '4949_5071'
    
    Returns:
        MongoDB数据库实例
    """
    if not db_suffix:
        # 默认使用第一个DataDiagnosticPlatform数据库
        db_names = client.list_database_names()
        filtered_db_names = [name for name in db_names if name.startswith("DataDiagnosticPlatform")]
        db = client[filtered_db_names[0]]
    else:
        db_name = f"DataDiagnosticPlatform_{db_suffix}"
        db = client[db_name]
    
    # 确保数据库具有必要的索引
    return ensure_db_indices(db)

def get_db_by_name(db_name):
    """
    根据数据库名获取数据库连接
    """
    return ensure_db_indices(client[db_name])

def get_database_name_for_shot(shot_number):
    """
    根据炮号获取对应的数据库名
    """
    db_shot_mapping = find_databases_for_shot_numbers([int(shot_number)])
    if not db_shot_mapping:
        return None
    
    # 获取第一个数据库后缀
    db_suffix = list(db_shot_mapping.keys())[0]
    return f"DataDiagnosticPlatform_{db_suffix}"

def ensure_db_indices(db):
    """
    确保数据库具有必要的索引集合
    如果不存在，尝试从其他集合生成基本索引结构
    
    Args:
        db: MongoDB数据库实例
    """
    collections = db.list_collection_names()
    
    # 检查是否需要创建索引
    if 'index' not in collections and 'struct_trees' in collections:
        print(f"数据库 {db.name} 中不存在index集合，尝试创建基本索引...")
        
        try:
            # 创建索引集合
            index_collection = db["index"]
            
            # 从struct_trees获取数据
            struct_trees = db["struct_trees"].find({})
            
            # 准备索引数据
            channel_type_index = {}
            channel_name_index = {}
            error_name_index = {}
            
            # 遍历struct_trees数据构建索引
            for tree_doc in struct_trees:
                shot_number = tree_doc.get("shot_number", "unknown")
                
                if "struct_tree" in tree_doc:
                    for item in tree_doc["struct_tree"]:
                        channel_type = item.get("channel_type")
                        channel_name = item.get("channel_name")
                        error_names = item.get("error_name", [])
                        
                        # 确保是列表
                        if error_names and not isinstance(error_names, list):
                            error_names = [error_names]
                        
                        # 更新channel_type索引
                        if channel_type:
                            if shot_number not in channel_type_index:
                                channel_type_index[shot_number] = {}
                            if channel_type not in channel_type_index[shot_number]:
                                channel_type_index[shot_number][channel_type] = []
                            if channel_name not in channel_type_index[shot_number][channel_type]:
                                channel_type_index[shot_number][channel_type].append(channel_name)
                        
                        # 更新channel_name索引
                        if channel_name:
                            if shot_number not in channel_name_index:
                                channel_name_index[shot_number] = {}
                            if channel_name not in channel_name_index[shot_number]:
                                channel_name_index[shot_number][channel_name] = []
                            if channel_type not in channel_name_index[shot_number][channel_name]:
                                channel_name_index[shot_number][channel_name].append(channel_type)
                        
                        # 更新error_name索引
                        for error_name in error_names:
                            if error_name:
                                if shot_number not in error_name_index:
                                    error_name_index[shot_number] = {}
                                if error_name not in error_name_index[shot_number]:
                                    error_name_index[shot_number][error_name] = []
                                if channel_name not in error_name_index[shot_number][error_name]:
                                    error_name_index[shot_number][error_name].append(channel_name)
            
            # 保存索引数据
            if channel_type_index:
                index_collection.insert_one({
                    "key": "channel_type",
                    "index_data": channel_type_index
                })
                print(f"已创建channel_type索引，包含 {len(channel_type_index)} 个炮号")
            
            if channel_name_index:
                index_collection.insert_one({
                    "key": "channel_name",
                    "index_data": channel_name_index
                })
                print(f"已创建channel_name索引，包含 {len(channel_name_index)} 个炮号")
            
            if error_name_index:
                index_collection.insert_one({
                    "key": "error_name",
                    "index_data": error_name_index
                })
                print(f"已创建error_name索引，包含 {len(error_name_index)} 个炮号")
            
            print(f"数据库 {db.name} 基本索引创建完成")
            
        except Exception as e:
            print(f"创建索引时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    return db

@require_GET
def get_struct_tree(request):
    """
    获取结构树数据，支持shot_numbers, channel_names, error_names多条件过滤
    支持跨数据库查询
    返回时整体按channel_type、channel_name排序。
    """
    shot_numbers = request.GET.get('shot_numbers')
    channel_names = request.GET.get('channel_names')
    error_names = request.GET.get('error_names')
    db_suffix = request.GET.get('db_suffix')  # 可选参数
    
    shot_numbers = shot_numbers.split(',') if shot_numbers else []
    channel_names = channel_names.split(',') if channel_names else []
    error_names = error_names.split(',') if error_names else []

    result = []
    
    if db_suffix:
        # 如果指定了数据库，使用原有逻辑
        db = get_db(db_suffix)
        struct_trees_collection = db["struct_trees"]

        query = {}
        if shot_numbers:
            query['shot_number'] = {'$in': shot_numbers}
        docs = struct_trees_collection.find(query)
        
        for doc in docs:
            for item in doc.get('struct_tree', []):
                if channel_names and item.get('channel_name') not in channel_names:
                    continue
                if error_names:
                    item_errors = item.get('error_name', [])
                    # 兼容各种"无异常"情况
                    if item_errors is None or item_errors == "" or item_errors == []:
                        item_errors_set = set(["NO ERROR"])
                    else:
                        if isinstance(item_errors, str):
                            item_errors_set = set([item_errors])
                        else:
                            item_errors_set = set(item_errors)
                    if "NO ERROR" in error_names:
                        if not (not item_errors_set or "NO ERROR" in item_errors_set):
                            continue
                    elif not item_errors_set.intersection(error_names):
                        continue
                result.append(item)
    else:
        # 如果没有指定数据库，则根据炮号自动匹配多个数据库
        if not shot_numbers:
            return OrJsonResponse([])
        
        db_shot_mapping = find_databases_for_shot_numbers(shot_numbers)
        
        for db_suffix_auto, shots_in_db in db_shot_mapping.items():
            try:
                db = get_db(db_suffix_auto)
                struct_trees_collection = db["struct_trees"]

                query = {'shot_number': {'$in': shots_in_db}}
                docs = struct_trees_collection.find(query)
                
                for doc in docs:
                    for item in doc.get('struct_tree', []):
                        if channel_names and item.get('channel_name') not in channel_names:
                            continue
                        if error_names:
                            item_errors = item.get('error_name', [])
                            # 兼容各种"无异常"情况
                            if item_errors is None or item_errors == "" or item_errors == []:
                                item_errors_set = set(["NO ERROR"])
                            else:
                                if isinstance(item_errors, str):
                                    item_errors_set = set([item_errors])
                                else:
                                    item_errors_set = set(item_errors)
                            if "NO ERROR" in error_names:
                                if not (not item_errors_set or "NO ERROR" in item_errors_set):
                                    continue
                            elif not item_errors_set.intersection(error_names):
                                continue
                        
                        # 添加数据库信息到结果中，以便前端知道数据来源
                        item_with_db = item.copy()
                        item_with_db['source_db'] = db_suffix_auto
                        result.append(item_with_db)
                        
            except Exception as e:
                print(f"从数据库 {db_suffix_auto} 获取数据时出错: {str(e)}")
                continue

    # 整体排序：先按channel_type，再按channel_name
    result.sort(key=lambda x: (x.get('channel_type', ''), x.get('channel_name', '')))
    return OrJsonResponse(result)

@require_GET
def get_shot_number_index(request):
    """
    获取所有炮号列表，支持跨数据库查询
    """
    # 获取所有DataDiagnosticPlatform数据库的炮号
    db_names = client.list_database_names()
    filtered_db_names = [name for name in db_names if name.startswith("DataDiagnosticPlatform")]
    
    all_shot_numbers = set()
    
    for db_name in filtered_db_names:
        try:
            db = client[db_name]
            collections = db.list_collection_names()
            
            if 'index' in collections:
                index_collection = db["index"]
                all_docs = list(index_collection.find({}))
                for doc in all_docs:
                    all_shot_numbers.update(doc.get("index_data", {}).keys())
            elif 'struct_trees' in collections:
                # 如果索引集合不存在，尝试从struct_trees集合获取炮号
                shot_numbers = set(db["struct_trees"].distinct("shot_number"))
                all_shot_numbers.update(shot_numbers)
            else:
                print(f"警告: 数据库 {db_name} 中不存在index或struct_trees集合")
                
        except Exception as e:
            print(f"警告: 从数据库 {db_name} 获取炮号时出错: {str(e)}")
            continue
    
    try:
        return OrJsonResponse(sorted(list(all_shot_numbers)))
    except Exception as e:
        import traceback
        error_msg = f"获取炮号索引出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({"error": error_msg}, status=500)

def get_index_by_key(key, request):
    """
    通用索引获取函数，支持按炮号过滤，支持跨数据库查询
    """
    shot_numbers = request.GET.getlist('shot_numbers[]') or request.GET.get('shot_numbers')
    
    if isinstance(shot_numbers, str):
        shot_numbers = shot_numbers.split(',') if shot_numbers else []
    
    print(f"获取索引，key={key}, shot_numbers={shot_numbers}")
    
    # 如果有指定炮号，使用跨数据库查询
    if shot_numbers:
        print(f"使用跨数据库查询获取 {key} 索引")
        result = get_multi_db_index_data(key, shot_numbers)
        return OrJsonResponse(result)
    
    # 如果没有指定炮号，获取所有数据库的索引数据
    db_names = client.list_database_names()
    filtered_db_names = [name for name in db_names if name.startswith("DataDiagnosticPlatform")]
    
    result = {}
    
    for db_name in filtered_db_names:
        try:
            db = client[db_name]
            collections = db.list_collection_names()
            
            if 'index' not in collections:
                print(f"警告: 数据库 {db_name} 中不存在'index'集合")
                continue
            
            index_collection = db["index"]
            doc = index_collection.find_one({'key': key})
            
            if doc and "index_data" in doc:
                for shot, name_dict in doc["index_data"].items():
                    for name, indices in name_dict.items():
                        if name not in result:
                            result[name] = set()
                        result[name].update(indices)
                        
        except Exception as e:
            print(f"警告: 从数据库 {db_name} 获取索引时出错: {str(e)}")
            continue
    
    try:
        # 转换set为list
        result = {k: list(v) for k, v in result.items()}
        print(f"处理后的结果大小: {len(result)}")
        return OrJsonResponse(result)
    except Exception as e:
        import traceback
        error_msg = f"获取索引出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({"error": error_msg}, status=500)

@require_GET
def get_channel_type_index(request):
    return get_index_by_key('channel_type', request)

@require_GET
def get_channel_name_index(request):
    return get_index_by_key('channel_name', request)

@require_GET
def get_errors_name_index(request):
    return get_index_by_key('error_name', request)

@require_GET
def get_error_origin_index(request):
    return get_index_by_key('error_origin', request)


@require_GET
def get_error_data(request):
    """
    获取异常数据，直接查MongoDB，支持自动查找数据库
    """
    channel_key = request.GET.get('channel_key')
    channel_type = request.GET.get('channel_type')
    error_name = request.GET.get('error_name')
    error_index = request.GET.get('error_index')
    
    if channel_key and channel_type and error_name and error_index is not None:
        try:
            error_index = int(error_index)
        except ValueError:
            return OrJsonResponse({'error': 'Invalid error_index'}, status=400)
        if '_' in channel_key:
            channel_name, shot_number = channel_key.rsplit('_', 1)
        else:
            return OrJsonResponse({'error': 'Invalid channel_key format'}, status=400)
            
        # 根据炮号自动查找正确的数据库
        db_shot_mapping = find_databases_for_shot_numbers([str(shot_number)])
        
        if not db_shot_mapping:
            return OrJsonResponse({'error': 'No database found for this shot number'}, status=404)
        
        # 使用第一个匹配的数据库
        db_suffix_auto = list(db_shot_mapping.keys())[0]
        db = get_db(db_suffix_auto)
            
        errors_collection = db["errors_data"]
        
        doc = errors_collection.find_one({
            "shot_number": str(shot_number),
            "channel_number": channel_name,
            "error_type": error_name
        })
        
        if doc and "data" in doc:
            return OrJsonResponse(doc["data"])
        else:
            return OrJsonResponse({'error': 'Not found'}, status=404)
    else:
        return OrJsonResponse({'error': 'Required parameters are missing'}, status=400)

def downsample_to_frequency(x_values, y_values, target_freq=1000):
    """
    对数据进行高效降采样到指定频率，同时保留信号特征
    
    Args:
        x_values: 时间序列数据的X值（时间值）
        y_values: 对应的Y值
        target_freq: 目标频率，默认1000Hz (1KHz)
        
    Returns:
        降采样后的x_values和y_values
    """
    if len(x_values) <= target_freq:
        return x_values, y_values
    
    # 确定数据的时间范围
    time_start = min(x_values)
    time_end = max(x_values)
    time_span = time_end - time_start
    
    # 基于目标频率计算总采样点数
    n_samples = int(time_span * target_freq)
    
    # 如果目标点数比原始点数多，直接返回原始数据
    if n_samples >= len(x_values):
        return x_values, y_values
    
    # 计算降采样比例
    sample_ratio = len(x_values) // n_samples
    
    # 增强的特征保留降采样
    if sample_ratio > 10:  # 对于高降采样比率
        # 步骤1: 先进行均匀采样作为基础点集
        base_indices = np.arange(0, len(x_values), sample_ratio)
        if len(base_indices) > n_samples:
            base_indices = base_indices[:n_samples]
        
        # 步骤2: 识别关键特征点 - 寻找局部极值
        # 使用滑动窗口检测局部极值点，窗口大小根据降采样比例自适应调整
        window_size = min(sample_ratio // 2, 20)  # 避免窗口过大
        if window_size < 2:
            window_size = 2
            
        # 计算局部极值点
        extrema_indices = []
        for i in range(window_size, len(y_values) - window_size, window_size):
            window = y_values[i-window_size:i+window_size]
            if y_values[i] == max(window) or y_values[i] == min(window):
                # 如果是窗口内的极值点，添加到特征点列表
                extrema_indices.append(i)
        
        # 步骤3: 合并基础点集和特征点集，确保不超过目标点数
        all_indices = np.unique(np.concatenate([base_indices, extrema_indices]))
        
        # 如果合并后点数超过目标点数，优先保留特征点并进行下采样
        if len(all_indices) > n_samples:
            # 保留所有特征点
            kept_extrema = np.array(extrema_indices)
            # 计算剩余可用的点数
            remaining_slots = n_samples - len(kept_extrema)
            if remaining_slots > 0:
                # 从基础点集中抽样填充剩余点位
                mask = np.isin(base_indices, kept_extrema, invert=True)
                candidates = base_indices[mask]
                if len(candidates) > remaining_slots:
                    # 均匀抽取剩余点位
                    step = len(candidates) // remaining_slots
                    base_selection = candidates[::step][:remaining_slots]
                else:
                    base_selection = candidates
                # 合并特征点和基础点，并排序
                final_indices = np.sort(np.concatenate([kept_extrema, base_selection]))
            else:
                # 如果特征点已经超过了目标点数，则进行均匀下采样
                step = len(kept_extrema) // n_samples
                final_indices = kept_extrema[::step][:n_samples]
        else:
            final_indices = all_indices
            
            # 如果点数仍不足，可以补充一些点
            if len(final_indices) < n_samples:
                # 创建掩码，标记未选中的点
                mask = np.ones(len(x_values), dtype=bool)
                mask[final_indices] = False
                remaining_indices = np.arange(len(x_values))[mask]
                
                # 确定需要补充的点数
                to_add = n_samples - len(final_indices)
                if len(remaining_indices) > to_add:
                    # 均匀选择额外点
                    step = len(remaining_indices) // to_add
                    extra_indices = remaining_indices[::step][:to_add]
                    # 合并并排序
                    final_indices = np.sort(np.concatenate([final_indices, extra_indices]))
        
        # 提取最终的采样点
        new_times = x_values[final_indices]
        new_values = y_values[final_indices]
    else:
        # 对于小幅度降采样，使用更简单的方法以保持速度
        # 结合等间隔采样和线性插值，兼顾准确性和效率
        indices = np.linspace(0, len(x_values)-1, n_samples).astype(int)
        new_times = x_values[indices]
        new_values = y_values[indices]
    
    print(f"特征保留降采样: 从 {len(x_values)} 点 降至 {len(new_times)} 点")
    return new_times, new_values

def compress_response(view_func):
    """
    装饰器：压缩响应内容
    """
    def wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        if isinstance(response, HttpResponse):
            response.headers['Content-Encoding'] = 'gzip'
            response.content = gzip.compress(response.content)
        return response
    return wrapped_view

# 使用orjson创建更快的JsonResponse
def OrJsonResponse(data, status=200):
    """使用orjson创建更快的JsonResponse，同时保持对numpy的支持"""
    return HttpResponse(
        orjson.dumps(data, option=orjson.OPT_SERIALIZE_NUMPY),
        content_type='application/json',
        status=status
    )

@require_GET
def get_channel_data(request, channel_key=None):
    """
    获取通道数据
    """
    start_time = time.time()
    try:
        if channel_key is None:
            channel_key = request.GET.get('channel_key')
        else:
            pass
        
        # 获取采样参数，默认采用降采样
        sample_mode = request.GET.get('sample_mode', 'downsample')  # 可选值: 'full', 'downsample'
        sample_freq = float(request.GET.get('sample_freq', 1000))   # 默认1KHz，改为float类型
        
        # 收集日志信息，最后统一打印
        logs = []
        logs.append(f"请求通道数据，通道键: '{channel_key}', 采样模式: {sample_mode}, 目标频率: {sample_freq} KHz")
        
        # channel_type = request.GET.get('channel_type')
        if channel_key: # and channel_type:
            if '_' in channel_key:
                # 解析通道键格式
                channel_name, shot_number = channel_key.rsplit('_', 1)
                try:
                    num = int(channel_name)
                    channel_name, shot_number = shot_number, channel_name
                    logs.append(f"格式交换: '{channel_name}_{shot_number}' (通道名_炮号)")
                except ValueError:
                    # 格式已正确为"通道名_炮号"
                    logs.append(f"正确格式: '{channel_name}_{shot_number}' (通道名_炮号)")
                    pass
                    
                try:
                    shot_number = int(shot_number)
                except ValueError:
                    return OrJsonResponse({'error': f"无法将炮号转换为整数: '{shot_number}'"}, status=400)
            else:
                return OrJsonResponse({'error': 'Invalid channel_key format'}, status=400)
            
            DB_list = ["exl50u", "eng50u"]
            DBS = {
                'exl50': {
                    'name': 'exl50',
                    'addr': '192.168.20.11',
                    'path': '192.168.20.11::/media/ennfusion/trees/exl50',
                    'subtrees': ['FBC', 'PAI', 'PMNT']
                },
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
                },
                'ecrhlab': {
                    'name': 'ecrhlab',
                    'addr': '192.168.20.32',
                    'path': '192.168.20.32::/media/ecrhdb/trees/ecrhlab',
                    'subtrees': ['PAI']
                },
                'ts': {
                    'name': 'ts',
                    'addr': '192.168.20.28',
                    'path': '192.168.20.28::/media/ennts/trees/ts',
                    'subtrees': ['AI']
                },
            }
            data = {}
            logs.append(f"通道名: {channel_name}")
            
            db_start_time = time.time()
            for DB in DB_list:
                tree_start_time = time.time()

                tree = MdsTree(shot_number, dbname=DB, path=DBS[DB]['path'], subtrees=DBS[DB]['subtrees'])
                logs.append(f"创建MdsTree对象耗时: {time.time() - tree_start_time:.2f}秒")
                
                data_start_time = time.time()
                if channel_name[:2] == 'MP' or channel_name[:4] == 'FLUX':
                    data_x, data_y, unit = tree.getData(channel_name, -7, 5)
                else:
                    data_x, data_y, unit = tree.getData(channel_name)
                logs.append(f"获取数据耗时: {time.time() - data_start_time:.2f}秒")
                logs.append(f"原始数据量: X轴 {len(data_x)} 点, Y轴 {len(data_y)} 点")
                
                # 计算原始频率，由Hz转换为KHz
                original_frequency = len(data_x) / (data_x[-1] - data_x[0]) if len(data_x) > 1 else 0
                original_frequency_khz = original_frequency / 1000
                logs.append(f"原始频率: {original_frequency_khz}KHz")
                
                if len(data_x) != 0:
                    is_downsampled = False
                    is_upsampled = False
                    
                    # 处理采样率调整
                    if sample_mode != 'full' and sample_freq > 0:
                        # 将sample_freq从KHz转换为Hz
                        target_freq_hz = sample_freq * 1000
                        
                        # 如果目标频率小于原始频率，进行降采样
                        if target_freq_hz < original_frequency:
                            downsampling_start = time.time()
                            data_x, data_y = downsample_to_frequency(data_x, data_y, target_freq=target_freq_hz)
                            logs.append(f"降采样耗时: {time.time() - downsampling_start:.2f}秒")
                            is_downsampled = True
                        # 如果目标频率大于原始频率，进行插值采样
                        elif target_freq_hz > original_frequency:
                            upsampling_start = time.time()
                            # 为了避免混淆，创建一个专门的插值采样函数
                            data_x, data_y = upsample_to_frequency(data_x, data_y, target_freq=target_freq_hz)
                            logs.append(f"插值采样耗时: {time.time() - upsampling_start:.2f}秒")
                            is_upsampled = True
                    
                    # 计算前端绘图需要的数据统计信息
                    calculate_start_time = time.time()
                    
                    # 计算Y值的统计数据
                    y_min = float(np.min(data_y))
                    y_max = float(np.max(data_y))
                    y_mean = float(np.mean(data_y))
                    y_median = float(np.median(data_y))
                    y_std = float(np.std(data_y))
                    
                    # 计算X轴范围
                    x_min = float(np.min(data_x))
                    x_max = float(np.max(data_x))
                    
                    # 计算数据范围，用于Y轴缩放
                    y_range = y_max - y_min
                    y_range_padding = y_range * 0.2  # 添加20%的padding
                    y_axis_min = y_min - y_range_padding
                    y_axis_max = y_max + y_range_padding
                    
                    # 判断通道类型
                    is_digital = False
                    if y_min >= 0 and y_max <= 1 and np.all(np.logical_or(np.isclose(data_y, 0), np.isclose(data_y, 1))):
                        is_digital = True
                        
                    # 归一化数据（用于多通道对比）
                    y_abs_max = max(abs(y_min), abs(y_max))
                    if y_abs_max > 0:
                        y_normalized = list(data_y / y_abs_max)
                    else:
                        y_normalized = list(data_y)

                    # ====== FFT 计算及计时 ======
                    fft_start_time = time.time()
                    N = len(data_y)
                    if N > 1:
                        # 采样间隔
                        dt = (data_x[-1] - data_x[0]) / (N - 1)
                        # 采样频率
                        fs = 1.0 / dt
                        
                        # 执行FFT（与MATLAB保持一致的处理方式）
                        fft_result = np.fft.fft(data_y)
                        
                        # 计算双边谱的幅度（不进行归一化，保持MATLAB的原始幅度）
                        amplitude_double_sided = np.abs(fft_result)
                        
                        # 生成频率轴（双边谱）
                        freq_double_sided = np.fft.fftfreq(N, d=dt)
                        
                        # 转换为单边谱（只保留正频率和零频率）
                        if N % 2 == 0:  # 偶数长度
                            # 正频率点数（包含零频率，不包含Nyquist频率的负频率对应）
                            n_positive = N // 2 + 1
                            freq = freq_double_sided[:n_positive]
                            amplitude = amplitude_double_sided[:n_positive].copy()
                            
                            # 单边谱幅度处理：除直流和Nyquist分量外，其他分量乘以2
                            amplitude[1:-1] = amplitude[1:-1] * 2
                        else:  # 奇数长度
                            n_positive = (N + 1) // 2
                            freq = freq_double_sided[:n_positive]
                            amplitude = amplitude_double_sided[:n_positive].copy()
                            
                            # 单边谱幅度处理：除直流分量外，其他分量乘以2
                            amplitude[1:] = amplitude[1:] * 2
                        
                        # 如果需要归一化到N（可选），可以取消下面的注释
                        # amplitude = amplitude / N
                        
                        logs.append(f"采样频率: {fs:.2f} Hz")
                        logs.append(f"频率分辨率: {fs/N:.4f} Hz")
                        logs.append(f"最大频率: {freq[-1]:.2f} Hz")
                    else:
                        freq = np.array([])
                        amplitude = np.array([])
                    fft_time = time.time() - fft_start_time
                    logs.append(f"FFT计算耗时: {fft_time:.4f}秒")
                    logs.append(f"FFT点数: {len(freq)}")
                    # ====== END FFT ======

                    logs.append(f"计算统计数据耗时: {time.time() - calculate_start_time:.2f}秒")
                    
                    data = {
                        'channel_number': channel_name,
                        'X_value': list(data_x),
                        'Y_value': list(data_y),
                        'X_unit': 's',
                        'Y_unit': str(unit) if unit is not None else 'Y',  # 确保单位是字符串类型
                        'is_downsampled': is_downsampled,
                        'is_upsampled': is_upsampled,
                        'points': len(data_x),
                        'originalFrequency': original_frequency_khz,
                        # 添加新的统计数据
                        'stats': {
                            'y_min': y_min,
                            'y_max': y_max,
                            'y_mean': y_mean,
                            'y_median': y_median,
                            'y_std': y_std,
                            'x_min': x_min,
                            'x_max': x_max,
                            'y_axis_min': y_axis_min,
                            'y_axis_max': y_axis_max
                        },
                        'is_digital': is_digital,
                        'Y_normalized': y_normalized,
                        # 新增FFT结果
                        'freq': freq.tolist(),
                        'amplitude': amplitude.tolist(),
                    }
                    
                    # 使用orjson替代标准json进行序列化，大幅提升性能
                    serialize_start_time = time.time()
                    response = OrJsonResponse(data)
                    logs.append(f"响应创建耗时: {time.time() - serialize_start_time:.2f}秒")
                    
                    logs.append(f"数据库遍历总耗时: {time.time() - db_start_time:.2f}秒")
                    logs.append(f"总耗时: {time.time() - start_time:.2f}秒")
                    
                    # 打印表格形式的日志
                    width = 80
                    
                    # 计算字符串显示宽度的函数
                    def display_width(s):
                        width = 0
                        for c in s:
                            # 东亚宽字符（中文、日文等）计为2个单位宽度
                            if unicodedata.east_asian_width(c) in ['F', 'W']:
                                width += 2
                            else:
                                width += 1
                        return width
                    
                    # 根据显示宽度调整字符串格式化
                    def format_str(s, width, align='<'):
                        # 计算实际显示宽度
                        disp_width = display_width(s)
                        # 调整padding以适应显示宽度
                        padding = width - disp_width
                        if padding < 0:
                            padding = 0
                        
                        if align == '^':  # 居中对齐
                            left_padding = padding // 2
                            right_padding = padding - left_padding
                            return ' ' * left_padding + s + ' ' * right_padding
                        elif align == '>':  # 右对齐
                            return ' ' * padding + s
                        else:  # 左对齐
                            return s + ' ' * padding
                    
                    print(f"+{'-'*width}+")
                    title = '请求通道数据概览'
                    title_padding = width - 2 - display_width(title)
                    print(f"| {' ' * (title_padding//2)}{title}{' ' * (title_padding - title_padding//2)} |")
                    print(f"+{'-'*width}+")
                    for log in logs:
                        if ":" in log:
                            key, value = log.split(":", 1)
                            key_str = key + ':'
                            value_str = value.strip()
                            # 固定键宽度为25，值宽度为width-27
                            formatted_key = format_str(key_str, 25)
                            formatted_value = format_str(value_str, width-27, '>')
                            print(f"| {formatted_key}{formatted_value} |")
                        else:
                            formatted_log = format_str(log, width-2, '^')
                            print(f"| {formatted_log} |")
                    print(f"+{'-'*width}+")
                    
                    return response
                    
            logs.append(f"数据库遍历总耗时: {time.time() - db_start_time:.2f}秒")
            logs.append(f"总耗时: {time.time() - start_time:.2f}秒")
            
            # 打印表格形式的日志
            width = 80
            
            # 计算字符串显示宽度的函数
            def display_width(s):
                width = 0
                for c in s:
                    # 东亚宽字符（中文、日文等）计为2个单位宽度
                    if unicodedata.east_asian_width(c) in ['F', 'W']:
                        width += 2
                    else:
                        width += 1
                return width
            
            # 根据显示宽度调整字符串格式化
            def format_str(s, width, align='<'):
                # 计算实际显示宽度
                disp_width = display_width(s)
                # 调整padding以适应显示宽度
                padding = width - disp_width
                if padding < 0:
                    padding = 0
                
                if align == '^':  # 居中对齐
                    left_padding = padding // 2
                    right_padding = padding - left_padding
                    return ' ' * left_padding + s + ' ' * right_padding
                elif align == '>':  # 右对齐
                    return ' ' * padding + s
                else:  # 左对齐
                    return s + ' ' * padding
            
            print(f"+{'-'*width}+")
            title = '请求通道数据概览'
            title_padding = width - 2 - display_width(title)
            print(f"| {' ' * (title_padding//2)}{title}{' ' * (title_padding - title_padding//2)} |")
            print(f"+{'-'*width}+")
            for log in logs:
                if ":" in log:
                    key, value = log.split(":", 1)
                    key_str = key + ':'
                    value_str = value.strip()
                    # 固定键宽度为25，值宽度为width-27
                    formatted_key = format_str(key_str, 25)
                    formatted_value = format_str(value_str, width-27, '>')
                    print(f"| {formatted_key}{formatted_value} |")
                else:
                    formatted_log = format_str(log, width-2, '^')
                    print(f"| {formatted_log} |")
            print(f"+{'-'*width}+")
        else:
            return OrJsonResponse({'error': 'channel_key or channel_type parameter is missing'}, status=400)
    except Exception as e:
        # 打印错误信息
        width = 80
        
        # 计算字符串显示宽度的函数
        def display_width(s):
            width = 0
            for c in s:
                # 东亚宽字符（中文、日文等）计为2个单位宽度
                if unicodedata.east_asian_width(c) in ['F', 'W']:
                    width += 2
                else:
                    width += 1
            return width
        
        # 根据显示宽度调整字符串格式化
        def format_str(s, width, align='<'):
            # 计算实际显示宽度
            disp_width = display_width(s)
            # 调整padding以适应显示宽度
            padding = width - disp_width
            if padding < 0:
                padding = 0
            
            if align == '^':  # 居中对齐
                left_padding = padding // 2
                right_padding = padding - left_padding
                return ' ' * left_padding + s + ' ' * right_padding
            elif align == '>':  # 右对齐
                return ' ' * padding + s
            else:  # 左对齐
                return s + ' ' * padding
                
        print(f"+{'-'*width}+")
        title = '错误信息概览'
        title_padding = width - 2 - display_width(title)
        print(f"| {' ' * (title_padding//2)}{title}{' ' * (title_padding - title_padding//2)} |")
        print(f"+{'-'*width}+")
        
        error_msg = f"发生错误，总耗时: {time.time() - start_time:.2f}秒"
        formatted_error = format_str(error_msg, width-2)
        print(f"| {formatted_error} |")
        print(f"+{'-'*width}+")
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈跟踪
        return OrJsonResponse({'error': str(e)}, status=500)

# 添加一个插值采样函数
def upsample_to_frequency(x_values, y_values, target_freq=1000):
    """
    对数据进行插值采样到指定频率
    
    Args:
        x_values: 时间序列数据的X值（时间值）
        y_values: 对应的Y值
        target_freq: 目标频率，单位Hz
        
    Returns:
        插值采样后的x_values和y_values
    """
    # 计算原始频率
    time_span = max(x_values) - min(x_values)
    original_freq = len(x_values) / time_span
    
    # 如果目标频率小于或等于原始频率，直接返回原始数据
    if target_freq <= original_freq:
        return x_values, y_values
    
    # 基于目标频率计算总采样点数
    n_samples = int(time_span * target_freq)
    
    # 创建均匀分布的新时间点
    new_times = np.linspace(min(x_values), max(x_values), n_samples)
    
    # 使用线性插值计算对应的Y值
    new_values = np.interp(new_times, x_values, y_values)
    
    print(f"插值采样: 从 {len(x_values)} 点 增至 {len(new_times)} 点")
    return new_times, new_values

# 添加表达式解析类
class ExpressionParser:
    def __init__(self, get_channel_data_func):
        self.get_channel_data_func = get_channel_data_func
        self.tokens = []
        self.current = 0
        self.context_stack = []  # 用于跟踪解析上下文
    
    def parse(self, expression):
        """解析表达式并计算结果"""
        self.tokenize(expression)
        self.current = 0
        return self.expression()
    
    def tokenize(self, expression):
        """将表达式分词 - 增强版支持函数前缀"""
        # 去除多余的空格但保留函数调用中的逗号分隔符
        expression = ' '.join(expression.split())

        # 实现增强的分词器
        self.tokens = []
        i = 0

        while i < len(expression):
            char = expression[i]

            # 跳过空格
            if char == ' ':
                i += 1
                continue
            
            # 处理函数类型前缀 [Python] 或 [Matlab]
            if char == '[':
                start = i
                # 查找配对的右括号
                bracket_count = 1
                i += 1
                while i < len(expression) and bracket_count > 0:
                    if expression[i] == '[':
                        bracket_count += 1
                    elif expression[i] == ']':
                        bracket_count -= 1
                    i += 1
                
                # 检查是否是函数类型前缀
                prefix = expression[start:i]
                if prefix in ['[Python]', '[Matlab]']:
                    self.tokens.append(prefix)
                else:
                    # 如果不是已知的前缀，按字符处理
                    self.tokens.append('[')
                    i = start + 1
                continue
            
            # 处理运算符和括号
            if char in "+-*/(),&|!":
                self.tokens.append(char)
                i += 1
            # 处理数字（包括小数）
            elif char.isdigit() or char == '.':
                start = i
                # 继续读取数字和小数点
                while i < len(expression) and (expression[i].isdigit() or expression[i] == '.'):
                    i += 1
                token = expression[start:i]
                # 验证是否是有效的数字
                try:
                    float(token)
                    self.tokens.append(token)
                except ValueError:
                    # 如果不是有效数字，按字符处理
                    self.tokens.append(char)
                    i = start + 1
            # 处理标识符（通道标识符和函数名）
            elif char.isalpha() or char == '_':
                start = i
                # 继续读取直到遇到非标识符字符
                while i < len(expression) and (expression[i].isalnum() or expression[i] == '_'):
                    i += 1
                self.tokens.append(expression[start:i])
            else:
                i += 1

        return self.tokens
    
    def expression(self):
        """解析逻辑或运算（最低优先级）"""
        return self.logical_or()

    def logical_or(self):
        """解析逻辑或运算 (|)"""
        result = self.logical_and()

        while self.current < len(self.tokens) and self.tokens[self.current] == '|':
            operator = self.tokens[self.current]
            self.current += 1
            right = self.logical_and()
            result = self.or_operands(result, right)

        return result

    def logical_and(self):
        """解析逻辑与运算 (&)"""
        result = self.arithmetic_expression()

        while self.current < len(self.tokens) and self.tokens[self.current] == '&':
            operator = self.tokens[self.current]
            self.current += 1
            right = self.arithmetic_expression()
            result = self.and_operands(result, right)

        return result

    def arithmetic_expression(self):
        """解析加减运算"""
        result = self.term()

        while self.current < len(self.tokens) and self.tokens[self.current] in ['+', '-']:
            operator = self.tokens[self.current]
            self.current += 1
            right = self.term()

            if operator == '+':
                result = self.add_operands(result, right)
            elif operator == '-':
                result = self.subtract_operands(result, right)

        return result

    def add_operands(self, left, right):
        """执行加法运算，支持通道数据与常量的运算"""
        print(f"加法运算调试:")
        left_y = left.get('Y_value', [])
        right_y = right.get('Y_value', [])
        left_y_len = len(left_y) if isinstance(left_y, list) else f"scalar({left_y})"
        right_y_len = len(right_y) if isinstance(right_y, list) else f"scalar({right_y})"
        print(f"  left: is_constant={left.get('is_constant')}, channel_name={left.get('channel_name')}, Y_len={left_y_len}")
        print(f"  right: is_constant={right.get('is_constant')}, channel_name={right.get('channel_name')}, Y_len={right_y_len}")
        
        # 如果两个都是常量，返回常量结果
        if left.get('is_constant', False) and right.get('is_constant', False):
            result_value = left['Y_value'] + right['Y_value']
            return {
                'X_value': [],
                'Y_value': result_value,
                'channel_name': f"({left['channel_name']}+{right['channel_name']})",
                'is_constant': True
            }
        
        # 如果右操作数是常量
        if right.get('is_constant', False):
            constant_value = right['Y_value']
            result = left.copy()
            # 确保左操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            result['Y_value'] = [y + constant_value for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', 'unknown')
            right_name = right.get('channel_name', str(constant_value))
            result['channel_name'] = f"({left_name}+{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 如果左操作数是常量
        if left.get('is_constant', False):
            constant_value = left['Y_value']
            result = right.copy()
            # 确保右操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            result['Y_value'] = [y + constant_value for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', str(constant_value))
            right_name = right.get('channel_name', 'unknown')
            result['channel_name'] = f"({left_name}+{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 两个都是通道数据
        min_len = min(len(left['X_value']), len(right['X_value']))
        result = left.copy()
        result['X_value'] = left['X_value'][:min_len]
        result['Y_value'] = left['Y_value'][:min_len]
        right_y = right['Y_value'][:min_len]

        # 执行加法
        result['Y_value'] = [x + y for x, y in zip(result['Y_value'], right_y)]
        
        # 更新channel_name为表达式表示
        left_name = left.get('channel_name', 'unknown')
        right_name = right.get('channel_name', 'unknown')
        result['channel_name'] = f"({left_name}+{right_name})"
        result['is_expression_result'] = True  # 标记为表达式结果
        
        print(f"加法运算结果: channel_name={result['channel_name']}, is_expression_result={result.get('is_expression_result')}")
        
        return result

    def subtract_operands(self, left, right):
        """执行减法运算，支持通道数据与常量的运算"""
        # 如果两个都是常量，返回常量结果
        if left.get('is_constant', False) and right.get('is_constant', False):
            result_value = left['Y_value'] - right['Y_value']
            return {
                'X_value': [],
                'Y_value': result_value,
                'channel_name': f"({left['channel_name']}-{right['channel_name']})",
                'is_constant': True
            }
        
        # 如果右操作数是常量
        if right.get('is_constant', False):
            constant_value = right['Y_value']
            result = left.copy()
            # 确保左操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            result['Y_value'] = [y - constant_value for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', 'unknown')
            right_name = right.get('channel_name', str(constant_value))
            result['channel_name'] = f"({left_name}-{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 如果左操作数是常量
        if left.get('is_constant', False):
            constant_value = left['Y_value']
            result = right.copy()
            # 确保右操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            result['Y_value'] = [constant_value - y for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', str(constant_value))
            right_name = right.get('channel_name', 'unknown')
            result['channel_name'] = f"({left_name}-{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 两个都是通道数据
        min_len = min(len(left['X_value']), len(right['X_value']))
        result = left.copy()
        result['X_value'] = left['X_value'][:min_len]
        result['Y_value'] = left['Y_value'][:min_len]
        right_y = right['Y_value'][:min_len]

        # 执行减法
        result['Y_value'] = [x - y for x, y in zip(result['Y_value'], right_y)]
        
        # 更新channel_name为表达式表示
        left_name = left.get('channel_name', 'unknown')
        right_name = right.get('channel_name', 'unknown')
        result['channel_name'] = f"({left_name}-{right_name})"
        result['is_expression_result'] = True  # 标记为表达式结果
        
        return result
    
    def term(self):
        """解析乘除运算"""
        result = self.factor()

        while self.current < len(self.tokens) and self.tokens[self.current] in ['*', '/']:
            operator = self.tokens[self.current]
            self.current += 1
            right = self.factor()

            if operator == '*':
                result = self.multiply_operands(result, right)
            elif operator == '/':
                result = self.divide_operands(result, right)

        return result

    def multiply_operands(self, left, right):
        """执行乘法运算，支持通道数据与常量的运算"""
        # 如果两个都是常量，返回常量结果
        if left.get('is_constant', False) and right.get('is_constant', False):
            result_value = left['Y_value'] * right['Y_value']
            return {
                'X_value': [],
                'Y_value': result_value,
                'channel_name': f"({left['channel_name']}*{right['channel_name']})",
                'is_constant': True
            }
        
        # 如果右操作数是常量
        if right.get('is_constant', False):
            constant_value = right['Y_value']
            result = left.copy()
            # 确保左操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            result['Y_value'] = [y * constant_value for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', 'unknown')
            right_name = right.get('channel_name', str(constant_value))
            result['channel_name'] = f"({left_name}*{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 如果左操作数是常量
        if left.get('is_constant', False):
            constant_value = left['Y_value']
            result = right.copy()
            # 确保右操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            result['Y_value'] = [y * constant_value for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', str(constant_value))
            right_name = right.get('channel_name', 'unknown')
            result['channel_name'] = f"({left_name}*{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 两个都是通道数据
        min_len = min(len(left['X_value']), len(right['X_value']))
        result = left.copy()
        result['X_value'] = left['X_value'][:min_len]
        result['Y_value'] = left['Y_value'][:min_len]
        right_y = right['Y_value'][:min_len]

        # 执行乘法
        result['Y_value'] = [x * y for x, y in zip(result['Y_value'], right_y)]
        
        # 更新channel_name为表达式表示
        left_name = left.get('channel_name', 'unknown')
        right_name = right.get('channel_name', 'unknown')
        result['channel_name'] = f"({left_name}*{right_name})"
        result['is_expression_result'] = True  # 标记为表达式结果
        
        return result

    def divide_operands(self, left, right):
        """执行除法运算，支持通道数据与常量的运算"""
        # 如果两个都是常量，返回常量结果
        if left.get('is_constant', False) and right.get('is_constant', False):
            if right['Y_value'] == 0:
                raise ValueError("除数不能为0")
            result_value = left['Y_value'] / right['Y_value']
            return {
                'X_value': [],
                'Y_value': result_value,
                'channel_name': f"({left['channel_name']}/{right['channel_name']})",
                'is_constant': True
            }
        
        # 如果右操作数是常量
        if right.get('is_constant', False):
            constant_value = right['Y_value']
            if constant_value == 0:
                raise ValueError("除数不能为0")
            result = left.copy()
            # 确保左操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            result['Y_value'] = [y / constant_value for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', 'unknown')
            right_name = right.get('channel_name', str(constant_value))
            result['channel_name'] = f"({left_name}/{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 如果左操作数是常量
        if left.get('is_constant', False):
            constant_value = left['Y_value']
            result = right.copy()
            # 确保右操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            result['Y_value'] = [constant_value / y if y != 0 else float('inf') for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', str(constant_value))
            right_name = right.get('channel_name', 'unknown')
            result['channel_name'] = f"({left_name}/{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 两个都是通道数据
        min_len = min(len(left['X_value']), len(right['X_value']))
        result = left.copy()
        result['X_value'] = left['X_value'][:min_len]
        result['Y_value'] = left['Y_value'][:min_len]
        right_y = right['Y_value'][:min_len]

        # 执行除法，避免除以0
        result['Y_value'] = [x / y if y != 0 else float('inf') for x, y in zip(result['Y_value'], right_y)]
        
        # 更新channel_name为表达式表示
        left_name = left.get('channel_name', 'unknown')
        right_name = right.get('channel_name', 'unknown')
        result['channel_name'] = f"({left_name}/{right_name})"
        result['is_expression_result'] = True  # 标记为表达式结果
        
        return result

    def and_operands(self, left, right):
        """执行逻辑与运算，支持通道数据与常量的运算"""
        print(f"逻辑与运算调试:")
        left_y = left.get('Y_value', [])
        right_y = right.get('Y_value', [])
        left_y_len = len(left_y) if isinstance(left_y, list) else f"scalar({left_y})"
        right_y_len = len(right_y) if isinstance(right_y, list) else f"scalar({right_y})"
        print(f"  left: is_constant={left.get('is_constant')}, channel_name={left.get('channel_name')}, Y_len={left_y_len}")
        print(f"  right: is_constant={right.get('is_constant')}, channel_name={right.get('channel_name')}, Y_len={right_y_len}")
        
        # 如果两个都是常量，返回常量结果
        if left.get('is_constant', False) and right.get('is_constant', False):
            result_value = 1 if (left['Y_value'] != 0 and right['Y_value'] != 0) else 0
            return {
                'X_value': [],
                'Y_value': result_value,
                'channel_name': f"({left['channel_name']}&{right['channel_name']})",
                'is_constant': True
            }
        
        # 如果右操作数是常量
        if right.get('is_constant', False):
            constant_value = right['Y_value']
            result = left.copy()
            # 确保左操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            # 逻辑与：两个值都非0则为1，否则为0
            result['Y_value'] = [1 if (y != 0 and constant_value != 0) else 0 for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', 'unknown')
            right_name = right.get('channel_name', str(constant_value))
            result['channel_name'] = f"({left_name}&{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 如果左操作数是常量
        if left.get('is_constant', False):
            constant_value = left['Y_value']
            result = right.copy()
            # 确保右操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            # 逻辑与：两个值都非0则为1，否则为0
            result['Y_value'] = [1 if (y != 0 and constant_value != 0) else 0 for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', str(constant_value))
            right_name = right.get('channel_name', 'unknown')
            result['channel_name'] = f"({left_name}&{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 两个都是通道数据
        min_len = min(len(left['X_value']), len(right['X_value']))
        result = left.copy()
        result['X_value'] = left['X_value'][:min_len]
        result['Y_value'] = left['Y_value'][:min_len]
        right_y = right['Y_value'][:min_len]

        # 执行逻辑与：两个值都非0则为1，否则为0
        result['Y_value'] = [1 if (x != 0 and y != 0) else 0 for x, y in zip(result['Y_value'], right_y)]
        
        # 更新channel_name为表达式表示
        left_name = left.get('channel_name', 'unknown')
        right_name = right.get('channel_name', 'unknown')
        result['channel_name'] = f"({left_name}&{right_name})"
        result['is_expression_result'] = True  # 标记为表达式结果
        
        print(f"逻辑与运算结果: channel_name={result['channel_name']}, is_expression_result={result.get('is_expression_result')}")
        
        return result

    def or_operands(self, left, right):
        """执行逻辑或运算，支持通道数据与常量的运算"""
        print(f"逻辑或运算调试:")
        left_y = left.get('Y_value', [])
        right_y = right.get('Y_value', [])
        left_y_len = len(left_y) if isinstance(left_y, list) else f"scalar({left_y})"
        right_y_len = len(right_y) if isinstance(right_y, list) else f"scalar({right_y})"
        print(f"  left: is_constant={left.get('is_constant')}, channel_name={left.get('channel_name')}, Y_len={left_y_len}")
        print(f"  right: is_constant={right.get('is_constant')}, channel_name={right.get('channel_name')}, Y_len={right_y_len}")
        
        # 如果两个都是常量，返回常量结果
        if left.get('is_constant', False) and right.get('is_constant', False):
            result_value = 1 if (left['Y_value'] != 0 or right['Y_value'] != 0) else 0
            return {
                'X_value': [],
                'Y_value': result_value,
                'channel_name': f"({left['channel_name']}|{right['channel_name']})",
                'is_constant': True
            }
        
        # 如果右操作数是常量
        if right.get('is_constant', False):
            constant_value = right['Y_value']
            result = left.copy()
            # 确保左操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            # 逻辑或：至少一个值非0则为1，否则为0
            result['Y_value'] = [1 if (y != 0 or constant_value != 0) else 0 for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', 'unknown')
            right_name = right.get('channel_name', str(constant_value))
            result['channel_name'] = f"({left_name}|{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 如果左操作数是常量
        if left.get('is_constant', False):
            constant_value = left['Y_value']
            result = right.copy()
            # 确保右操作数的Y_value是列表
            if not isinstance(result['Y_value'], list):
                result['Y_value'] = [result['Y_value']]
            # 逻辑或：至少一个值非0则为1，否则为0
            result['Y_value'] = [1 if (y != 0 or constant_value != 0) else 0 for y in result['Y_value']]
            
            # 更新channel_name为表达式表示
            left_name = left.get('channel_name', str(constant_value))
            right_name = right.get('channel_name', 'unknown')
            result['channel_name'] = f"({left_name}|{right_name})"
            result['is_expression_result'] = True
            
            return result

        # 两个都是通道数据
        min_len = min(len(left['X_value']), len(right['X_value']))
        result = left.copy()
        result['X_value'] = left['X_value'][:min_len]
        result['Y_value'] = left['Y_value'][:min_len]
        right_y = right['Y_value'][:min_len]

        # 执行逻辑或：至少一个值非0则为1，否则为0
        result['Y_value'] = [1 if (x != 0 or y != 0) else 0 for x, y in zip(result['Y_value'], right_y)]
        
        # 更新channel_name为表达式表示
        left_name = left.get('channel_name', 'unknown')
        right_name = right.get('channel_name', 'unknown')
        result['channel_name'] = f"({left_name}|{right_name})"
        result['is_expression_result'] = True  # 标记为表达式结果
        
        print(f"逻辑或运算结果: channel_name={result['channel_name']}, is_expression_result={result.get('is_expression_result')}")
        
        return result

    def not_operand(self, operand):
        """执行逻辑非运算"""
        print(f"逻辑非运算调试:")
        operand_y = operand.get('Y_value', [])
        operand_y_len = len(operand_y) if isinstance(operand_y, list) else f"scalar({operand_y})"
        print(f"  operand: is_constant={operand.get('is_constant')}, channel_name={operand.get('channel_name')}, Y_len={operand_y_len}")
        
        # 如果是常量，返回常量结果
        if operand.get('is_constant', False):
            result_value = 1 if operand['Y_value'] == 0 else 0
            return {
                'X_value': [],
                'Y_value': result_value,
                'channel_name': f"(!{operand['channel_name']})",
                'is_constant': True
            }
        
        # 对于通道数据
        result = operand.copy()
        # 确保Y_value是列表
        if not isinstance(result['Y_value'], list):
            result['Y_value'] = [result['Y_value']]
        
        # 逻辑非：0变为1，非0变为0
        result['Y_value'] = [1 if y == 0 else 0 for y in result['Y_value']]
        
        # 更新channel_name为表达式表示
        operand_name = operand.get('channel_name', 'unknown')
        result['channel_name'] = f"(!{operand_name})"
        result['is_expression_result'] = True  # 标记为表达式结果
        
        print(f"逻辑非运算结果: channel_name={result['channel_name']}, is_expression_result={result.get('is_expression_result')}")
        
        return result
    
    def factor(self):
        """解析括号、通道标识符、数字常量和函数调用（支持前缀），以及一元非运算符"""
        if self.current < len(self.tokens):
            token = self.tokens[self.current]

            # 处理一元非运算符
            if token == '!':
                self.current += 1
                operand = self.factor()
                return self.not_operand(operand)

            # 处理括号表达式
            elif token == '(':
                self.current += 1
                result = self.expression()

                # 必须有匹配的右括号
                if self.current < len(self.tokens) and self.tokens[self.current] == ')':
                    self.current += 1
                    return result
                else:
                    raise ValueError("缺少右括号")

            # 处理数字常量
            elif self.is_number(token):
                self.current += 1
                # 返回数字常量，格式与通道数据一致
                return {
                    'X_value': [],  # 数字常量没有X轴数据
                    'Y_value': float(token),  # 数字常量作为标量值
                    'channel_name': str(token),
                    'is_constant': True  # 标记为常量
                }

            # 处理函数类型前缀
            elif token in ['[Python]', '[Matlab]']:
                prefix = token
                self.current += 1
                
                # 下一个token应该是函数名
                if self.current < len(self.tokens):
                    function_name = self.tokens[self.current]
                    # 检查是否是函数调用（有左括号）
                    if (self.current + 1 < len(self.tokens) and 
                        self.tokens[self.current + 1] == '('):
                        return self.parse_function_call(function_name, prefix)
                    else:
                        raise ValueError(f"期望在 {prefix} 后有函数调用")
                else:
                    raise ValueError(f"期望在 {prefix} 后有函数名")

            # 处理通道标识符或函数调用（无前缀）
            elif token.isalpha() or '_' in token:
                # 检查是否是函数调用
                if self.current + 1 < len(self.tokens) and self.tokens[self.current + 1] == '(':
                    return self.parse_function_call(token)
                else:
                    self.current += 1
                    # 处理通道标识符
                    channel_key = token

                    # 检查是否是通道键格式（通道名_炮号）
                    if '_' in channel_key and len(channel_key.split('_')) == 2:
                        # 根据上下文决定处理方式
                        if self.should_return_channel_string():
                            # 在导入函数参数中，返回通道名字符串
                            print(f"导入函数参数 - 识别通道键: {channel_key}，返回通道名字符串")
                            return {
                                'X_value': [],
                                'Y_value': channel_key,  # 使用通道名作为值
                                'channel_name': channel_key,
                                'is_constant': False,
                                'is_channel_name': True  # 标记这是一个通道名参数
                            }
                        else:
                            # 在表达式运算或内置函数中，获取实际通道数据
                            print(f"表达式运算 - 识别通道键: {channel_key}，获取通道数据")
                            result = self._get_channel_data_safely(channel_key)
                            print(f"factor方法返回的通道数据: channel_name={result.get('channel_name')}, is_constant={result.get('is_constant')}")
                            return result
                    else:
                        # 不是标准通道键格式，尝试获取通道数据
                        return self._get_channel_data_safely(channel_key)
    
    def _get_channel_data_safely(self, channel_key):
        """安全地获取通道数据，失败时回退到通道名字符串"""
        try:
            # 直接使用传入的函数获取通道数据，传递None作为请求参数（由函数内部处理）
            response = self.get_channel_data_func(None, channel_key)

            if hasattr(response, 'content'):
                # 对于HttpResponse对象
                try:
                    channel_data = json.loads(response.content.decode('utf-8'))
                except Exception:
                    raise ValueError(f"解析通道 {channel_key} 返回数据失败")
            else:
                # 对于JsonResponse对象
                channel_data = response

            # 检查返回的数据是否有效
            if 'error' in channel_data:
                raise ValueError(f"获取通道 {channel_key} 数据失败: {channel_data['error']}")

            # 确保返回的数据包含所需的键
            if 'X_value' not in channel_data or 'Y_value' not in channel_data:
                raise ValueError(f"通道 {channel_key} 返回数据格式不正确，缺少 X_value 或 Y_value")

            # 标记为通道数据
            channel_data['is_constant'] = False
            
            # 确保channel_name字段正确设置
            if 'channel_name' not in channel_data:
                channel_data['channel_name'] = channel_key
            
            print(f"成功获取通道 {channel_key} 数据，数据点数: {len(channel_data.get('Y_value', []))}")
            print(f"通道数据的channel_name: {channel_data.get('channel_name')}")
            return channel_data
        
        except Exception as e:
            # 获取通道数据失败时，根据上下文决定处理方式
            if self.should_return_channel_string():
                print(f"导入函数参数 - 获取通道 {channel_key} 数据失败: {str(e)}，回退到通道名字符串")
                return {
                    'X_value': [],
                    'Y_value': channel_key,  # 使用通道名作为值
                    'channel_name': channel_key,
                    'is_constant': False,
                    'is_channel_name': True  # 标记这是一个通道名参数
                }
            else:
                # 在表达式运算中，失败就是失败
                print(f"表达式运算 - 获取通道 {channel_key} 数据失败: {str(e)}")
                raise ValueError(f"获取通道 {channel_key} 数据失败: {str(e)}")

        raise ValueError(f"意外的标记: {self.tokens[self.current] if self.current < len(self.tokens) else 'EOF'}")

    def is_number(self, token):
        """检查token是否是数字"""
        try:
            float(token)
            return True
        except ValueError:
            return False
    
    def parse_function_call(self, function_name, prefix=None):
        """解析函数调用 - 增强版支持前缀和嵌套表达式"""
        self.current += 1  # 跳过函数名
        
        if self.current >= len(self.tokens) or self.tokens[self.current] != '(':
            raise ValueError(f"函数 {function_name} 缺少左括号")
        
        self.current += 1  # 跳过左括号
        
        # 推入函数调用上下文
        context_info = {
            'type': 'function_call',
            'function_name': function_name,
            'prefix': prefix,
            'is_imported_function': bool(prefix or function_name not in ['FFT', 'Pca'])
        }
        self.context_stack.append(context_info)
        
        # 解析参数列表
        args = []
        arg_index = 0
        while self.current < len(self.tokens) and self.tokens[self.current] != ')':
            if self.tokens[self.current] == ',':
                self.current += 1  # 跳过逗号
                arg_index += 1
                continue
            
            # 推入参数上下文
            param_context = {
                'type': 'function_argument',
                'function_name': function_name,
                'arg_index': arg_index,
                'is_imported_function': context_info['is_imported_function']
            }
            self.context_stack.append(param_context)
            
            # 解析参数 - 支持完整的表达式（包括嵌套函数调用）
            arg = self.expression()
            
            # 弹出参数上下文
            self.context_stack.pop()
            
            args.append(arg)
            
            # 如果下一个token是逗号，继续解析下一个参数
            if (self.current < len(self.tokens) and 
                self.tokens[self.current] == ','):
                continue
            # 如果下一个token是右括号，结束参数解析
            elif (self.current < len(self.tokens) and 
                  self.tokens[self.current] == ')'):
                break
            else:
                # 如果既不是逗号也不是右括号，可能有语法错误
                if self.current < len(self.tokens):
                    raise ValueError(f"函数 {function_name} 参数解析错误，意外的token: {self.tokens[self.current]}")
                else:
                    raise ValueError(f"函数 {function_name} 参数解析未完成")
        
        if self.current >= len(self.tokens) or self.tokens[self.current] != ')':
            raise ValueError(f"函数 {function_name} 缺少右括号")
        
        self.current += 1  # 跳过右括号
        
        # 弹出函数调用上下文
        self.context_stack.pop()
        
        # 调用相应的函数处理
        return self.call_function(function_name, args, prefix)
    
    def should_return_channel_string(self):
        """判断当前上下文是否应该返回通道名字符串而不是通道数据"""
        # 检查是否在导入函数的参数中，且这个参数是单独的通道名
        for context in reversed(self.context_stack):
            if context.get('type') == 'function_argument':
                # 如果是导入函数的参数
                if context.get('is_imported_function', False):
                    # 需要进一步检查是否是单独的通道名（非表达式）
                    return self._is_single_channel_argument()
        return False
    
    def _is_single_channel_argument(self):
        """检查当前是否是单独的通道名参数（非表达式）"""
        # 如果下一个token是运算符，说明这是表达式的一部分
        if self.current < len(self.tokens):
            next_token = self.tokens[self.current]
            if next_token in ['+', '-', '*', '/', '(']:
                return False  # 这是表达式，不是单独的通道名
        
        # 检查前一个token是否是运算符
        if self.current > 1:
            prev_token = self.tokens[self.current - 2]  # current已经+1了，所以-2
            if prev_token in ['+', '-', '*', '/', ')']:
                return False  # 这是表达式的一部分
        
        return True  # 看起来是单独的通道名
    
    def is_in_expression_context(self):
        """判断是否在表达式运算上下文中（需要实际数据）"""
        # 如果没有函数上下文，或者在内置函数中，都需要实际数据
        for context in reversed(self.context_stack):
            if context.get('type') == 'function_argument':
                # 在内置函数参数中，需要实际数据
                return not context.get('is_imported_function', False)
        return True  # 默认需要实际数据
    
    def parse_function_argument(self):
        """专门用于解析函数参数 - 对于导入函数，通道名参数返回字符串表示"""
        if self.current < len(self.tokens):
            token = self.tokens[self.current]

            # 处理括号表达式
            if token == '(':
                self.current += 1
                result = self.expression()

                # 必须有匹配的右括号
                if self.current < len(self.tokens) and self.tokens[self.current] == ')':
                    self.current += 1
                    return result
                else:
                    raise ValueError("缺少右括号")

            # 处理数字常量
            elif self.is_number(token):
                self.current += 1
                # 返回数字常量，格式与通道数据一致
                return {
                    'X_value': [],  # 数字常量没有X轴数据
                    'Y_value': float(token),  # 数字常量作为标量值
                    'channel_name': str(token),
                    'is_constant': True  # 标记为常量
                }

            # 处理函数类型前缀
            elif token in ['[Python]', '[Matlab]']:
                prefix = token
                self.current += 1
                
                # 下一个token应该是函数名
                if self.current < len(self.tokens):
                    function_name = self.tokens[self.current]
                    # 检查是否是函数调用（有左括号）
                    if (self.current + 1 < len(self.tokens) and 
                        self.tokens[self.current + 1] == '('):
                        return self.parse_function_call(function_name, prefix)
                    else:
                        raise ValueError(f"期望在 {prefix} 后有函数调用")
                else:
                    raise ValueError(f"期望在 {prefix} 后有函数名")

            # 处理通道标识符或函数调用（无前缀）
            elif token.isalpha() or '_' in token:
                # 检查是否是函数调用
                if self.current + 1 < len(self.tokens) and self.tokens[self.current + 1] == '(':
                    return self.parse_function_call(token)
                else:
                    # 对于导入函数的参数，如果看起来是通道名，直接返回通道名字符串
                    self.current += 1
                    return {
                        'X_value': [],
                        'Y_value': token,  # 直接使用token作为值
                        'channel_name': token,
                        'is_constant': False,
                        'is_channel_name': True  # 标记这是一个通道名参数
                    }

        raise ValueError(f"意外的标记: {self.tokens[self.current] if self.current < len(self.tokens) else 'EOF'}")
    
    def call_function(self, function_name, args, prefix=None):
        """调用函数（内置函数或导入函数）"""
        # 如果有前缀，说明是导入函数
        if prefix:
            return self.call_imported_function(function_name, args, prefix)
        else:
            # 检查是否是内置函数
            if function_name in ['FFT', 'Pca']:
                return self.call_builtin_function(function_name, args)
            else:
                # 可能是无前缀的导入函数，尝试调用
                return self.call_imported_function(function_name, args, None)
    
    def call_builtin_function(self, function_name, args):
        """调用内置函数"""
        if function_name == 'FFT':
            return self.fft_function(args)
        elif function_name == 'Pca':
            return self.pca_function(args)
        else:
            raise ValueError(f"未知的内置函数: {function_name}")
    
    def call_imported_function(self, function_name, args, prefix=None):
        """调用导入函数 - 重写版本支持正确的参数处理"""
        try:
            # 从imported_functions.json中查找函数信息
            if not os.path.exists(FUNCTIONS_FILE_PATH):
                raise ValueError("导入函数配置文件不存在")

            with open(FUNCTIONS_FILE_PATH, "r", encoding='utf-8') as f:
                functions_data = json.load(f)

            # 根据前缀确定函数类型
            preferred_extension = None
            if prefix == '[Python]':
                preferred_extension = '.py'
            elif prefix == '[Matlab]':
                preferred_extension = '.m'

            # 查找匹配的函数
            all_matches = [d for d in functions_data if d.get('name') == function_name]

            matched_func = None
            if preferred_extension:
                # 优先查找指定类型的函数
                for func in all_matches:
                    file_path = func.get('file_path', '')
                    if file_path.endswith(preferred_extension):
                        matched_func = func
                        break

            # 如果没找到指定类型的函数，使用第一个匹配的函数
            if not matched_func and all_matches:
                matched_func = all_matches[0]

            if not matched_func:
                raise ValueError(f"未找到导入函数: {function_name}")

            # 构建函数调用的参数数据 - 重写版本
            parameters = []
            parameter_strings = []  # 用于构建函数调用字符串
            
            print(f"导入函数 {function_name} 参数调试:")
            for i, arg in enumerate(args):
                print(f"  参数 {i}: 类型={type(arg)}")
                if isinstance(arg, dict):
                    print(f"    字典键: {list(arg.keys())}")
                    print(f"    is_constant: {arg.get('is_constant', 'None')}")
                    print(f"    is_channel_name: {arg.get('is_channel_name', 'None')}")
                    print(f"    is_expression_result: {arg.get('is_expression_result', 'None')}")
                    print(f"    channel_name: {arg.get('channel_name', 'None')}")
                    print(f"    function_type: {arg.get('function_type', 'None')}")
            
            for arg in args:
                if arg.get('is_constant', False):
                    # 常量参数直接使用数值
                    param_value = arg['Y_value']
                    parameters.append(param_value)
                    parameter_strings.append(str(param_value))
                    
                elif arg.get('is_channel_name', False):
                    # 通道名参数直接使用通道名字符串
                    channel_name = arg['channel_name']
                    parameters.append(channel_name)
                    parameter_strings.append(channel_name)
                    
                elif arg.get('is_expression_result', False):
                    # 这是表达式运算的结果，使用表达式字符串作为标识符
                    expr_str = arg.get('channel_name', 'expression_result')
                    parameters.append(expr_str)
                    parameter_strings.append(expr_str)
                    print(f"处理表达式结果参数: {expr_str}")
                    
                elif arg.get('function_type') == 'imported':
                    # 这是一个导入函数的执行结果，传递函数调用字符串
                    func_str = arg.get('channel_name', 'unknown_function')
                    parameters.append(func_str)
                    parameter_strings.append(func_str)
                    
                elif arg.get('function_type') == 'FFT':
                    # 这是FFT函数的结果，传递函数调用字符串
                    func_str = arg.get('channel_name', 'FFT_result')
                    parameters.append(func_str)
                    parameter_strings.append(func_str)
                    
                else:
                    # 通道数据或其他类型 - 对于导入函数，应该传递通道名而不是数据
                    if 'channel_name' in arg:
                        channel_name = arg['channel_name']
                        # 检查是否是通道键格式（通道名_炮号）
                        if '_' in channel_name and not channel_name.startswith('('):
                            # 这看起来像是通道键，直接使用
                            parameters.append(channel_name)
                            parameter_strings.append(channel_name)
                        else:
                            # 这是其他类型的数据，使用通道名或标识符
                            parameters.append(channel_name)
                            parameter_strings.append(channel_name)
                    else:
                        # 回退到未知标识符
                        parameters.append('unknown')
                        parameter_strings.append('unknown')

            # 构建函数调用字符串
            if prefix:
                original_func_str = f"{prefix}{function_name}({','.join(parameter_strings)})"
            else:
                original_func_str = f"{function_name}({','.join(parameter_strings)})"

            print(f"调用导入函数: {original_func_str}")
            print(f"参数列表: {parameters}")

            # 准备调用execute_function的数据
            execute_data = {
                "matched_function": matched_func,
                "target_file_name": function_name,
                "parameters": parameters,
                "original_func_str": original_func_str
            }

            # 调用execute_function执行导入函数
            result = execute_function(execute_data)

            if 'error' in result:
                raise ValueError(f"执行导入函数失败: {result['error']}")

            # 处理返回结果
            if 'result' in result:
                function_result = result['result']
                # 确保返回格式与通道数据一致
                if not isinstance(function_result, dict):
                    # 如果返回的不是字典，转换为标准格式
                    return {
                        'X_value': [],
                        'Y_value': function_result,
                        'channel_name': original_func_str,
                        'is_constant': True
                    }
                else:
                    # 确保有必要的键
                    if 'X_value' not in function_result:
                        function_result['X_value'] = []
                    if 'Y_value' not in function_result:
                        function_result['Y_value'] = []
                    if 'channel_name' not in function_result:
                        function_result['channel_name'] = original_func_str
                    
                    function_result['is_constant'] = False
                    function_result['function_type'] = 'imported'
                    print(f"导入函数 {function_name} 执行成功，返回数据点数: {len(function_result.get('Y_value', []))}")
                    return function_result
            else:
                raise ValueError("导入函数返回结果格式错误")

        except Exception as e:
            print(f"调用导入函数 {function_name} 失败: {str(e)}")
            raise ValueError(f"调用导入函数 {function_name} 失败: {str(e)}")
    
    def fft_function(self, args):
        """FFT函数实现"""
        if len(args) < 1:
            raise ValueError("FFT函数至少需要1个参数（通道数据）")
        
        # 获取通道数据
        channel_data = args[0]
        if channel_data.get('is_constant', False):
            raise ValueError("FFT函数的第一个参数必须是通道数据，不能是常量")
        
        # 获取频率限制参数（可选）
        frequency_limit = 1000.0  # 默认1000Hz
        if len(args) > 1:
            if args[1].get('is_constant', False):
                frequency_limit = float(args[1]['Y_value'])
            else:
                raise ValueError("FFT函数的第二个参数（频率限制）必须是数值常量")
        
        # 执行FFT计算
        x_values = np.array(channel_data['X_value'])
        y_values = np.array(channel_data['Y_value'])
        
        if len(y_values) < 2:
            raise ValueError("数据点数太少，无法进行FFT分析")
        
        # 计算采样间隔和频率
        dt = (x_values[-1] - x_values[0]) / (len(x_values) - 1)
        fs = 1.0 / dt
        
        # 执行FFT
        fft_result = np.fft.fft(y_values)
        amplitude = np.abs(fft_result)
        freq = np.fft.fftfreq(len(y_values), d=dt)
        
        # 只保留正频率部分
        positive_freq_indices = freq >= 0
        freq_positive = freq[positive_freq_indices]
        amplitude_positive = amplitude[positive_freq_indices]
        
        # 应用频率限制
        if frequency_limit > 0:
            freq_mask = freq_positive <= frequency_limit
            freq_positive = freq_positive[freq_mask]
            amplitude_positive = amplitude_positive[freq_mask]
        
        # 单边谱处理：除直流分量外，其他分量乘以2
        if len(amplitude_positive) > 1:
            amplitude_positive[1:] = amplitude_positive[1:] * 2
        
        return {
            'X_value': freq_positive.tolist(),
            'Y_value': amplitude_positive.tolist(),
            'channel_name': f"FFT({channel_data.get('channel_name', 'unknown')})",
            'X_unit': 'Hz',
            'Y_unit': 'Amplitude',
            'is_constant': False,
            'function_type': 'FFT'
        }
    
    def pca_function(self, args):
        """PCA函数实现"""
        if len(args) < 1:
            raise ValueError("PCA函数至少需要1个参数（通道数据）")
        
        # 获取通道数据
        channel_data = args[0]
        if channel_data.get('is_constant', False):
            raise ValueError("PCA函数的第一个参数必须是通道数据，不能是常量")
        
        # 获取主成分数量参数（可选）
        n_components = 2  # 默认2个主成分
        if len(args) > 1:
            if args[1].get('is_constant', False):
                n_components = int(args[1]['Y_value'])
            else:
                raise ValueError("PCA函数的第二个参数（主成分数量）必须是数值常量")
        
        # 获取窗口大小参数（可选）
        window_size = 100  # 默认窗口大小
        if len(args) > 2:
            if args[2].get('is_constant', False):
                window_size = int(args[2]['Y_value'])
            else:
                raise ValueError("PCA函数的第三个参数（窗口大小）必须是数值常量")
        
        # 执行PCA分析
        x_values = np.array(channel_data['X_value'])
        y_values = np.array(channel_data['Y_value'])
        
        if len(y_values) < window_size:
            raise ValueError(f"数据点数({len(y_values)})少于窗口大小({window_size})")
        
        # 检查sklearn是否可用
        if not sklearn_available:
            raise ValueError("PCA功能需要安装scikit-learn库")
        
        # 创建滑动窗口数据矩阵
        n_windows = len(y_values) - window_size + 1
        window_data = np.zeros((n_windows, window_size))
        
        for i in range(n_windows):
            window_data[i] = y_values[i:i + window_size]
        
        # 执行PCA
        pca = PCA(n_components=min(n_components, window_size))
        principal_components = pca.fit_transform(window_data)
        
        # 计算对应的时间轴（窗口中心时间）
        window_centers = []
        for i in range(n_windows):
            center_idx = i + window_size // 2
            window_centers.append(x_values[center_idx])
        
        # 返回第一主成分
        return {
            'X_value': window_centers,
            'Y_value': principal_components[:, 0].tolist(),
            'channel_name': f"PCA({channel_data.get('channel_name', 'unknown')})",
            'X_unit': 's',
            'Y_unit': 'PC1',
            'is_constant': False,
            'function_type': 'PCA',
            'pca_info': {
                'explained_variance_ratio': pca.explained_variance_ratio_.tolist(),
                'n_components': n_components,
                'window_size': window_size
            }
        }


def init_calculation(request):
    """初始化计算任务，返回唯一任务ID"""
    try:
        data = json.loads(request.body)
        expression = data.get('expression', '')
        db_suffix = data.get('db_suffix', '')
        
        # 生成唯一任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        calculation_tasks[task_id] = {
            'status': 'initialized',
            'step': '任务已创建',
            'progress': 0,
            'expression': expression,
            'db_suffix': db_suffix,
            'start_time': timezone.now().isoformat(),
            'last_update': timezone.now().isoformat(),
        }
        
        print(f"任务创建成功 - 任务ID: {task_id}, 表达式: {expression}, 数据库: {db_suffix}")
        print(f"当前活跃任务数: {len(calculation_tasks)}")
        
        return OrJsonResponse({'task_id': task_id, 'status': 'initialized'})
    except Exception as e:
        print(f"任务创建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return OrJsonResponse({'error': str(e)}, status=500)

@require_GET
def get_calculation_progress(request, task_id):
    """获取计算任务的进度"""
    try:
        print(f"查询任务进度 - 任务ID: {task_id}")
        print(f"当前活跃任务: {list(calculation_tasks.keys())}")
        
        if task_id not in calculation_tasks:
            print(f"任务未找到 - 任务ID: {task_id}")
            return OrJsonResponse({'error': '找不到指定的任务', 'task_id': task_id}, status=404)
        
        task_info = calculation_tasks[task_id]
        print(f"任务状态 - ID: {task_id}, 步骤: {task_info['step']}, 进度: {task_info['progress']}%, 状态: {task_info['status']}")
        
        # 清理过期任务（超过30分钟的任务），但不包括当前查询的任务
        current_time = timezone.now()
        expired_tasks = []
        for t_id in list(calculation_tasks.keys()):
            if t_id != task_id:  # 不清理当前查询的任务
                try:
                    last_update = datetime.fromisoformat(calculation_tasks[t_id]['last_update'])
                    if (current_time - last_update).total_seconds() > 1800:  # 30分钟
                        expired_tasks.append(t_id)
                except Exception as e:
                    print(f"解析任务更新时间出错: {str(e)}")
                    expired_tasks.append(t_id)
        
        # 清理过期任务
        for expired_id in expired_tasks:
            calculation_tasks.pop(expired_id, None)
            print(f"清理过期任务: {expired_id}")
        
        return OrJsonResponse(task_info)
    except Exception as e:
        print(f"获取任务进度出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return OrJsonResponse({'error': str(e)}, status=500)

def update_calculation_progress(task_id, step, progress, status='processing'):
    """更新计算任务的进度（供内部使用）"""
    if task_id in calculation_tasks:
        calculation_tasks[task_id].update({
            'status': status,
            'step': step,
            'progress': max(0, min(100, progress)),  # 确保进度在0-100范围内
            'last_update': timezone.now().isoformat()
        })
        
        # 添加详细日志以便调试
        print(f"进度更新 - 任务ID: {task_id}, 步骤: {step}, 进度: {progress}%, 状态: {status}")

def operator_strs(request):
    """
    处理计算请求
    """
    try:
        data = json.loads(request.body)
        anomaly_func_str = data.get('anomaly_func_str')
        channel_mess = data.get('channel_mess')
        task_id = data.get('task_id')
        # 获取采样率参数，如果未提供则默认为1.0 KHz
        sample_freq = data.get('sample_freq', 1.0)
        
        # 立即打印调试信息
        print(f"=== operator_strs 开始执行 ===")
        print(f"接收到任务ID: {task_id}")
        print(f"当前活跃任务: {list(calculation_tasks.keys())}")
        print(f"任务ID是否存在: {task_id in calculation_tasks if task_id else False}")
        
        # 如果提供了任务ID，检查并更新进度
        if task_id:
            if task_id in calculation_tasks:
                print(f"任务存在，开始更新进度...")
                update_calculation_progress(task_id, '开始解析表达式', 5)
            else:
                print(f"警告：任务ID {task_id} 不存在于 calculation_tasks 中！")
                # 重新创建任务（作为备用方案）
                calculation_tasks[task_id] = {
                    'status': 'processing',
                    'step': '开始解析表达式',
                    'progress': 5,
                    'expression': anomaly_func_str,
                    'start_time': timezone.now().isoformat(),
                    'last_update': timezone.now().isoformat(),
                }
                print(f"重新创建任务: {task_id}")
        else:
            print("警告：没有提供任务ID")
        
        print(f"收到计算请求: {anomaly_func_str}")
        print(f"采样率设置: {sample_freq} KHz")
        # print(f"通道数据: {len(channel_mess) if isinstance(channel_mess, list) else 1} 个通道")

        # 判定是否函数名是导入函数
        end_idx = anomaly_func_str.find('(')

        # 检查是否是带前缀的函数调用（如 [Python]FileName 或 [Matlab]FileName）
        is_prefixed_function = False
        actual_file_name = ""
        file_extension = ""

        if end_idx > 0 and ')' in anomaly_func_str[end_idx:]:
            # 检查是否以 [Python] 或 [Matlab] 开头
            if anomaly_func_str.startswith('[Python]') or anomaly_func_str.startswith('[Matlab]'):
                is_prefixed_function = True
                # 提取实际的文件名（去掉前缀）
                if anomaly_func_str.startswith('[Python]'):
                    actual_file_name = anomaly_func_str[8:end_idx]  # 去掉 "[Python]"
                    file_extension = '.py'
                elif anomaly_func_str.startswith('[Matlab]'):
                    actual_file_name = anomaly_func_str[8:end_idx]  # 去掉 "[Matlab]"
                    file_extension = '.m'

        # 原有的函数调用判断逻辑（不带前缀的函数）
        # 需要检查从开始到'('之间的所有字符是否构成有效的函数名（只能包含字母、数字、下划线）
        is_function_call = False
        if end_idx > 0 and ')' in anomaly_func_str[end_idx:]:
            potential_function_name = anomaly_func_str[:end_idx]
            # 检查是否是有效的函数名（只包含字母、数字、下划线，且以字母开头）
            is_function_call = (potential_function_name.isidentifier() and 
                              potential_function_name[0].isalpha() and
                              not any(op in potential_function_name for op in ['+', '-', '*', '/', '&', '|', '!']))

        # 如果是带前缀的函数调用，也认为是函数调用
        if is_prefixed_function:
            is_function_call = True

        # 创建通道键值映射，方便后续查找
        channel_map = {}
        if isinstance(channel_mess, list):
            for channel in channel_mess:
                # 使用"通道名_炮号"格式作为键
                channel_key = f"{channel['channel_name']}_{channel['shot_number']}"
                channel_map[channel_key] = channel
        else:
            # 兼容单通道情况
            channel_key = f"{channel_mess['channel_name']}_{channel_mess['shot_number']}"
            channel_map[channel_key] = channel_mess
            
        # 更新进度：数据准备完成
        if task_id and task_id in calculation_tasks:
            update_calculation_progress(task_id, '数据准备完成', 15)

        # 检查是否是函数调用
        if is_function_call:
            # 如果是带前缀的函数调用，使用实际的文件名
            if is_prefixed_function:
                target_file_name = actual_file_name
                target_extension = file_extension
            else:
                target_file_name = anomaly_func_str[:end_idx]
                target_extension = None  # 不指定扩展名，会查找所有匹配的文件
            print(f"识别到函数调用: {target_file_name} (原始字符串: {anomaly_func_str})")

            # 确保FUNCTIONS_FILE_PATH变量存在
            functions_file_path = os.path.join(settings.MEDIA_ROOT, "imported_functions.json")
            
            if os.path.exists(functions_file_path):
                with open(functions_file_path, "r", encoding='utf-8') as f:
                    functions_data = json.load(f)
                    # 添加详细调试信息
                    print(f"从文件读取到的函数数据类型: {type(functions_data)}")
                    print(f"函数数据长度: {len(functions_data) if isinstance(functions_data, list) else '不是列表'}")
                    for i, item in enumerate(functions_data):
                        print(f"条目 {i}: 类型={type(item)}, 内容={item}")
            else:
                functions_data = []
                print("函数文件不存在，使用空列表")
            
            # 根据文件名和类型查找导入的函数
            is_import_func = False
            matched_function = None
            for function in functions_data:
                # 检查function是否为字典类型，过滤掉无效条目
                if not isinstance(function, dict):
                    print(f"警告：跳过无效的函数条目（不是字典类型）: {function}")
                    continue
                
                file_path = function.get('file_path', '')
                # 提取文件名（不含扩展名）
                file_basename = os.path.splitext(os.path.basename(file_path))[0]
                
                # 如果指定了扩展名，需要同时匹配文件名和扩展名
                if target_extension:
                    if file_basename == target_file_name and file_path.endswith(target_extension):
                        is_import_func = True
                        matched_function = function
                        break
                else:
                    # 如果没有指定扩展名，只匹配文件名
                    if file_basename == target_file_name:
                        is_import_func = True
                        matched_function = function
                        break
                    
            # 更新进度：函数识别完成
            if task_id and task_id in calculation_tasks:
                update_calculation_progress(task_id, '函数识别完成', 25)

            if is_import_func:
                # 更新进度：开始执行导入函数
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, f'开始执行函数 {target_file_name}', 35)
                    
                func_data = {}
                func_data['matched_function'] = matched_function  # 传递匹配的函数信息
                func_data['target_file_name'] = target_file_name  # 传递目标文件名
                func_data['original_func_str'] = anomaly_func_str  # 添加原始函数调用字符串
                func_data['db_suffix'] = data.get('db_suffix')  # 从原始请求数据中获取数据库后缀
                # 提取函数参数（无论是否带前缀，参数提取方式都一样）
                params_str = anomaly_func_str[end_idx:].replace(" ", "").replace("(", "").replace(")", "")
                func_data['parameters'] = params_str.split(',')

                ##
                # 智能参数转换：识别通道名（格式：通道名_炮号）和数字
                ##
                def convert_parameter(param):
                    """智能转换参数：如果是数字则转换为float，如果是通道名则保持字符串"""
                    param = param.strip()
                    
                    # 检查是否是通道名格式（包含下划线，且下划线后面是数字）
                    if '_' in param:
                        parts = param.split('_')
                        if len(parts) == 2 and parts[1].isdigit():
                            # 这是通道名格式，保持字符串
                            return param
                    
                    # 尝试转换为数字
                    try:
                        # 先尝试转换为整数
                        if param.isdigit() or (param.startswith('-') and param[1:].isdigit()):
                            return int(param)
                        # 再尝试转换为浮点数
                        return float(param)
                    except ValueError:
                        # 如果都失败了，保持原始字符串
                        return param
                
                # 对所有参数进行智能转换
                func_data['parameters'] = [convert_parameter(param) for param in func_data['parameters']]

                # 更新进度：函数参数解析完成
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '函数参数解析完成', 45)

                # 更新进度：执行函数中
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, f'执行函数 {target_file_name} 中', 60)

                ret = execute_function(func_data)
                
                # 更新进度：函数执行完成
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '函数执行完成', 85)
                    
                # 标记计算完成，准备返回结果
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '计算完成，准备返回结果', 95)
                    
                # 最终完成状态会在前端处理结果后设置
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '计算完成', 100, 'completed')
                    
                return JsonResponse({"data": ret}, status=200)
            else:
                # 在这里检查是否是内置函数，如果是则使用表达式解析器处理
                print("operator-strs:", anomaly_func_str)
                
                # 更新进度：开始特殊函数处理
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '开始特殊函数处理', 35)
                
                # 定义内置函数列表
                builtin_functions = ['FFT', 'Pca']
                
                # 检查是否是内置函数调用
                is_builtin_function = False
                for builtin_func in builtin_functions:
                    if anomaly_func_str.startswith(builtin_func + '('):
                        is_builtin_function = True
                        break
                
                if is_builtin_function:
                    # 使用表达式解析器处理内置函数
                    print(f"识别到内置函数调用: {anomaly_func_str}")
                    
                    # 更新进度：处理内置函数
                    if task_id and task_id in calculation_tasks:
                        update_calculation_progress(task_id, f'处理内置函数: {anomaly_func_str}', 45)
                    
                    try:
                        # 创建表达式解析器
                        parser = ExpressionParser(lambda req, key: get_channel_data(create_mock_request(key, sample_freq), key))
                        
                        # 更新进度：解析内置函数表达式
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, '解析内置函数表达式', 55)
                        
                        # 解析表达式
                        result = parser.parse(anomaly_func_str)
                        
                        # 设置结果通道名
                        result['channel_name'] = anomaly_func_str
                        
                        # 更新进度：内置函数计算完成
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, '内置函数计算完成', 85)
                        
                        # 标记计算完成
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, '计算完成', 100, 'completed')
                        
                        return JsonResponse({"data": {"result": result}}, status=200)
                        
                    except Exception as e:
                        # 任务失败
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, f'内置函数处理出错: {str(e)}', 0, 'failed')
                        raise ValueError(f"处理内置函数时出错: {str(e)}")
                        
                elif anomaly_func_str[:3] == 'Pca':
                    # 保留旧的Pca处理逻辑，用于向后兼容
                    print('使用旧版Pca处理逻辑')
                    
                    # 更新进度：开始PCA分析
                    if task_id and task_id in calculation_tasks:
                        update_calculation_progress(task_id, '开始PCA分析', 45)
                        
                    anomaly_func_str = anomaly_func_str[3:]
                    params_list = anomaly_func_str.replace(" ", "")[1:-1].split(',')
                    [channel_name, period, condition_str, mode] = [params_list[0], ",".join(params_list[1:-2]),
                                                                   params_list[-2], params_list[-1]]
                    period = ast.literal_eval(period)
                    print('xxx')
                    # 使用第一个通道进行处理，保持向后兼容
                    channel_to_use = channel_mess[0] if isinstance(channel_mess, list) else channel_mess
                    
                    # 更新进度：PCA分析中
                    if task_id and task_id in calculation_tasks:
                        update_calculation_progress(task_id, 'PCA分析计算中', 70)
                        
                    ret = period_condition_anomaly(channel_name, period, condition_str, mode, channel_to_use)
                    
                    # 更新进度：PCA分析完成
                    if task_id and task_id in calculation_tasks:
                        update_calculation_progress(task_id, 'PCA分析完成', 90)

                    print(ret)
                    
                    # 标记计算完成
                    if task_id and task_id in calculation_tasks:
                        update_calculation_progress(task_id, '计算完成', 100, 'completed')
                        
                    return JsonResponse({"data": ret.tolist()}, status=200)
                else:
                    # 任务失败
                    if task_id and task_id in calculation_tasks:
                        update_calculation_progress(task_id, f'未知的函数: {target_file_name}', 0, 'failed')
                        
                    raise ValueError(f"未知的函数: {target_file_name}")
        else:
            # 更新进度：开始表达式解析
            if task_id and task_id in calculation_tasks:
                update_calculation_progress(task_id, '开始表达式解析', 30)
                
            # 检查表达式是否包含括号或运算符
            if '(' in anomaly_func_str or ')' in anomaly_func_str or any(op in anomaly_func_str for op in ['+', '-', '*', '/', '&', '|', '!']):
                # 使用表达式解析器处理带括号和运算优先级的表达式
                print(f"正在解析复杂表达式: {anomaly_func_str}")
                
                # 更新进度：解析复杂表达式
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '解析复杂表达式', 40)
                    
                # 修改表达式解析器初始化（新版本无需数据库选择）
                parser = ExpressionParser(lambda req, key: get_channel_data(create_mock_request(key, sample_freq), key))
                
                # 更新进度：获取通道数据
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '获取通道数据', 55)
                    
                result = parser.parse(anomaly_func_str)
                
                # 更新进度：计算表达式结果
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '计算表达式结果', 75)
                
                # 设置结果通道名
                result['channel_name'] = anomaly_func_str
                
                # 更新进度：表达式计算完成
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '表达式计算完成', 90)
                
                # 标记计算完成
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '计算完成', 100, 'completed')
                    
                return JsonResponse({"data": {"result": result}}, status=200)
            else:
                # 处理单通道情况
                channel_key = anomaly_func_str.strip()
                
                # 更新进度：查找通道数据
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, f'查找通道: {channel_key}', 40)
                    
                if channel_key in channel_map:
                    try:
                        # 更新进度：获取通道数据
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, f'获取通道数据: {channel_key}', 60)
                            
                        # 创建包含采样率的请求对象（新版本无需数据库选择）
                        mock_request = create_mock_request(channel_key, sample_freq)
                        response = get_channel_data(mock_request, channel_key)
                        channel_data = json.loads(response.content.decode('utf-8'))
                        
                        # 检查返回的数据是否有效
                        if 'error' in channel_data:
                            # 任务失败
                            if task_id and task_id in calculation_tasks:
                                update_calculation_progress(task_id, f'获取通道数据失败: {channel_data["error"]}', 0, 'failed')
                                
                            raise ValueError(f"获取通道 {channel_key} 数据失败: {channel_data['error']}")
                        
                        # 确保返回的数据包含所需的键
                        if 'X_value' not in channel_data or 'Y_value' not in channel_data:
                            # 任务失败
                            if task_id and task_id in calculation_tasks:
                                update_calculation_progress(task_id, f'通道数据格式错误: {channel_key}', 0, 'failed')
                                
                            raise ValueError(f"通道 {channel_key} 返回数据格式不正确，缺少 X_value 或 Y_value")
                        
                        # 设置通道名称
                        channel_data['channel_name'] = channel_key
                        
                        # 更新进度：处理通道数据
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, '处理通道数据完成', 85)
                            
                        # 标记计算完成
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, '计算完成', 100, 'completed')
                            
                        return JsonResponse({"data": {"result": channel_data}}, status=200)
                    except Exception as e:
                        # 任务失败
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, f'处理通道数据出错: {str(e)}', 0, 'failed')
                            
                        raise ValueError(f"处理通道 {channel_key} 数据时出错: {str(e)}")
                else:
                    # 任务失败
                    if task_id and task_id in calculation_tasks:
                        update_calculation_progress(task_id, f'未找到通道: {channel_key}', 0, 'failed')
                        
                    raise ValueError(f"未找到通道: {channel_key}")
    except Exception as e:
        # 如果提供了任务ID，标记任务失败
        if 'task_id' in locals() and locals().get('task_id') and locals().get('task_id') in calculation_tasks:
            update_calculation_progress(locals().get('task_id'), f'计算出错: {str(e)}', 0, 'failed')
            
        # 打印详细错误信息以便调试
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)

# 添加一个创建模拟请求对象的辅助函数
def create_mock_request(channel_key, sample_freq=1.0):
    """创建模拟请求对象用于获取通道数据（新版本无需数据库选择）"""
    class MockRequest:
        def __init__(self, channel_key, sample_freq):
            self.method = 'GET'  # 添加method属性，满足@require_GET装饰器要求
            self.GET = {
                'sample_mode': 'downsample',
                'sample_freq': str(sample_freq)
            }
            self.channel_key = channel_key
    
    return MockRequest(channel_key, sample_freq)

import importlib.util
import inspect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
import json

FUNCTIONS_FILE_PATH = os.path.join(settings.MEDIA_ROOT, "imported_functions.json")

# Import MATLAB engine if available
try:
    import matlab.engine # type: ignore

    matlab_engine_available = True
    eng = matlab.engine.start_matlab()
except ImportError:
    matlab_engine_available = False
    eng = None

# Helper function to read and update the JSON file
def update_functions_file(function_data):
    if os.path.exists(FUNCTIONS_FILE_PATH):
        with open(FUNCTIONS_FILE_PATH, "r", encoding='utf-8') as f:
            existing_data = json.load(f)
    else:
        existing_data = []

    # Check if function with the same name and file type already exists
    function_name = function_data.get('name')
    function_file_path = function_data.get('file_path', '')

    if function_name:
        # 获取当前文件的扩展名
        current_file_ext = ''
        if function_file_path.endswith('.py'):
            current_file_ext = '.py'
        elif function_file_path.endswith('.m'):
            current_file_ext = '.m'

        for existing_func in existing_data:
            if existing_func.get('name') == function_name:
                # 获取已存在文件的扩展名
                existing_file_path = existing_func.get('file_path', '')
                existing_file_ext = ''
                if existing_file_path.endswith('.py'):
                    existing_file_ext = '.py'
                elif existing_file_path.endswith('.m'):
                    existing_file_ext = '.m'

                # 只有当名称和文件类型都相同时才报错
                if current_file_ext == existing_file_ext:
                    file_type_name = 'Python' if current_file_ext == '.py' else 'MATLAB'
                    raise ValueError(f"算法 '{function_name}' ({file_type_name}) 已存在，不能重复导入")

    # Append the new function data to existing data
    existing_data.append(function_data)

    # Write updated data back to the JSON file
    with open(FUNCTIONS_FILE_PATH, "w", encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4, ensure_ascii=False)

# Function to load Python functions with parameter names
def load_python_functions(file_path):
    spec = importlib.util.spec_from_file_location("uploaded_module", file_path)
    uploaded_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uploaded_module)

    functions = {}
    for name, func in inspect.getmembers(uploaded_module, inspect.isfunction):
        params = inspect.signature(func).parameters
        param_names = [param_name for param_name in params]
        functions[name] = param_names
    return functions, uploaded_module


# Function to load MATLAB functions with parameter names
def load_matlab_functions(file_path):
    functions = {}
    if matlab_engine_available:
        # Add the path where the MATLAB file is located
        eng.addpath(os.path.dirname(file_path))

        # Extract function names and parameters using MATLAB commands
        try:
            # Use MATLAB to parse function definitions in the file
            # Extract function signatures as strings
            with open(file_path, 'r') as file:
                content = file.read()

            # Find all function definitions in the file
            matches = re.findall(r'function\s+\[?\w*\]?\s*=\s*(\w+)\s*\((.*?)\)', content)
            for match in matches:
                func_name, params = match
                param_names = [param.strip() for param in params.split(',')] if params else []
                functions[func_name] = param_names
        except Exception as e:
            print(f"Error loading MATLAB functions: {e}")
    return functions


# Global variable to store loaded Python module for function execution
loaded_module = None


@csrf_exempt
def upload_file(request):
    global loaded_module
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        fileInfo = json.loads(request.POST.get('fileInfo'))
        file_name = default_storage.save(f'uploads/{file.name}', file)
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)

        if file.name.endswith('.py'):
            # Load Python functions with parameter names
            functions, loaded_module = load_python_functions(file_path)
        elif file.name.endswith('.m') and matlab_engine_available:
            # Load MATLAB functions with parameter names
            functions = load_matlab_functions(file_path)
            loaded_module = None  # MATLAB functions don't use Python modules
        else:
            return JsonResponse({"error": "Unsupported file type or MATLAB engine not available"}, status=400)

        # Update the functions JSON file with the new functions
        try:
            for func_name, params in functions.items():
                # 添加文件路径信息到fileInfo中
                fileInfo['file_path'] = file_name  # 使用相对路径，相对于MEDIA_ROOT
                update_functions_file(fileInfo)
        except ValueError as e:
            # 如果函数已存在，删除已保存的文件并返回错误信息
            if os.path.exists(file_path):
                os.remove(file_path)
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse({"functions": [{"name": k, "parameters": v} for k, v in functions.items()]})

    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
def function_details(request, function_name):
    global loaded_module
    if loaded_module:
        for name, func in inspect.getmembers(loaded_module, inspect.isfunction):
            if name == function_name:
                params = list(inspect.signature(func).parameters.keys())
                return JsonResponse({"parameters": params})
    elif matlab_engine_available:
        return JsonResponse({"parameters": []})  # Customize if needed for MATLAB files
    return JsonResponse({"error": "Function not found"}, status=404)

@csrf_exempt
def view_imported_functions(request):
    if os.path.exists(FUNCTIONS_FILE_PATH):
        with open(FUNCTIONS_FILE_PATH, "r", encoding='utf-8') as f:
            functions_data = json.load(f)
    else:
        functions_data = []

    return JsonResponse({"imported_functions": functions_data})



def is_range_data(result):
    """
    判断函数结果是否为区间数据（X_range）而不是完整的通道数据
    
    Args:
        result: 函数执行结果
    
    Returns:
        bool: True 如果是区间数据，False 如果是完整通道数据
    """
    try:
        # 如果是列表且包含区间信息（有start_x, end_x等字段），认为是区间数据
        if isinstance(result, list) and len(result) > 0:
            first_item = result[0]
            if isinstance(first_item, dict):
                # 检查是否包含区间相关的字段
                range_fields = ['start_x', 'end_x', 'x_start', 'x_end', 'range_start', 'range_end']
                has_range_fields = any(field in first_item for field in range_fields)
                
                # 检查是否缺少完整通道数据的字段
                channel_fields = ['X_value', 'Y_value']
                has_channel_fields = all(field in first_item for field in channel_fields)
                
                # 如果有区间字段但没有完整通道数据字段，认为是区间数据
                if has_range_fields and not has_channel_fields:
                    return True
        
        # 如果是字典且包含区间信息但没有完整通道数据
        elif isinstance(result, dict):
            range_fields = ['start_x', 'end_x', 'x_start', 'x_end', 'range_start', 'range_end', 'ranges', 'intervals']
            has_range_fields = any(field in result for field in range_fields)
            
            channel_fields = ['X_value', 'Y_value']
            has_channel_fields = all(field in result for field in channel_fields)
            
            if has_range_fields and not has_channel_fields:
                return True
        
        return False
    except Exception as e:
        print(f"判断区间数据时出错: {str(e)}")
        return False

def normalize_algorithm_result(result):
    """
    统一处理算法结果，将不同格式的结果标准化
    
    Args:
        result: 算法执行的原始结果
    
    Returns:
        dict: 标准化后的结果字典
    """
    try:
        normalized_result = {}
        
        # 情况1: result是字典类型
        if isinstance(result, dict):
            normalized_result.update(result)
        
        # 情况2: result是列表类型 (直接作为X_range)
        elif isinstance(result, list):
            normalized_result["X_range"] = result
        
        # 情况3: result是字符串类型，可能是JSON字符串
        elif isinstance(result, str):
            try:
                # 尝试解析JSON字符串
                parsed_result = json.loads(result)
                if isinstance(parsed_result, dict):
                    # 如果解析后是字典，则合并到结果中
                    normalized_result.update(parsed_result)
                elif isinstance(parsed_result, list):
                    # 如果解析后是列表，作为X_range
                    normalized_result["X_range"] = parsed_result
                else:
                    # 其他类型的解析结果，作为algorithm_result
                    normalized_result["algorithm_result"] = parsed_result
            except (json.JSONDecodeError, TypeError):
                # 如果不是有效的JSON字符串，直接作为algorithm_result
                normalized_result["algorithm_result"] = result
        
        # 情况4: 其他类型 (数字、布尔值等)
        else:
            normalized_result["algorithm_result"] = result
        
        return normalized_result
        
    except Exception as e:
        print(f"标准化算法结果时出错: {str(e)}")
        # 发生错误时，将原始结果作为algorithm_result返回
        return {"algorithm_result": result}

@csrf_exempt
def execute_function(data):
    """
    执行函数
    """
    # 优先使用传递的匹配函数信息
    matched_func = data.get("matched_function")
    target_file_name = data.get("target_file_name")
    parameters = data.get("parameters", [])
    db_suffix = data.get("db_suffix")  # 获取数据库后缀
    original_func_str = data.get("original_func_str", "")  # 获取完整的函数调用字符串

    # 如果没有传递匹配的函数信息，则使用旧的查找方式（向后兼容）
    if not matched_func:
        function_name = data.get("function_name")
        if not function_name:
            return {"error": "No function information provided"}

        # 从imported_functions.json中查找函数信息
        if not os.path.exists(FUNCTIONS_FILE_PATH):
            return {"error": "Functions file not found"}

        with open(FUNCTIONS_FILE_PATH, "r", encoding='utf-8') as f:
            functions_data = json.load(f)

        # 根据原始函数调用字符串确定函数类型
        original_func_str = data.get("original_func_str", "")
        preferred_extension = None

        if original_func_str.startswith('[Python]'):
            preferred_extension = '.py'
        elif original_func_str.startswith('[Matlab]'):
            preferred_extension = '.m'

        # 查找匹配的函数，优先选择指定类型的函数
        all_matches = [d for d in functions_data if d.get('name') == function_name]

        if preferred_extension:
            # 优先查找指定类型的函数
            for func in all_matches:
                file_path = func.get('file_path', '')
                if file_path.endswith(preferred_extension):
                    matched_func = func
                    break

        # 如果没找到指定类型的函数，使用第一个匹配的函数
        if not matched_func and all_matches:
            matched_func = all_matches[0]

        if not matched_func:
            return {"error": f"Function '{function_name}' not found in imported functions"}

    if not matched_func:
        return {"error": f"Function file '{target_file_name}' not found in imported functions"}

    # 获取函数文件路径
    file_path = matched_func.get('file_path')
    if not file_path:
        return {"error": f"File path not found for function file '{target_file_name}'"}

    # 构建完整的文件路径
    full_file_path = os.path.join(settings.MEDIA_ROOT, file_path)
    if not os.path.exists(full_file_path):
        return {"error": f"Function file not found: {file_path}"}

    # 处理参数：将通道名转换为通道数据
    processed_parameters = []
    channel_data_for_result = []  # 保存所有通道数据用于最终结果合并
    
    for idx, param in enumerate(parameters):
        if idx < len(matched_func.get('input', [])):
            param_info = matched_func['input'][idx]
            if param_info.get('paraType') == '通道对象':
                try:
                    # 检查参数是否为表达式（包含运算符）
                    if any(op in str(param) for op in ['+', '-', '*', '/', '(', ')']):
                        # 参数是表达式，需要先解析表达式
                        print(f"检测到表达式参数: {param}")
                        
                        # 创建表达式解析器
                        def get_channel_data_for_parser(req, key):
                            mock_req = create_mock_request(key, 1.0)
                            return get_channel_data(mock_req, key)
                        parser = ExpressionParser(get_channel_data_for_parser)
                        
                        # 解析表达式得到结果
                        channel_data = parser.parse(str(param))
                        
                        # 设置通道名称
                        channel_data['channel_name'] = str(param)
                        
                        # 保存表达式计算的通道数据，用于最终结果合并
                        result_data_copy = channel_data.copy()
                        result_data_copy['expression'] = str(param)  # 标记这是表达式计算结果
                        channel_data_for_result.append(result_data_copy)
                        
                        print(f"表达式解析成功: {param}")
                    else:
                        # 参数是单个通道名，直接获取通道数据
                        mock_request = create_mock_request(param, 1.0)  # 使用默认采样率
                        response = get_channel_data(mock_request, param)
                        if hasattr(response, 'content'):
                            channel_data = json.loads(response.content.decode('utf-8'))
                        else:
                            channel_data = response

                        if 'error' in channel_data:
                            return {"error": f"Failed to get channel data for {param}: {channel_data['error']}"}
                        
                        # 保存单个通道数据，用于最终结果合并
                        result_data_copy = channel_data.copy()
                        result_data_copy['channel_name'] = str(param)
                        channel_data_for_result.append(result_data_copy)

                    # 对于Python函数，直接传递字典；对于MATLAB函数，转换为struct
                    if full_file_path.endswith('.py'):
                        processed_parameters.append(channel_data)
                    else:
                        # MATLAB函数需要转换为struct
                        fields_values = sum(([k, matlab.double(v) if isinstance(v, list) else v] for k, v in channel_data.items()), [])
                        processed_parameters.append(eng.feval('struct', *fields_values))
                except Exception as e:
                    return {"error": f"Error processing channel parameter {param}: {str(e)}"}
            else:
                # 非通道对象参数直接使用
                processed_parameters.append(param)
        else:
            processed_parameters.append(param)

    # 根据文件类型执行函数
    if full_file_path.endswith('.py'):
        # 执行Python函数
        try:
            print(f"尝试加载Python文件: {full_file_path}")
            print(f"文件是否存在: {os.path.exists(full_file_path)}")
            
            # 动态加载Python模块
            spec = importlib.util.spec_from_file_location("dynamic_module", full_file_path)
            dynamic_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dynamic_module)

            # 获取模块中所有的函数
            available_functions = [name for name, obj in inspect.getmembers(dynamic_module) if inspect.isfunction(obj)]
            print(f"模块中可用的函数: {available_functions}")
            
            # 选择要执行的函数
            func = None
            function_name_to_use = None
            
            # 如果有传递的目标文件名，尝试找到同名函数
            if target_file_name:
                if target_file_name in available_functions:
                    func = getattr(dynamic_module, target_file_name)
                    function_name_to_use = target_file_name
                    print(f"找到同名函数: {target_file_name}")
            
            # 如果没有找到同名函数，使用第一个可用函数
            if not func and available_functions:
                function_name_to_use = available_functions[0]
                func = getattr(dynamic_module, function_name_to_use)
                print(f"使用第一个可用函数: {function_name_to_use}")
            
            # 如果还是没有找到函数，返回错误
            if not func:
                return {"error": f"No functions found in file {full_file_path}"}

            print(f"执行函数: {function_name_to_use}，参数: {processed_parameters}")
            result = func(*processed_parameters)
            print(f"函数执行成功，结果: {result}")
            
            # 如果有通道数据，将其合并到result中
            if channel_data_for_result:
                print(f"合并通道数据到结果中: {len(channel_data_for_result)} 个")
                
                # 将函数返回结果和通道数据合并
                merged_result = {}
                
                # 首先使用标准化函数处理算法结果
                normalized_result = normalize_algorithm_result(result)
                merged_result.update(normalized_result)
                
                # 然后添加第一个通道数据的字段（如果有多个，取第一个）
                channel_data = channel_data_for_result[0]
                # 添加通道数据字段，但不覆盖已有的函数返回结果字段
                for key, value in channel_data.items():
                    if key not in merged_result and key not in ['expression', 'is_constant']:
                        merged_result[key] = value
                
                # 使用完整的函数调用字符串作为channel_name，如果没有则使用通道数据中的channel_name
                if original_func_str:
                    merged_result['channel_name'] = original_func_str
                elif 'channel_name' in channel_data:
                    merged_result['channel_name'] = channel_data['channel_name']
                if 'expression' in channel_data:
                    merged_result['expression'] = channel_data['expression']
                
                function_result = {"result": merged_result}
            else:
                # 即使没有通道数据，也使用标准化函数处理结果
                normalized_result = normalize_algorithm_result(result)
                function_result = {"result": normalized_result}
            
            return function_result
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"执行Python函数时出错: {str(e)}")
            print(f"错误堆栈: {error_traceback}")
            return {"error": f"Error executing Python function: {str(e)}"}

    elif full_file_path.endswith('.m') and matlab_engine_available:
        # 执行MATLAB函数
        try:
            # 添加MATLAB文件路径
            eng.addpath(os.path.dirname(full_file_path))

            # 对于MATLAB文件，函数名通常与文件名相同
            matlab_function_name = target_file_name if target_file_name else os.path.splitext(os.path.basename(full_file_path))[0]
            print(f"执行MATLAB函数: {matlab_function_name}")
            
            result = getattr(eng, matlab_function_name)(*processed_parameters)
            result = json.loads(result)
            
            # 如果有通道数据，将其合并到result中
            if channel_data_for_result:
                print(f"合并通道数据到结果中: {len(channel_data_for_result)} 个")
                
                # 将函数返回结果和通道数据合并
                merged_result = {}
                
                # 首先使用标准化函数处理算法结果
                normalized_result = normalize_algorithm_result(result)
                merged_result.update(normalized_result)
                
                # 然后添加第一个通道数据的字段（如果有多个，取第一个）
                channel_data = channel_data_for_result[0]
                # 添加通道数据字段，但不覆盖已有的函数返回结果字段
                for key, value in channel_data.items():
                    if key not in merged_result and key not in ['expression', 'is_constant']:
                        merged_result[key] = value
                
                # 使用完整的函数调用字符串作为channel_name，如果没有则使用通道数据中的channel_name
                if original_func_str:
                    merged_result['channel_name'] = original_func_str
                elif 'channel_name' in channel_data:
                    merged_result['channel_name'] = channel_data['channel_name']
                if 'expression' in channel_data:
                    merged_result['expression'] = channel_data['expression']
                
                function_result = {"result": merged_result}
            else:
                # 即使没有通道数据，也使用标准化函数处理结果
                normalized_result = normalize_algorithm_result(result)
                function_result = {"result": normalized_result}
            
            return function_result
        except Exception as e:
            return {"error": f"Error executing MATLAB function: {str(e)}"}
    else:
        return {"error": "Unsupported file type or MATLAB engine not available"}

def verify_user(request):
    """
    验证用户
    """
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return JsonResponse({'success': False, 'message': '用户名或密码不能为空'}, status=400)
            
        result = send_post_request(username, password)
        
        if '错误' in result:
            return JsonResponse({'success': False, 'message': result['错误']}, status=500)
            
        # 检查返回的消息是否包含错误信息
        if 'username or password error' in result.get('message', '').lower():
            return JsonResponse({'success': False, 'message': result['message']})
            
        return JsonResponse({'success': True, 'message': result.get('message', '')})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
def verify_username(request):
    """
    仅验证用户名是否存在（用于主平台集成）
    """
    try:
        data = json.loads(request.body)
        username = data.get('username')
        
        if not username:
            return JsonResponse({'success': False, 'message': '用户名不能为空'}, status=400)
        
        # 读取用户列表文件
        user_list_path = os.path.join('static', 'user_list.csv')
        if not os.path.exists(user_list_path):
            return JsonResponse({'success': False, 'message': '用户列表文件不存在'}, status=500)
        
        # 查找用户
        with open(user_list_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['username'] == username:
                    # 找到用户，返回权限信息
                    authority = int(row.get('power', 0))
                    real_name = row.get('real_name', username)
                    return JsonResponse({
                        'success': True, 
                        'message': f'用户 {real_name} 验证成功',
                        'authority': authority,
                        'real_name': real_name
                    })
        
        # 用户不存在
        return JsonResponse({'success': False, 'message': '用户不存在'}, status=404)
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

# 新增辅助函数：更新错误类型索引
def update_error_type_index(error_type, add_to_channel=None, remove_from_channel=None):
    """
    更新错误类型索引文件，添加或删除特定通道的索引
    
    Args:
        error_type (str): 错误类型名称
        add_to_channel (dict, optional): 需要添加到错误类型索引的通道信息，格式为 {"channel_name": 名称, "shot_number": 炮号}
        remove_from_channel (dict, optional): 需要从错误类型索引中移除的通道信息，格式为 {"channel_name": 名称, "shot_number": 炮号}
    """
    try:
        # 读取结构树数据，获取索引位置
        struct_tree_path = os.path.join('static', 'StructTree.json')
        with open(struct_tree_path, 'r', encoding='utf-8') as f:
            struct_tree = json.load(f)
            
        # 读取错误类型索引文件
        error_name_index_path = os.path.join('static', 'IndexFile', 'error_name_index.json')
        if os.path.exists(error_name_index_path):
            with open(error_name_index_path, 'r', encoding='utf-8') as f:
                error_name_index = json.load(f)
        else:
            error_name_index = {}
            
        # 如果错误类型不在索引中，初始化为空列表
        if error_type not in error_name_index:
            error_name_index[error_type] = []
            
        # 添加通道到索引
        if add_to_channel:
            # 查找通道在结构树中的索引位置
            channel_indices = []
            for idx, item in enumerate(struct_tree):
                if (item.get('channel_name') == add_to_channel['channel_name'] and 
                    str(item.get('shot_number')) == str(add_to_channel['shot_number'])):
                    channel_indices.append(idx)
                    
            # 将通道索引添加到错误类型索引中（去重）
            for idx in channel_indices:
                if idx not in error_name_index[error_type]:
                    error_name_index[error_type].append(idx)
                    
        # 从索引中移除通道
        if remove_from_channel:
            # 查找通道在结构树中的索引位置
            channel_indices = []
            for idx, item in enumerate(struct_tree):
                if (item.get('channel_name') == remove_from_channel['channel_name'] and 
                    str(item.get('shot_number')) == str(remove_from_channel['shot_number'])):
                    channel_indices.append(idx)
                    
            # 从错误类型索引中移除通道索引
            error_name_index[error_type] = [
                idx for idx in error_name_index[error_type] 
                if idx not in channel_indices
            ]
            
            # 如果错误类型索引为空，从索引中删除该错误类型
            if not error_name_index[error_type]:
                error_name_index.pop(error_type, None)
                
        # 保存更新后的索引文件
        with open(error_name_index_path, 'w', encoding='utf-8') as f:
            json.dump(error_name_index, f, ensure_ascii=False, indent=4)
            
        return True
    except Exception as e:
        print(f"更新错误类型索引出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

@csrf_exempt
def sync_error_data(request):
    """
    同步异常标注数据（只做添加，不清空原有数据），只操作MongoDB。
    """
    def format_manual_error(error, channel_name, shot_number):
        return {
            "person": error.get('person', 'unknown'),
            "diagnostic_name": error.get('anomalyDiagnosisName') or error.get('diagnostic_name') or error.get('诊断名称') or "",
            "channel_number": channel_name,
            "error_type": error.get('anomalyCategory') or error.get('error_type') or error.get('异常类别') or "",
            "shot_number": shot_number,
            "X_error": [[float(error.get('startX', 0)), float(error.get('endX', 0))]],
            "Y_error": [],
            "diagnostic_time": error.get('annotationTime', ''),
            "error_description": error.get('anomalyDescription', '')
        }
    try:
        data = json.loads(request.body)
        
        # 按炮号分组处理不同数据库
        channels_by_shot = {}
        for channel_data in data.get('channels', []):
            channel_key = channel_data['channelKey']
            channel_name, shot_number = channel_key.rsplit('_', 1)
            shot_number = str(shot_number)
            
            if shot_number not in channels_by_shot:
                channels_by_shot[shot_number] = []
            channels_by_shot[shot_number].append({
                'channel_key': channel_key,
                'channel_name': channel_name,
                'error_data': channel_data['errorData']
            })
        
        # 为每个炮号组找到对应的数据库并处理
        for shot_number, shot_channels in channels_by_shot.items():
            # 根据炮号找到对应的数据库
            db_name = get_database_name_for_shot(shot_number)
            
            if not db_name:
                print(f"警告: 未找到炮号 {shot_number} 对应的数据库")
                continue
                
            # 使用找到的数据库
            db = get_db_by_name(db_name)
            errors_collection = db["errors_data"]
            struct_trees_collection = db["struct_trees"]
            index_collection = db["index"]
            
            for channel_info in shot_channels:
                channel_name = channel_info['channel_name']
                manual_errors, machine_errors = channel_info['error_data']
                
                # 格式化人工异常
                formatted_manual_errors = [
                    format_manual_error(e, channel_name, shot_number)
                    for e in manual_errors
                    if (e.get('anomalyCategory') or e.get('error_type') or e.get('异常类别'))
                ]
                # 机器异常直接用原格式
                formatted_machine_errors = [
                    e for e in machine_errors
                    if (e.get('anomalyCategory') or e.get('error_type') or e.get('异常类别'))
                ]
                # 合并所有异常类型
                error_types = set()
                for error in formatted_manual_errors:
                    if error['error_type']:
                        error_types.add(error['error_type'])
                for error in formatted_machine_errors:
                    et = error.get('error_type') or error.get('anomalyCategory') or error.get('异常类别')
                    if et:
                        error_types.add(et)
                # 保存到MongoDB（每个异常类型一条记录，人工和机器分开）
                for error_type in error_types:
                    # 取该类型的人工异常和机器异常
                    manual_list = [e for e in formatted_manual_errors if e['error_type'] == error_type]
                    machine_list = [e for e in formatted_machine_errors if (e.get('error_type') or e.get('anomalyCategory') or e.get('异常类别')) == error_type]
                    errors_collection.update_one(
                        {
                            "shot_number": shot_number,
                            "channel_number": channel_name,
                            "error_type": error_type
                        },
                        {
                            "$set": {"data": [manual_list, machine_list]}
                        },
                        upsert=True
                    )
                # 2. 更新 struct_trees_collection
                struct_trees_collection.update_one(
                    {
                        "shot_number": shot_number,
                        "struct_tree.channel_name": channel_name
                    },
                    {
                        "$addToSet": {"struct_tree.$.error_name": {"$each": list(error_types)}}
                    }
                )
                # 3. 更新 index_collection
                for error_type in error_types:
                    index_collection.update_one(
                        {"key": "error_name"},
                        {"$addToSet": {f"index_data.{shot_number}.{error_type}": channel_name}},
                        upsert=True
                    )
        return JsonResponse({'message': '同步成功'})
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)

@csrf_exempt
def delete_error_data(request):
    """
    删除指定通道的指定错误类型数据，只操作MongoDB。
    """
    try:
        data = json.loads(request.body)
        diagnostic_name = data.get('diagnostic_name')
        channel_number = data.get('channel_number')
        shot_number = data.get('shot_number')
        error_type = data.get('error_type')
        
        if not all([diagnostic_name, channel_number, shot_number, error_type]):
            return JsonResponse({'error': '缺少必要参数', 'data': data}, status=400)
        
        shot_number = str(shot_number)
        shot_number_int = int(shot_number)
        
        # 根据炮号找到对应的数据库
        db_name = get_database_name_for_shot(shot_number)
        
        if not db_name:
            return JsonResponse({'error': f'未找到炮号 {shot_number} 对应的数据库'}, status=404)
        
        # 使用找到的数据库
        db = get_db_by_name(db_name)
        errors_collection = db["errors_data"]
        struct_trees_collection = db["struct_trees"]
        index_collection = db["index"]
        
        # 1. 删除 errors_collection 中的异常（只移除diagnostic_name对应的异常，若人工和机器都空则整个记录删除）
        doc = errors_collection.find_one({
            "shot_number": shot_number,
            "channel_number": channel_number,
            "error_type": error_type
        })
        if doc and "data" in doc:
            manual_errors, machine_errors = doc["data"]
            # 过滤掉diagnostic_name对应的异常
            manual_errors = [e for e in manual_errors if e.get('diagnostic_name') != diagnostic_name]
            machine_errors = [e for e in machine_errors if e.get('diagnostic_name') != diagnostic_name]
            if not manual_errors and not machine_errors:
                # 两个都空，直接删除整个记录
                errors_collection.delete_one({
                    "shot_number": shot_number,
                    "channel_number": channel_number,
                    "error_type": error_type
                })
            else:
                # 否则只更新
                errors_collection.update_one(
                    {
                        "shot_number": shot_number,
                        "channel_number": channel_number,
                        "error_type": error_type
                    },
                    {"$set": {"data": [manual_errors, machine_errors]}}
                )
        # 2. struct_trees_collection，删除struct_tree下对应通道的error_name中的异常类型
        struct_trees_collection.update_one(
            {
                "shot_number": shot_number,
                "struct_tree.channel_name": channel_number
            },
            {
                "$pull": {"struct_tree.$.error_name": error_type}
            }
        )
        # 检查error_name是否已空，若空则移除该字段
        doc = struct_trees_collection.find_one({"shot_number": shot_number})
        if doc and "struct_tree" in doc:
            for item in doc["struct_tree"]:
                if item.get("channel_name") == channel_number:
                    if "error_name" in item and (not item["error_name"] or len(item["error_name"]) == 0):
                        struct_trees_collection.update_one(
                            {"shot_number": shot_number, "struct_tree.channel_name": channel_number},
                            {"$unset": {"struct_tree.$.error_name": ""}}
                        )
        # 3. index_collection，删除index_data下对应炮号、异常类型下的通道名
        index_doc = index_collection.find_one({"key": "error_name"})
        if index_doc and "index_data" in index_doc:
            index_data = index_doc["index_data"]
            changed = False
            if shot_number in index_data:
                if error_type in index_data[shot_number]:
                    if channel_number in index_data[shot_number][error_type]:
                        index_data[shot_number][error_type].remove(channel_number)
                        changed = True
                    # 如果该异常类型下通道名列表为空则移除该异常类型
                    if not index_data[shot_number][error_type]:
                        del index_data[shot_number][error_type]
                        changed = True
                # 如果该炮号下所有异常类型都为空则移除该炮号
                if not index_data[shot_number]:
                    del index_data[shot_number]
                    changed = True
            if changed:
                index_collection.update_one(
                    {"key": "error_name"},
                    {"$set": {"index_data": index_data}}
                )
        return JsonResponse({'message': '删除成功'})
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


def bezier_to_points(bezier_segments, num_points=100):
    """将贝塞尔曲线段转换为归一化采样点序列"""
    if not bezier_segments or len(bezier_segments) < 2: return []
    
    # 生成曲线点
    points = []
    for i in range(len(bezier_segments) - 1):
        p0 = (bezier_segments[i]['x'], bezier_segments[i]['y'])
        p3 = (bezier_segments[i+1]['x'], bezier_segments[i+1]['y'])
        handle_out = bezier_segments[i].get('handleOut')
        handle_in = bezier_segments[i+1].get('handleIn')
        
        # 每段生成适当数量的点
        segment_points_count = max(5, num_points // (len(bezier_segments) - 1))
        
        # 如果有控制点，使用三次贝塞尔曲线；否则使用线性插值
        if handle_out and handle_in:
            p1 = (p0[0] + handle_out['x'], p0[1] + handle_out['y'])
            p2 = (p3[0] + handle_in['x'], p3[1] + handle_in['y'])
            for j in range(segment_points_count):
                t = j / (segment_points_count - 1) if segment_points_count > 1 else 0
                x = (1-t)**3 * p0[0] + 3*(1-t)**2 * t * p1[0] + 3*(1-t) * t**2 * p2[0] + t**3 * p3[0]
                y = (1-t)**3 * p0[1] + 3*(1-t)**2 * t * p1[1] + 3*(1-t) * t**2 * p2[1] + t**3 * p3[1]
                points.append((x, y))
        else:
            for j in range(segment_points_count):
                t = j / (segment_points_count - 1) if segment_points_count > 1 else 0
                points.append(((1-t) * p0[0] + t * p3[0], (1-t) * p0[1] + t * p3[1]))
    
    # 归一化曲线
    if points:
        x_values, y_values = zip(*points)
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        x_range = max(x_max - x_min, 0.0001)
        y_range = max(y_max - y_min, 0.0001)
        
        # 返回归一化后的点
        return [((x - x_min) / x_range, (y - y_min) / y_range) for x, y in points]
    return []


def sketch_query(request):
    """
    处理手绘查询请求，接收sampling、已选中的通道列表和绘制的路径数据
    """
    # 从请求中获取 JSON 数据
    data = json.loads(request.body)
    # 获取数据库后缀
    db_suffix = data.get('db_suffix')  # 新增参数
    db = get_db(db_suffix)
    # 获取采样率  单位KHz
    sampling = data.get('sampling')
    # 获取选择的通道列表
    selected_channels = data.get('selectedChannels')
    # 获取路径数据
    raw_query_pattern = data.get('rawQueryPattern')
    # 新增参数获取
    lowpass_amplitude = data.get('lowpassAmplitude')  # 前端已将ms转换为s
    x_filter_range = data.get('xFilterRange')
    y_filter_range = data.get('yFilterRange')
    pattern_repeat_count = data.get('patternRepeatCount')
    max_match_per_channel = data.get('maxMatchPerChannel')
    amplitude_limit_range = data.get('amplitudeLimitRange')
    time_span_limit_range = data.get('timeSpanLimitRange')  # 前端已将ms转换为s
    
    # selected_channels 格式为 [{'channel_name': 'B07_H', 'shot_number': '4470', 'channel_type': 'B'},...]
    # raw_query_pattern 格式为 [{'x': 0.1, 'y': 0.1, 'handleOut': {'x': 0.1, 'y': 0.1}, 'handleIn': {'x': 0.1, 'y': 0.1}},...] 为贝塞尔曲线
    print(f"接收到手绘查询请求: 采样率={sampling}KHz, 选择通道数={len(selected_channels)}, 路径点数={len(raw_query_pattern)}")
    
    try:
        # 将贝塞尔曲线转换为采样点序列并归一化
        normalized_curve = bezier_to_points(raw_query_pattern)
        
        # 创建修改后的通道数据获取函数
        def get_channel_data_local(channel, sampling_rate):
            """为模式匹配专门定制的获取通道数据的函数（新版本无需数据库选择）"""
            channel_key = f"{channel['channel_name']}_{channel['shot_number']}"
            
            # 使用统一的create_mock_request函数
            mock_request = create_mock_request(channel_key, sampling_rate)
            
            # 直接调用views中的get_channel_data函数
            response = get_channel_data(mock_request, channel_key)
            
            # 解析结果
            if hasattr(response, 'content'):
                try:
                    return json.loads(response.content.decode('utf-8'))
                except Exception as e:
                    print(f"解析通道数据失败: {str(e)}")
                    return None
            return None
        
        # 获取通道数据，执行模式匹配
        start_time = time.time()
        
        # 准备通道数据
        channel_data_list = []
        for channel in selected_channels:
            channel_data = get_channel_data_local(channel, sampling)
            if channel_data:
                # 添加通道信息到数据中
                channel_data['channel_name'] = channel['channel_name']
                channel_data['shot_number'] = channel['shot_number']
                channel_data_list.append(channel_data)
        
        # 执行模式匹配
        
        results = match_pattern(
            normalized_curve, channel_data_list,
            lowpass_amplitude=lowpass_amplitude,
            x_filter_range=x_filter_range,
            y_filter_range=y_filter_range,
            pattern_repeat_count=pattern_repeat_count,
            max_match_per_channel=max_match_per_channel,
            amplitude_limit_range=amplitude_limit_range,
            time_span_limit_range=time_span_limit_range
        )
        
        print(f"模式匹配完成, 耗时: {time.time() - start_time:.2f}秒, 找到匹配结果: {len(results)}个")
        
        return JsonResponse({
            'success': True,
            'results': results,
            'message': f'成功处理查询'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': f'处理查询时发生错误: {str(e)}'
        }, status=500)

@csrf_exempt
def get_channels_errors(request):
    """
    获取多个通道的异常数据，专门用于更新通道异常数据而不刷新整个列表
    支持自动跨数据库查询
    POST请求，参数格式：
    {
        "channels": [
            {
                "channel_name": "通道名",
                "shot_number": "炮号",
                "channel_type": "通道类型"
            },
            ...
        ]
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    try:
        data = json.loads(request.body)
        channels = data.get('channels', [])
        
        if not channels:
            return JsonResponse({'error': 'No channels provided'}, status=400)
        
        # 按炮号分组通道
        channels_by_shot = {}
        for channel_info in channels:
            shot_number = str(channel_info.get('shot_number', ''))
            if shot_number:
                if shot_number not in channels_by_shot:
                    channels_by_shot[shot_number] = []
                channels_by_shot[shot_number].append(channel_info)
        
        result = []
        
        # 为每个炮号组找到对应的数据库
        for shot_number, shot_channels in channels_by_shot.items():
            db_shot_mapping = find_databases_for_shot_numbers([shot_number])
            
            if not db_shot_mapping:
                # 如果找不到数据库，为这些通道设置空异常
                for channel_info in shot_channels:
                    result.append({
                        "channel_name": channel_info.get('channel_name'),
                        "shot_number": channel_info.get('shot_number'),
                        "errors": [{"error_name": "NO ERROR", "color": "rgba(0, 0, 0, 0)"}]
                    })
                continue
            
            # 使用第一个匹配的数据库
            db_suffix_auto = list(db_shot_mapping.keys())[0]
            db = get_db(db_suffix_auto)
            struct_trees_collection = db["struct_trees"]
            
            # 查找该炮号的结构树数据
            doc = struct_trees_collection.find_one({'shot_number': shot_number})
            
            for channel_info in shot_channels:
                channel_name = channel_info.get('channel_name')
                channel_type = channel_info.get('channel_type')
                shot_num = channel_info.get('shot_number')
                
                channel_errors = []
                if doc and "struct_tree" in doc:
                    for item in doc["struct_tree"]:
                        if (item.get('channel_type') == channel_type and 
                            item.get('channel_name') == channel_name and 
                            str(item.get('shot_number')) == str(shot_num)):
                            error_names = item.get('error_name', [])
                            if not error_names:
                                error_names = ["NO ERROR"]
                            channel_errors = [
                                {
                                    "error_name": error_name,
                                    "color": "rgba(0, 0, 0, 0)" if error_name == "NO ERROR" else "rgba(220, 20, 60, 0.3)"
                                }
                                for error_name in error_names
                            ]
                            break
                
                if not channel_errors:
                    channel_errors = [{"error_name": "NO ERROR", "color": "rgba(0, 0, 0, 0)"}]
                
                result.append({
                    "channel_name": channel_name,
                    "shot_number": shot_num,
                    "errors": channel_errors
                })
        
        return JsonResponse(result, safe=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

class JsonEncoder(json.JSONEncoder):
    """Convert numpy classes to JSON serializable objects."""

    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(JsonEncoder, self).default(obj)

@require_GET
def get_datadiagnosticplatform_dbs(request):
    """
    获取所有以DataDiagnosticPlatform开头的数据库名
    """
    client = MongoClient("mongodb://localhost:27017")
    db_names = client.list_database_names()
    filtered_db_names = [name for name in db_names if name.startswith("DataDiagnosticPlatform")]
    
    # 只返回后缀部分，去掉前缀"DataDiagnosticPlatform_"
    db_suffixes = [name.replace("DataDiagnosticPlatform_", "") for name in filtered_db_names]
    
    # 对db_suffixes按区间起始数字排序
    # 修正排序逻辑，先去掉中括号再分割
    def parse_range(s):
        try:
            s = s.strip('[]')
            start, end = s.split('_')
            return (int(start), int(end))
        except Exception:
            return (float('inf'), float('inf'))

    db_suffixes.sort(key=parse_range)

    return JsonResponse({"db_names": filtered_db_names, "db_suffixes": db_suffixes})

@require_GET
def initialize_db_indices(request):
    """
    初始化指定数据库的索引结构
    可用于修复索引问题
    """
    db_suffix = request.GET.get('db_suffix')
    
    if not db_suffix:
        return JsonResponse({"error": "必须指定数据库后缀"}, status=400)
    
    try:
        db = get_db(db_suffix)
        
        # 检查索引集合
        collections = db.list_collection_names()
        
        # 检查索引集合状态
        index_status = {
            "database": db.name,
            "has_index_collection": 'index' in collections, 
            "has_struct_trees": 'struct_trees' in collections,
            "collections": collections
        }
        
        # 如果索引集合存在，获取各索引的数据量
        if 'index' in collections:
            # 获取索引数据统计信息
            index_stats = []
            for key in ['channel_type', 'channel_name', 'error_name']:
                doc = db['index'].find_one({"key": key})
                if doc and "index_data" in doc:
                    shot_count = len(doc["index_data"])
                    total_items = sum(len(shot_data) for shot_data in doc["index_data"].values())
                    index_stats.append({
                        "key": key,
                        "shot_count": shot_count,
                        "total_items": total_items
                    })
                else:
                    index_stats.append({
                        "key": key,
                        "shot_count": 0,
                        "total_items": 0,
                        "exists": False
                    })
            
            index_status["index_stats"] = index_stats
            
        # 验证struct_trees数据
        if 'struct_trees' in collections:
            shot_count = db['struct_trees'].count_documents({})
            index_status["struct_trees_shot_count"] = shot_count
        
        # 如果指定了强制重建标志，删除现有索引并重建
        if request.GET.get('force_rebuild') == 'true' and 'index' in collections:
            db['index'].drop()
            index_status["rebuild_started"] = True
            # 重新获取数据库实例，触发索引重建
            db = get_db(db_suffix)
            
            # 更新状态
            collections = db.list_collection_names()
            index_status["has_index_collection"] = 'index' in collections
        
        return JsonResponse(index_status)
        
    except Exception as e:
        import traceback
        error_msg = f"初始化数据库索引出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return JsonResponse({"error": error_msg}, status=500)

def get_function_params(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']  # 获取上传的文件
        file_content = uploaded_file.read().decode('utf-8')  # 读取并解码文件内容

        # 判断文件类型（Python 或 MATLAB）
        if uploaded_file.name.endswith('.py'):
            # 解析 Python 文件
            function_params = extract_python_function_params(file_content)
        elif uploaded_file.name.endswith('.m'):
            # 解析 MATLAB 文件
            function_params = extract_matlab_function_params(file_content)
        else:
            return JsonResponse({'status': 'error', 'message': '不支持的文件类型'}, status=400)

        return JsonResponse({'status': 'success', 'functions': function_params})

    return JsonResponse({'status': 'error', 'message': '没有文件上传'}, status=400)


def extract_python_function_params(file_content):
    tree = ast.parse(file_content)
    function_params = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            params = [arg.arg for arg in node.args.args]
            function_params.append({'function_name': node.name, 'params': params})

    return function_params


def extract_matlab_function_params(file_content):
    function_pattern = r"function.*\((.*?)\)"
    matches = re.findall(function_pattern, file_content)

    function_params = []

    for match in matches:
        params = [param.strip() for param in match.split(',')]
        function_params.append({'params': params})

    return function_params

@csrf_exempt
def delete_imported_function(request):
    """
    删除已导入的算法（imported_functions.json 及上传的文件）
    """
    import os
    import json
    from django.conf import settings
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        function_name = data.get('function_name')
        file_type = data.get('file_type', '')  # 新增：获取文件类型

        if not function_name:
            return JsonResponse({'error': 'function_name required'}, status=400)

        # 1. 删除 imported_functions.json 里的对应项
        file_path = os.path.join(settings.MEDIA_ROOT, "imported_functions.json")
        if not os.path.exists(file_path):
            return JsonResponse({'error': 'imported_functions.json not found'}, status=404)

        with open(file_path, "r", encoding="utf-8") as f:
            functions = json.load(f)

        # 2. 查找要删除的函数（根据名称和文件类型）
        function_to_delete = None
        new_functions = []

        for f in functions:
            if f.get('name') == function_name:
                # 如果指定了文件类型，则需要匹配文件类型
                if file_type:
                    func_file_path = f.get('file_path', '')
                    if func_file_path.endswith(file_type):
                        function_to_delete = f
                        continue  # 跳过这个函数，不添加到新列表中
                else:
                    # 如果没有指定文件类型，删除所有同名函数（保持原有行为）
                    function_to_delete = f
                    continue
            new_functions.append(f)

        if not function_to_delete:
            error_msg = f"算法 '{function_name}'"
            if file_type:
                type_name = 'Python' if file_type == '.py' else 'MATLAB' if file_type == '.m' else file_type
                error_msg += f" ({type_name})"
            error_msg += " 不存在"
            return JsonResponse({'error': error_msg}, status=404)

        # 3. 删除对应的文件
        file_to_delete_path = function_to_delete.get('file_path')
        if file_to_delete_path:
            file_abs = os.path.join(settings.MEDIA_ROOT, file_to_delete_path)
            if os.path.exists(file_abs):
                os.remove(file_abs)

        # 4. 保存新列表
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(new_functions, f, ensure_ascii=False, indent=4)

        return JsonResponse({'success': True})
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)

@csrf_exempt
def save_sketch_template(request):
    """
    保存手绘查询模板
    POST请求，参数格式：
    {
        "template_name": "模板名称",
        "raw_query_pattern": [曲线数据],
        "parameters": {
            "lowpassAmplitude": 0.03,
            "xFilterRange": [start, end],
            "yFilterRange": [start, end],
            "patternRepeatCount": 0,
            "maxMatchPerChannel": 100,
            "amplitudeLimit": null,
            "timeSpanLimit": null
        },
        "description": "模板描述"
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        template_name = data.get('template_name', '').strip()
        raw_query_pattern = data.get('raw_query_pattern', [])
        parameters = data.get('parameters', {})
        description = data.get('description', '').strip()
        
        if not template_name:
            return JsonResponse({'error': '模板名称不能为空'}, status=400)
        
        if not raw_query_pattern or len(raw_query_pattern) < 2:
            return JsonResponse({'error': '手绘曲线数据无效'}, status=400)
        
        # 创建模板数据
        template_data = {
            'template_name': template_name,
            'raw_query_pattern': raw_query_pattern,
            'parameters': parameters,
            'description': description,
            'created_time': timezone.now().isoformat(),
            'last_modified': timezone.now().isoformat()
        }
        
        # 保存到文件
        templates_file_path = os.path.join(settings.MEDIA_ROOT, "sketch_templates.json")
        
        # 读取现有模板
        if os.path.exists(templates_file_path):
            with open(templates_file_path, "r", encoding='utf-8') as f:
                templates = json.load(f)
        else:
            templates = []
        
        # 检查是否已存在同名模板
        existing_template_index = -1
        for i, template in enumerate(templates):
            if template.get('template_name') == template_name:
                existing_template_index = i
                break
        
        if existing_template_index >= 0:
            # 更新现有模板
            template_data['created_time'] = templates[existing_template_index].get('created_time', template_data['created_time'])
            templates[existing_template_index] = template_data
            message = '模板更新成功'
        else:
            # 添加新模板
            templates.append(template_data)
            message = '模板保存成功'
        
        # 保存到文件
        with open(templates_file_path, "w", encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
        
        print(f"手绘查询模板保存成功: {template_name}")
        return JsonResponse({'success': True, 'message': message})
        
    except Exception as e:
        import traceback
        error_msg = f"保存手绘查询模板出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return JsonResponse({'error': error_msg}, status=500)

@csrf_exempt 
def get_sketch_templates(request):
    """
    获取所有手绘查询模板
    GET请求
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET method is allowed'}, status=405)
    
    try:
        templates_file_path = os.path.join(settings.MEDIA_ROOT, "sketch_templates.json")
        
        if not os.path.exists(templates_file_path):
            return JsonResponse({'templates': []})
        
        with open(templates_file_path, "r", encoding='utf-8') as f:
            templates = json.load(f)
        
        # 按创建时间倒序排列
        templates.sort(key=lambda x: x.get('created_time', ''), reverse=True)
        
        return JsonResponse({'templates': templates})
        
    except Exception as e:
        import traceback
        error_msg = f"获取手绘查询模板出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return JsonResponse({'error': error_msg}, status=500)

@csrf_exempt
def delete_sketch_template(request):
    """
    删除手绘查询模板
    POST请求，参数格式：
    {
        "template_name": "模板名称"
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        template_name = data.get('template_name', '').strip()
        
        if not template_name:
            return JsonResponse({'error': '模板名称不能为空'}, status=400)
        
        templates_file_path = os.path.join(settings.MEDIA_ROOT, "sketch_templates.json")
        
        if not os.path.exists(templates_file_path):
            return JsonResponse({'error': '模板文件不存在'}, status=404)
        
        with open(templates_file_path, "r", encoding='utf-8') as f:
            templates = json.load(f)
        
        # 查找并删除模板
        templates = [t for t in templates if t.get('template_name') != template_name]
        
        # 保存更新后的模板列表
        with open(templates_file_path, "w", encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
        
        print(f"手绘查询模板删除成功: {template_name}")
        return JsonResponse({'success': True, 'message': '模板删除成功'})
        
    except Exception as e:
        import traceback
        error_msg = f"删除手绘查询模板出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return JsonResponse({'error': error_msg}, status=500)

@require_GET
def get_system_monitor_status(request):
    """
    获取系统监控状态
    直接读取 monitor_status.json 文件
    """
    try:
        # 构造状态文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(current_dir)
        status_file = os.path.join(backend_dir, "monitor_status.json")
        if not os.path.exists(status_file):
            return OrJsonResponse({
                'success': False,
                'error': '监控状态文件不存在'
            }, status=503)
        with open(status_file, "r") as f:
            status = json.load(f)
        return OrJsonResponse({
            'success': True,
            'data': status
        })
    except Exception as e:
        import traceback
        error_msg = f"获取监控状态失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)

# 算法管理相关视图函数

@require_GET
def get_algorithm_channel_map(request):
    """
    获取算法通道映射数据
    """
    try:
        # 构造算法映射文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        algorithm_map_file = os.path.join(project_root, "RunDetectAlgorithm", "algorithmChannelMap.json")

        if not os.path.exists(algorithm_map_file):
            return OrJsonResponse({
                'success': False,
                'error': '算法映射文件不存在'
            }, status=404)

        with open(algorithm_map_file, "r", encoding='utf-8') as f:
            algorithm_data = json.load(f)

        return OrJsonResponse({
            'success': True,
            'data': algorithm_data
        })

    except Exception as e:
        import traceback
        error_msg = f"获取算法映射数据失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)

@csrf_exempt
def create_algorithm_channel_category(request):
    """
    创建新的通道类别
    POST请求，参数格式：
    {
        "category_name": "类别名称"
    }
    """
    if request.method != 'POST':
        return OrJsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        category_name = data.get('category_name', '').strip()

        if not category_name:
            return OrJsonResponse({'error': '类别名称不能为空'}, status=400)

        # 构造文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        algorithm_map_file = os.path.join(project_root, "RunDetectAlgorithm", "algorithmChannelMap.json")
        algorithm_dir = os.path.join(project_root, "RunDetectAlgorithm", "algorithm")

        # 读取现有数据
        if os.path.exists(algorithm_map_file):
            with open(algorithm_map_file, "r", encoding='utf-8') as f:
                algorithm_data = json.load(f)
        else:
            algorithm_data = {}

        # 检查类别是否已存在
        if category_name in algorithm_data:
            return OrJsonResponse({'error': '类别已存在'}, status=400)

        # 添加新类别
        algorithm_data[category_name] = {}

        # 保存到JSON文件
        with open(algorithm_map_file, "w", encoding='utf-8') as f:
            json.dump(algorithm_data, f, ensure_ascii=False, indent=2)

        # 创建对应的文件夹
        category_folder = os.path.join(algorithm_dir, category_name)
        if not os.path.exists(category_folder):
            os.makedirs(category_folder)

        print(f"通道类别创建成功: {category_name}")
        return OrJsonResponse({'success': True, 'message': '类别创建成功'})

    except Exception as e:
        import traceback
        error_msg = f"创建通道类别失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({'error': error_msg}, status=500)

@csrf_exempt
def delete_algorithm_channel_category(request, category_name):
    """
    删除通道类别
    """
    if request.method != 'DELETE':
        return OrJsonResponse({'error': 'Only DELETE method is allowed'}, status=405)

    try:
        # 构造文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        algorithm_map_file = os.path.join(project_root, "RunDetectAlgorithm", "algorithmChannelMap.json")
        algorithm_dir = os.path.join(project_root, "RunDetectAlgorithm", "algorithm")

        # 读取现有数据
        if not os.path.exists(algorithm_map_file):
            return OrJsonResponse({'error': '算法映射文件不存在'}, status=404)

        with open(algorithm_map_file, "r", encoding='utf-8') as f:
            algorithm_data = json.load(f)

        # 检查类别是否存在
        if category_name not in algorithm_data:
            return OrJsonResponse({'error': '类别不存在'}, status=404)

        # 删除类别
        del algorithm_data[category_name]

        # 保存到JSON文件
        with open(algorithm_map_file, "w", encoding='utf-8') as f:
            json.dump(algorithm_data, f, ensure_ascii=False, indent=2)

        # 删除对应的文件夹
        import shutil
        category_folder = os.path.join(algorithm_dir, category_name)
        if os.path.exists(category_folder):
            shutil.rmtree(category_folder)

        print(f"通道类别删除成功: {category_name}")
        return OrJsonResponse({'success': True, 'message': '类别删除成功'})

    except Exception as e:
        import traceback
        error_msg = f"删除通道类别失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({'error': error_msg}, status=500)

@csrf_exempt
def create_algorithm_channel_algorithm(request):
    """
    创建新的算法
    POST请求，参数格式：
    {
        "category_name": "类别名称",
        "algorithm_name": "算法名称"
    }
    """
    if request.method != 'POST':
        return OrJsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        category_name = data.get('category_name', '').strip()
        algorithm_name = data.get('algorithm_name', '').strip()

        if not category_name or not algorithm_name:
            return OrJsonResponse({'error': '类别名称和算法名称不能为空'}, status=400)

        # 构造文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        algorithm_map_file = os.path.join(project_root, "RunDetectAlgorithm", "algorithmChannelMap.json")

        # 读取现有数据
        if not os.path.exists(algorithm_map_file):
            return OrJsonResponse({'error': '算法映射文件不存在'}, status=404)

        with open(algorithm_map_file, "r", encoding='utf-8') as f:
            algorithm_data = json.load(f)

        # 检查类别是否存在
        if category_name not in algorithm_data:
            return OrJsonResponse({'error': '类别不存在'}, status=404)

        # 检查算法是否已存在
        if algorithm_name in algorithm_data[category_name]:
            return OrJsonResponse({'error': '算法已存在'}, status=400)

        # 添加新算法
        algorithm_data[category_name][algorithm_name] = []

        # 保存到JSON文件
        with open(algorithm_map_file, "w", encoding='utf-8') as f:
            json.dump(algorithm_data, f, ensure_ascii=False, indent=2)

        print(f"算法创建成功: {category_name}/{algorithm_name}")
        return OrJsonResponse({'success': True, 'message': '算法创建成功'})

    except Exception as e:
        import traceback
        error_msg = f"创建算法失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({'error': error_msg}, status=500)

@csrf_exempt
def delete_algorithm_channel_algorithm(request, category_name, algorithm_name):
    """
    删除算法
    """
    if request.method != 'DELETE':
        return OrJsonResponse({'error': 'Only DELETE method is allowed'}, status=405)

    try:
        # 构造文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        algorithm_map_file = os.path.join(project_root, "RunDetectAlgorithm", "algorithmChannelMap.json")
        algorithm_dir = os.path.join(project_root, "RunDetectAlgorithm", "algorithm")

        # 读取现有数据
        if not os.path.exists(algorithm_map_file):
            return OrJsonResponse({'error': '算法映射文件不存在'}, status=404)

        with open(algorithm_map_file, "r", encoding='utf-8') as f:
            algorithm_data = json.load(f)

        # 检查类别和算法是否存在
        if category_name not in algorithm_data:
            return OrJsonResponse({'error': '类别不存在'}, status=404)

        if algorithm_name not in algorithm_data[category_name]:
            return OrJsonResponse({'error': '算法不存在'}, status=404)

        # 删除算法
        del algorithm_data[category_name][algorithm_name]

        # 保存到JSON文件
        with open(algorithm_map_file, "w", encoding='utf-8') as f:
            json.dump(algorithm_data, f, ensure_ascii=False, indent=2)

        # 删除对应的算法文件
        category_folder = os.path.join(algorithm_dir, category_name)
        if os.path.exists(category_folder):
            mat_file = os.path.join(category_folder, f"{algorithm_name}.mat")
            py_file = os.path.join(category_folder, f"{algorithm_name}.py")

            if os.path.exists(mat_file):
                os.remove(mat_file)
            if os.path.exists(py_file):
                os.remove(py_file)

        print(f"算法删除成功: {category_name}/{algorithm_name}")
        return OrJsonResponse({'success': True, 'message': '算法删除成功'})

    except Exception as e:
        import traceback
        error_msg = f"删除算法失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({'error': error_msg}, status=500)

@csrf_exempt
def create_algorithm_channel_channels(request):
    """
    添加通道到算法
    POST请求，参数格式：
    {
        "category_name": "类别名称",
        "algorithm_name": "算法名称",
        "channel_names": ["通道1", "通道2", ...]
    }
    """
    if request.method != 'POST':
        return OrJsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        category_name = data.get('category_name', '').strip()
        algorithm_name = data.get('algorithm_name', '').strip()
        channel_names = data.get('channel_names', [])

        if not category_name or not algorithm_name or not channel_names:
            return OrJsonResponse({'error': '参数不能为空'}, status=400)

        # 构造文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        algorithm_map_file = os.path.join(project_root, "RunDetectAlgorithm", "algorithmChannelMap.json")

        # 读取现有数据
        if not os.path.exists(algorithm_map_file):
            return OrJsonResponse({'error': '算法映射文件不存在'}, status=404)

        with open(algorithm_map_file, "r", encoding='utf-8') as f:
            algorithm_data = json.load(f)

        # 检查类别和算法是否存在
        if category_name not in algorithm_data:
            return OrJsonResponse({'error': '类别不存在'}, status=404)

        if algorithm_name not in algorithm_data[category_name]:
            return OrJsonResponse({'error': '算法不存在'}, status=404)

        # 添加通道（去重）
        existing_channels = set(algorithm_data[category_name][algorithm_name])
        new_channels = [ch.strip() for ch in channel_names if ch.strip() not in existing_channels]

        if new_channels:
            algorithm_data[category_name][algorithm_name].extend(new_channels)

            # 保存到JSON文件
            with open(algorithm_map_file, "w", encoding='utf-8') as f:
                json.dump(algorithm_data, f, ensure_ascii=False, indent=2)

            print(f"通道添加成功: {category_name}/{algorithm_name} - {new_channels}")
            return OrJsonResponse({'success': True, 'message': f'成功添加 {len(new_channels)} 个通道'})
        else:
            return OrJsonResponse({'success': True, 'message': '所有通道已存在，无需添加'})

    except Exception as e:
        import traceback
        error_msg = f"添加通道失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({'error': error_msg}, status=500)

@csrf_exempt
def delete_algorithm_channel_channel(request, category_name, algorithm_name, channel_name):
    """
    删除通道
    """
    if request.method != 'DELETE':
        return OrJsonResponse({'error': 'Only DELETE method is allowed'}, status=405)

    try:
        # 构造文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        algorithm_map_file = os.path.join(project_root, "RunDetectAlgorithm", "algorithmChannelMap.json")

        # 读取现有数据
        if not os.path.exists(algorithm_map_file):
            return OrJsonResponse({'error': '算法映射文件不存在'}, status=404)

        with open(algorithm_map_file, "r", encoding='utf-8') as f:
            algorithm_data = json.load(f)

        # 检查类别、算法和通道是否存在
        if category_name not in algorithm_data:
            return OrJsonResponse({'error': '类别不存在'}, status=404)

        if algorithm_name not in algorithm_data[category_name]:
            return OrJsonResponse({'error': '算法不存在'}, status=404)

        if channel_name not in algorithm_data[category_name][algorithm_name]:
            return OrJsonResponse({'error': '通道不存在'}, status=404)

        # 删除通道
        algorithm_data[category_name][algorithm_name].remove(channel_name)

        # 保存到JSON文件
        with open(algorithm_map_file, "w", encoding='utf-8') as f:
            json.dump(algorithm_data, f, ensure_ascii=False, indent=2)

        print(f"通道删除成功: {category_name}/{algorithm_name}/{channel_name}")
        return OrJsonResponse({'success': True, 'message': '通道删除成功'})

    except Exception as e:
        import traceback
        error_msg = f"删除通道失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({'error': error_msg}, status=500)

@csrf_exempt
def upload_algorithm_files(request):
    """
    上传算法文件（.mat 和 .py）
    POST请求，multipart/form-data格式：
    - category: 类别名称
    - algorithm: 算法名称
    - mat_file: .mat文件
    - py_file: .py文件
    """
    if request.method != 'POST':
        return OrJsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        category_name = request.POST.get('category', '').strip()
        algorithm_name = request.POST.get('algorithm', '').strip()
        mat_file = request.FILES.get('mat_file')
        py_file = request.FILES.get('py_file')

        if not category_name or not algorithm_name:
            return OrJsonResponse({'error': '类别名称和算法名称不能为空'}, status=400)

        if not mat_file or not py_file:
            return OrJsonResponse({'error': '必须同时上传 .mat 和 .py 文件'}, status=400)

        # 验证文件扩展名
        if not mat_file.name.endswith('.mat'):
            return OrJsonResponse({'error': '.mat 文件格式不正确'}, status=400)

        if not py_file.name.endswith('.py'):
            return OrJsonResponse({'error': '.py 文件格式不正确'}, status=400)

        # 验证文件名是否一致
        mat_basename = os.path.splitext(mat_file.name)[0]
        py_basename = os.path.splitext(py_file.name)[0]

        if mat_basename != py_basename:
            return OrJsonResponse({'error': '.mat 和 .py 文件名必须相同'}, status=400)

        # 构造目标路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        algorithm_dir = os.path.join(project_root, "RunDetectAlgorithm", "algorithm")
        category_folder = os.path.join(algorithm_dir, category_name)

        # 确保目录存在
        if not os.path.exists(category_folder):
            os.makedirs(category_folder)

        # 保存文件
        mat_path = os.path.join(category_folder, mat_file.name)
        py_path = os.path.join(category_folder, py_file.name)

        # 写入 .mat 文件
        with open(mat_path, 'wb') as f:
            for chunk in mat_file.chunks():
                f.write(chunk)

        # 写入 .py 文件
        with open(py_path, 'wb') as f:
            for chunk in py_file.chunks():
                f.write(chunk)

        # 简单的文件验证（检查文件是否可读）
        try:
            # 验证 .py 文件语法
            with open(py_path, 'r', encoding='utf-8') as f:
                py_content = f.read()
                compile(py_content, py_path, 'exec')

            print(f"算法文件上传成功: {category_name}/{algorithm_name}")
            return OrJsonResponse({'success': True, 'message': '文件上传成功'})

        except SyntaxError as e:
            # 如果Python文件有语法错误，删除已上传的文件
            if os.path.exists(mat_path):
                os.remove(mat_path)
            if os.path.exists(py_path):
                os.remove(py_path)
            return OrJsonResponse({'error': f'Python文件语法错误: {str(e)}'}, status=400)

    except Exception as e:
        import traceback
        error_msg = f"上传算法文件失败: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({'error': error_msg}, status=500)

@csrf_exempt
def import_algorithm_to_detection(request):
    """导入算法或模板到异常检测方法"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'})
    
    try:
        data = json.loads(request.body)
        algorithm_type = data.get('type')  # 'imported_function' 或 'sketch_template'
        algorithm_name = data.get('algorithm_name')
        category_name = data.get('category_name')
        source_data = data.get('source_data')
        
        if not all([algorithm_type, algorithm_name, category_name]):
            return JsonResponse({'success': False, 'message': '缺少必要参数'})
        
        # 加载现有的算法通道映射
        # 使用绝对路径，相对于Django项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        algorithm_map_path = os.path.join(project_root, 'RunDetectAlgorithm', 'algorithmChannelMap.json')
        with open(algorithm_map_path, 'r', encoding='utf-8') as f:
            algorithm_channel_map = json.load(f)
        
        # 确保类别存在
        if category_name not in algorithm_channel_map:
            algorithm_channel_map[category_name] = {}
        
        if algorithm_type == 'imported_function':
            # 处理用户导入的算法 - 算法键包含文件类型信息
            file_type = source_data.get('fileType', '')
            file_type_suffix = '_python' if file_type == 'Python' else '_matlab' if file_type == 'MATLAB' else ''
            algorithm_key = f"imported_{algorithm_name}{file_type_suffix}"
            algorithm_channel_map[category_name][algorithm_key] = []
            
            # 创建算法适配器文件
            create_imported_function_adapter(algorithm_name, source_data, category_name, algorithm_key)
            
        elif algorithm_type == 'sketch_template':
            # 处理手绘模板
            algorithm_key = f"sketch_{algorithm_name}"
            algorithm_channel_map[category_name][algorithm_key] = []
            
            # 创建手绘模板适配器文件
            create_sketch_template_adapter(algorithm_name, source_data, category_name, algorithm_key)
        
        else:
            return JsonResponse({'success': False, 'message': '不支持的算法类型'})
        
        # 保存更新后的算法通道映射
        with open(algorithm_map_path, 'w', encoding='utf-8') as f:
            json.dump(algorithm_channel_map, f, ensure_ascii=False, indent=2)
        
        return JsonResponse({'success': True, 'message': '算法导入成功'})
        
    except Exception as e:
        logger.error(f"导入算法失败: {e}")
        return JsonResponse({'success': False, 'message': f'导入失败: {str(e)}'})

def create_imported_function_adapter(algorithm_name, source_data, category_name, algorithm_key):
    """为用户导入的算法创建适配器文件"""
    # 从imported_functions.json中获取算法信息
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    imported_functions_path = os.path.join(project_root, 'backend', 'imported_functions.json')
    try:
        with open(imported_functions_path, 'r', encoding='utf-8') as f:
            imported_functions = json.load(f)
        
        # 查找对应的算法信息 - 需要考虑同名但不同类型的算法
        algorithm_info = None
        file_type_preference = source_data.get('fileType', '')  # 从前端传来的文件类型
        
        # 如果指定了文件类型，优先匹配对应类型的算法
        if file_type_preference:
            for func in imported_functions:
                if func['name'] == algorithm_name:
                    func_file_type = 'Python' if func['file_path'].endswith('.py') else 'MATLAB' if func['file_path'].endswith('.m') else ''
                    if func_file_type == file_type_preference:
                        algorithm_info = func
                        break
        
        # 如果没有找到指定类型的算法，或者没有指定类型，则使用第一个匹配的算法
        if not algorithm_info:
            for func in imported_functions:
                if func['name'] == algorithm_name:
                    algorithm_info = func
                    break
        
        if not algorithm_info:
            raise Exception(f"未找到算法信息: {algorithm_name}")
        
        # 确定文件扩展名
        file_path = algorithm_info['file_path']
        if file_path.endswith('.py'):
            file_ext = 'py'
        elif file_path.endswith('.m'):
            file_ext = 'm'
        else:
            raise Exception(f"不支持的文件类型: {file_path}")
        
        # 创建适配器目录
        adapter_dir = os.path.join(project_root, 'RunDetectAlgorithm', 'algorithm', category_name)
        os.makedirs(adapter_dir, exist_ok=True)
        
        if file_ext == 'py':
            # 获取参数配置
            parameters = source_data.get('parameters', {})
            input_params = algorithm_info.get('input', [])
            
            # 创建Python适配器
            adapter_content = f'''# 自动生成的适配器文件，用于导入的Python算法: {algorithm_name}
import sys
import os
import importlib.util
import numpy as np

def func(Y_value, X_value=None):
    """
    适配器函数，用于调用用户导入的算法
    """
    try:
        # 动态导入用户的算法文件
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        file_path = os.path.join(project_root, '{file_path}')
        spec = importlib.util.spec_from_file_location("{algorithm_name}", file_path)
        user_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(user_module)
        
        # 构造通道数据对象
        channel_data = {{
            'X_value': X_value if X_value is not None else np.arange(len(Y_value)),
            'Y_value': Y_value
        }}
        
        # 调用用户算法（使用配置的参数）
        # 获取配置的参数
        configured_params = {repr(parameters)}
        
        # 构建函数调用参数
        call_args = [channel_data]  # 通道数据总是第一个参数
        
        # 按照函数定义的顺序添加其他参数
        input_params = {repr(input_params)}
        for param in input_params:
            if param['paraName'] != 'channel_key':  # 跳过通道参数
                param_value = configured_params.get(param['paraName'], param.get('default', 0.1))
                # 根据参数类型进行转换
                if param['paraType'] == '浮点数':
                    try:
                        param_value = float(param_value) if param_value else 0.1
                    except:
                        param_value = 0.1
                elif param['paraType'] == '整数':
                    try:
                        param_value = int(param_value) if param_value else 1
                    except:
                        param_value = 1
                call_args.append(param_value)
        
        # 调用算法函数
        if hasattr(user_module, '{algorithm_name}'):
            result = getattr(user_module, '{algorithm_name}')(*call_args)
        else:
            # 查找第一个可调用的函数
            for attr_name in dir(user_module):
                attr = getattr(user_module, attr_name)
                if callable(attr) and not attr_name.startswith('_'):
                    result = attr(*call_args)
                    break
            else:
                raise Exception("未找到可调用的函数")
        
        # 处理结果，转换为异常检测格式
        if isinstance(result, dict) and 'X_range' in result:
            # 结果是范围格式
            return result['X_range']
        else:
            # 假设结果是二维数组格式
            return result if isinstance(result, list) else []
            
    except Exception as e:
        print(f"调用用户算法 {algorithm_name} 失败: {{e}}")
        return []
'''
        
        elif file_ext == 'm':
            # 获取参数配置
            parameters = source_data.get('parameters', {})
            input_params = algorithm_info.get('input', [])
            
            # 创建MATLAB适配器 - 使用简单的字符串拼接避免模板问题
            matlab_adapter_code = '''# 自动生成的适配器文件，用于导入的MATLAB算法: ''' + algorithm_name + '''
import scipy.io as sio
import numpy as np
import subprocess
import os
import tempfile

def func(Y_value, X_value=None):
    """
    适配器函数，用于调用用户导入的MATLAB算法
    """
    try:
        # 创建临时文件存储输入数据
        with tempfile.NamedTemporaryFile(suffix='.mat', delete=False) as temp_input:
            input_data = {
                'X_value': X_value if X_value is not None else np.arange(len(Y_value)),
                'Y_value': Y_value
            }
            # 准备算法参数
            algorithm_params = ''' + repr(parameters) + '''
            input_param_defs = ''' + repr(input_params) + '''
            
            # 构建MATLAB函数参数
            matlab_params = {'channel_key': input_data}
            for param in input_param_defs:
                if param['paraName'] != 'channel_key':
                    param_value = algorithm_params.get(param['paraName'], param.get('default', 0.1))
                    # 类型转换
                    if param['paraType'] == '浮点数':
                        try:
                            param_value = float(param_value) if param_value else 0.1
                        except:
                            param_value = 0.1
                    elif param['paraType'] == '整数':
                        try:
                            param_value = int(param_value) if param_value else 1
                        except:
                            param_value = 1
                    matlab_params[param['paraName']] = param_value
            
            sio.savemat(temp_input.name, matlab_params)
            temp_input_name = temp_input.name
            
        # 调用MATLAB算法
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        matlab_file = os.path.join(project_root, ''' + file_path + ''')
            
        # 创建临时MATLAB脚本来调用算法
        with tempfile.NamedTemporaryFile(suffix='.m', mode='w', delete=False) as temp_script:
            # 构建MATLAB函数调用参数列表
            param_names = ['channel_key']
            for param in input_param_defs:
                if param['paraName'] != 'channel_key':
                    param_names.append(param['paraName'])
            
            param_list = ', '.join(param_names)
            
            script_content = f"""
            load('{temp_input_name}');
            result = ''' + algorithm_name + '''({param_list});
            save('{temp_input_name.replace('.mat', '_output.mat')}', 'result');
            exit;
            """
            temp_script.write(script_content)
            temp_script_path = temp_script.name
        
        # 执行MATLAB
        subprocess.run(['matlab', '-batch', f"run('{temp_script_path}')"], 
                     cwd=os.path.dirname(matlab_file), check=True, capture_output=True)
        
        # 读取结果
        output_file = temp_input_name.replace('.mat', '_output.mat')
        if os.path.exists(output_file):
            result_data = sio.loadmat(output_file)
            result = result_data.get('result', [])
            
            # 清理临时文件
            os.unlink(temp_input_name)
            os.unlink(temp_script_path)
            os.unlink(output_file)
            
            # 处理结果
            if isinstance(result, np.ndarray):
                return result.tolist() if result.size > 0 else []
            else:
                return result if isinstance(result, list) else []
        else:
            raise Exception("MATLAB执行失败，未生成结果文件")
                
    except Exception as e:
        print(f"调用MATLAB算法 ''' + algorithm_name + ''' 失败: {e}")
        return []
'''
            adapter_content = matlab_adapter_code
        
        # 写入适配器文件 - 使用算法键作为文件名（已包含类型信息）
        adapter_file_path = os.path.join(adapter_dir, f'{algorithm_key}.py')
        with open(adapter_file_path, 'w', encoding='utf-8') as f:
            f.write(adapter_content)
        
        print(f"已创建算法适配器: {adapter_file_path}")
        
    except Exception as e:
        raise Exception(f"创建算法适配器失败: {e}")

def create_sketch_template_adapter(template_name, source_data, category_name, algorithm_key):
    """为手绘模板创建适配器文件"""
    # 从sketch_templates.json中获取模板信息
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sketch_templates_path = os.path.join(project_root, 'backend', 'sketch_templates.json')
    try:
        with open(sketch_templates_path, 'r', encoding='utf-8') as f:
            sketch_templates = json.load(f)
        
        # 查找对应的模板信息 - sketch_templates.json是数组结构
        template_info = None
        if isinstance(sketch_templates, list):
            # 数组结构
            for template in sketch_templates:
                if template.get('template_name') == template_name:
                    template_info = template
                    break
        elif isinstance(sketch_templates, dict) and 'templates' in sketch_templates:
            # 对象结构
            for template in sketch_templates['templates']:
                if template.get('template_name') == template_name:
                    template_info = template
                    break
        
        if not template_info:
            raise Exception(f"未找到模板信息: {template_name}")
        
        # 创建适配器目录
        adapter_dir = os.path.join(project_root, 'RunDetectAlgorithm', 'algorithm', category_name)
        os.makedirs(adapter_dir, exist_ok=True)
        
        # 创建手绘模式适配器
        adapter_content = f'''# 自动生成的适配器文件，用于手绘模板: {template_name}
import sys
import os
import numpy as np

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

from backend.api.pattern_matching_Qetch import match_pattern

def func(Y_value, X_value=None):
    """
    适配器函数，用于调用手绘模板匹配算法
    """
    try:
        # 构造时间轴（如果没有提供）
        if X_value is None:
            X_value = np.arange(len(Y_value))
        
        # 对数据进行降采样到5KHz（按照用户要求）
        X_value_resampled, Y_value_resampled = downsample_to_5khz(X_value, Y_value)
        
        # 构造通道数据
        channel_data = {{
            'X_value': X_value_resampled,
            'Y_value': Y_value_resampled
        }}
        
        # 模板参数 - 使用安全的字符串转换
        import json as json_module
        template_params = json_module.dumps(template_info.get('parameters', {{}}))
        raw_query_pattern = json_module.dumps(template_info.get('raw_query_pattern', []))
        
        # 解析JSON参数
        template_params_dict = json_module.loads(template_params)
        raw_query_pattern_list = json_module.loads(raw_query_pattern)
        
        # 调用模式匹配算法
        matches = match_pattern(
            normalized_query_pattern=raw_query_pattern_list,
            channel_data_list=[channel_data],
            lowpass_amplitude=template_params_dict.get('lowpassAmplitude'),
            x_filter_range=template_params_dict.get('xFilterRange'),
            y_filter_range=template_params_dict.get('yFilterRange'),
            pattern_repeat_count=template_params_dict.get('patternRepeatCount'),
            max_match_per_channel=template_params_dict.get('maxMatchPerChannel'),
            amplitude_limit=template_params_dict.get('amplitudeLimit'),
            time_span_limit=template_params_dict.get('timeSpanLimit')
        )
        
        # 处理匹配结果，转换为异常检测格式
        error_ranges = []
        if matches and len(matches) > 0:
            for match in matches[0]:  # 取第一个通道的匹配结果
                if 'start_point' in match and 'end_point' in match:
                    start_x = match['start_point'].get('origX', match['start_point']['x'])
                    end_x = match['end_point'].get('origX', match['end_point']['x'])
                    error_ranges.append([start_x, end_x])
        
        return error_ranges
        
    except Exception as e:
        print(f"调用手绘模板 {template_name} 失败: {{e}}")
        return []

def downsample_to_5khz(x_values, y_values):
    """
    将数据降采样到5KHz频率
    """
    if len(x_values) <= 5000:
        return x_values, y_values
    
    # 确定数据的时间范围
    time_start = min(x_values)
    time_end = max(x_values)
    time_span = time_end - time_start
    
    # 基于5KHz频率计算总采样点数
    n_samples = int(time_span * 5000)
    
    # 如果目标点数比原始点数多，直接返回原始数据
    if n_samples >= len(x_values):
        return x_values, y_values
    
    # 使用与views.py中相同的降采样方法
    from backend.api.views import downsample_to_frequency
    return downsample_to_frequency(x_values, y_values, target_freq=5000)
'''
        
        # 写入适配器文件
        adapter_file_path = os.path.join(adapter_dir, f'{algorithm_key}.py')
        with open(adapter_file_path, 'w', encoding='utf-8') as f:
            f.write(adapter_content)
        
        print(f"已创建手绘模板适配器: {adapter_file_path}")
        
    except Exception as e:
        raise Exception(f"创建手绘模板适配器失败: {e}")

@require_GET
def get_shot_statistics(request):
    """
    获取指定炮号的统计信息，参考data_diagnostic_statistics.py的统计逻辑
    """
    shot_numbers_str = request.GET.get('shot_numbers', '')
    if not shot_numbers_str:
        return OrJsonResponse({'error': 'shot_numbers parameter is required'}, status=400)
    
    shot_numbers = [s.strip() for s in shot_numbers_str.split(',') if s.strip()]
    if not shot_numbers:
        return OrJsonResponse({'error': 'No valid shot numbers provided'}, status=400)
    
    try:
        # 按炮号分组到对应的数据库
        db_shot_mapping = find_databases_for_shot_numbers(shot_numbers)
        
        if not db_shot_mapping:
            return OrJsonResponse({'error': 'No databases found for the provided shot numbers'}, status=404)
        
        # 为每个炮号生成统计信息
        shot_statistics = {}
        
        for db_suffix, shots_in_db in db_shot_mapping.items():
            try:
                db = get_db(db_suffix)
                struct_trees_collection = db["struct_trees"]
                
                # 处理该数据库中的每个炮号
                for shot_number in shots_in_db:
                    shot_doc = struct_trees_collection.find_one({'shot_number': shot_number})
                    
                    if not shot_doc:
                        # 如果没有找到该炮号，设置空统计
                        shot_statistics[shot_number] = {
                            'shot_number': shot_number,
                            'total_channels': 0,
                            'total_errors': 0,
                            'normal_channels': 0,
                            'error_channels': 0,
                            'error_rate': 0,
                            'channel_types': {},
                            'error_types': {},
                            'channel_status': {},
                            'database': f"DataDiagnosticPlatform_{db_suffix}"
                        }
                        continue
                    
                    struct_tree = shot_doc.get('struct_tree', [])
                    
                    # 初始化统计计数器
                    channel_types = Counter()
                    error_types = Counter()
                    channel_status = Counter()
                    
                    total_channels = len(struct_tree)
                    total_errors = 0
                    normal_channels = 0
                    
                    for channel in struct_tree:
                        channel_type = channel.get('channel_type', 'Unknown')
                        error_names = channel.get('error_name', [])
                        status = channel.get('status', 'unknown')
                        
                        # 统计通道类型
                        channel_types[channel_type] += 1
                        
                        # 统计通道状态
                        channel_status[status] += 1
                        
                        # 处理异常信息
                        has_error = False
                        if not error_names or error_names == [] or error_names == [''] or 'NO ERROR' in error_names:
                            normal_channels += 1
                        else:
                            # 确保error_names是列表
                            if isinstance(error_names, str):
                                error_names = [error_names]
                            
                            for error_name in error_names:
                                if error_name and error_name != 'NO ERROR' and error_name.strip():
                                    error_types[error_name] += 1
                                    total_errors += 1
                                    has_error = True
                            
                            if not has_error:
                                normal_channels += 1
                    
                    error_channels = total_channels - normal_channels
                    error_rate = (error_channels / total_channels * 100) if total_channels > 0 else 0
                    
                    shot_statistics[shot_number] = {
                        'shot_number': shot_number,
                        'total_channels': total_channels,
                        'total_errors': total_errors,
                        'normal_channels': normal_channels,
                        'error_channels': error_channels,
                        'error_rate': round(error_rate, 2),
                        'channel_types': dict(channel_types.most_common()),
                        'error_types': dict(error_types.most_common()),
                        'channel_status': dict(channel_status.most_common()),
                        'database': f"DataDiagnosticPlatform_{db_suffix}"
                    }
                    
            except Exception as e:
                print(f"警告: 处理数据库 {db_suffix} 时出错: {str(e)}")
                # 为该数据库中的炮号设置错误统计
                for shot_number in shots_in_db:
                    if shot_number not in shot_statistics:
                        shot_statistics[shot_number] = {
                            'shot_number': shot_number,
                            'error': f'Database error: {str(e)}',
                            'database': f"DataDiagnosticPlatform_{db_suffix}"
                        }
        
        # 确保所有请求的炮号都有统计信息（即使是空的）
        for shot_number in shot_numbers:
            if shot_number not in shot_statistics:
                shot_statistics[shot_number] = {
                    'shot_number': shot_number,
                    'total_channels': 0,
                    'total_errors': 0,
                    'normal_channels': 0,
                    'error_channels': 0,
                    'error_rate': 0,
                    'channel_types': {},
                    'error_types': {},
                    'channel_status': {},
                    'database': 'Not found'
                }
        
        # 按炮号排序返回
        sorted_stats = [shot_statistics[shot] for shot in sorted(shot_statistics.keys(), key=int)]
        
        return OrJsonResponse({
            'shot_statistics': sorted_stats,
            'total_shots': len(sorted_stats),
            'summary': {
                'total_channels': sum(stat.get('total_channels', 0) for stat in sorted_stats),
                'total_errors': sum(stat.get('total_errors', 0) for stat in sorted_stats),
                'average_error_rate': round(sum(stat.get('error_rate', 0) for stat in sorted_stats) / len(sorted_stats), 2) if sorted_stats else 0
            }
        })
        
    except Exception as e:
        import traceback
        error_msg = f"获取炮号统计信息时出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({"error": error_msg}, status=500)

@require_GET
def get_error_statistics_files(request):
    """
    获取Errors_Result_Statistics文件夹中的文件名列表，支持分页
    
    Query参数:
    - page: 页码 (默认: 1)
    - page_size: 每页数量 (默认: 20, 最大: 500)
    - search: 搜索关键词 (可选)
    """
    try:
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 20)), 500)  # 限制最大每页100个
        search = request.GET.get('search', '').strip()
        
        # 确保页码和页面大小为正数
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        
        # 获取Errors_Result_Statistics文件夹路径
        import os
        from django.conf import settings
        
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        errors_folder = os.path.join(project_root, 'Errors_Result_Statistics')
        
        # 检查文件夹是否存在
        if not os.path.exists(errors_folder):
            return JsonResponse({
                'error': 'Errors_Result_Statistics folder not found',
                'files': [],
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_files': 0,
                    'total_pages': 0
                }
            })
        
        # 解析搜索条件，支持打印机式输入（如：1-10,25）
        def parse_search_condition(search_str):
            """解析搜索条件，支持范围（如：1-10）和单个值（如：25）的组合"""
            if not search_str:
                return None
            
            target_shots = set()
            # 按逗号分割多个条件
            conditions = search_str.split(',')
            
            for condition in conditions:
                condition = condition.strip()
                if not condition:
                    continue
                
                # 检查是否是范围（包含连字符）
                if '-' in condition:
                    try:
                        # 解析范围，如 "1-10"
                        parts = condition.split('-')
                        if len(parts) == 2:
                            start = int(parts[0].strip())
                            end = int(parts[1].strip())
                            # 添加范围内的所有炮号
                            for shot in range(start, end + 1):
                                target_shots.add(shot)
                    except (ValueError, IndexError):
                        # 如果解析失败，忽略这个条件
                        continue
                else:
                    # 单个炮号
                    try:
                        shot = int(condition)
                        target_shots.add(shot)
                    except ValueError:
                        # 如果解析失败，忽略这个条件
                        continue
            
            return target_shots if target_shots else None
        
        # 检查文件是否匹配搜索条件
        def is_file_matched(filename, target_shots):
            """检查文件是否匹配搜索条件"""
            if not target_shots:
                return True  # 没有搜索条件时，匹配所有文件
            
            # 从文件名提取炮号
            if filename.startswith('shot_') and '_errors.json' in filename:
                try:
                    shot_str = filename.replace('shot_', '').replace('_errors.json', '')
                    shot_number = int(shot_str)
                    return shot_number in target_shots
                except (ValueError, TypeError):
                    return False
            return False
        
        # 获取所有JSON文件
        all_files = []
        target_shots = parse_search_condition(search)
        
        for filename in os.listdir(errors_folder):
            if filename.endswith('.json'):
                # 如果指定了搜索条件，进行精确匹配
                if not is_file_matched(filename, target_shots):
                    continue
                all_files.append(filename)
        
        # 按炮号数值从大到小排序（最新的优先显示）
        def extract_shot_number(filename):
            """从文件名中提取炮号数值"""
            if filename.startswith('shot_') and '_errors.json' in filename:
                try:
                    shot_str = filename.replace('shot_', '').replace('_errors.json', '')
                    return int(shot_str)
                except (ValueError, TypeError):
                    return 0  # 如果无法解析为数字，返回0
            return 0  # 不符合命名规则的文件返回0
        
        # 按炮号数值从大到小排序
        all_files.sort(key=extract_shot_number, reverse=True)
        
        # 计算分页信息
        total_files = len(all_files)
        total_pages = (total_files + page_size - 1) // page_size
        
        # 确保页码在有效范围内
        if page > total_pages and total_pages > 0:
            page = total_pages
        
        # 计算当前页的文件
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        current_page_files = all_files[start_index:end_index]
        
        # 为每个文件获取基本信息
        files_info = []
        for filename in current_page_files:
            file_path = os.path.join(errors_folder, filename)
            try:
                file_stat = os.stat(file_path)
                file_size_mb = file_stat.st_size / (1024 * 1024)  # 转换为MB
                
                # 尝试从文件名提取炮号信息
                shot_number = None
                if filename.startswith('shot_') and '_errors.json' in filename:
                    shot_number = filename.replace('shot_', '').replace('_errors.json', '')
                
                files_info.append({
                    'filename': filename,
                    'file_size_mb': round(file_size_mb, 2),
                    'shot_number': shot_number,
                    'modified_time': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception as e:
                # 如果获取文件信息失败，仍然返回文件名
                files_info.append({
                    'filename': filename,
                    'file_size_mb': 0,
                    'shot_number': None,
                    'modified_time': None,
                    'error': str(e)
                })
        
        return JsonResponse({
            'files': files_info,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_files': total_files,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_previous': page > 1
            }
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@require_GET
def download_error_file(request):
    """
    单个错误统计文件下载接口，参数filename
    """
    import os
    from django.http import FileResponse, Http404
    filename = request.GET.get('filename', '').strip()
    if not filename or not filename.endswith('.json'):
        return JsonResponse({'error': '参数错误'}, status=400)
    # 获取文件路径
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    errors_folder = os.path.join(project_root, 'Errors_Result_Statistics')
    file_path = os.path.join(errors_folder, filename)
    if not os.path.exists(file_path):
        return JsonResponse({'error': '文件不存在'}, status=404)
    # 返回文件流
    response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    response['Content-Type'] = 'application/json'
    return response

@csrf_exempt
@require_POST
def download_error_files(request):
    """
    批量下载错误统计文件，前端POST json: { filenames: ["shot_4_errors.json", ...] }
    返回zip压缩包
    """
    import os
    try:
        data = json.loads(request.body)
        filenames = data.get('filenames', [])
        if not isinstance(filenames, list) or not filenames:
            return JsonResponse({'error': '参数错误'}, status=400)
        # 获取文件路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        errors_folder = os.path.join(project_root, 'Errors_Result_Statistics')
        # 创建zip流
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in filenames:
                if not filename.endswith('.json'):
                    continue
                file_path = os.path.join(errors_folder, filename)
                if os.path.exists(file_path):
                    zipf.write(file_path, arcname=filename)
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="error_files.zip"'
        return response
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)
