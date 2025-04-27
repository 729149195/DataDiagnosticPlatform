import json
import os
from pymongo import MongoClient, ASCENDING

# 连接MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["DataDiagnosticPlatform"]
struct_trees_collection = db["struct_trees"]
index_collection = db["index"]

# 从MongoDB读取完整的结构树数据
# 查找最新的完整结构树数据（按shot_list字段）
complete_tree_doc = struct_trees_collection.find_one(
    {"shot_list": {"$exists": True}},
    sort=[("_id", -1)]  # 获取最新的文档
)

if not complete_tree_doc:
    print("未找到完整的结构树数据在MongoDB中")
    exit(1)

data = complete_tree_doc["struct_tree"]
print(f"成功从MongoDB加载了结构树数据，包含 {len(data)} 个条目")

# 遍历数据，为每个key创建索引
key_index_data = {}

# 为每个key生成索引
for idx, item in enumerate(data):
    for key, value in item.items():
        if key not in key_index_data:
            key_index_data[key] = {}
        if type(value) != list:
            if value not in key_index_data[key]:
                key_index_data[key][value] = []
            key_index_data[key][value].append(idx)
        else:
            if len(value) == 0:
                key_index_data[key].setdefault('NO ERROR', []).append(idx)
            for v in value:
                if v not in key_index_data[key]:
                    key_index_data[key][v] = []
                key_index_data[key][v].append(idx)

# 将索引数据存储到MongoDB
print("开始将索引数据存储到MongoDB...")
for key, index_data in key_index_data.items():
    # 清除旧的索引数据
    index_collection.delete_one({"key": key})
    
    # 添加新的索引数据
    index_collection.insert_one({
        "key": key,
        "index_data": index_data,
        "struct_tree_id": complete_tree_doc["_id"]  # 关联结构树文档ID
    })
    print(f"已将 {key} 的索引数据存储到MongoDB")

# 为index集合创建索引以提高查询性能
index_collection.create_index([("key", ASCENDING)])

print("所有索引数据已成功存储到MongoDB的index集合中")