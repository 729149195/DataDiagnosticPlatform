# 自动生成的适配器文件，用于导入的Python算法: LargerThanThreshold
import sys
import os
import importlib.util
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def func(Y_value, X_value=None):
    """
    适配器函数，用于调用用户导入的算法
    """
    try:
        # 动态导入用户的算法文件
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        file_path = os.path.join(project_root, 'uploads/LargerThanThreshold.py')
        spec = importlib.util.spec_from_file_location("LargerThanThreshold", file_path)
        user_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(user_module)
        
        # 构造通道数据对象
        channel_data = {
            'X_value': X_value if X_value is not None else np.arange(len(Y_value)),
            'Y_value': Y_value
        }
        
        # 调用用户算法（使用配置的参数）
        # 获取配置的参数
        configured_params = {'threshold': '0.1'}
        
        # 构建函数调用参数
        call_args = [channel_data]  # 通道数据总是第一个参数
        
        # 按照函数定义的顺序添加其他参数
        input_params = [{'paraName': 'channel_key', 'paraType': '通道对象', 'paraDefinition': '', 'domain': '', 'default': ''}, {'paraName': 'threshold', 'paraType': '浮点数', 'paraDefinition': '', 'domain': '', 'default': ''}]
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
        if hasattr(user_module, 'LargerThanThreshold'):
            result = getattr(user_module, 'LargerThanThreshold')(*call_args)
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
        print(f"调用用户算法 LargerThanThreshold 失败: {e}")
        return []
