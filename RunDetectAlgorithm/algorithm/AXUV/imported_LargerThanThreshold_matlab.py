import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 自动生成的适配器文件，用于导入的MATLAB算法: LargerThanThreshold
import scipy.io as sio
import numpy as np
import subprocess
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
            algorithm_params = {'threshold': '0.1'}
            input_param_defs = [{'paraName': 'channel_key', 'paraType': '通道对象', 'paraDefinition': '', 'domain': '', 'default': ''}, {'paraName': 'threshold', 'paraType': '浮点数', 'paraDefinition': '', 'domain': '', 'default': ''}]
            
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
        matlab_file = os.path.join(project_root, 'uploads/LargerThanThreshold.m')
            
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
            result = LargerThanThreshold({param_list});
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
        print(f"调用MATLAB算法 LargerThanThreshold 失败: {e}")
        return []
