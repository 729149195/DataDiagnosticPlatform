import re
import time
from datetime import datetime
import importlib
import json

import MDSplus ## type: ignore
import numpy as np

from mdsConn import MdsTree, formChaPool

class JsonEncoder(json.JSONEncoder):
    """Convert numpy classes to JSON serializable objects."""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(JsonEncoder, self).default(obj)

#
# tree = MdsTree(6666)
# ip = tree.getData('IP')
#
# print(ip)

def import_module_from_path(module_name, file_path):
    # 创建一个模块规范
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    # 创建模块对象
    module = importlib.util.module_from_spec(spec)
    # 执行模块
    spec.loader.exec_module(module)
    return module

def remove_digits(s: str) -> str:
    """去掉字符串中的所有数字"""
    return re.match(r'^[^\d]*', s)[0]


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

def RUN(shot_list, channel_list):
    with open('RunDetectAlgorithm/algorithmChannelMap.json', encoding='utf-8') as f:
        algorithm_channel_map = json.load(f)
    # with open('typeChannelMap.json', encoding='utf-8') as f:
    #     typeChannelMap = json.load(f)
    detect_channel_type_list = algorithm_channel_map.keys()
    # error_channel_map = algorithm_channel_map[channel_type]
    DB_list = ["exl50u", "eng50u"]
    # idx = 0
    # cp = formChaPool(DB_list[idx], -1, path=DBS[DB_list[idx]]['path'], subtrees=DBS[DB_list[idx]]['subtrees'])
    # result = [item for item in cp if 'MP037' in item]
    # print(result)

    struct_tree = []
    # shot_list = list(range(4470, 4571))
    shot_list = list(range(*shot_list))
    read_time = 0
    # shot_list = list([4474])
    for DB in DB_list:
        for i in shot_list:
            start = time.time()
            try:
                tree = MdsTree(i, dbname=DB, path=DBS[DB]['path'], subtrees=DBS[DB]['subtrees'])
                channel_pool = tree.formChannelPool()
                if len(channel_list) == 0:
                    channel_list = channel_pool
                # for s in channel_pool:
                #     if any(c.islower() for c in s):
                #         print(s)
            except Exception as e:
                print(f"炮号{str(i)}发生异常: {e}, 跳过本次循环")
                continue
            idx = 0
            for channel_name in channel_pool:
                if channel_name not in channel_list:
                    continue
                channel_type = remove_digits(channel_name).upper()
                if channel_type == 'MIR':
                    channel_type = 'Mirnov'


                temp = {
                    "shot_number": str(i),
                    "channel_type": channel_type,
                    "channel_name": channel_name,
                    'db_name': DB,
                    'error_name': []
                }
                try:
                    detect_type = channel_type
                    if detect_type in ['MP', 'FLUX', 'IPF']:
                        detect_type = 'MP'
                    if detect_type in list(detect_channel_type_list):
                        read_start = time.time()
                        if detect_type == 'MP':
                            X_value, Y_value = tree.getData(channel_name, -7, 5)
                        else:
                            X_value, Y_value = tree.getData(channel_name)
                        if len(Y_value) == 0:
                            continue
                            # time_diffs = np.diff(np.array(X_value))
                            # sample_rate = 10 ** round(np.log10(1 / np.mean(time_diffs)))
                        X_unit = 's'
                        if channel_type == 'TS':
                            X_unit = 'ns'

                        # Y_unit = channel_data[2]
                        read_end = time.time()
                        read_time += read_end - read_start
                        error_channel_map = algorithm_channel_map[detect_type]
                        error_type_list = error_channel_map.keys()
                        for error in error_type_list:
                            if channel_name in error_channel_map[error]:
                                # print(f'{channel_name}__{error}')
                                path = f'RunDetectAlgorithm/algorithm/{detect_type}/{error}.py'
                                moduleX = import_module_from_path(error, path)

                                # start = time.time()
                                if error == 'error_axuv_Detector_channel_damage':
                                    _, other_channel_data = tree.getData('ECRH0_UA')
                                    error_indexes = moduleX.func(Y_value, other_channel_data)
                                elif error == 'error_sxr_spectra_saturation':
                                    _, other_channel_data = tree.getData('IP')
                                    error_indexes = moduleX.func(Y_value, other_channel_data)
                                elif channel_type == 'TS':
                                    error_indexes = moduleX.func(Y_value, X_value)
                                else:
                                    error_indexes = moduleX.func(Y_value)
                                # end = time.time()
                                # print("算法运行时间：", round(end - start, 2))
                                # 算法运行时间： 2.74
                                if channel_type != 'TS':
                                    X_value_error = [[X_value[indice[0]], X_value[indice[1]]] for indice in error_indexes]
                                else:
                                    X_value_error = error_indexes
                                # Y_value_error = [list(Y_value[indice[0]: indice[1]+1]) for indice in error_indexes]


                                # 需要确定一下这个写法是否正确 --- 说明检测到了异常
                                if len(error_indexes) != 0:
                                    # 先写一段保存异常结果的代码
                                    with open(f'backend/static/ErrorData/{str(i)}_{channel_name}_{error}.json', 'w', encoding='utf-8') as f:
                                        json.dump([[], [{
                                            'person': "mechine",
                                            'diagnostic_name': channel_type,
                                            'channel_number': channel_name,
                                            'error_type': error,
                                            "shot_number": str(i),
                                            'X_error': list(X_value_error),
                                            # 'Y_error': list(Y_value_error),
                                            'diagonistic_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            "error_description": '',
                                            # "sample_rate":sample_rate
                                        }]], f, ensure_ascii=False, cls=JsonEncoder)
                                    # 放入结构树的代码
                                    temp['error_name'].append(error)
                except Exception as e:
                    print(f"{channel_name}-{i}诊断发生异常: {e}, 跳过本次循环")
                struct_tree.append(temp)
                # print(f'写入通道{channel_name}')
            end = time.time()
            tree.close()
            print(f'已执行完{DB}-{str(i)}, 运行时间:{round(end-start, 2)}s, 读取时间:{round(read_time, 2)}s')
    with open(f'structTree{shot_list[0]}_{shot_list[-1]}.json', 'w', encoding='utf-8') as f:
        json_str = json.dumps(struct_tree, ensure_ascii=False)
        f.write(json_str)

with open('RunDetectAlgorithm/algorithmChannelMap.json', encoding='utf-8') as f:
    algorithm_channel_map = json.load(f)
# shot_list = [4470, 4571]
shot_list = [4571, 5071]
# error_list = {'HCN_NE': ['error_hcn_hop']}
channel_list = []
# for key in error_list:
    # for v in error_list[key]:
        # channel_list.extend(algorithm_channel_map[key][v])
RUN(shot_list, channel_list)

# import json

# def merge_json_lists(list1, list2, keys=['shot_number', 'channel_name']):
#     merged = {}
#     for item in list1 + list2:
#         curK = item[keys[0]]+item[keys[1]]
#         if curK in merged:
#             merged[curK].update(item)  # 如果存在则更新
#         else:
#             merged[curK] = item  # 如果不存在则添加
#     return list(merged.values())

# def sort_by_multiple_keys(data, keys=['channel_name', 'shot_number']):
#     """
#     按多个键排序字典列表
#     keys: 元组或列表，指定排序的键和顺序
#     例如: ('date', 'name') 表示先按date排序，再按name排序
#     """
#     return sorted(data, key=lambda x: tuple(x[key] for key in keys))

# # 读取文件
# with open('StructTree.json', 'r', encoding='utf-8') as f1:
#     data1 = json.load(f1)
    
# with open('structTree4470_4570.json', 'r', encoding='utf-8') as f2:
#     data2 = json.load(f2)

# # 合并数据
# merged_data = merge_json_lists(data1, data2)

# sorted_data = sort_by_multiple_keys(merged_data)

# # 保存结果
# with open('StructTree.json', 'w', encoding='utf-8') as outfile:
#     json.dump(sorted_data, outfile, ensure_ascii=False, indent=4)







