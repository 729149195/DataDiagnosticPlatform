# 自动生成的适配器文件，用于手绘模板: test
import sys
import os
import numpy as np

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
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
        channel_data = {
            'X_value': X_value_resampled,
            'Y_value': Y_value_resampled
        }
        
        # 模板参数 - 使用安全的字符串转换
        import json as json_module
        template_params = json_module.dumps(template_info.get('parameters', {}))
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
        print(f"调用手绘模板 test 失败: {e}")
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
