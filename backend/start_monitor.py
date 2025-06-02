#!/usr/bin/env python3
"""
监控程序启动脚本
确保系统监控程序正常运行
"""

import os
import sys
import time

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def main():
    """启动监控程序"""
    try:
        # 导入监控模块
        from backend.monitor_status import start_monitor, get_monitor_status
        
        print("正在启动系统监控程序...")
        
        # 启动监控
        if start_monitor():
            print("监控程序启动成功！")
        else:
            print("监控程序已在运行中")
        
        # 等待几秒钟让监控程序初始化
        time.sleep(3)
        
        # 检查监控状态
        status = get_monitor_status()
        print(f"监控状态: {status}")
        
        return True
        
    except Exception as e:
        print(f"启动监控程序失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    
    print("监控程序启动完成，按 Ctrl+C 退出...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止监控程序...")
        sys.exit(0) 