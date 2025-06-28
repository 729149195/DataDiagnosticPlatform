#!/usr/bin/env python3
"""
测试表达式解析器的修复
"""

import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings')
sys.path.append('backend')
django.setup()

from backend.api.views import ExpressionParser

def mock_get_channel_data(request, channel_key):
    """模拟获取通道数据"""
    print(f"模拟获取通道数据: {channel_key}")
    
    # 模拟不同通道的数据
    if channel_key == 'AXUV001_11820':
        return {
            'X_value': list(range(1000)),
            'Y_value': [i * 0.1 for i in range(1000)],  # 简单递增数据
            'channel_name': channel_key,
            'is_constant': False
        }
    elif channel_key == 'AXUV002_11820':
        return {
            'X_value': list(range(1000)),
            'Y_value': [i * 0.2 for i in range(1000)],  # 不同的递增数据
            'channel_name': channel_key,
            'is_constant': False
        }
    else:
        return {'error': f'Channel {channel_key} not found'}

def test_expressions():
    """测试不同的表达式"""
    parser = ExpressionParser(mock_get_channel_data)
    
    test_cases = [
        # 内置函数中的表达式运算
        "FFT(AXUV001_11820+AXUV002_11820,1000)",
        
        # 导入函数中的表达式运算  
        "[Matlab]NoiseThreshold(AXUV001_11820*0.8+AXUV002_11820/2,0.5)",
        
        # 导入函数中的单独通道名
        "[Matlab]NoiseThreshold(AXUV001_11820,0.5)",
        
        # 简单的表达式运算
        "AXUV001_11820+AXUV002_11820",
        
        # 复杂的嵌套
        "FFT([Matlab]NoiseThreshold(AXUV001_11820,0.5),100)",
    ]
    
    for i, expression in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}: {expression}")
        print(f"{'='*60}")
        
        try:
            result = parser.parse(expression)
            
            if isinstance(result, dict):
                print(f"结果类型: {type(result)}")
                print(f"是否为常量: {result.get('is_constant', False)}")
                print(f"是否为通道名: {result.get('is_channel_name', False)}")
                
                if 'Y_value' in result:
                    y_val = result['Y_value']
                    if isinstance(y_val, list):
                        print(f"数据点数: {len(y_val)}")
                        if len(y_val) > 0:
                            print(f"数据范围: {min(y_val):.3f} ~ {max(y_val):.3f}")
                    else:
                        print(f"Y值: {y_val}")
                        
                if 'channel_name' in result:
                    print(f"通道名: {result['channel_name']}")
                    
                print("✓ 解析成功")
            else:
                print(f"意外的结果类型: {type(result)}")
                
        except Exception as e:
            print(f"✗ 解析失败: {str(e)}")

if __name__ == "__main__":
    test_expressions() 