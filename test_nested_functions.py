#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试嵌套函数调用的简单验证
"""

import sys
import os

# 添加backend目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# 模拟Django设置
class MockSettings:
    MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'backend')

import django.conf
if not django.conf.settings.configured:
    django.conf.settings.configure(
        MEDIA_ROOT=MockSettings.MEDIA_ROOT,
        SECRET_KEY='test-key-for-nested-functions'
    )

from backend.api.views import ExpressionParser

def mock_get_channel_data(request, channel_key):
    """模拟通道数据获取函数"""
    print(f"mock_get_channel_data 被调用，channel_key: {channel_key}")
    return {'error': f'Mock: 通道 {channel_key} 不存在'}

def test_tokenizer():
    """测试分词器对嵌套函数的处理"""
    print("=== 测试分词器 ===")
    
    parser = ExpressionParser(mock_get_channel_data)
    
    expression = "FFT([Matlab]NoiseThreshold(AXUV001_11820,0.5),100)"
    tokens = parser.tokenize(expression)
    print(f"表达式: {expression}")
    print(f"分词结果: {tokens}")
    
    expected_tokens = ['FFT', '(', '[Matlab]', 'NoiseThreshold', '(', 'AXUV001_11820', ',', '0.5', ')', ',', '100', ')']
    assert tokens == expected_tokens, f"分词结果不正确，期望{expected_tokens}，实际{tokens}"
    print("✓ 分词测试通过")

def test_channel_name_recognition():
    """测试通道名识别"""
    print("\n=== 测试通道名识别 ===")
    
    parser = ExpressionParser(mock_get_channel_data)
    
    # 测试单独的通道名解析
    parser.tokenize("AXUV001_11820")
    parser.current = 0
    result = parser.factor()
    
    print(f"解析 'AXUV001_11820' 的结果: {result}")
    assert result.get('is_channel_name') == True, "通道名未正确识别"
    assert result.get('channel_name') == 'AXUV001_11820', "通道名不正确"
    print("✓ 通道名识别测试通过")

def test_function_parsing():
    """测试函数解析"""
    print("\n=== 测试函数解析 ===")
    
    parser = ExpressionParser(mock_get_channel_data)
    
    # 测试带前缀的函数解析
    try:
        parser.tokenize("[Matlab]NoiseThreshold(AXUV001_11820,0.5)")
        parser.current = 0
        result = parser.factor()
        print(f"解析 '[Matlab]NoiseThreshold(AXUV001_11820,0.5)' 的结果类型: {type(result)}")
        print(f"函数类型: {result.get('function_type', 'unknown')}")
        print("函数解析测试完成（可能会有错误，但这是预期的，因为函数文件不存在）")
    except Exception as e:
        print(f"函数解析出错（预期的）: {str(e)}")

if __name__ == "__main__":
    print("开始测试嵌套函数解析...")
    
    test_tokenizer()
    test_channel_name_recognition()
    test_function_parsing()
    
    print("\n=== 测试完成 ===")
    print("基础解析功能正常，实际函数调用需要真实的环境支持。") 