import numpy as np
# filename = 'error_hxr_saturation_counts_ex.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = ret['X_value']
# Y_value_error = np.array(ret['Y_value_error'])
# lp_value_error = ret['lp_value_error']
#
# avgV = np.average(Y_value_error[:50000])

def func(Y_value_error):
    # 定义文件路径
    file_path = 'RunDetectAlgorithm/baseline.txt'

    # 从文件中读取浮点数
    try:
        with open(file_path, 'r') as file:
            number = float(file.read().strip())
            # print(f"从文件中读取的浮点数: {number}")
    except FileNotFoundError:
        print(f"文件 {file_path} 不存在！")
        exit(1)
    except ValueError:
        print(f"文件 {file_path} 中的内容不是有效的浮点数！")
        exit(1)

    ranges = []
    i = 0
    # minV = np.min(Y_value_error[50000]) * 1.1
    while i < len(Y_value_error):
        if Y_value_error[i] < 1:
            start = i
            i += 1
            while i < len(Y_value_error) and Y_value_error[i] < 1:
                i += 1
            if i - start > 1:
                ranges.append([start, i-1])
        i += 1
    spec_interval = Y_value_error[100000:150000]
    number = (max(spec_interval) - min(spec_interval)) / 2

    # 将处理后的浮点数写回文件
    with open(file_path, 'w') as file:
        file.write(str(number))
        # print(f"已将处理后的浮点数写入文件 {file_path}")
    return ranges