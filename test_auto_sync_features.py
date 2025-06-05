#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试auto_mg_md_sync.py新增功能的测试脚本
本脚本使用测试数据库，不会影响生产数据
"""

import re
import time
from pymongo import MongoClient
from auto_mg_md_sync import (
    get_shot_channel_count, 
    check_latest_shot_channel_stability,
    merge_databases,
    get_all_mg_shot_ranges,
    MG_DB_PATTERN
)

def create_test_databases(mongo_client):
    """创建测试数据库用于验证合并功能"""
    print("创建测试数据库...")
    
    # 创建几个测试数据库，模拟不满100炮号的情况
    test_dbs = [
        ("TestDataDiagnosticPlatform_[1_30]", 1, 30),
        ("TestDataDiagnosticPlatform_[31_60]", 31, 60),
        ("TestDataDiagnosticPlatform_[61_80]", 61, 80),
        ("TestDataDiagnosticPlatform_[81_90]", 81, 90),
        ("TestDataDiagnosticPlatform_[91_100]", 91, 100),  # 这个是满100的，不应该被合并
    ]
    
    for db_name, start, end in test_dbs:
        db = mongo_client[db_name]
        
        # 创建测试的struct_trees数据
        for shot in range(start, end + 1):
            test_struct_tree = [
                {
                    "shot_number": str(shot),
                    "channel_type": "TEST",
                    "channel_name": f"TEST_CH_{i}",
                    "db_name": "test_db",
                    "error_name": [],
                    "status": "success"
                }
                for i in range(1, 6)  # 每个炮号5个测试通道
            ]
            
            db["struct_trees"].insert_one({
                "shot_number": str(shot),
                "struct_tree": test_struct_tree
            })
        
        # 创建测试的data_statistics数据
        for shot in range(start, end + 1):
            db["data_statistics"].insert_one({
                "shot_number": str(shot),
                "total_channels_expected": 5,
                "total_channels_processed": 5,
                "status_counts": {"success": 5}
            })
        
        # 创建测试的index数据
        db["index"].insert_one({
            "key": "channel_type",
            "index_data": {
                str(shot): {"TEST": [0, 1, 2, 3, 4]} for shot in range(start, end + 1)
            }
        })
        
        print(f"已创建测试数据库: {db_name} (炮号范围: {start}-{end})")

def test_database_merge():
    """测试数据库合并功能"""
    print("\n=== 测试数据库合并功能 ===")
    
    mongo_client = MongoClient("mongodb://localhost:27017")
    
    # 清理可能存在的测试数据库
    cleanup_test_databases(mongo_client)
    
    # 创建测试数据库
    create_test_databases(mongo_client)
    
    # 显示合并前的数据库状态
    print("\n合并前的测试数据库:")
    test_shot_ranges = get_test_mg_shot_ranges(mongo_client)
    for start, end in test_shot_ranges:
        print(f"  TestDataDiagnosticPlatform_[{start}_{end}] - {end-start+1}个炮号")
    
    # 执行合并（需要修改合并函数以支持测试数据库）
    test_merge_databases(mongo_client)
    
    # 显示合并后的数据库状态
    print("\n合并后的测试数据库:")
    test_shot_ranges = get_test_mg_shot_ranges(mongo_client)
    for start, end in test_shot_ranges:
        print(f"  TestDataDiagnosticPlatform_[{start}_{end}] - {end-start+1}个炮号")
    
    # 验证合并结果
    verify_merge_results(mongo_client)
    
    # 清理测试数据库
    cleanup_test_databases(mongo_client)
    print("测试数据库已清理")

def get_test_mg_shot_ranges(mongo_client):
    """获取测试数据库的炮号范围"""
    db_names = mongo_client.list_database_names()
    shot_ranges = []
    test_pattern = re.compile(r"TestDataDiagnosticPlatform_\[(\d+)_(\d+)\]")
    
    for name in db_names:
        m = test_pattern.match(name)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            shot_ranges.append((start, end))
    return sorted(shot_ranges)

def test_merge_databases(mongo_client):
    """测试版本的数据库合并函数"""
    print("开始测试数据库合并...")
    
    shot_ranges = get_test_mg_shot_ranges(mongo_client)
    if not shot_ranges:
        print("没有找到任何测试数据库，跳过合并")
        return
    
    # 找出需要合并的数据库（炮号范围小于100的）
    databases_to_merge = []
    for start, end in shot_ranges:
        if end - start + 1 < 100:
            databases_to_merge.append((start, end))
    
    print(f"找到 {len(databases_to_merge)} 个不满100炮号的测试数据库需要合并")
    
    # 按起始炮号排序
    databases_to_merge.sort()
    
    i = 0
    while i < len(databases_to_merge):
        merge_group = [databases_to_merge[i]]
        total_shots = databases_to_merge[i][1] - databases_to_merge[i][0] + 1
        
        # 尝试将连续的数据库合并到100炮号
        j = i + 1
        while j < len(databases_to_merge) and total_shots < 100:
            next_start, next_end = databases_to_merge[j]
            next_shots = next_end - next_start + 1
            
            # 检查是否连续且合并后不超过100炮号
            if (next_start == merge_group[-1][1] + 1 and 
                total_shots + next_shots <= 100):
                merge_group.append((next_start, next_end))
                total_shots += next_shots
                j += 1
            else:
                break
        
        # 如果找到了需要合并的组（超过1个数据库）
        if len(merge_group) > 1:
            merge_start = merge_group[0][0]
            merge_end = merge_group[-1][1]
            
            print(f"合并测试数据库组: {[f'[{s}_{e}]' for s, e in merge_group]} -> [{merge_start}_{merge_end}]")
            
            try:
                # 执行合并
                execute_test_database_merge(mongo_client, merge_group, merge_start, merge_end)
                print(f"成功合并为 TestDataDiagnosticPlatform_[{merge_start}_{merge_end}]")
                
                # 从待合并列表中移除已合并的数据库
                for k in range(len(merge_group)):
                    databases_to_merge.pop(i)
                    
            except Exception as e:
                print(f"合并失败: {e}")
                i += 1
        else:
            i += 1

def execute_test_database_merge(mongo_client, merge_group, target_start, target_end):
    """执行测试数据库的合并操作"""
    target_db_name = f"TestDataDiagnosticPlatform_[{target_start}_{target_end}]"
    target_db = mongo_client[target_db_name]
    
    for start, end in merge_group:
        source_db_name = f"TestDataDiagnosticPlatform_[{start}_{end}]"
        source_db = mongo_client[source_db_name]
        
        print(f"正在合并源测试数据库: {source_db_name}")
        
        # 合并struct_trees集合
        for doc in source_db["struct_trees"].find():
            shot_number = doc.get("shot_number")
            struct_tree = doc.get("struct_tree", [])
            
            existing_doc = target_db["struct_trees"].find_one({"shot_number": shot_number})
            if existing_doc:
                target_db["struct_trees"].update_one(
                    {"shot_number": shot_number},
                    {"$addToSet": {"struct_tree": {"$each": struct_tree}}}
                )
            else:
                target_db["struct_trees"].insert_one(doc)
        
        # 合并data_statistics集合
        for doc in source_db["data_statistics"].find():
            target_db["data_statistics"].update_one(
                {"shot_number": doc.get("shot_number")},
                {"$set": doc},
                upsert=True
            )
        
        # 合并index集合
        for doc in source_db["index"].find():
            key = doc.get("key")
            index_data = doc.get("index_data", {})
            
            existing_index = target_db["index"].find_one({"key": key})
            if existing_index:
                existing_index_data = existing_index.get("index_data", {})
                existing_index_data.update(index_data)
                target_db["index"].update_one(
                    {"key": key},
                    {"$set": {"index_data": existing_index_data}}
                )
            else:
                target_db["index"].insert_one(doc)
    
    # 删除源数据库
    for start, end in merge_group:
        source_db_name = f"TestDataDiagnosticPlatform_[{start}_{end}]"
        print(f"删除源测试数据库: {source_db_name}")
        mongo_client.drop_database(source_db_name)

def verify_merge_results(mongo_client):
    """验证合并结果的正确性"""
    print("\n验证合并结果...")
    
    test_shot_ranges = get_test_mg_shot_ranges(mongo_client)
    
    # 验证合并后的数据库
    for start, end in test_shot_ranges:
        db_name = f"TestDataDiagnosticPlatform_[{start}_{end}]"
        db = mongo_client[db_name]
        
        # 检查炮号范围
        shot_count = end - start + 1
        print(f"数据库 {db_name}: {shot_count} 个炮号")
        
        # 检查struct_trees数据完整性
        struct_docs = list(db["struct_trees"].find())
        print(f"  struct_trees文档数: {len(struct_docs)}")
        
        # 检查每个炮号的数据
        for shot in range(start, end + 1):
            shot_doc = db["struct_trees"].find_one({"shot_number": str(shot)})
            if shot_doc:
                struct_tree = shot_doc.get("struct_tree", [])
                print(f"    炮号 {shot}: {len(struct_tree)} 个通道")
            else:
                print(f"    警告: 炮号 {shot} 数据缺失")

def cleanup_test_databases(mongo_client):
    """清理所有测试数据库"""
    db_names = mongo_client.list_database_names()
    test_pattern = re.compile(r"TestDataDiagnosticPlatform_.*")
    
    for name in db_names:
        if test_pattern.match(name):
            mongo_client.drop_database(name)
            print(f"已删除测试数据库: {name}")

def test_channel_stability_check():
    """测试通道稳定性检查功能（使用模拟数据）"""
    print("\n=== 测试通道稳定性检查功能 ===")
    print("注意: 此测试使用模拟的通道数据，不会连接实际的MDS数据库")
    
    # 模拟通道数稳定的情况
    print("模拟测试: 通道数稳定的情况")
    print("实际使用时会连接MDS数据库检查真实的通道数")
    
    # 这里只是演示逻辑，实际测试需要真实的MDS环境
    mock_channel_count = 150
    print(f"模拟炮号通道数: {mock_channel_count}")
    print("在实际环境中，会持续60秒检查通道数是否变化")
    print("如果通道数稳定，会再等待30秒确认")

def main():
    """主测试函数"""
    print("开始测试auto_mg_md_sync.py的新增功能\n")
    
    try:
        # 测试数据库合并功能
        test_database_merge()
        
        print("\n" + "="*50)
        
        # 测试通道稳定性检查功能
        test_channel_stability_check()
        
        print("\n所有测试完成!")
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 确保清理所有测试数据库
        mongo_client = MongoClient("mongodb://localhost:27017")
        cleanup_test_databases(mongo_client)

if __name__ == "__main__":
    main() 