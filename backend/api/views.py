import ast
import json
import orjson
import os
import re
import time
import gzip
import MDSplus # type: ignore
import numpy as np
from django.http import JsonResponse, HttpResponse
import uuid
import threading
from django.utils import timezone
from datetime import datetime
import unicodedata  # 添加这一行来导入unicodedata模块
from django.views.decorators.csrf import csrf_exempt  # 添加CSRF豁免
from django.views.decorators.http import require_GET

from api.self_algorithm_utils import period_condition_anomaly
from api.Mds import MdsTree
from api.verify_user import send_post_request
from api.pattern_matching_Qetch import match_pattern  # 只导入模式匹配函数
from pymongo import MongoClient, ASCENDING, UpdateMany
from collections import defaultdict

# 存储计算任务状态的字典
calculation_tasks = {}

# MongoDB 配置：
client = MongoClient("mongodb://localhost:27017")
# 移除固定的db赋值，改为根据请求参数动态选择数据库
# db = client["DataDiagnosticPlatform_4949_5071"]
# 改为在各函数中动态获取数据库参数

# 获取数据库实例的辅助函数
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
        if filtered_db_names:
            db = client[filtered_db_names[0]]
        else:
            db = client["DataDiagnosticPlatform_4949_5071"]  # 如果没有找到，使用默认值
    else:
        db_name = f"DataDiagnosticPlatform_{db_suffix}"
        db = client[db_name]
    
    # 确保数据库具有必要的索引
    return ensure_db_indices(db)

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

def get_struct_tree(request):
    """
    获取结构树数据，支持shot_numbers, channel_names, error_names多条件过滤
    返回时整体按channel_type、channel_name排序。
    """
    shot_numbers = request.GET.get('shot_numbers')
    channel_names = request.GET.get('channel_names')
    error_names = request.GET.get('error_names')
    db_suffix = request.GET.get('db_suffix')  # 新增参数
    
    shot_numbers = shot_numbers.split(',') if shot_numbers else []
    channel_names = channel_names.split(',') if channel_names else []
    error_names = error_names.split(',') if error_names else []

    # 获取对应的数据库
    db = get_db(db_suffix)
    struct_trees_collection = db["struct_trees"]

    query = {}
    if shot_numbers:
        query['shot_number'] = {'$in': shot_numbers}
    docs = struct_trees_collection.find(query)
    result = []
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
    # 整体排序：先按channel_type，再按channel_name
    result.sort(key=lambda x: (x.get('channel_type', ''), x.get('channel_name', '')))
    return OrJsonResponse(result)

def get_shot_number_index(request):
    """
    获取所有炮号列表
    """
    db_suffix = request.GET.get('db_suffix')  # 新增参数
    db = get_db(db_suffix)
    index_collection = db["index"]
    
    try:
        # 检查集合是否存在
        collections = db.list_collection_names()
        if 'index' not in collections:
            print(f"警告: 数据库 {db.name} 中不存在'index'集合，从struct_trees集合获取炮号")
            
            # 如果索引集合不存在，尝试从struct_trees集合获取炮号
            if 'struct_trees' in collections:
                # 从struct_trees集合获取炮号
                shot_numbers = set(db["struct_trees"].distinct("shot_number"))
                return OrJsonResponse(sorted(list(shot_numbers)))
            else:
                print(f"警告: 数据库 {db.name} 中不存在struct_trees集合")
                return OrJsonResponse([])
        
        all_docs = list(index_collection.find({}))
        shot_numbers = set()
        for doc in all_docs:
            shot_numbers.update(doc.get("index_data", {}).keys())
        return OrJsonResponse(sorted(list(shot_numbers)))
    except Exception as e:
        import traceback
        error_msg = f"获取炮号索引出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({"error": error_msg}, status=500)

def get_index_by_key(key, request):
    """
    通用索引获取函数，支持按炮号过滤
    """
    shot_numbers = request.GET.getlist('shot_numbers[]') or request.GET.get('shot_numbers')
    db_suffix = request.GET.get('db_suffix')  # 新增参数
    
    print(f"获取索引，key={key}, db_suffix={db_suffix}, shot_numbers={shot_numbers}")
    
    if isinstance(shot_numbers, str):
        shot_numbers = [shot_numbers]
    
    db = get_db(db_suffix)
    index_collection = db["index"]
    
    try:
        # 检查集合是否存在
        collections = db.list_collection_names()
        if 'index' not in collections:
            print(f"警告: 数据库 {db.name} 中不存在'index'集合")
            return OrJsonResponse({"error": f"数据库 {db.name} 中不存在索引集合", "collections": collections}, status=404)
        
        # 检查索引数据是否存在
        doc = index_collection.find_one({'key': key})
        print(f"查询索引集合结果: key={key}, 结果={doc is not None}")
        
        result = {}
        if doc and "index_data" in doc:
            print(f"索引数据大小: {len(doc['index_data'])}")
            if shot_numbers:
                # 检查每个炮号是否在索引中
                for shot in shot_numbers:
                    if shot in doc["index_data"]:
                        for name, indices in doc["index_data"].get(shot, {}).items():
                            if name not in result:
                                result[name] = set()
                            result[name].update(indices)
                    else:
                        print(f"炮号 {shot} 不在索引中")
                result = {k: list(v) for k, v in result.items()}
            else:
                for shot, name_dict in doc["index_data"].items():
                    for name, indices in name_dict.items():
                        if name not in result:
                            result[name] = set()
                        result[name].update(indices)
                result = {k: list(v) for k, v in result.items()}
            
            print(f"处理后的结果大小: {len(result)}")
            return OrJsonResponse(result)
        else:
            print(f"索引数据不存在: key={key}")
            return OrJsonResponse({})
    except Exception as e:
        import traceback
        error_msg = f"获取索引出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return OrJsonResponse({"error": error_msg}, status=500)

def get_channel_type_index(request):
    return get_index_by_key('channel_type', request)

def get_channel_name_index(request):
    return get_index_by_key('channel_name', request)

def get_errors_name_index(request):
    return get_index_by_key('error_name', request)

def get_error_origin_index(request):
    return get_index_by_key('error_origin', request)

def get_error_data(request):
    """
    获取异常数据，直接查MongoDB
    """
    channel_key = request.GET.get('channel_key')
    channel_type = request.GET.get('channel_type')
    error_name = request.GET.get('error_name')
    error_index = request.GET.get('error_index')
    db_suffix = request.GET.get('db_suffix')  # 新增参数
    
    if channel_key and channel_type and error_name and error_index is not None:
        try:
            error_index = int(error_index)
        except ValueError:
            return OrJsonResponse({'error': 'Invalid error_index'}, status=400)
        if '_' in channel_key:
            channel_name, shot_number = channel_key.rsplit('_', 1)
        else:
            return OrJsonResponse({'error': 'Invalid channel_key format'}, status=400)
            
        db = get_db(db_suffix)
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
        db_suffix = request.GET.get('db_suffix')  # 新增参数
        
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
    
    def parse(self, expression):
        """解析表达式并计算结果"""
        self.tokenize(expression)
        self.current = 0
        return self.expression()
    
    def tokenize(self, expression):
        """将表达式分词"""
        # 去除所有空格
        expression = expression.replace(" ", "")
        
        # 实现一个简单的分词器
        self.tokens = []
        i = 0
        
        while i < len(expression):
            char = expression[i]
            
            # 处理运算符和括号
            if char in "+-*/()":
                self.tokens.append(char)
                i += 1
            # 处理通道标识符（字母、数字、下划线的组合）
            elif char.isalnum() or char == '_':
                start = i
                # 继续读取直到遇到非标识符字符
                while i < len(expression) and (expression[i].isalnum() or expression[i] == '_'):
                    i += 1
                self.tokens.append(expression[start:i])
            else:
                i += 1
        
        return self.tokens
    
    def expression(self):
        """解析加减运算"""
        result = self.term()
        
        while self.current < len(self.tokens) and self.tokens[self.current] in ['+', '-']:
            operator = self.tokens[self.current]
            self.current += 1
            right = self.term()
            
            if operator == '+':
                # 确保X轴数据匹配
                min_len = min(len(result['X_value']), len(right['X_value']))
                result['X_value'] = result['X_value'][:min_len]
                result['Y_value'] = result['Y_value'][:min_len]
                right['X_value'] = right['X_value'][:min_len]
                right['Y_value'] = right['Y_value'][:min_len]
                
                # 执行加法
                result['Y_value'] = [x + y for x, y in zip(result['Y_value'], right['Y_value'])]
            elif operator == '-':
                # 确保X轴数据匹配
                min_len = min(len(result['X_value']), len(right['X_value']))
                result['X_value'] = result['X_value'][:min_len]
                result['Y_value'] = result['Y_value'][:min_len]
                right['X_value'] = right['X_value'][:min_len]
                right['Y_value'] = right['Y_value'][:min_len]
                
                # 执行减法
                result['Y_value'] = [x - y for x, y in zip(result['Y_value'], right['Y_value'])]
        
        return result
    
    def term(self):
        """解析乘除运算"""
        result = self.factor()
        
        while self.current < len(self.tokens) and self.tokens[self.current] in ['*', '/']:
            operator = self.tokens[self.current]
            self.current += 1
            right = self.factor()
            
            if operator == '*':
                # 确保X轴数据匹配
                min_len = min(len(result['X_value']), len(right['X_value']))
                result['X_value'] = result['X_value'][:min_len]
                result['Y_value'] = result['Y_value'][:min_len]
                right['X_value'] = right['X_value'][:min_len]
                right['Y_value'] = right['Y_value'][:min_len]
                
                # 执行乘法
                result['Y_value'] = [x * y for x, y in zip(result['Y_value'], right['Y_value'])]
            elif operator == '/':
                # 确保X轴数据匹配
                min_len = min(len(result['X_value']), len(right['X_value']))
                result['X_value'] = result['X_value'][:min_len]
                result['Y_value'] = result['Y_value'][:min_len]
                right['X_value'] = right['X_value'][:min_len]
                right['Y_value'] = right['Y_value'][:min_len]
                
                # 执行除法，避免除以0
                result['Y_value'] = [x / y if y != 0 else float('inf') for x, y in zip(result['Y_value'], right['Y_value'])]
        
        return result
    
    def factor(self):
        """解析括号和通道标识符"""
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
            
            # 处理通道标识符
            elif token.isalnum() or '_' in token:
                self.current += 1
                # 获取通道数据
                channel_key = token
                
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
                
                return channel_data
        
        raise ValueError(f"意外的标记: {self.tokens[self.current] if self.current < len(self.tokens) else 'EOF'}")


def init_calculation(request):
    """初始化计算任务，返回唯一任务ID"""
    try:
        data = json.loads(request.body)
        expression = data.get('expression', '')
        
        # 生成唯一任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        calculation_tasks[task_id] = {
            'status': 'pending',
            'step': '准备计算',
            'progress': 0,
            'expression': expression,
            'start_time': timezone.now().isoformat(),
            'last_update': timezone.now().isoformat(),
        }
        
        return OrJsonResponse({'task_id': task_id, 'status': 'initialized'})
    except Exception as e:
        return OrJsonResponse({'error': str(e)}, status=500)

def get_calculation_progress(request, task_id):
    """获取计算任务的进度"""
    try:
        if task_id not in calculation_tasks:
            return OrJsonResponse({'error': '找不到指定的任务'}, status=404)
        
        task_info = calculation_tasks[task_id]
        
        # 清理过期任务（超过30分钟的任务）
        current_time = timezone.now()
        for t_id in list(calculation_tasks.keys()):
            last_update = datetime.fromisoformat(calculation_tasks[t_id]['last_update'])
            if (current_time - last_update).total_seconds() > 1800:  # 30分钟
                calculation_tasks.pop(t_id, None)
        
        return OrJsonResponse(task_info)
    except Exception as e:
        return OrJsonResponse({'error': str(e)}, status=500)

def update_calculation_progress(task_id, step, progress, status='processing'):
    """更新计算任务的进度（供内部使用）"""
    if task_id in calculation_tasks:
        calculation_tasks[task_id].update({
            'status': status,
            'step': step,
            'progress': progress,
            'last_update': timezone.now().isoformat()
        })

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
        
        # 如果提供了任务ID，进行进度更新
        if task_id and task_id in calculation_tasks:
            update_calculation_progress(task_id, '解析表达式', 10)
        
        print(f"收到计算请求: {anomaly_func_str}")
        print(f"采样率设置: {sample_freq} KHz")
        # print(f"通道数据: {len(channel_mess) if isinstance(channel_mess, list) else 1} 个通道")

        # 判定是否函数名是导入函数
        end_idx = anomaly_func_str.find('(')
        is_function_call = end_idx > 0 and anomaly_func_str[0].isalpha() and ')' in anomaly_func_str[end_idx:]

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
            
        # 更新进度：准备数据完成
        if task_id and task_id in calculation_tasks:
            update_calculation_progress(task_id, '准备数据完成', 20)

        # 检查是否是函数调用
        if is_function_call:
            func_name = anomaly_func_str[:end_idx]
            print(func_name)

            # 确保FUNCTIONS_FILE_PATH变量存在
            functions_file_path = os.path.join(settings.MEDIA_ROOT, "imported_functions.json")
            
            if os.path.exists(functions_file_path):
                with open(functions_file_path, "r", encoding='utf-8') as f:
                    functions_data = json.load(f)
            else:
                functions_data = []
            is_import_func = False
            for function in functions_data:
                if function['name'] == func_name:
                    is_import_func = True
                    
            # 更新进度：函数识别完成
            if task_id and task_id in calculation_tasks:
                update_calculation_progress(task_id, '函数识别完成', 30)

            if is_import_func:
                # 更新进度：开始执行函数
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, f'执行函数 {func_name}', 40)
                    
                data = {}
                data['function_name'] = func_name
                params_str = anomaly_func_str[end_idx:].replace(" ", "").replace("(", "").replace(")", "")
                data['parameters'] = params_str.split(',')

                ##
                # 需要补一段输入参数转换的代码
                ##
                # data['parameters'] = [float(i) for i in data['parameters']]
                if len(data['parameters']) > 1:  # 确保有足够的参数再访问索引1
                    data['parameters'][1] = float(data['parameters'][1])
                    
                # 更新进度：函数参数解析完成
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '函数参数解析完成', 50)
                    
                ret = execute_function(data)
                
                # 更新进度：函数执行完成
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '函数执行完成', 90)
                    
                # 标记计算完成
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '计算完成', 100, 'completed')
                    
                return JsonResponse({"data": ret}, status=200)
            else:
                # 在这里可以添加对channel_names的处理逻辑
                print("operator-strs:", anomaly_func_str)
                
                # 更新进度：开始特殊函数处理
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '开始特殊函数处理', 40)
                    
                if anomaly_func_str[:3] == 'Pca':
                    print('xxxx')
                    
                    # 更新进度：开始PCA分析
                    if task_id and task_id in calculation_tasks:
                        update_calculation_progress(task_id, '开始PCA分析', 50)
                        
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
                        update_calculation_progress(task_id, 'PCA分析中', 70)
                        
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
                        update_calculation_progress(task_id, f'未知的函数: {func_name}', 0, 'failed')
                        
                    raise ValueError(f"未知的函数: {func_name}")
        else:
            # 更新进度：开始表达式解析
            if task_id and task_id in calculation_tasks:
                update_calculation_progress(task_id, '开始表达式解析', 40)
                
            # 检查表达式是否包含括号或运算符
            if '(' in anomaly_func_str or ')' in anomaly_func_str or any(op in anomaly_func_str for op in ['+', '-', '*', '/']):
                # 使用表达式解析器处理带括号和运算优先级的表达式
                print(f"正在解析复杂表达式: {anomaly_func_str}")
                
                # 更新进度：解析复杂表达式
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '解析复杂表达式', 50)
                    
                # 修改表达式解析器初始化，传入采样率
                parser = ExpressionParser(lambda req, key: get_channel_data(create_mock_request(key, sample_freq), key))
                
                # 更新进度：获取通道数据
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '获取通道数据', 60)
                    
                result = parser.parse(anomaly_func_str)
                
                # 更新进度：计算表达式结果
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '计算表达式结果', 80)
                
                # 设置结果通道名
                result['channel_name'] = anomaly_func_str
                
                # 标记计算完成
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, '计算完成', 100, 'completed')
                    
                return JsonResponse({"data": {"result": result}}, status=200)
            else:
                # 处理单通道情况
                channel_key = anomaly_func_str.strip()
                
                # 更新进度：查找通道数据
                if task_id and task_id in calculation_tasks:
                    update_calculation_progress(task_id, f'查找通道: {channel_key}', 50)
                    
                if channel_key in channel_map:
                    try:
                        # 更新进度：获取通道数据
                        if task_id and task_id in calculation_tasks:
                            update_calculation_progress(task_id, f'获取通道数据: {channel_key}', 70)
                            
                        # 创建包含采样率的请求对象
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
                            update_calculation_progress(task_id, '处理通道数据', 90)
                            
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
        if 'task_id' in data and data['task_id'] in calculation_tasks:
            update_calculation_progress(data['task_id'], f'计算出错: {str(e)}', 0, 'failed')
            
        # 打印详细错误信息以便调试
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)

# 添加一个创建模拟请求对象的辅助函数
def create_mock_request(channel_key, sample_freq):
    """创建一个包含采样率的模拟请求对象"""
    class MockRequest:
        def __init__(self, channel_key, sample_freq):
            self.GET = {
                'channel_key': channel_key,
                'sample_mode': 'downsample',
                'sample_freq': sample_freq
            }
    
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
    import matlab.engine

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
        for func_name, params in functions.items():
            update_functions_file(fileInfo)

        return JsonResponse({"functions": [{"name": k, "parameters": v} for k, v in functions.items()]})
    ##
    # 需要补一段用到 fileinfo 的代码，将前端输入的函数文件信息保存到 imported_functions 里
    ##

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

@csrf_exempt
def execute_function(data):
    """
    执行函数
    """
    global loaded_module
    function_name = data.get("function_name")
    parameters = data.get("parameters", [])

    # 参数逻辑更换，如通道名的数据切换为通道数据
    if os.path.exists(FUNCTIONS_FILE_PATH):
        with open(FUNCTIONS_FILE_PATH, "r", encoding='utf-8') as f:
            functions_data = json.load(f)

    matched_func = next((d for d in functions_data if d.get('name') == function_name), None)
    for idx, param in enumerate(matched_func['input']):
        if param['paraType'] == '通道对象':
            cur_param = parameters[idx]
            response = get_channel_data('', cur_param)
            ret = json.loads(response.content.decode('utf-8'))
            fields_values = sum(([k, matlab.double(v) if isinstance(v, list) else v] for k, v in ret.items()), [])
            parameters[idx] = eng.feval('struct', *fields_values)

    if loaded_module:
        # Execute Python function
        func = getattr(loaded_module, function_name, None)
        if not func:
            return {"error": "Function not found"}
        try:
            result = func(*parameters)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    elif matlab_engine_available:
        # Execute MATLAB function
        try:
            result = getattr(eng, function_name)(*parameters)
            result = json.loads(result)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    else:
        return {"error": "MATLAB engine is not available"}

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
        db_suffix = data.get('db_suffix')  # 新增参数
        db = get_db(db_suffix)
        errors_collection = db["errors_data"]
        struct_trees_collection = db["struct_trees"]
        index_collection = db["index"]
        
        for channel_data in data.get('channels', []):  # 假设数据结构调整为包含channels字段
            channel_key = channel_data['channelKey']
            manual_errors, machine_errors = channel_data['errorData']
            channel_name, shot_number = channel_key.rsplit('_', 1)
            shot_number = str(shot_number)
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
        db_suffix = data.get('db_suffix')  # 新增参数
        
        if not all([diagnostic_name, channel_number, shot_number, error_type]):
            return JsonResponse({'error': '缺少必要参数', 'data': data}, status=400)
            
        db = get_db(db_suffix)
        errors_collection = db["errors_data"]
        struct_trees_collection = db["struct_trees"]
        index_collection = db["index"]
        
        shot_number = str(shot_number)
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
        
    # selected_channels 格式为 [{'channel_name': 'B07_H', 'shot_number': '4470', 'channel_type': 'B'},...]
    # raw_query_pattern 格式为 [{'x': 0.1, 'y': 0.1, 'handleOut': {'x': 0.1, 'y': 0.1}, 'handleIn': {'x': 0.1, 'y': 0.1}},...] 为贝塞尔曲线
    print(f"接收到手绘查询请求: 采样率={sampling}KHz, 选择通道数={len(selected_channels)}, 路径点数={len(raw_query_pattern)}")
    
    try:
        # 将贝塞尔曲线转换为采样点序列并归一化
        normalized_curve = bezier_to_points(raw_query_pattern)
        
        # 创建修改后的通道数据获取函数
        def get_channel_data_local(channel, sampling_rate, db_suffix):
            """为模式匹配专门定制的获取通道数据的函数"""
            channel_key = f"{channel['channel_name']}_{channel['shot_number']}"
            
            # 创建一个模拟请求对象
            class MockRequest:
                def __init__(self, channel_key, sample_freq, db_suffix):
                    self.GET = {
                        'channel_key': channel_key,
                        'sample_mode': 'downsample',
                        'sample_freq': sample_freq,
                        'db_suffix': db_suffix  # 添加数据库参数
                    }
                
            mock_request = MockRequest(channel_key, sampling_rate, db_suffix)
            
            # 直接调用views中的get_channel_data函数
            response = get_channel_data(mock_request)
            
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
            channel_data = get_channel_data_local(channel, sampling, db_suffix)
            if channel_data:
                # 添加通道信息到数据中
                channel_data['channel_name'] = channel['channel_name']
                channel_data['shot_number'] = channel['shot_number']
                channel_data_list.append(channel_data)
        
        # 执行模式匹配
        
        results = match_pattern(normalized_curve, channel_data_list)
        
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
    POST请求，参数格式：
    {
        "db_suffix": "4949_5071",  // 新增参数
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
        db_suffix = data.get('db_suffix')  # 新增参数
        
        if not channels:
            return JsonResponse({'error': 'No channels provided'}, status=400)
            
        db = get_db(db_suffix)
        struct_trees_collection = db["struct_trees"]
        
        result = []
        for channel_info in channels:
            channel_name = channel_info.get('channel_name')
            shot_number = channel_info.get('shot_number')
            channel_type = channel_info.get('channel_type')
            if not channel_name or not shot_number:
                continue
            doc = struct_trees_collection.find_one({'shot_number': str(shot_number)})
            channel_errors = []
            if doc and "struct_tree" in doc:
                for item in doc["struct_tree"]:
                    if (item.get('channel_type') == channel_type and 
                        item.get('channel_name') == channel_name and 
                        str(item.get('shot_number')) == str(shot_number)):
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
            result.append({
                "channel_name": channel_name,
                "shot_number": shot_number,
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


