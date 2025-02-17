import os
import json
from pymongo import MongoClient
from tqdm import tqdm

# MongoDB连接配置
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "data_diagnostic"
# MongoDB 文档大小限制 (16MB)
MAX_DOCUMENT_SIZE = 16 * 1024 * 1024

def connect_mongodb():
    """连接到MongoDB数据库"""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db

def import_struct_tree(db):
    """导入StructTree.json"""
    print("正在导入StructTree.json...")
    with open("StructTree.json", 'r', encoding='utf-8') as f:
        struct_data = json.load(f)
    
    # 如果数据太大，需要分片存储
    if len(json.dumps(struct_data).encode('utf-8')) > MAX_DOCUMENT_SIZE:
        print("StructTree.json 文件过大，进行分片存储...")
        # 删除已存在的集合
        db.struct_tree.drop()
        db.struct_tree_chunks.drop()
        
        # 将数据转换为字符串并分片
        data_str = json.dumps(struct_data)
        chunk_size = MAX_DOCUMENT_SIZE // 2  # 预留一些空间给其他字段
        total_chunks = (len(data_str) + chunk_size - 1) // chunk_size
        
        # 存储元数据
        db.struct_tree.insert_one({
            "type": "chunked",
            "total_chunks": total_chunks,
            "total_size": len(data_str)
        })
        
        # 存储数据分片
        for i in range(total_chunks):
            chunk = data_str[i * chunk_size: (i + 1) * chunk_size]
            db.struct_tree_chunks.insert_one({
                "chunk_id": i,
                "data": chunk
            })
        print(f"StructTree.json 已分片存储为 {total_chunks} 个分片")
    else:
        # 如果集合已存在，先删除
        db.struct_tree.drop()
        # 直接插入数据
        db.struct_tree.insert_one({"tree": struct_data})
    print("StructTree.json导入完成")

def split_error_data(error_data):
    """将错误数据分片"""
    # 将数据转换为JSON字符串来检查大小
    data_str = json.dumps(error_data)
    data_size = len(data_str.encode('utf-8'))
    
    # 如果数据大小超过限制，需要分片
    if data_size > MAX_DOCUMENT_SIZE:
        if isinstance(error_data, list):
            # 计算需要的分片数
            num_chunks = (data_size // (MAX_DOCUMENT_SIZE // 2)) + 1  # 预留一半空间给其他字段
            # 计算每个分片的大小
            chunk_size = max(1, len(error_data) // num_chunks)
            # 分割数据
            chunks = []
            for i in range(0, len(error_data), chunk_size):
                chunk = error_data[i:i + chunk_size]
                # 确保分片后的数据大小不超过限制
                while len(json.dumps(chunk).encode('utf-8')) > MAX_DOCUMENT_SIZE // 2:
                    chunk_size = chunk_size // 2
                    chunk = error_data[i:i + chunk_size]
                chunks.append(chunk)
            return chunks
        else:
            # 如果不是列表，将数据转换为字符串后分片
            safe_size = MAX_DOCUMENT_SIZE // 2  # 预留一半空间给其他字段
            chunks = []
            current_chunk = []
            current_size = 0
            
            # 如果是字符串类型的数据，按字符分割
            if isinstance(error_data, str):
                for char in error_data:
                    char_size = len(char.encode('utf-8'))
                    if current_size + char_size > safe_size:
                        chunks.append(''.join(current_chunk))
                        current_chunk = [char]
                        current_size = char_size
                    else:
                        current_chunk.append(char)
                        current_size += char_size
                
                if current_chunk:
                    chunks.append(''.join(current_chunk))
            else:
                # 对于其他类型的数据，直接存储字符串形式
                chunk_size = safe_size
                for i in range(0, len(data_str), chunk_size):
                    chunks.append(data_str[i:i + chunk_size])
            
            return chunks
    
    # 如果数据大小在限制内，直接返回原数据
    return [error_data]

def import_error_data(db):
    """导入ErrorData目录下的所有JSON文件"""
    print("正在导入错误数据文件...")
    error_dir = "ErrorData"
    
    # 如果集合已存在，先删除
    db.error_data.drop()
    db.error_data_chunks.drop()
    
    # 遍历ErrorData目录下的所有JSON文件
    for filename in tqdm(os.listdir(error_dir)):
        if filename.endswith('.json'):
            file_path = os.path.join(error_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    error_data = json.load(f)
                
                # 从文件名中提取信息
                parts = filename.replace('.json', '').split('_')
                shot_number = parts[0]
                channel = parts[1]
                error_type = '_'.join(parts[2:])
                
                # 检查数据大小
                data_chunks = split_error_data(error_data)
                
                if len(data_chunks) > 1:
                    # 存储主文档
                    main_doc = {
                        "_id": filename.replace('.json', ''),
                        "filename": filename,
                        "shot_number": shot_number,
                        "channel": channel,
                        "error_type": error_type,
                        "is_chunked": True,
                        "total_chunks": len(data_chunks)
                    }
                    db.error_data.insert_one(main_doc)
                    
                    # 存储数据分片
                    for i, chunk in enumerate(data_chunks):
                        chunk_doc = {
                            "parent_id": main_doc["_id"],
                            "chunk_id": i,
                            "data": chunk
                        }
                        # 确保分片大小不超过限制
                        chunk_str = json.dumps(chunk_doc)
                        if len(chunk_str.encode('utf-8')) > MAX_DOCUMENT_SIZE:
                            print(f"警告: {filename} 的分片 {i} 仍然太大，跳过该分片")
                            continue
                        db.error_data_chunks.insert_one(chunk_doc)
                else:
                    # 直接存储数据
                    document = {
                        "_id": filename.replace('.json', ''),
                        "filename": filename,
                        "shot_number": shot_number,
                        "channel": channel,
                        "error_type": error_type,
                        "is_chunked": False,
                        "data": error_data
                    }
                    db.error_data.insert_one(document)
                
            except Exception as e:
                print(f"处理文件 {filename} 时发生错误: {str(e)}")
                continue
    
    print("错误数据文件导入完成")

def import_index_files(db):
    """导入所有索引文件"""
    index_files = {
        "shot_number_index": "shot_number_index.json",
        "channel_name_index": "channel_name_index.json",
        "channel_type_index": "channel_type_index.json",
        "db_name_index": "db_name_index.json",
        "error_name_index": "error_name_index.json",
        "error_origin_index": "error_origin_index.json"
    }
    
    for collection_name, filename in index_files.items():
        print(f"正在导入 {filename}...")
        file_path = os.path.join("IndexFile", filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            # 如果集合已存在，先删除
            db[collection_name].drop()
            # 插入数据
            db[collection_name].insert_one({"index": index_data})
            print(f"{filename} 导入完成")
            
        except Exception as e:
            print(f"导入 {filename} 时发生错误: {str(e)}")

def create_indexes(db):
    """创建必要的索引"""
    print("正在创建索引...")
    # 为error_data创建索引
    db.error_data.create_index([("filename", 1)])
    db.error_data.create_index([("shot_number", 1)])
    db.error_data.create_index([("channel", 1)])
    db.error_data.create_index([("error_type", 1)])
    
    # 为分片数据创建索引
    db.error_data_chunks.create_index([("parent_id", 1), ("chunk_id", 1)])
    db.struct_tree_chunks.create_index([("chunk_id", 1)])
    
    print("索引创建完成")

def main():
    try:
        # 连接数据库
        db = connect_mongodb()
        
        # 导入各类数据
        import_struct_tree(db)
        import_error_data(db)
        import_index_files(db)
        
        # 创建索引
        create_indexes(db)
        
        print("所有数据导入完成！")
        
    except Exception as e:
        print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main() 