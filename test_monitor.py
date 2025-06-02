#!/usr/bin/env python3
"""
测试监控模块脚本
"""

import sys
import os

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_monitor():
    """测试监控模块"""
    try:
        print("正在测试监控模块...")
        
        # 导入监控模块
        from backend.monitor_status import get_monitor_status, start_monitor
        print("✓ 监控模块导入成功")
        
        # 检查监控状态
        status = get_monitor_status()
        print(f"✓ 获取监控状态成功: running={status.get('is_running', False)}")
        
        # 显示详细状态
        print(f"  - MDS+最新炮号: {status.get('mds_latest_shot', 'N/A')}")
        print(f"  - MongoDB最新炮号: {status.get('mongo_latest_shot', 'N/A')}")
        print(f"  - 正在处理炮号: {status.get('mongo_processing_shot', 'N/A')}")
        print(f"  - 最后更新时间: {status.get('last_update', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_monitor()
    if success:
        print("\n✓ 监控模块测试通过！")
    else:
        print("\n✗ 监控模块测试失败！")
        sys.exit(1) 