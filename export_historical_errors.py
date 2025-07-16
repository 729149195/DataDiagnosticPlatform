#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史异常数据导出脚本
用于导出此前已运行但未生成异常统计文件的炮号数据
数据库按每100炮分组存储，格式：DataDiagnosticPlatform_[start_end]
"""

import os
import sys
import json
import argparse
import math
from datetime import datetime
from pymongo import MongoClient
from tqdm import tqdm
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('export_historical_errors.log')
    ]
)
logger = logging.getLogger('HistoricalErrorsExport')

class JsonEncoder(json.JSONEncoder):
    """Convert numpy classes to JSON serializable objects."""
    def default(self, obj):
        import numpy as np
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(JsonEncoder, self).default(obj)

def get_database_ranges(start_shot, end_shot, batch_size=100):
    """
    根据炮号范围计算需要访问的数据库名称列表
    数据库命名规则：DataDiagnosticPlatform_[range_start_range_end]
    
    Args:
        start_shot: 起始炮号
        end_shot: 结束炮号  
        batch_size: 每个数据库包含的炮号数量（默认100）
    
    Returns:
        list: 包含(db_name, db_start, db_end, shots_in_range)的元组列表
    """
    databases = []
    
    # 计算起始炮号对应的数据库起始范围
    start_db_range = (start_shot - 1) // batch_size * batch_size + 1
    
    current_start = start_db_range
    while current_start <= end_shot:
        current_end = current_start + batch_size - 1
        db_name = f"DataDiagnosticPlatform_[{current_start}_{current_end}]"
        
        # 计算该数据库中实际需要导出的炮号范围
        actual_start = max(current_start, start_shot)
        actual_end = min(current_end, end_shot)
        
        if actual_start <= actual_end:
            shots_in_range = list(range(actual_start, actual_end + 1))
            databases.append((db_name, current_start, current_end, shots_in_range))
        
        current_start = current_end + 1
    
    return databases

def export_shot_errors_to_json(db, shot_number, project_root_path):
    """
    将指定炮号的异常数据导出为JSON文件
    (从Get_structtrees_errors_indexs.py复制的函数)
    """
    errors_collection = db["errors_data"]
    
    # 创建输出文件夹
    output_dir = os.path.join(project_root_path, "Errors_Result_Statistics")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"已创建输出目录: {output_dir}")
    
    # 查询当前炮号的所有异常数据
    try:
        error_docs = list(errors_collection.find({"shot_number": shot_number}))
        
        if not error_docs:
            logger.info(f"炮号 {shot_number} 没有异常数据，跳过JSON导出")
            return False
        
        # 组织数据结构：按通道名分组
        shot_errors = {
            "shot_number": shot_number,
            "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "channels": {}
        }
        
        for error_doc in error_docs:
            channel_number = error_doc.get("channel_number", "")
            error_type = error_doc.get("error_type", "")
            data = error_doc.get("data", [])
            
            # 确保data格式正确并提取异常信息
            if len(data) >= 2 and len(data[1]) > 0:
                error_info = data[1][0]  # 获取第一个异常信息
                
                # 初始化通道数据结构
                if channel_number not in shot_errors["channels"]:
                    shot_errors["channels"][channel_number] = {
                        "channel_name": channel_number,
                        "channel_type": error_info.get("diagnostic_name", ""),
                        "errors": []
                    }
                
                # 添加异常信息
                error_detail = {
                    "error_type": error_type,
                    "detection_time": error_info.get("diagonistic_time", ""),
                    "time_segments": error_info.get("X_error", []),
                    "error_description": error_info.get("error_description", ""),
                    "detector": error_info.get("person", "mechine")
                }
                
                shot_errors["channels"][channel_number]["errors"].append(error_detail)
        
        # 计算统计信息
        total_channels = len(shot_errors["channels"])
        total_errors = sum(len(channel["errors"]) for channel in shot_errors["channels"].values())
        
        shot_errors["statistics"] = {
            "total_channels_with_errors": total_channels,
            "total_error_count": total_errors,
            "error_types": list(set(
                error["error_type"] 
                for channel in shot_errors["channels"].values() 
                for error in channel["errors"]
            ))
        }
        
        # 保存为JSON文件
        output_file = os.path.join(output_dir, f"shot_{shot_number}_errors.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(shot_errors, f, ensure_ascii=False, indent=2, cls=JsonEncoder)
        
        logger.info(f"已将炮号 {shot_number} 的异常数据导出到: {output_file}")
        logger.info(f"  - 异常通道数: {total_channels}")
        logger.info(f"  - 总异常数: {total_errors}")
        logger.info(f"  - 异常类型: {len(shot_errors['statistics']['error_types'])} 种")
        
        return True
        
    except Exception as e:
        logger.error(f"导出炮号 {shot_number} 的异常数据到JSON文件时发生异常: {e}")
        return False

def export_historical_errors(start_shot, end_shot, mongo_host="mongodb://localhost:27017"):
    """
    导出历史异常数据的主函数
    
    Args:
        start_shot: 起始炮号
        end_shot: 结束炮号
        mongo_host: MongoDB连接字符串
    """
    print(f"开始导出炮号范围 {start_shot}-{end_shot} 的历史异常数据")
    
    # 连接MongoDB
    client = MongoClient(mongo_host)
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # 计算需要访问的数据库
    database_ranges = get_database_ranges(start_shot, end_shot)
    
    print(f"需要访问 {len(database_ranges)} 个数据库:")
    for db_name, db_start, db_end, shots in database_ranges:
        print(f"  - {db_name}: 炮号 {shots[0]}-{shots[-1]} (共{len(shots)}个)")
    
    # 统计信息
    total_shots = end_shot - start_shot + 1
    processed_shots = 0
    success_shots = 0
    failed_shots = 0
    empty_shots = 0
    
    # 逐数据库处理
    for db_name, db_start, db_end, shots_in_range in database_ranges:
        print(f"\n正在处理数据库: {db_name}")
        
        try:
            db = client[db_name]
            errors_collection = db["errors_data"]
            
            # 检查数据库是否存在
            if db_name not in client.list_database_names():
                logger.warning(f"数据库 {db_name} 不存在，跳过")
                failed_shots += len(shots_in_range)
                processed_shots += len(shots_in_range)
                continue
            
            # 检查errors_data集合是否存在
            if "errors_data" not in db.list_collection_names():
                logger.warning(f"数据库 {db_name} 中没有 errors_data 集合，跳过")
                failed_shots += len(shots_in_range)
                processed_shots += len(shots_in_range)
                continue
            
            # 处理该数据库中的每个炮号
            for shot in tqdm(shots_in_range, desc=f"导出 {db_name}"):
                try:
                    success = export_shot_errors_to_json(db, str(shot), project_root)
                    
                    if success:
                        success_shots += 1
                    else:
                        empty_shots += 1
                    
                    processed_shots += 1
                    
                except Exception as e:
                    logger.error(f"处理炮号 {shot} 时发生异常: {e}")
                    failed_shots += 1
                    processed_shots += 1
        
        except Exception as e:
            logger.error(f"访问数据库 {db_name} 时发生异常: {e}")
            failed_shots += len(shots_in_range)
            processed_shots += len(shots_in_range)
    
    # 关闭MongoDB连接
    client.close()
    
    # 打印统计结果
    print(f"\n==== 导出完成统计 ====")
    print(f"总炮号数: {total_shots}")
    print(f"已处理: {processed_shots}")
    print(f"成功导出: {success_shots}")
    print(f"无异常数据: {empty_shots}")
    print(f"失败: {failed_shots}")
    print(f"成功率: {success_shots/total_shots*100:.1f}%")
    
    # 输出目录信息
    output_dir = os.path.join(project_root, "Errors_Result_Statistics")
    print(f"\n异常数据文件已导出到: {output_dir}")
    
    # 统计输出文件
    if os.path.exists(output_dir):
        json_files = [f for f in os.listdir(output_dir) if f.endswith('.json') and f.startswith('shot_')]
        print(f"共生成 {len(json_files)} 个异常数据文件")

def main():
    """主函数，处理命令行参数"""
    parser = argparse.ArgumentParser(description='导出历史异常数据文件')
    parser.add_argument('start_shot', type=int, help='起始炮号')
    parser.add_argument('end_shot', type=int, help='结束炮号')
    parser.add_argument('--mongo-host', type=str, default="mongodb://localhost:27017", 
                        help='MongoDB连接字符串 (默认: mongodb://localhost:27017)')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='数据库分组大小 (默认: 100，应与原始数据库分组一致)')
    
    args = parser.parse_args()
    
    # 验证参数
    if args.start_shot > args.end_shot:
        print("错误：起始炮号不能大于结束炮号")
        sys.exit(1)
    
    if args.start_shot < 1:
        print("错误：炮号必须大于0")
        sys.exit(1)
    
    print(f"历史异常数据导出工具")
    print(f"炮号范围: {args.start_shot} - {args.end_shot}")
    print(f"MongoDB: {args.mongo_host}")
    print(f"数据库分组大小: {args.batch_size}")
    
    # 确认执行
    confirm = input("\n确认开始导出？(y/N): ")
    if confirm.lower() not in ['y', 'yes']:
        print("已取消导出")
        sys.exit(0)
    
    try:
        export_historical_errors(args.start_shot, args.end_shot, args.mongo_host)
    except KeyboardInterrupt:
        print("\n用户中断，导出已停止")
        sys.exit(1)
    except Exception as e:
        logger.error(f"导出过程中发生错误: {e}")
        print(f"导出失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 