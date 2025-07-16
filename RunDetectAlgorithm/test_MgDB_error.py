from pymongo import MongoClient
from pymongo.errors import OperationFailure # 用于捕获权限等错误
import re

# 连接MongoDB服务器
client = MongoClient("mongodb://localhost:27017")

# 目标集合的名称
target_collections = ["struct_trees", "data_statistics"]
target_document_count_to_filter_out = 100 # 我们要过滤掉文档数量为此值的数据库

# 获取服务器上所有数据库的名称列表
try:
    all_database_names = client.list_database_names()
except OperationFailure as e:
    print(f"错误：无法列出数据库。请检查MongoDB连接和用户权限。详情: {e}")
    client.close()
    exit()
except Exception as e:
    print(f"连接 MongoDB 或列出数据库时发生未知错误: {e}")
    client.close()
    exit()

# 筛选出名称以 "]" 结尾的数据库
databases_ending_with_bracket = []
shot_numbers = []

for db_name_on_server in all_database_names:
    if db_name_on_server.endswith("]"):
        databases_ending_with_bracket.append(db_name_on_server)
        
        # 提取炮号 - 假设数据库名格式类似 "something[shot_number]"
        match = re.search(r'\[(\d+)\]$', db_name_on_server)
        if match:
            shot_number = int(match.group(1))
            shot_numbers.append(shot_number)

# 检查是否有符合条件的数据库
if not databases_ending_with_bracket:
    print("在 MongoDB 服务器上，没有找到任何名称以 ']' 结尾的数据库。")
    client.close()
    exit()

print(f"在 MongoDB 服务器上，找到 {len(databases_ending_with_bracket)} 个名称以 ']' 结尾的数据库。")
print(f"正在检查每个数据库下的集合 {target_collections}，并筛选出文档数量不为 {target_document_count_to_filter_out} 的数据库...\n")

# 存储有问题的数据库信息
problematic_databases = []
found_matching_filter = False

for db_name_item in databases_ending_with_bracket:
    try:
        # 连接到特定的数据库
        db = client[db_name_item]
        
        # 检查每个目标集合
        db_has_issues = False
        db_info = {"name": db_name_item, "issues": []}
        
        for collection_name in target_collections:
            # 检查目标集合是否存在于当前数据库中
            if collection_name not in db.list_collection_names():
                # 如果集合不存在，其文档数可以视为0，不等于100，所以应该显示
                db_info["issues"].append(f"集合 '{collection_name}' 不存在 (文档数视为 0)")
                db_has_issues = True
                continue

            # 获取集合
            collection = db[collection_name]

            # 统计集合中的文档总数
            document_count = collection.count_documents({})

            # 核心过滤条件：只记录文档数量不是 target_document_count_to_filter_out (100) 的情况
            if document_count != target_document_count_to_filter_out:
                db_info["issues"].append(f"集合 '{collection_name}' 文档数量: {document_count}")
                db_has_issues = True

        if db_has_issues:
            problematic_databases.append(db_info)
            found_matching_filter = True
            
            print(f"数据库: '{db_name_item}'")
            for issue in db_info["issues"]:
                print(f"  -> {issue}")
            print("-" * 30)

    except OperationFailure as e:
        # 通常由于权限问题
        db_info = {"name": db_name_item, "issues": [f"无法访问数据库，权限问题？详情: {e}"]}
        problematic_databases.append(db_info)
        
        print(f"数据库: '{db_name_item}'")
        print(f"  -> 无法访问数据库。权限问题？ 详情: {e}")
        print("-" * 30)
        found_matching_filter = True
    except Exception as e:
        db_info = {"name": db_name_item, "issues": [f"处理数据库时发生错误: {e}"]}
        problematic_databases.append(db_info)
        
        print(f"数据库: '{db_name_item}'")
        print(f"  -> 处理数据库时发生错误: {e}")
        print("-" * 30)
        found_matching_filter = True

if not found_matching_filter:
    print(f"所有名称以 ']' 结尾的数据库，其 {target_collections} 集合的文档数量均为 {target_document_count_to_filter_out}，或者无法访问。")

# 检查炮号连续性
print("\n" + "="*50)
print("炮号连续性检查:")
print("="*50)

if shot_numbers:
    shot_numbers.sort()
    min_shot = min(shot_numbers)
    max_shot = max(shot_numbers)
    
    print(f"现有数据库炮号范围: {min_shot} - {max_shot}")
    print(f"实际存在的数据库数量: {len(shot_numbers)}")
    
    # 检查已有数据库之间的连续性
    missing_shots = []
    for i in range(len(shot_numbers) - 1):
        current_shot = shot_numbers[i]
        next_shot = shot_numbers[i + 1]
        
        # 检查当前炮号和下一个炮号之间是否有缺失
        if next_shot - current_shot > 1:
            # 添加缺失的炮号
            for missing in range(current_shot + 1, next_shot):
                missing_shots.append(missing)
    
    if missing_shots:
        print(f"期望连续的数据库数量: {max_shot - min_shot + 1}")
        print(f"\n在已有数据库之间发现缺失的炮号数据库 ({len(missing_shots)} 个):")
        
        # 将连续的缺失炮号分组显示
        ranges = []
        if missing_shots:
            missing_shots.sort()
            start = end = missing_shots[0]
            
            for shot in missing_shots[1:]:
                if shot == end + 1:
                    end = shot
                else:
                    if start == end:
                        ranges.append(str(start))
                    else:
                        ranges.append(f"{start}-{end}")
                    start = end = shot
            
            # 添加最后一个范围
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            
            print(f"缺失范围: {', '.join(ranges)}")
            
            # 显示不连续的段落
            print(f"\n不连续的段落:")
            for i in range(len(shot_numbers) - 1):
                current_shot = shot_numbers[i]
                next_shot = shot_numbers[i + 1]
                if next_shot - current_shot > 1:
                    gap_size = next_shot - current_shot - 1
                    print(f"  {current_shot} -> {next_shot} (缺失 {gap_size} 个: {current_shot + 1}-{next_shot - 1})")
    else:
        print("✓ 所有已有数据库的炮号都是连续的")
else:
    print("无法提取炮号信息，跳过连续性检查")

# 总结报告
print("\n" + "="*50)
print("总结报告:")
print("="*50)
print(f"1. 集合文档数量异常的数据库: {len(problematic_databases)} 个")
if shot_numbers:
    if missing_shots:
        print(f"2. 在已有数据库之间缺失的炮号数据库: {len(missing_shots)} 个")
    else:
        print("2. 炮号连续性: 正常")
else:
    print("2. 炮号连续性: 无法检查（未找到炮号信息）")

# 关闭MongoDB连接
client.close()