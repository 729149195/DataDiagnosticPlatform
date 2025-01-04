import ast
import json
import os
import re
import threading
from urllib.parse import urlparse, parse_qs

import numpy as np
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import JsonResponse

from api.self_algorithm_utils import period_condition_anomaly, channel_read
from api.utils import filter_range, merge_overlapping_intervals
from api.Mds import MdsTree
from api.verify_user import send_post_request
# import matplotlib.pyplot as plt

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
    
def get_channel_data(request):
    try:
        channel_key = request.GET.get('channel_key')
        # channel_type = request.GET.get('channel_type')
        if channel_key: # and channel_type:
            if '_' in channel_key:
                channel_name, shot_number = channel_key.rsplit('_', 1)
                try:
                    num = int(channel_name)
                    channel_name, shot_number = shot_number, channel_name
                except ValueError:
                    pass
                shot_number = int(shot_number)
            else:
                return JsonResponse({'error': 'Invalid channel_key format'}, status=400)
            
            # file_path = os.path.join(
            #     'static', 'Data', shot_number, channel_type, channel_name, f"{channel_name}.json"
            # )
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
            # 暂不确定通道位于哪个数据库中，（这个也需要记录在 struct-tree 里)
            # print(channel_type)
            print(channel_name)
            for DB in DB_list:
                tree = MdsTree(shot_number, dbname=DB, path=DBS[DB]['path'], subtrees=DBS[DB]['subtrees'])
                data_x, data_y, unit = tree.getData(channel_name)
                if len(data_x) != 0:
                    data = {
                        # 'channel_type':channel_type,
                        'channel_number':channel_name,
                        'X_value': list(data_x),
                        'Y_value': list(data_y),
                        'X_unit': 's', #一维数据的 X 轴默认是秒
                        'Y_unit': 'Y',
                    }
                    # print(data)
                    return JsonResponse(data, encoder=JsonEncoder)
            # else:
            #     return JsonResponse({'error': 'File not found'}, status=404)
        else:
            return JsonResponse({'error': 'channel_key or channel_type parameter is missing'}, status=400)
    except Exception as e:
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

def process_channel_names(request):
    try:
        data = json.loads(request.body)
        anomaly_func_str = data.get('anomaly_func_str')
        channel_mess = data.get('channel_mess')

        # 判定是否函数名是导入函数
        end_idx = anomaly_func_str.find('(')
        func_name = anomaly_func_str[:end_idx]
        print(func_name)

        if os.path.exists(FUNCTIONS_FILE_PATH):
            with open(FUNCTIONS_FILE_PATH, "r") as f:
                functions_data = json.load(f)
        else:
            functions_data = []
        is_import_func = False
        for function in functions_data:
            if function['name'] == func_name:
                is_import_func = True

        if is_import_func:
            data = {}
            data['function_name'] = func_name
            params_str = anomaly_func_str[end_idx:].replace(" ", "").replace("(", "").replace(")", "")
            data['parameters'] = params_str.split(',')

            ##
            # 需要补一段输入参数转换的代码
            ##
            # data['parameters'] = [float(i) for i in data['parameters']]
            data['parameters'][1] = float(data['parameters'][1])
            ret = execute_function(data)
            return JsonResponse({"data": ret}, status=200)
        else:
            # 在这里可以添加对channel_names的处理逻辑
            print("operator-strs:", anomaly_func_str)
            if anomaly_func_str[:3] == 'Pca':
                print('xxxx')
                anomaly_func_str = anomaly_func_str[3:]
                params_list = anomaly_func_str.replace(" ", "")[1:-1].split(',')
                [channel_name, period, condition_str, mode] = [params_list[0], ",".join(params_list[1:-2]),
                                                               params_list[-2], params_list[-1]]
                period = ast.literal_eval(period)
                print('xxx')
                ret = period_condition_anomaly(channel_name, period, condition_str, mode, channel_mess)

                print(ret)

            return JsonResponse({"data": ret.tolist()}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


import os
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
        with open(FUNCTIONS_FILE_PATH, "r") as f:
            existing_data = json.load(f)
    else:
        existing_data = []

    # Append the new function data to existing data
    existing_data.append(function_data)

    # Write updated data back to the JSON file
    with open(FUNCTIONS_FILE_PATH, "w") as f:
        json.dump(existing_data, f, indent=4)

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
        with open(FUNCTIONS_FILE_PATH, "r") as f:
            functions_data = json.load(f)
    else:
        functions_data = []

    return JsonResponse({"imported_functions": functions_data})

@csrf_exempt
def execute_function(data):
    global loaded_module
    function_name = data.get("function_name")
    parameters = data.get("parameters", [])
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


