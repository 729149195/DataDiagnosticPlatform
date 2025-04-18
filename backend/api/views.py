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

from api.self_algorithm_utils import period_condition_anomaly
from api.Mds import MdsTree
from api.verify_user import send_post_request

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
    对数据进行降采样到指定频率
    
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
    
    # 使用NumPy的线性插值计算新的采样点
    # 创建均匀分布的时间点
    new_times = np.linspace(time_start, time_end, n_samples)
    
    # 使用插值计算对应的Y值
    new_values = np.interp(new_times, x_values, y_values)
    
    print(f"降采样: 从 {len(x_values)} 点 降至 {len(new_times)} 点")
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
    start_time = time.time()
    try:
        if channel_key is None:
            channel_key = request.GET.get('channel_key')
        else:
            pass
        
        # 获取采样参数，默认采用降采样
        sample_mode = request.GET.get('sample_mode', 'downsample')  # 可选值: 'full', 'downsample'
        sample_freq = int(request.GET.get('sample_freq', 1000))     # 默认1KHz
        
        # 调试输出
        print(f"请求通道数据，通道键: '{channel_key}', 采样模式: {sample_mode}, 频率: {sample_freq} Hz")
        
        # channel_type = request.GET.get('channel_type')
        if channel_key: # and channel_type:
            if '_' in channel_key:
                # 解析通道键格式
                channel_name, shot_number = channel_key.rsplit('_', 1)
                try:
                    num = int(channel_name)
                    channel_name, shot_number = shot_number, channel_name
                    print(f"格式交换: '{channel_name}_{shot_number}' (通道名_炮号)")
                except ValueError:
                    # 格式已正确为"通道名_炮号"
                    print(f"正确格式: '{channel_name}_{shot_number}' (通道名_炮号)")
                    pass
                    
                try:
                    shot_number = int(shot_number)
                except ValueError:
                    return JsonResponse({'error': f"invalid literal for int() with base 10: '{shot_number}'"}, status=400)
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
            print(channel_name)
            # if channel_name[:2] == 'TS':
            #     conn_start_time = time.time()
            #     conn = MDSplus.Connection('192.168.20.11')  # EXL50 database
            #     print('xxxxxxxxxxxxxxxxxxxxxxx', shot_number, type(shot_number))
            #     try:
            #         conn.openTree('exl50u', shot_number)
            #     except Exception as e:
            #         print('ABC',e)
            #     c_n = f'EXL50U::TOP.AI:{channel_name}'
            #     data = conn.get(r"\{}".format(c_n))
            #     print(f"MDSplus连接和查询耗时: {time.time() - conn_start_time:.2f}秒")
            #     print(data)
            db_start_time = time.time()
            for DB in DB_list:
                tree_start_time = time.time()

                tree = MdsTree(shot_number, dbname=DB, path=DBS[DB]['path'], subtrees=DBS[DB]['subtrees'])
                print(f"创建MdsTree对象耗时: {time.time() - tree_start_time:.2f}秒")
                
                data_start_time = time.time()
                data_x, data_y, unit = tree.getData(channel_name)
                print(f"获取数据耗时: {time.time() - data_start_time:.2f}秒")
                print(f"原始数据量: X轴 {len(data_x)} 点, Y轴 {len(data_y)} 点")
                
                if len(data_x) != 0:
                    # 根据客户端参数决定是否进行降采样
                    if sample_mode == 'downsample' and len(data_x) > sample_freq:
                        downsampling_start = time.time()
                        data_x, data_y = downsample_to_frequency(data_x, data_y, target_freq=sample_freq)
                        print(f"降采样耗时: {time.time() - downsampling_start:.2f}秒")
                        is_downsampled = True
                    else:
                        is_downsampled = False
                        
                    original_frequency = len(data_x) / (data_x[-1] - data_x[0]) if len(data_x) > 1 else 0
                    print(f"原始频率: {original_frequency/1000}KHz")
                    
                    data = {
                        'channel_number': channel_name,
                        'X_value': list(data_x),
                        'Y_value': list(data_y),
                        'X_unit': 's',
                        'Y_unit': 'Y',
                        'is_downsampled': is_downsampled,
                        'points': len(data_x),
                        'original_frequency_khz': original_frequency/1000
                    }
                    
                    
                    # 使用orjson替代标准json进行序列化，大幅提升性能
                    serialize_start_time = time.time()
                    response = OrJsonResponse(data)
                    print(f"响应创建耗时: {time.time() - serialize_start_time:.2f}秒")
                    
                    print(f"数据库遍历总耗时: {time.time() - db_start_time:.2f}秒")
                    print(f"总耗时: {time.time() - start_time:.2f}秒")
                    
                    return response
                    
            print(f"数据库遍历总耗时: {time.time() - db_start_time:.2f}秒")
            print(f"总耗时: {time.time() - start_time:.2f}秒")
        else:
            return JsonResponse({'error': 'channel_key or channel_type parameter is missing'}, status=400)
    except Exception as e:
        print(f"发生错误，总耗时: {time.time() - start_time:.2f}秒")
        return JsonResponse({'error': str(e)}, status=500)
    
def get_error_data(request):
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


def submit_data(request):
    try:
        # 从请求中获取 JSON 数据
        data = json.loads(request.body)

        selected_channels = data.get('selectedChannels')
        paths = data.get('paths')
        brush_begin = data.get('brush_begin')
        brush_end = data.get('brush_end')
        time_begin = data.get('time_begin')
        time_during = data.get('time_during')
        time_end = data.get('time_end')
        upper_bound = data.get('upper_bound')
        scope_bound = data.get('scope_bound')
        lower_bound = data.get('lower_bound')
        smoothness = data.get('smoothness')
        sampling = data.get('sampling')
        print(data)
        # plt.figure(figsize=(10, 8))
    
        # for subpath in paths:
        #     x_coords = [point['x'] for point in subpath]
        #     y_coords = [point['y'] for point in subpath]
        #     plt.plot(x_coords, y_coords, marker='o', linestyle='-', label='路径')

        # plt.title('路径绘制')
        # plt.xlabel('X 坐标')
        # plt.ylabel('Y 坐标')
        # plt.legend()
        # plt.grid(True)
        # plt.axis('equal')  # 保持X和Y轴比例相同
        # plt.show()
        return JsonResponse({"message": "Data processing started"}, status=200)
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
    try:
        # 获取请求数据
        data = json.loads(request.body)
        diagnostic_name = data.get('diagnostic_name')
        channel_number = data.get('channel_number')
        shot_number = data.get('shot_number')
        error_type = data.get('error_type')

        if not all([diagnostic_name, channel_number, shot_number, error_type]):
            return JsonResponse({'error': '缺少必要参数'}, status=400)

        # 构建错误数据文件路径
        error_file_name = f"{shot_number}_{channel_number}_{error_type}.json"
        error_file_path = os.path.join('static', 'ErrorData', error_file_name)

        # 检查文件是否存在
        if not os.path.exists(error_file_path):
            return JsonResponse({'error': '未找到对应的错误数据文件'}, status=404)

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
            with open(struct_tree_path, 'r', encoding='utf-8') as f:
                struct_tree = json.load(f)

            # 更新对应通道的 error_name
            for item in struct_tree:
                if (item['shot_number'] == shot_number and 
                    item['channel_name'] == channel_number and 
                    'error_name' in item):
                    # 从 error_name 列表中移除对应的错误类型
                    if error_type in item['error_name']:
                        item['error_name'].remove(error_type)
                    break

            # 保存更新后的 StructTree.json
            with open(struct_tree_path, 'w', encoding='utf-8') as f:
                json.dump(struct_tree, f, indent=2, ensure_ascii=False)

        return JsonResponse({'message': '删除成功'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


