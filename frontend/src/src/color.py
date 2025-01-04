import scipy.io
import json
import numpy as np

def mat_to_json(mat_file_path, json_file_path, variable_name=None):
    """
    将.mat文件中的数据读取，处理后保存为JSON文件。

    :param mat_file_path: 输入的.mat文件路径
    :param json_file_path: 输出的JSON文件路径
    :param variable_name: .mat文件中变量的名称，如果未提供，则使用第一个变量
    """
    # 读取.mat文件
    mat_contents = scipy.io.loadmat(mat_file_path)
    
    # 如果没有指定变量名，获取第一个非魔术变量
    if variable_name is None:
        # .mat文件中包含一些以双下划线开头的元数据字段，过滤掉它们
        variables = {key: value for key, value in mat_contents.items() if not key.startswith('__')}
        if not variables:
            raise ValueError(".mat 文件中没有找到有效的数据变量。")
        variable_name, data = next(iter(variables.items()))
        print(f"使用变量 '{variable_name}' 来处理数据。")
    else:
        if variable_name not in mat_contents:
            raise ValueError(f"变量 '{variable_name}' 不存在于.mat 文件中。")
        data = mat_contents[variable_name]
    
    # 检查数据的形状是否为 (253, 3)
    if data.shape != (253, 3):
        print(f"警告: 数据的形状为 {data.shape}，预期形状为 (253, 3)。")

    # 确保数据类型为浮点数
    if not issubclass(data.dtype.type, np.floating):
        raise TypeError("数据类型必须是浮点数。")

    # 将每个数值乘以 256，并转换为整数
    processed_data = (data * 256).astype(int).tolist()

    # 保存为JSON文件
    with open(json_file_path, 'w') as json_file:
        json.dump(processed_data, json_file, indent=2)
    
    print(f"数据已成功保存到 '{json_file_path}'。")

if __name__ == "__main__":
    # 设置输入和输出文件路径
    input_mat_file = 'mycolors.mat'      # 替换为你的.mat文件路径
    output_json_file = 'color.json' # 替换为你希望保存的JSON文件路径

    # 如果你知道.mat文件中变量的名称，可以在这里指定，例如 'myData'
    # 否则，将自动使用第一个变量
    variable_name = None  # 或者例如 'myData'

    try:
        mat_to_json(input_mat_file, output_json_file, variable_name)
    except Exception as e:
        print(f"发生错误: {e}")
