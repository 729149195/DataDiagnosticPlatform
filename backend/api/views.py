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

from api.self_algorithm_utils import period_condition_anomaly
from api.Mds import MdsTree
from api.verify_user import send_post_request
from api.pattern_matching import match_pattern  # 只导入模式匹配函数

# 存储计算任务状态的字典
calculation_tasks = {}

class JsonEncoder(json.JSONEncoder):
    """Convert numpy classes to JSON serializable objects."""

    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(JsonEncoder, self).default(obj)

def get_struct_tree(request):
    try:
        with open(os.path.join('static', 'StructTree.json'), encoding='unicode_escape') as f:
            data = json.load(f)
        indices_param = request.GET.get('indices', '')
        if indices_param:
            indices = [int(i) for i in indices_param.split(',') if i.strip().isdigit()]
            filtered_data = [data[i] for i in indices if 0 <= i < len(data)]
            return JsonResponse(filtered_data, safe=False)
        else:
            return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def get_shot_number_index(request):
    try:
        with open(os.path.join('static', 'IndexFile', 'shot_number_index.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def get_channel_type_index(request):
    try:
        with open(os.path.join('static', 'IndexFile', 'channel_type_index.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def get_channel_name_index(request):
    try:
        with open(os.path.join('static', 'IndexFile', 'channel_name_index.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def get_errors_name_index(request):
    try:
        with open(os.path.join('static', 'IndexFile', 'error_name_index.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)   
     
def get_error_origin_index(request):
    try:
        with open(os.path.join('static', 'IndexFile', 'error_origin_index.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def downsample_to_frequency(x_values, y_values, target_freq=1000):
    """
    对数据进行高效降采样到指定频率
    
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
    
    # 使用高效的矢量化操作进行降采样
    # 方法一：直接等间隔抽样（速度最快）
    if sample_ratio > 10:  # 对于高降采样比率，使用混合策略
        # 方法：先等距离取固定点，加上局部极值点
        # 计算每个区间的索引
        indices = np.arange(0, len(x_values), sample_ratio)[:n_samples]
        
        # 确保长度匹配
        if len(indices) > n_samples:
            indices = indices[:n_samples]
        elif len(indices) < n_samples:
            # 补足点数
            extra_indices = np.linspace(0, len(x_values)-1, n_samples-len(indices)).astype(int)
            indices = np.sort(np.concatenate([indices, extra_indices]))
            
        new_times = x_values[indices]
        new_values = y_values[indices]
    else:
        # 方法二：对于降采样程度不高的情况，使用线性插值（平滑且快速）
        new_times = np.linspace(time_start, time_end, n_samples)
        new_values = np.interp(new_times, x_values, y_values)
    
    print(f"高效降采样: 从 {len(x_values)} 点 降至 {len(new_times)} 点")
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
def OrJsonResponse(data):
    """使用orjson创建更快的JsonResponse，同时保持对numpy的支持"""
    # orjson不需要自定义encoder，它内置支持numpy类型
    # 设置option保持精度和按顺序输出
    return HttpResponse(
        orjson.dumps(data, option=orjson.OPT_SERIALIZE_NUMPY),
        content_type='application/json'
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
                    return JsonResponse({'error': f"无法将炮号转换为整数: '{shot_number}'"}, status=400)
            else:
                return JsonResponse({'error': 'Invalid channel_key format'}, status=400)
            
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
            return JsonResponse({'error': 'channel_key or channel_type parameter is missing'}, status=400)
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
        return JsonResponse({'error': str(e)}, status=500)

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

def get_error_data(request):
    """
    获取异常数据
    """
    try:
        channel_key = request.GET.get('channel_key')
        channel_type = request.GET.get('channel_type')
        error_name = request.GET.get('error_name')
        error_index = request.GET.get('error_index')

        if channel_key and channel_type and error_name and error_index is not None:
            try:
                error_index = int(error_index)
            except ValueError:
                return JsonResponse({'error': 'Invalid error_index'}, status=400)

            if '_' in channel_key:
                channel_name, shot_number = channel_key.rsplit('_', 1)
            else:
                return JsonResponse({'error': 'Invalid channel_key format'}, status=400)

            anomaly_file_name = f"{error_name}{error_index}.json"

            file_path = os.path.join(
                'static', 'ErrorData', f'{shot_number}_{channel_name}_{error_name}.json'
            )

            if os.path.exists(file_path):
                with open(file_path, encoding='unicode_escape') as f:
                    data = json.load(f)
                return JsonResponse(data, encoder=JsonEncoder, safe=False)
            else:
                return JsonResponse({'error': 'File not found'}, status=404)


        else:
            return JsonResponse({'error': 'Required parameters are missing'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
                
                # 创建一个模拟请求对象
                class MockRequest:
                    def __init__(self, channel_key):
                        self.GET = {'channel_key': channel_key, 'sample_mode': 'downsample'}
                
                mock_request = MockRequest(channel_key)
                response = self.get_channel_data_func(mock_request, channel_key)
                
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
        
        return JsonResponse({'task_id': task_id, 'status': 'initialized'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_calculation_progress(request, task_id):
    """获取计算任务的进度"""
    try:
        if task_id not in calculation_tasks:
            return JsonResponse({'error': '找不到指定的任务'}, status=404)
        
        task_info = calculation_tasks[task_id]
        
        # 清理过期任务（超过30分钟的任务）
        current_time = timezone.now()
        for t_id in list(calculation_tasks.keys()):
            last_update = datetime.fromisoformat(calculation_tasks[t_id]['last_update'])
            if (current_time - last_update).total_seconds() > 1800:  # 30分钟
                calculation_tasks.pop(t_id, None)
        
        return JsonResponse(task_info)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
        
        # 如果提供了任务ID，进行进度更新
        if task_id and task_id in calculation_tasks:
            update_calculation_progress(task_id, '解析表达式', 10)
        
        print(f"收到计算请求: {anomaly_func_str}")
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
                    
                parser = ExpressionParser(get_channel_data)
                
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
                            
                        response = get_channel_data('', channel_key)
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

def sync_error_data(request):
    """
    同步异常标注数据
    """
    try:
        # 获取请求数据
        data = json.loads(request.body)
        
        # 读取现有的 StructTree.json
        struct_tree_path = os.path.join('static', 'StructTree.json')
        with open(struct_tree_path, 'r', encoding='utf-8') as f:
            struct_tree = json.load(f)

        # 处理每个通道的数据
        for channel_data in data:
            channel_key = channel_data['channelKey']
            manual_errors, machine_errors = channel_data['errorData']

            # 从 channel_key 解析通道信息
            channel_name, shot_number = channel_key.rsplit('_', 1)

            # 转换人工标注数据格式
            converted_manual_errors = []
            for error in manual_errors:
                # 检查必要字段是否存在且不为空
                if not error.get('anomalyCategory') or not error.get('anomalyDiagnosisName'):
                    continue

                converted_error = {
                    "person": error.get('person', 'unknown'),
                    "diagnostic_name": error.get('anomalyDiagnosisName', ''),
                    "channel_number": channel_name,
                    "error_type": error.get('anomalyCategory', ''),
                    "shot_number": shot_number,
                    "X_error": [[float(error.get('startX', 0)), float(error.get('endX', 0))]],
                    "Y_error": [],
                    "diagnostic_time": error.get('annotationTime', ''),
                    "error_description": error.get('anomalyDescription', '')
                }
                # 只有当 error_type 不为空时才添加
                if converted_error['error_type'].strip():
                    converted_manual_errors.append(converted_error)

            # 对每个异常类型创建或更新文件
            error_types = set()
            # 只添加非空的 error_type
            for error in converted_manual_errors:
                if error['error_type'].strip():
                    error_types.add(error['error_type'])
            for error in machine_errors:
                if error.get('error_type', '').strip():
                    error_types.add(error['error_type'])

            for error_type in error_types:
                # 跳过空的 error_type
                if not error_type.strip():
                    continue

                # 构建文件名
                error_file_name = f"{shot_number}_{channel_name}_{error_type}.json"
                error_file_path = os.path.join('static', 'ErrorData', error_file_name)

                # 准备新的错误数据
                current_manual_errors = [error for error in converted_manual_errors if error['error_type'] == error_type]
                current_machine_errors = [error for error in machine_errors if error['error_type'] == error_type]

                # 如果文件已存在，读取现有数据并合并
                if os.path.exists(error_file_path):
                    with open(error_file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        
                    # 合并人工标注数据
                    existing_manual_errors = existing_data[0]
                    # 使用字典来去重，基于 person, startX, endX 的组合
                    manual_error_dict = {
                        f"{error.get('person')}_{error.get('X_error', [[]])[0][0]}_{error.get('X_error', [[]])[0][1]}": error 
                        for error in existing_manual_errors
                    }
                    # 添加新的人工标注数据
                    for error in current_manual_errors:
                        key = f"{error.get('person')}_{error.get('X_error', [[]])[0][0]}_{error.get('X_error', [[]])[0][1]}"
                        manual_error_dict[key] = error
                    
                    # 合并机器识别数据
                    existing_machine_errors = existing_data[1]
                    # 使用字典来去重，基于 X_error 的组合
                    machine_error_dict = {
                        f"{error.get('X_error', [[]])[0][0]}_{error.get('X_error', [[]])[0][1]}": error 
                        for error in existing_machine_errors
                    }
                    # 添加新的机器识别数据
                    for error in current_machine_errors:
                        key = f"{error.get('X_error', [[]])[0][0]}_{error.get('X_error', [[]])[0][1]}"
                        machine_error_dict[key] = error

                    # 准备最终的合并数据
                    merged_data = [
                        list(manual_error_dict.values()),
                        list(machine_error_dict.values())
                    ]

                    # 保存合并后的数据
                    with open(error_file_path, 'w', encoding='utf-8') as f:
                        json.dump(merged_data, f, indent=2, ensure_ascii=False)
                else:
                    # 创建新文件
                    new_error_data = [current_manual_errors, current_machine_errors]
                    with open(error_file_path, 'w', encoding='utf-8') as f:
                        json.dump(new_error_data, f, indent=2, ensure_ascii=False)
                    
                    # 更新 StructTree.json
                    for item in struct_tree:
                        if (item['shot_number'] == shot_number and 
                            item['channel_name'] == channel_name):
                            # 确保 error_name 是列表
                            if 'error_name' not in item:
                                item['error_name'] = []
                            # 只有当 error_type 不为空且不在列表中时才添加
                            if error_type.strip() and error_type not in item['error_name']:
                                item['error_name'].append(error_type)
                            break

        # 保存更新后的 StructTree.json
        with open(struct_tree_path, 'w', encoding='utf-8') as f:
            json.dump(struct_tree, f, indent=2, ensure_ascii=False)

        return JsonResponse({'message': '同步成功'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def delete_error_data(request):
    """
    删除指定通道的指定错误类型数据
    """
    try:
        # 获取请求数据
        data = json.loads(request.body)
        diagnostic_name = data.get('diagnostic_name')
        channel_number = data.get('channel_number')
        shot_number = data.get('shot_number')
        error_type = data.get('error_type')
        
        # 记录删除请求
        print(f"收到删除请求: {data}")

        if not all([diagnostic_name, channel_number, shot_number, error_type]):
            return JsonResponse({'error': '缺少必要参数', 'data': data}, status=400)

        # 构建错误数据文件路径
        error_file_name = f"{shot_number}_{channel_number}_{error_type}.json"
        error_file_path = os.path.join('static', 'ErrorData', error_file_name)
        
        print(f"查找文件: {error_file_path}")

        # 检查文件是否存在
        if not os.path.exists(error_file_path):
            # 尝试创建目录（如果不存在）
            os.makedirs(os.path.join('static', 'ErrorData'), exist_ok=True)
            
            # 如果文件不存在，直接返回成功（可能已经被删除）
            return JsonResponse({'message': '未找到文件，可能已被删除', 'file': error_file_name})

        # 读取错误数据文件
        with open(error_file_path, 'r', encoding='utf-8') as f:
            error_data = json.load(f)

        # 分别处理人工标注和机器标注数据
        manual_errors, machine_errors = error_data

        # 从人工标注数据中移除指定的异常
        manual_errors = [error for error in manual_errors 
                        if error.get('diagnostic_name') != diagnostic_name]

        # 从机器标注数据中移除指定的异常
        machine_errors = [error for error in machine_errors 
                         if error.get('diagnostic_name') != diagnostic_name]

        # 保存更新后的数据
        updated_error_data = [manual_errors, machine_errors]
        with open(error_file_path, 'w', encoding='utf-8') as f:
            json.dump(updated_error_data, f, indent=2, ensure_ascii=False)

        # 如果两个列表都为空，删除文件
        if not manual_errors and not machine_errors:
            os.remove(error_file_path)

            # 更新 StructTree.json
            struct_tree_path = os.path.join('static', 'StructTree.json')
            if os.path.exists(struct_tree_path):
                with open(struct_tree_path, 'r', encoding='utf-8') as f:
                    struct_tree = json.load(f)

                # 更新对应通道的 error_name
                for item in struct_tree:
                    if (str(item.get('shot_number')) == str(shot_number) and 
                        item.get('channel_name') == channel_number and 
                        'error_name' in item):
                        # 从 error_name 列表中移除对应的错误类型
                        if error_type in item['error_name']:
                            item['error_name'].remove(error_type)
                        break

                # 保存更新后的 StructTree.json
                with open(struct_tree_path, 'w', encoding='utf-8') as f:
                    json.dump(struct_tree, f, indent=2, ensure_ascii=False)

        return JsonResponse({'message': '删除成功', 'file': error_file_name})
    except Exception as e:
        import traceback
        print(f"删除错误数据时发生异常: {str(e)}")
        traceback.print_exc()
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
        def get_channel_data_local(channel, sampling_rate):
            """为模式匹配专门定制的获取通道数据的函数"""
            channel_key = f"{channel['channel_name']}_{channel['shot_number']}"
            
            # 创建一个模拟请求对象
            class MockRequest:
                def __init__(self, channel_key, sample_freq):
                    self.GET = {
                        'channel_key': channel_key,
                        'sample_mode': 'downsample',
                        'sample_freq': sample_freq
                    }
                
            mock_request = MockRequest(channel_key, sampling_rate)
            
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
            channel_data = get_channel_data_local(channel, sampling)
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
        # 获取请求数据
        data = json.loads(request.body)
        channels = data.get('channels', [])
        
        if not channels:
            return JsonResponse({'error': 'No channels provided'}, status=400)
        
        # 读取结构树数据
        with open(os.path.join('static', 'StructTree.json'), encoding='unicode_escape') as f:
            struct_tree = json.load(f)
        
        # 准备返回的结果
        result = []
        
        # 遍历请求的通道，获取每个通道的异常数据
        for channel_info in channels:
            channel_name = channel_info.get('channel_name')
            shot_number = channel_info.get('shot_number')
            channel_type = channel_info.get('channel_type')
            
            if not channel_name or not shot_number:
                continue
            
            # 查找通道在结构树中的数据
            channel_errors = []
            for item in struct_tree:
                if (item.get('channel_type') == channel_type and 
                    item.get('channel_name') == channel_name and 
                    item.get('shot_number') == shot_number):
                    # 找到匹配的通道，获取其异常数据
                    error_names = item.get('error_name', [])
                    if not error_names:
                        error_names = ["NO ERROR"]
                    
                    # 构建异常数据
                    channel_errors = [
                        {
                            "error_name": error_name,
                            "color": "rgba(0, 0, 0, 0)" if error_name == "NO ERROR" else "rgba(220, 20, 60, 0.3)"
                        }
                        for error_name in error_names
                    ]
                    break
            
            # 添加到结果中
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
 



