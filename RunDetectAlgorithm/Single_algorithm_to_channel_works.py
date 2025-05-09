"""
单算法异常检测更新工具

该模块用于对指定算法重新运行异常检测，并更新所有以DataDiagnosticPlatform开头的MongoDB数据库中相关通道的errors_data。
同时根据情况决定是否需要更新相应的索引结构。

用法:
python Single_algorithm_to_channel.py <通道类型> <算法名称>

示例:
python Single_algorithm_to_channel.py HXR error_hxr_saturation_counts
"""
import re
import time
import sys
import traceback
import json
import logging
import importlib.util
import random
from datetime import datetime
import os

import numpy as np
from pymongo import MongoClient, ASCENDING, UpdateMany
from tqdm import tqdm

from mdsConn import MdsTree

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('single_algorithm_update.log')
    ]
)
logger = logging.getLogger('SingleAlgorithmUpdate')

# 数据库配置信息
DBS = {
    'exl50':{
        'name':'exl50',
        'addr':'192.168.20.11',
        'path':'192.168.20.11::/media/ennfusion/trees/exl50',
        'subtrees':['FBC','PAI','PMNT']
    },
    'exl50u':{
        'name':'exl50u',
        'addr':'192.168.20.11',
        'path':'192.168.20.11::/media/ennfusion/trees/exl50u',
        'subtrees':['FBC','PAI','PMNT']
    },
    'eng50u':{
        'name':'eng50u',
        'addr':'192.168.20.41',
        'path':'192.168.20.41::/media/ennfusion/ENNMNT/trees/eng50u',
        'subtrees':['PMNT']
    },
    'ecrhlab':{
        'name':'ecrhlab',
        'addr':'192.168.20.32',
        'path':'192.168.20.32::/media/ecrhdb/trees/ecrhlab',
        'subtrees':['PAI']
    },
    'ts':{
        'name':'ts',
        'addr':'192.168.20.28',
        'path':'192.168.20.28::/media/ennts/trees/ts',
        'subtrees':['AI']
    },
}

class JsonEncoder(json.JSONEncoder):
    """转换numpy类型为JSON可序列化对象"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(JsonEncoder, self).default(obj)

def import_module_from_path(module_name, file_path):
    """动态导入指定路径的模块"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def remove_digits(s: str) -> str:
    """去掉字符串中的所有数字"""
    return re.match(r'^[^\d]*', s)[0]

def get_target_databases():
    """获取所有以DataDiagnosticPlatform开头的MongoDB数据库"""
    client = MongoClient("mongodb://localhost:27017")
    db_names = client.list_database_names()
    target_dbs = [db for db in db_names if db.startswith("DataDiagnosticPlatform_[4571_4580]")]
    return target_dbs

def extract_shot_range(db_name):
    """从数据库名称中提取炮号范围"""
    match = re.search(r'\[(\d+)_(\d+)\]', db_name)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None

def process_channel(channel_data, algorithm_module, tree):
    """对单个通道运行指定算法并返回检测结果"""
    shot_num = channel_data["shot_number"]
    channel_name = channel_data["channel_name"]
    DB = channel_data["db_name"]
    channel_type = channel_data["channel_type"]
    
    # 创建结果结构
    result = {
        "status": "processing",
        "error_data": None,
        "message": ""
    }
    
    max_retries = 5
    try:
        # 读取通道数据
        X_value, Y_value = None, None
        for retry in range(max_retries):
            try:
                if channel_type == 'MP':
                    X_value, Y_value = tree.getData(channel_name, -7, 5)
                else:
                    X_value, Y_value = tree.getData(channel_name)
                break
            except Exception as e:
                if retry < max_retries - 1:
                    wait_time = (2 ** retry) * 0.5 + random.uniform(0, 0.5)
                    time.sleep(wait_time)
                    continue
                result["status"] = "data_read_failed"
                result["message"] = f"数据读取失败: {str(e)}"
                return result
        
        if X_value is None or Y_value is None or len(Y_value) == 0:
            result["status"] = "empty_data"
            result["message"] = "数据为空或无效"
            return result
        
        X_unit = 's'
        if channel_type == 'TS':
            X_unit = 'ns'
        
        # 获取可能需要的辅助通道数据
        aux_channel_data = {}
        if channel_type == 'AXUV' and algorithm_module.__name__ == 'error_axuv_Detector_channel_damage':
            try:
                _, aux_data = tree.getData('ECRH0_UA')
                aux_channel_data['ECRH0_UA'] = aux_data
            except Exception as e:
                result["status"] = "aux_data_read_failed"
                result["message"] = f"辅助数据读取失败: {str(e)}"
                return result
                
        elif channel_type == 'SDDINTEN' and algorithm_module.__name__ == 'error_sxr_spectra_saturation':
            try:
                _, aux_data = tree.getData('IP')
                aux_channel_data['IP'] = aux_data
            except Exception as e:
                result["status"] = "aux_data_read_failed"
                result["message"] = f"辅助数据读取失败: {str(e)}"
                return result
        
        # 运行异常检测算法
        try:
            if algorithm_module.__name__ == 'error_axuv_Detector_channel_damage':
                if 'ECRH0_UA' not in aux_channel_data:
                    result["status"] = "missing_aux_data"
                    result["message"] = "缺少ECRH0_UA辅助数据"
                    return result
                error_indexes = algorithm_module.func(Y_value, aux_channel_data['ECRH0_UA'])
            elif algorithm_module.__name__ == 'error_sxr_spectra_saturation':
                if 'IP' not in aux_channel_data:
                    result["status"] = "missing_aux_data"
                    result["message"] = "缺少IP辅助数据"
                    return result
                error_indexes = algorithm_module.func(Y_value, aux_channel_data['IP'])
            elif channel_type == 'TS':
                error_indexes = algorithm_module.func(Y_value, X_value)
            else:
                error_indexes = algorithm_module.func(Y_value)
        except Exception as e:
            result["status"] = "algorithm_failed"
            result["message"] = f"算法执行失败: {str(e)}"
            return result
        
        # 处理检测结果
        try:
            if channel_type != 'TS':
                X_value_error = [[X_value[indice[0]], X_value[indice[1]]] for indice in error_indexes if indice[0] < len(X_value) and indice[1] < len(X_value)]
            else:
                X_value_error = error_indexes
        except Exception as e:
            result["status"] = "result_processing_failed"
            result["message"] = f"结果处理失败: {str(e)}"
            return result
        
        # 检测到异常，准备数据
        if len(error_indexes) != 0:
            error_data = [[], [{
                'person': "mechine",
                'diagnostic_name': channel_type,
                'channel_number': channel_name,
                'error_type': algorithm_module.__name__,
                "shot_number": str(shot_num),
                'X_error': list(X_value_error),
                'diagonistic_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error_description": '',
            }]]
            
            result["status"] = "success"
            result["error_data"] = error_data
        else:
            # 未检测到异常
            result["status"] = "success_no_error"
            result["message"] = "未检测到异常"
    except Exception as e:
        result["status"] = "processing_error"
        result["message"] = f"处理异常: {str(e)}"
    
    return result

def update_index_for_channel(db, shot_number, channel_name, error_name, has_error):
    """更新单个通道的索引信息"""
    struct_trees_collection = db["struct_trees"]
    index_collection = db["index"]
    
    # 获取结构树数据
    struct_data = struct_trees_collection.find_one({"shot_number": shot_number})
    if not struct_data or "struct_tree" not in struct_data:
        logger.warning(f"未找到炮号 {shot_number} 的结构树数据")
        return False
    
    struct_tree = struct_data["struct_tree"]
    
    # 找到通道在结构树中的索引
    channel_idx = None
    for idx, item in enumerate(struct_tree):
        if item.get("channel_name") == channel_name:
            channel_idx = idx
            # 更新error_name字段
            if has_error and error_name not in item.get("error_name", []):
                if "error_name" not in item:
                    item["error_name"] = []
                item["error_name"].append(error_name)
            elif not has_error and error_name in item.get("error_name", []):
                item["error_name"].remove(error_name)
            
            # 更新结构树
            struct_trees_collection.update_one(
                {"shot_number": shot_number},
                {"$set": {f"struct_tree.{idx}": item}}
            )
            break
    
    if channel_idx is None:
        logger.warning(f"在结构树中未找到通道 {channel_name}")
        return False
    
    # 更新error_name索引
    index_doc = index_collection.find_one({"key": "error_name"})
    if index_doc and "index_data" in index_doc and shot_number in index_doc["index_data"]:
        shot_index = index_doc["index_data"][shot_number]
        
        # 更新error_name索引
        if has_error:
            if error_name not in shot_index:
                shot_index[error_name] = []
            if channel_idx not in shot_index[error_name]:
                shot_index[error_name].append(channel_idx)
        else:
            if error_name in shot_index and channel_idx in shot_index[error_name]:
                shot_index[error_name].remove(channel_idx)
                if not shot_index[error_name]:  # 如果列表为空，删除该键
                    del shot_index[error_name]
        
        # 保存更新后的索引
        index_collection.update_one(
            {"key": "error_name"},
            {"$set": {f"index_data.{shot_number}": shot_index}}
        )
    
    return True

def main():
    # 解析命令行参数
    if len(sys.argv) != 3:
        print("用法: python Single_algorithm_to_channel.py <通道类型> <算法名称>")
        print("示例: python Single_algorithm_to_channel.py HXR error_hxr_saturation_counts")
        sys.exit(1)
    
    channel_type = sys.argv[1]
    algorithm_name = sys.argv[2]
    
    print(f"开始处理通道类型 {channel_type} 的 {algorithm_name} 算法")
    
    # 确定配置文件路径
    config_path = 'algorithmChannelMap.json'
    if not os.path.exists(config_path):
        config_path = os.path.join('RunDetectAlgorithm', 'algorithmChannelMap.json')
    
    # 加载算法与通道映射关系
    try:
        with open(config_path, encoding='utf-8') as f:
            algorithm_channel_map = json.load(f)
    except Exception as e:
        logger.error(f"无法加载算法映射配置文件: {e}")
        print(f"错误: 无法加载算法映射配置文件 - {e}")
        sys.exit(1)
    
    # 检查指定的通道类型和算法是否存在
    if channel_type not in algorithm_channel_map:
        logger.error(f"通道类型 {channel_type} 不存在于配置文件中")
        print(f"错误: 通道类型 {channel_type} 不存在于配置文件中")
        sys.exit(1)
    
    if algorithm_name not in algorithm_channel_map[channel_type]:
        logger.error(f"算法 {algorithm_name} 不存在于通道类型 {channel_type} 的配置中")
        print(f"错误: 算法 {algorithm_name} 不存在于通道类型 {channel_type} 的配置中")
        sys.exit(1)
    
    # 获取需要处理的通道列表
    target_channels = algorithm_channel_map[channel_type][algorithm_name]
    print(f"将处理 {len(target_channels)} 个通道: {', '.join(target_channels[:5])}{'...' if len(target_channels) > 5 else ''}")
    
    # 加载算法模块
    algorithm_path = f'algorithm/{channel_type}/{algorithm_name}.py'
    if not os.path.exists(algorithm_path):
        # 尝试不同的相对路径
        alternate_path = os.path.join('RunDetectAlgorithm', 'algorithm', channel_type, f'{algorithm_name}.py')
        if os.path.exists(alternate_path):
            algorithm_path = alternate_path
        else:
            logger.error(f"无法找到算法文件: {algorithm_path} 或 {alternate_path}")
            print(f"错误: 无法找到算法文件。尝试了以下路径:")
            print(f"  - {os.path.abspath(algorithm_path)}")
            print(f"  - {os.path.abspath(alternate_path)}")
            sys.exit(1)
    
    print(f"使用算法文件路径: {os.path.abspath(algorithm_path)}")
    
    try:
        algorithm_module = import_module_from_path(algorithm_name, algorithm_path)
        print(f"成功加载算法模块: {algorithm_name}")
    except Exception as e:
        logger.error(f"无法加载算法模块 {algorithm_name}: {e}")
        print(f"错误: 无法加载算法模块 - {e}")
        sys.exit(1)
    
    # 获取所有目标数据库
    target_dbs = get_target_databases()
    if not target_dbs:
        logger.warning("未找到以DataDiagnosticPlatform开头的数据库")
        print("警告: 未找到以DataDiagnosticPlatform开头的数据库")
        sys.exit(0)
    
    print(f"找到 {len(target_dbs)} 个目标数据库: {', '.join(target_dbs)}")
    
    # 处理每个数据库
    for db_name in target_dbs:
        print(f"\n正在处理数据库: {db_name}")
        client = MongoClient("mongodb://localhost:27017")
        db = client[db_name]
        
        # 获取数据库中的所有炮号
        struct_trees_collection = db["struct_trees"]
        errors_collection = db["errors_data"]
        
        shot_start, shot_end = extract_shot_range(db_name)
        if shot_start is None or shot_end is None:
            logger.warning(f"无法从数据库名 {db_name} 中提取炮号范围，将扫描所有文档")
            # 获取所有唯一的炮号
            shot_numbers = struct_trees_collection.distinct("shot_number")
        else:
            logger.info(f"数据库 {db_name} 炮号范围: {shot_start} - {shot_end}")
            shot_numbers = [str(i) for i in range(shot_start, shot_end + 1)]
        
        print(f"数据库 {db_name} 中有 {len(shot_numbers)} 个炮号需要处理")
        
        # 统计变量
        total_channels = 0
        processed_channels = 0
        updated_channels = 0
        failed_channels = 0
        
        # 首先计算总通道数以便显示整体进度
        print("正在统计需要处理的通道数量...")
        for shot_number in tqdm(shot_numbers, desc="统计通道数量"):
            struct_data = struct_trees_collection.find_one({"shot_number": shot_number})
            if struct_data and "struct_tree" in struct_data:
                for item in struct_data["struct_tree"]:
                    if item.get("channel_name") in target_channels:
                        total_channels += 1
        
        print(f"找到 {total_channels} 个需要处理的通道")
        
        # 创建总进度条
        with tqdm(total=total_channels, desc="总进度") as pbar_total:
            # 扫描每个炮号
            for shot_number in tqdm(shot_numbers, desc=f"炮号"):
                # 获取该炮的结构树
                struct_data = struct_trees_collection.find_one({"shot_number": shot_number})
                if not struct_data or "struct_tree" not in struct_data:
                    continue
                
                struct_tree = struct_data["struct_tree"]
                
                # 找到目标通道
                channels_to_process = []
                for item in struct_tree:
                    if item.get("channel_name") in target_channels:
                        channels_to_process.append(item)
                
                # 处理每个通道
                for channel_data in channels_to_process:
                    channel_name = channel_data.get("channel_name", "未知通道")
                    pbar_total.set_description(f"总进度 - 当前: 炮号{shot_number} 通道{channel_name}")
                    processed_channels += 1
                    # 新增：为每个shot只建立一次MdsTree连接
                    if len(channels_to_process) > 0:
                        # 只在第一个通道时建立连接
                        if channel_data == channels_to_process[0]:
                            try:
                                tree = MdsTree(int(shot_number), dbname=channel_data["db_name"], path=DBS[channel_data["db_name"]]['path'], subtrees=DBS[channel_data["db_name"]]['subtrees'])
                            except Exception as e:
                                logger.warning(f"MdsTree连接失败 - 炮号: {shot_number}, 错误: {str(e)}")
                                failed_channels += len(channels_to_process)
                                break
                        # 传递tree对象
                        result = process_channel(channel_data, algorithm_module, tree)
                    else:
                        result = process_channel(channel_data, algorithm_module, None)
                    
                    if result["status"] == "success" and result["error_data"]:
                        # 更新errors_data集合
                        error_data = result["error_data"]
                        query = {
                            "shot_number": channel_data["shot_number"],
                            "channel_number": channel_data["channel_name"],
                            "error_type": algorithm_name
                        }
                        
                        errors_collection.update_one(
                            query,
                            {"$set": {"data": error_data}},
                            upsert=True
                        )
                        
                        # 更新索引
                        update_index_for_channel(
                            db, 
                            channel_data["shot_number"], 
                            channel_data["channel_name"], 
                            algorithm_name, 
                            True
                        )
                        
                        updated_channels += 1
                        
                    elif result["status"] == "success_no_error":
                        # 检查是否需要删除现有的错误数据
                        query = {
                            "shot_number": channel_data["shot_number"],
                            "channel_number": channel_data["channel_name"],
                            "error_type": algorithm_name
                        }
                        
                        existing_error = errors_collection.find_one(query)
                        if existing_error:
                            # 删除错误数据
                            errors_collection.delete_one(query)
                            
                            # 更新索引，移除错误标记
                            update_index_for_channel(
                                db, 
                                channel_data["shot_number"], 
                                channel_data["channel_name"], 
                                algorithm_name, 
                                False
                            )
                            
                            updated_channels += 1
                    else:
                        # 处理失败的通道
                        failed_channels += 1
                        logger.warning(
                            f"处理通道失败 - 炮号: {channel_data['shot_number']}, "
                            f"通道: {channel_data['channel_name']}, "
                            f"状态: {result['status']}, "
                            f"消息: {result['message']}"
                        )
                    
                    # 更新总进度条
                    pbar_total.update(1)
                    # 在最后一个通道后关闭tree连接
                    if channel_data == channels_to_process[-1]:
                        try:
                            tree.close()
                        except:
                            pass
        
        # 打印统计信息
        print(f"\n数据库 {db_name} 处理完成:")
        print(f"- 总通道数: {total_channels}")
        print(f"- 已处理: {processed_channels}")
        print(f"- 已更新: {updated_channels}")
        print(f"- 处理失败: {failed_channels}")
    
    print("\n所有数据库处理完成!")

if __name__ == "__main__":
    main()
