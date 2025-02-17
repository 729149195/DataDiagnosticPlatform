import json
from pymongo import MongoClient
import os

# MongoDB连接配置
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "data_diagnostic"

def connect_mongodb():
    """连接到MongoDB数据库"""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db

def get_error_data(db, filename=None, shot_number=None, channel=None, error_type=None):
    """获取错误数据
    可以通过文件名、炮号、通道号或错误类型来查询
    """
    query = {}
    if filename:
        query["filename"] = filename
    if shot_number:
        query["shot_number"] = shot_number
    if channel:
        query["channel"] = channel
    if error_type:
        query["error_type"] = error_type

    # 查询主文档
    doc = db.error_data.find_one(query)
    if not doc:
        return None

    # 如果数据被分片存储
    if doc.get("is_chunked", False):
        # 获取所有分片
        chunks = list(db.error_data_chunks.find(
            {"parent_id": doc["_id"]},
            {"data": 1, "chunk_id": 1}
        ).sort("chunk_id"))
        
        # 组合分片数据
        if isinstance(chunks[0]["data"], list):
            # 如果是列表类型，直接连接
            full_data = []
            for chunk in chunks:
                full_data.extend(chunk["data"])
        else:
            # 如果是字符串类型，需要先连接再解析
            full_data = ""
            for chunk in chunks:
                full_data += chunk["data"]
            try:
                full_data = json.loads(full_data)
            except json.JSONDecodeError:
                pass
        
        doc["data"] = full_data
    return doc

def update_error_data(db, filename, update_data):
    """更新错误数据
    Args:
        db: MongoDB数据库连接
        filename: 要更新的文件名
        update_data: 要更新的数据字典，例如：{"error_type": "new_error_type"}
    Returns:
        bool: 更新是否成功
    """
    try:
        # 更新主文档
        result = db.error_data.update_one(
            {"filename": filename},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            print(f"成功更新文件 {filename} 的数据")
            return True
        else:
            print(f"未找到文件 {filename} 或数据未变化")
            return False
    except Exception as e:
        print(f"更新文件 {filename} 时发生错误: {str(e)}")
        return False

def delete_error_data(db, filename):
    """删除错误数据
    Args:
        db: MongoDB数据库连接
        filename: 要删除的文件名
    Returns:
        bool: 删除是否成功
    """
    try:
        # 先查询文档是否存在
        doc = db.error_data.find_one({"filename": filename})
        if not doc:
            print(f"未找到文件 {filename}")
            return False

        # 如果是分片存储，删除所有分片
        if doc.get("is_chunked", False):
            db.error_data_chunks.delete_many({"parent_id": doc["_id"]})

        # 删除主文档
        result = db.error_data.delete_one({"filename": filename})
        
        if result.deleted_count > 0:
            print(f"成功删除文件 {filename} 的数据")
            return True
        else:
            print(f"删除文件 {filename} 失败")
            return False
    except Exception as e:
        print(f"删除文件 {filename} 时发生错误: {str(e)}")
        return False

def update_index_data(db, index_type, new_index_data):
    """更新索引数据
    Args:
        db: MongoDB数据库连接
        index_type: 索引类型（例如：'error_name_index'）
        new_index_data: 新的索引数据
    Returns:
        bool: 更新是否成功
    """
    try:
        result = db[index_type].update_one(
            {},  # 更新第一个文档
            {"$set": {"index": new_index_data}},
            upsert=True
        )
        print(f"成功更新 {index_type} 索引数据")
        return True
    except Exception as e:
        print(f"更新 {index_type} 索引时发生错误: {str(e)}")
        return False

def get_struct_tree(db):
    """获取结构树数据"""
    doc = db.struct_tree.find_one()
    if not doc:
        return None

    # 检查是否是分片存储
    if doc.get("type") == "chunked":
        # 获取所有分片
        chunks = list(db.struct_tree_chunks.find().sort("chunk_id"))
        # 组合分片数据
        data_str = ""
        for chunk in chunks:
            data_str += chunk["data"]
        return json.loads(data_str)
    else:
        return doc.get("tree")

def get_index_data(db, index_type):
    """获取索引数据"""
    doc = db[index_type].find_one()
    return doc.get("index") if doc else None

def sync_error_data(db, channel_data_list):
    """同步错误数据到MongoDB
    Args:
        db: MongoDB数据库连接
        channel_data_list: 包含通道数据的列表，每个元素包含channelKey和errorData
    Returns:
        bool: 同步是否成功
    """
    try:
        for channel_data in channel_data_list:
            channel_key = channel_data['channelKey']
            manual_errors, machine_errors = channel_data['errorData']

            # 从channel_key解析通道信息
            channel_name, shot_number = channel_key.rsplit('_', 1)

            # 转换人工标注数据格式
            converted_manual_errors = []
            for error in manual_errors:
                if not error.get('anomalyCategory') or not error.get('anomalyDiagnosisName'):
                    continue

                converted_error = {
                    "person": error.get('person', 'unknown'),
                    "diagnostic_name": error.get('anomalyDiagnosisName', ''),
                    "channel_number": channel_name,
                    "error_type": error.get('anomalyCategory', ''),
                    "shot_number": shot_number,
                    "X_error": [[float(error.get('startX', 0)), float(error.get('endX', 0))]],
                    "Y_error": [],
                    "diagnostic_time": error.get('annotationTime', ''),
                    "error_description": error.get('anomalyDescription', '')
                }
                if converted_error['error_type'].strip():
                    converted_manual_errors.append(converted_error)

            # 获取所有非空的错误类型
            error_types = set()
            for error in converted_manual_errors:
                if error['error_type'].strip():
                    error_types.add(error['error_type'])
            for error in machine_errors:
                if error.get('error_type', '').strip():
                    error_types.add(error['error_type'])

            # 处理每种错误类型
            for error_type in error_types:
                if not error_type.strip():
                    continue

                # 构建文档ID
                doc_id = f"{shot_number}_{channel_name}_{error_type}"

                # 准备当前错误类型的数据
                current_manual_errors = [error for error in converted_manual_errors if error['error_type'] == error_type]
                current_machine_errors = [error for error in machine_errors if error['error_type'] == error_type]

                # 查找现有文档
                existing_doc = db.error_data.find_one({"_id": doc_id})

                if existing_doc:
                    # 合并现有数据和新数据
                    existing_manual_errors = existing_doc.get('manual_errors', [])
                    existing_machine_errors = existing_doc.get('machine_errors', [])

                    # 使用字典去重
                    manual_error_dict = {
                        f"{error.get('person')}_{error.get('X_error', [[]])[0][0]}_{error.get('X_error', [[]])[0][1]}": error
                        for error in existing_manual_errors
                    }
                    for error in current_manual_errors:
                        key = f"{error.get('person')}_{error.get('X_error', [[]])[0][0]}_{error.get('X_error', [[]])[0][1]}"
                        manual_error_dict[key] = error

                    machine_error_dict = {
                        f"{error.get('X_error', [[]])[0][0]}_{error.get('X_error', [[]])[0][1]}": error
                        for error in existing_machine_errors
                    }
                    for error in current_machine_errors:
                        key = f"{error.get('X_error', [[]])[0][0]}_{error.get('X_error', [[]])[0][1]}"
                        machine_error_dict[key] = error

                    # 更新文档
                    db.error_data.update_one(
                        {"_id": doc_id},
                        {
                            "$set": {
                                "manual_errors": list(manual_error_dict.values()),
                                "machine_errors": list(machine_error_dict.values()),
                                "shot_number": shot_number,
                                "channel": channel_name,
                                "error_type": error_type
                            }
                        }
                    )
                else:
                    # 创建新文档
                    db.error_data.insert_one({
                        "_id": doc_id,
                        "filename": f"{doc_id}.json",
                        "shot_number": shot_number,
                        "channel": channel_name,
                        "error_type": error_type,
                        "manual_errors": current_manual_errors,
                        "machine_errors": current_machine_errors
                    })

            # 更新结构树
            update_struct_tree(db, shot_number, channel_name, list(error_types))

        return True
    except Exception as e:
        print(f"同步错误数据时发生错误: {str(e)}")
        return False

def update_struct_tree(db, shot_number, channel_name, error_types):
    """更新结构树中的错误类型
    Args:
        db: MongoDB数据库连接
        shot_number: 炮号
        channel_name: 通道名
        error_types: 错误类型列表
    """
    try:
        # 获取现有的结构树
        struct_tree = get_struct_tree(db)
        if not struct_tree:
            return

        # 更新对应通道的error_name
        updated = False
        for item in struct_tree:
            if (item['shot_number'] == shot_number and 
                item['channel_name'] == channel_name):
                if 'error_name' not in item:
                    item['error_name'] = []
                # 添加新的错误类型
                for error_type in error_types:
                    if error_type.strip() and error_type not in item['error_name']:
                        item['error_name'].append(error_type)
                updated = True
                break

        if updated:
            # 更新结构树文档
            db.struct_tree.update_one(
                {},
                {"$set": {"tree": struct_tree}},
                upsert=True
            )
    except Exception as e:
        print(f"更新结构树时发生错误: {str(e)}")

def delete_error_data_by_diagnostic(db, diagnostic_name, channel_number, shot_number, error_type):
    """根据诊断名称删除错误数据
    Args:
        db: MongoDB数据库连接
        diagnostic_name: 诊断名称
        channel_number: 通道号
        shot_number: 炮号
        error_type: 错误类型
    Returns:
        bool: 删除是否成功
    """
    try:
        # 构建文档ID
        doc_id = f"{shot_number}_{channel_number}_{error_type}"
        
        # 查找文档
        doc = db.error_data.find_one({"_id": doc_id})
        if not doc:
            print(f"未找到对应的错误数据文档")
            return False

        # 过滤掉指定诊断名称的错误
        manual_errors = [error for error in doc.get('manual_errors', [])
                        if error.get('diagnostic_name') != diagnostic_name]
        machine_errors = [error for error in doc.get('machine_errors', [])
                        if error.get('diagnostic_name') != diagnostic_name]

        if not manual_errors and not machine_errors:
            # 如果没有剩余的错误数据，删除整个文档
            db.error_data.delete_one({"_id": doc_id})
            
            # 更新结构树
            struct_tree = get_struct_tree(db)
            if struct_tree:
                for item in struct_tree:
                    if (item['shot_number'] == shot_number and 
                        item['channel_name'] == channel_number and 
                        'error_name' in item):
                        if error_type in item['error_name']:
                            item['error_name'].remove(error_type)
                            # 更新结构树
                            db.struct_tree.update_one(
                                {},
                                {"$set": {"tree": struct_tree}},
                                upsert=True
                            )
                            break
        else:
            # 更新文档
            db.error_data.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "manual_errors": manual_errors,
                        "machine_errors": machine_errors
                    }
                }
            )

        return True
    except Exception as e:
        print(f"删除错误数据时发生错误: {str(e)}")
        return False

def main():
    """示例操作"""
    db = connect_mongodb()
    
    # 1. 同步数据示例
    print("\n1. 同步错误数据示例：")
    test_channel_data = [{
        "channelKey": "AXUV004_1",
        "errorData": [
            [  # manual_errors
                {
                    "person": "test_user",
                    "anomalyDiagnosisName": "test_diagnosis",
                    "anomalyCategory": "test_error",
                    "startX": 1.0,
                    "endX": 2.0,
                    "annotationTime": "2024-02-17",
                    "anomalyDescription": "test description"
                }
            ],
            []  # machine_errors
        ]
    }]
    sync_error_data(db, test_channel_data)
    
    # 2. 删除数据示例
    print("\n2. 删除错误数据示例：")
    delete_error_data_by_diagnostic(
        db,
        diagnostic_name="test_diagnosis",
        channel_number="AXUV004",
        shot_number="1",
        error_type="test_error"
    )

if __name__ == "__main__":
    main() 