#!/usr/bin/env python3
"""
监控服务启动脚本
用于启动和管理独立的监控服务
"""

import os
import sys
import subprocess
import argparse
import time

def get_script_path():
    """获取监控服务脚本路径"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, 'backend', 'monitor_service.py')

def start_service():
    """启动监控服务"""
    script_path = get_script_path()
    
    if not os.path.exists(script_path):
        print(f"错误: 监控服务脚本不存在: {script_path}")
        return False
    
    print("启动监控服务...")
    try:
        # 启动后台进程
        subprocess.Popen([
            sys.executable, script_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print("✓ 监控服务已启动")
        print("提示: 使用 'python start_monitor_service.py status' 查看状态")
        return True
        
    except Exception as e:
        print(f"启动失败: {e}")
        return False

def check_status():
    """检查监控服务状态"""
    try:
        # 添加项目路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        sys.path.insert(0, os.path.join(current_dir, 'backend'))
        
        from backend.monitor_status import read_status_from_file
        
        status = read_status_from_file()
        
        print("监控服务状态:")
        print(f"  运行状态: {'运行中' if status.get('is_running', False) else '已停止'}")
        print(f"  MDS+最新炮号: {status.get('mds_latest_shot', 'N/A')}")
        print(f"  MongoDB最新炮号: {status.get('mongo_latest_shot', 'N/A')}")
        print(f"  正在处理炮号: {status.get('mongo_processing_shot', 'N/A')}")
        print(f"  最后更新: {status.get('last_update', 'N/A')}")
        print(f"  下次更新: {status.get('next_update', 'N/A')}")
        
        return status.get('is_running', False)
        
    except Exception as e:
        print(f"检查状态失败: {e}")
        return False

def stop_service():
    """停止监控服务"""
    try:
        # 添加项目路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        sys.path.insert(0, os.path.join(current_dir, 'backend'))
        
        from backend.monitor_status import stop_monitor
        
        stop_monitor()
        print("✓ 监控服务已停止")
        return True
        
    except Exception as e:
        print(f"停止服务失败: {e}")
        return False

def run_foreground():
    """在前台运行监控服务"""
    script_path = get_script_path()
    
    if not os.path.exists(script_path):
        print(f"错误: 监控服务脚本不存在: {script_path}")
        return False
    
    print("在前台运行监控服务... (按 Ctrl+C 停止)")
    try:
        subprocess.run([sys.executable, script_path])
        return True
    except KeyboardInterrupt:
        print("\n用户中断")
        return True
    except Exception as e:
        print(f"运行失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='监控服务管理器')
    parser.add_argument('action', nargs='?', default='start',
                      choices=['start', 'stop', 'status', 'run', 'restart'],
                      help='操作: start(启动), stop(停止), status(状态), run(前台运行), restart(重启)')
    
    args = parser.parse_args()
    
    if args.action == 'start':
        start_service()
    elif args.action == 'stop':
        stop_service()
    elif args.action == 'status':
        check_status()
    elif args.action == 'run':
        run_foreground()
    elif args.action == 'restart':
        print("重启监控服务...")
        stop_service()
        time.sleep(2)
        start_service()

if __name__ == "__main__":
    main() 