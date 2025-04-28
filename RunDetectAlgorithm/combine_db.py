from pymongo import MongoClient
from tqdm import tqdm

def get_shot_numbers(db):
    """获取数据库中所有炮号"""
    shots = set()
    for doc in db['struct_trees'].find({}, {'shot_number': 1}):
        try:
            shots.add(int(doc['shot_number']))
        except Exception:
            continue
    return shots

def find_intervals(numbers):
    """将数字列表转为区间字符串"""
    numbers = sorted(set(numbers))
    if not numbers:
        return ""
    intervals = []
    start = prev = numbers[0]
    for n in numbers[1:]:
        if n == prev + 1:
            prev = n
        else:
            intervals.append(f"[{start}_{prev}]")
            start = prev = n
    intervals.append(f"[{start}_{prev}]")
    return "_".join(intervals)

def merge_index_collections(client, db_names, dst_db):
    """合并所有数据库的index集合，按key聚合index_data"""
    key_indexdata_map = {}
    # 遍历所有数据库
    for db_name in tqdm(db_names, desc="Collecting index data"):
        src_col = client[db_name]['index']
        for doc in src_col.find({}):
            key = doc['key']
            index_data = doc.get('index_data', {})
            if key not in key_indexdata_map:
                key_indexdata_map[key] = {}
            # 合并index_data
            for shot_number, value in index_data.items():
                key_indexdata_map[key][shot_number] = value
    # 写入目标数据库
    dst_col = dst_db['index']
    for key, index_data in tqdm(key_indexdata_map.items(), desc="Writing merged index"):
        dst_col.update_one(
            {"key": key},
            {"$set": {"key": key, "index_data": index_data}},
            upsert=True
        )

def copy_collections(client, db_names, dst_db, collections):
    for col_name in collections:
        if col_name == 'index':
            merge_index_collections(client, db_names, dst_db)
        else:
            for db_name in tqdm(db_names, desc=f"Migrating {col_name}"):
                src_col = client[db_name][col_name]
                dst_col = dst_db[col_name]
                docs = list(src_col.find({}))
                if docs:
                    for doc in tqdm(docs, desc=f"Inserting docs to {col_name} from {db_name}", leave=False):
                        if 'shot_number' in doc:
                            dst_col.delete_many({'shot_number': doc['shot_number']})
                        dst_col.insert_one(doc)

def main():
    client = MongoClient("mongodb://localhost:27017")
    # 手动指定需要聚合的数据库名
    db_names = [
        "DataDiagnosticPlatform_4571_5071",
        "DataDiagnosticPlatform_4746_5071",
        # 继续添加更多数据库名
    ]
    all_shots = set()
    for db_name in db_names:
        db = client[db_name]
        shots = get_shot_numbers(db)
        all_shots.update(shots)
    # 生成新数据库名
    interval_str = find_intervals(all_shots)
    new_db_name = f"DataDiagnosticPlatform_{interval_str}"
    print(f"New database name: {new_db_name}")
    new_db = client[new_db_name]
    # 只迁移这三个集合
    collections = ['errors_data', 'struct_trees', 'index']
    # 数据库级进度条
    copy_collections(client, db_names, new_db, collections)
    print("Data aggregation completed!")

if __name__ == "__main__":
    main()