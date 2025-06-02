#!/usr/bin/env python3
"""
独立的监控服务
持续监控MDS+和MongoDB状态，将结果保存到文件中供Django API使用
"""

import sys
import os
import time
import signal

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

# 导入监控模块
from monitor_status import start_monitor, get_monitor_status, stop_monitor

def signal_handler(signum, frame):
    """信号处理器"""
    print(f"\n接收到信号 {signum}，正在停止监控服务...")
    stop_monitor()
    sys.exit(0)

def main():
    """主函数"""
    print("=" * 50)
    print("启动独立监控服务")
    print("=" * 50)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
    
    try:
        # 启动监控
        if start_monitor():
            print("✓ 监控服务启动成功")
        else:
            print("⚠ 监控服务已在运行或启动失败")
        
        # 显示初始状态
        time.sleep(2)
        status = get_monitor_status()
        print(f"✓ 初始状态: MDS+={status.get('mds_latest_shot', 'N/A')}, MongoDB={status.get('mongo_latest_shot', 'N/A')}")
        
        print("监控服务运行中... (按 Ctrl+C 停止)")
        print("-" * 50)
        
        # 主循环
        while True:
            time.sleep(30)  # 每30秒显示一次状态
            status = get_monitor_status()
            if status.get('is_running', False):
                print(f"[运行中] MDS+最新: {status.get('mds_latest_shot', 'N/A')}, "
                      f"MongoDB最新: {status.get('mongo_latest_shot', 'N/A')}, "
                      f"正在处理: {status.get('mongo_processing_shot', 'N/A')}")
            else:
                print("[警告] 监控服务未在运行")
                
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"监控服务出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("停止监控服务")
        stop_monitor()

if __name__ == "__main__":
    main() 