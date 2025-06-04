#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试单炮聚合补齐逻辑的脚本
"""

def simulate_single_shot_aggregation(mg_latest, md_latest, BATCH_SIZE=100):
    """
    模拟单炮聚合补齐的逻辑
    """
    print(f"开始模拟: mg_latest={mg_latest}, md_latest={md_latest}, BATCH_SIZE={BATCH_SIZE}")
    
    original_mg_latest = mg_latest
    
    while mg_latest < md_latest:
        # 模拟在处理过程中可能有新的md炮号产生
        # 这里为了测试简单，我们不模拟这种情况
        
        # 收集待处理的炮号
        pending_shots = []
        current_shot = mg_latest + 1
        
        # 收集炮号直到达到批次大小或没有更多炮号
        while current_shot <= md_latest and len(pending_shots) < BATCH_SIZE:
            pending_shots.append(current_shot)
            current_shot += 1
        
        if pending_shots:
            batch_start = pending_shots[0]
            batch_end = pending_shots[-1]
            batch_count = len(pending_shots)
            
            print(f"  聚合批次: 炮号 {batch_start}-{batch_end} (共{batch_count}个炮号)")
            print(f"  数据库名: DataDiagnosticPlatform_[{batch_start}_{batch_end}]")
            
            # 模拟处理
            mg_latest = batch_end
            print(f"  处理完成，mg_latest更新为: {mg_latest}")
        else:
            # 没有待处理的炮号，退出循环
            break
    
    print(f"聚合补齐完成: 从 {original_mg_latest} 处理到 {mg_latest}")
    print()

def simulate_database_extension_scenario():
    """
    模拟数据库扩展场景：已有DataDiagnosticPlatform_[11401_11452]，新增炮号11453
    """
    print("=== 数据库扩展场景测试 ===")
    print("假设现有数据库: DataDiagnosticPlatform_[11401_11452] (包含52个炮号)")
    print("新增炮号: 11453")
    print("期望结果: 扩展为 DataDiagnosticPlatform_[11401_11453]\n")
    
    # 当前逻辑的行为
    print("当前逻辑的实际行为:")
    mg_latest = 11452  # 来自DataDiagnosticPlatform_[11401_11452]
    md_latest = 11453  # 新的炮号
    
    # 模拟当前逻辑
    simulate_single_shot_aggregation(mg_latest, md_latest, BATCH_SIZE=100)
    
    print("❌ 问题: 当前逻辑会创建新数据库 DataDiagnosticPlatform_[11453_11453]")
    print("   而不是扩展现有数据库为 DataDiagnosticPlatform_[11401_11453]\n")
    
    return False

def get_last_db_info(shot_ranges):
    """
    获取最后一个数据库的信息
    """
    if not shot_ranges:
        return None, None, 0
    
    # 找到最后一个数据库（按结束炮号排序）
    last_range = max(shot_ranges, key=lambda x: x[1])
    start_shot, end_shot = last_range
    count = end_shot - start_shot + 1
    
    return start_shot, end_shot, count

def simulate_smart_aggregation(existing_ranges, new_md_latest, BATCH_SIZE=100):
    """
    模拟智能聚合逻辑：考虑扩展现有数据库
    """
    print(f"智能聚合逻辑:")
    print(f"现有数据库范围: {existing_ranges}")
    print(f"新的md_latest: {new_md_latest}")
    
    if not existing_ranges:
        mg_latest = 0
    else:
        mg_latest = max(end for start, end in existing_ranges)
    
    print(f"当前mg_latest: {mg_latest}")
    
    if mg_latest >= new_md_latest:
        print("已同步，无需处理")
        return
    
    # 获取最后一个数据库的信息
    last_start, last_end, last_count = get_last_db_info(existing_ranges)
    
    if last_start is not None and last_count < BATCH_SIZE:
        # 最后一个数据库未满，可以扩展
        remaining_capacity = BATCH_SIZE - last_count
        shots_to_add = new_md_latest - last_end
        
        if shots_to_add <= remaining_capacity:
            # 可以完全扩展到现有数据库
            new_end = new_md_latest
            print(f"✅ 扩展现有数据库: DataDiagnosticPlatform_[{last_start}_{last_end}] -> DataDiagnosticPlatform_[{last_start}_{new_end}]")
            print(f"   从 {last_count} 个炮号扩展到 {last_count + shots_to_add} 个炮号")
        else:
            # 先扩展现有数据库到满100个，然后创建新数据库
            new_end_for_existing = last_end + remaining_capacity
            print(f"✅ 扩展现有数据库: DataDiagnosticPlatform_[{last_start}_{last_end}] -> DataDiagnosticPlatform_[{last_start}_{new_end_for_existing}] (满100个)")
            
            # 处理剩余炮号
            remaining_start = new_end_for_existing + 1
            if remaining_start <= new_md_latest:
                print(f"✅ 创建新数据库: DataDiagnosticPlatform_[{remaining_start}_{new_md_latest}]")
    else:
        # 最后一个数据库已满或不存在，创建新数据库
        new_start = mg_latest + 1
        print(f"✅ 创建新数据库: DataDiagnosticPlatform_[{new_start}_{new_md_latest}]")

# 测试不同的场景
if __name__ == "__main__":
    print("=== 测试单炮聚合补齐逻辑 ===\n")
    
    # 测试场景1: 需要补齐的炮号少于100个
    print("场景1: 需要补齐50个炮号")
    simulate_single_shot_aggregation(mg_latest=1000, md_latest=1050, BATCH_SIZE=100)
    
    # 测试场景2: 需要补齐的炮号正好100个
    print("场景2: 需要补齐100个炮号")
    simulate_single_shot_aggregation(mg_latest=1000, md_latest=1100, BATCH_SIZE=100)
    
    # 测试场景3: 需要补齐的炮号多于100个但少于200个
    print("场景3: 需要补齐150个炮号")
    simulate_single_shot_aggregation(mg_latest=1000, md_latest=1150, BATCH_SIZE=100)
    
    # 测试场景4: 需要补齐的炮号是230个
    print("场景4: 需要补齐230个炮号")
    simulate_single_shot_aggregation(mg_latest=1000, md_latest=1230, BATCH_SIZE=100)
    
    # 测试场景5: 需要补齐1个炮号
    print("场景5: 需要补齐1个炮号")
    simulate_single_shot_aggregation(mg_latest=1000, md_latest=1001, BATCH_SIZE=100)
    
    # 测试用户提到的具体场景
    print("\n" + "="*60)
    simulate_database_extension_scenario()
    
    # 测试智能聚合逻辑
    print("=== 智能聚合逻辑测试 ===\n")
    
    # 场景1: 最后一个数据库未满，可以扩展
    print("智能场景1: 最后一个数据库有52个炮号，新增1个炮号")
    existing_ranges = [(11301, 11400), (11401, 11452)]  # 最后一个数据库有52个炮号
    simulate_smart_aggregation(existing_ranges, 11453, BATCH_SIZE=100)
    print()
    
    # 场景2: 最后一个数据库未满，新增的炮号会超出容量
    print("智能场景2: 最后一个数据库有52个炮号，新增60个炮号")
    existing_ranges = [(11301, 11400), (11401, 11452)]  # 最后一个数据库有52个炮号
    simulate_smart_aggregation(existing_ranges, 11512, BATCH_SIZE=100)
    print()
    
    # 场景3: 最后一个数据库已满
    print("智能场景3: 最后一个数据库已满100个炮号，新增10个炮号")
    existing_ranges = [(11301, 11400), (11401, 11500)]  # 最后一个数据库有100个炮号
    simulate_smart_aggregation(existing_ranges, 11510, BATCH_SIZE=100)
    print() 