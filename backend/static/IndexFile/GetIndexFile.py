import json
import os

# 定义输入文件和输出目录
input_file = 'backend/static/StructTree.json'  # 替换为您的 JSON 文件路径


# 读取 JSON 文件
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 遍历数据，为每个 key 创建索引文件
key_index_files = {}

# 为每个 key 生成索引
for idx, item in enumerate(data):
    for key, value in item.items():
        if key not in key_index_files:
            key_index_files[key] = {}
        if type(value) != list:
            if value not in key_index_files[key]:
                key_index_files[key][value] = []
            key_index_files[key][value].append(idx)
        else:
            if len(value) == 0:
                key_index_files[key].setdefault('NO ERROR', []).append(idx)
            for v in value:
                if v not in key_index_files[key]:
                    key_index_files[key][v] = []
                key_index_files[key][v].append(idx)

# 为每个 key 单独保存索引文件
for key, index_data in key_index_files.items():
    output_file = os.path.join('backend/static/IndexFile/', f"{key}_index.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=4)



# import json
# with open('../StructTree.json', 'r', encoding='utf-8') as f:
#     data = json.load(f)
#     print(data[303])