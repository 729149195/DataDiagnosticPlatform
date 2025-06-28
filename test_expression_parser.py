#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试增强的表达式解析器
支持嵌套运算：FFT([Matlab]NoiseThreshold(AXUV001_11820,0.5),1000)、FFT(AXUV001_11820+AXUV002_11820,1000)
"""

import sys
import os
import json
import numpy as np

# 添加backend目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# 模拟Django设置
class MockSettings:
    MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'backend')

# 设置模拟的Django设置
import django.conf
if not django.conf.settings.configured:
    django.conf.settings.configure(
        MEDIA_ROOT=MockSettings.MEDIA_ROOT,
        SECRET_KEY='test-key-for-expression-parser'
    )

from backend.api.views import ExpressionParser

def mock_get_channel_data(request, channel_key):
    """模拟通道数据获取函数"""
    # 模拟不同通道的数据
    if channel_key == 'AXUV001_11820':
        return {
            'X_value': [0.0, 0.1, 0.2, 0.3, 0.4],
            'Y_value': [1.0, 2.0, 3.0, 4.0, 5.0],
            'channel_name': 'AXUV001_11820',
            'X_unit': 's',
            'Y_unit': 'V'
        }
    elif channel_key == 'AXUV002_11820':
        return {
            'X_value': [0.0, 0.1, 0.2, 0.3, 0.4],
            'Y_value': [2.0, 3.0, 4.0, 5.0, 6.0],
            'channel_name': 'AXUV002_11820',
            'X_unit': 's',
            'Y_unit': 'V'
        }
    else:
        return {'error': f'Channel {channel_key} not found'}

def mock_execute_function(data):
    """模拟导入函数执行"""
    function_name = data.get('target_file_name', '')
    parameters = data.get('parameters', [])
    
    if function_name == 'NoiseThreshold':
        # 模拟NoiseThreshold函数：对输入数据添加噪声阈值处理
        if len(parameters) >= 2:
            channel_name = parameters[0]
            threshold = float(parameters[1]) if isinstance(parameters[1], (int, float, str)) else 0.5
            
            # 获取通道数据
            channel_data = mock_get_channel_data(None, channel_name)
            if 'error' in channel_data:
                return {'error': channel_data['error']}
            
            # 应用噪声阈值（简单示例：对Y值进行阈值处理）
            y_values = np.array(channel_data['Y_value'])
            processed_y = np.where(np.abs(y_values) > threshold, y_values, 0.0)
            
            return {
                'result': {
                    'X_value': channel_data['X_value'],
                    'Y_value': processed_y.tolist(),
                    'channel_name': f"NoiseThreshold({channel_name},{threshold})",
                    'X_unit': channel_data.get('X_unit', ''),
                    'Y_unit': channel_data.get('Y_unit', ''),
                    'function_type': 'imported'
                }
            }
    
    return {'error': f'Unknown function: {function_name}'}

def test_basic_operations():
    """测试基本的数学运算"""
    print("=== 测试基本数学运算 ===")
    
    parser = ExpressionParser(mock_get_channel_data)
    
    # 测试通道加法
    try:
        result = parser.parse("AXUV001_11820 + AXUV002_11820")
        print(f"AXUV001_11820 + AXUV002_11820 = {result['Y_value']}")
        assert result['Y_value'] == [3.0, 5.0, 7.0, 9.0, 11.0], "通道加法结果不正确"
        print("✓ 通道加法测试通过")
    except Exception as e:
        print(f"✗ 通道加法测试失败: {e}")
    
    # 测试通道与常数运算
    try:
        result = parser.parse("AXUV001_11820 * 2")
        print(f"AXUV001_11820 * 2 = {result['Y_value']}")
        assert result['Y_value'] == [2.0, 4.0, 6.0, 8.0, 10.0], "通道乘法结果不正确"
        print("✓ 通道乘法测试通过")
    except Exception as e:
        print(f"✗ 通道乘法测试失败: {e}")

def test_builtin_functions():
    """测试内置函数"""
    print("\n=== 测试内置函数 ===")
    
    parser = ExpressionParser(mock_get_channel_data)
    
    # 测试FFT函数
    try:
        result = parser.parse("FFT(AXUV001_11820)")
        print(f"FFT(AXUV001_11820) 结果长度: {len(result['Y_value'])}")
        assert 'function_type' in result and result['function_type'] == 'FFT', "FFT函数类型标记不正确"
        print("✓ FFT函数测试通过")
    except Exception as e:
        print(f"✗ FFT函数测试失败: {e}")

def test_nested_expressions():
    """测试嵌套表达式"""
    print("\n=== 测试嵌套表达式 ===")
    
    parser = ExpressionParser(mock_get_channel_data)
    
    # 测试函数嵌套通道运算
    try:
        result = parser.parse("FFT(AXUV001_11820 + AXUV002_11820)")
        print(f"FFT(AXUV001_11820 + AXUV002_11820) 结果长度: {len(result['Y_value'])}")
        assert 'function_type' in result and result['function_type'] == 'FFT', "嵌套FFT函数类型标记不正确"
        print("✓ 函数嵌套通道运算测试通过")
    except Exception as e:
        print(f"✗ 函数嵌套通道运算测试失败: {e}")

def test_tokenizer():
    """测试分词器对函数前缀的处理"""
    print("\n=== 测试分词器 ===")
    
    parser = ExpressionParser(mock_get_channel_data)
    
    # 测试函数前缀分词
    try:
        tokens = parser.tokenize("[Python]NoiseThreshold(AXUV001_11820,0.5)")
        print(f"分词结果: {tokens}")
        assert '[Python]' in tokens, "Python前缀未正确分词"
        assert 'NoiseThreshold' in tokens, "函数名未正确分词"
        print("✓ 函数前缀分词测试通过")
    except Exception as e:
        print(f"✗ 函数前缀分词测试失败: {e}")
    
    try:
        tokens = parser.tokenize("[Matlab]NoiseThreshold(AXUV001_11820,0.5)")
        print(f"分词结果: {tokens}")
        assert '[Matlab]' in tokens, "Matlab前缀未正确分词"
        print("✓ Matlab前缀分词测试通过")
    except Exception as e:
        print(f"✗ Matlab前缀分词测试失败: {e}")

def test_complex_expressions():
    """测试复杂的嵌套表达式"""
    print("\n=== 测试复杂嵌套表达式 ===")
    
    parser = ExpressionParser(mock_get_channel_data)
    
    # 测试复杂的数学表达式
    try:
        result = parser.parse("(AXUV001_11820 + AXUV002_11820) * 2 - 1")
        print(f"(AXUV001_11820 + AXUV002_11820) * 2 - 1 = {result['Y_value']}")
        expected = [5.0, 9.0, 13.0, 17.0, 21.0]  # ((1+2)*2-1, (2+3)*2-1, ...)
        assert result['Y_value'] == expected, f"复杂表达式结果不正确，期望{expected}，实际{result['Y_value']}"
        print("✓ 复杂数学表达式测试通过")
    except Exception as e:
        print(f"✗ 复杂数学表达式测试失败: {e}")

if __name__ == "__main__":
    print("开始测试增强的表达式解析器...")
    
    # 模拟导入函数执行（修改全局的execute_function）
    import backend.api.views as views_module
    views_module.execute_function = mock_execute_function
    
    test_tokenizer()
    test_basic_operations()
    test_builtin_functions()
    test_nested_expressions()
    test_complex_expressions()
    
    print("\n=== 测试完成 ===")
    print("注意：导入函数测试需要实际的函数文件和配置，当前仅测试解析器的基本功能。") 