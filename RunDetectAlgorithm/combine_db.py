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

def copy_collections(src_db, dst_db, collections):
    """将指定集合从src_db复制到dst_db"""
    for col_name in collections:
        src_col = src_db[col_name]
        dst_col = dst_db[col_name]
        docs = list(src_col.find({}))
        if docs:
            # 文档级进度条
            for doc in tqdm(docs, desc=f"Inserting docs to {col_name}", leave=False):
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
    for db_name in tqdm(db_names, desc="Migrating databases"):
        print(f"Migrating database: {db_name}")
        # 集合级进度条
        for col_name in tqdm(collections, desc=f"Migrating collections in {db_name}", leave=False):
            copy_collections(client[db_name], new_db, [col_name])
    print("Data aggregation completed!")

if __name__ == "__main__":
    main()