import numpy as np


def func(arr, threshold=60000, window_size=3):
    # 将4*1024的数组按列求和，得到1*1024的数组
    column_sums = np.sum(arr, axis=0)

    # 初始化窗口的和
    current_sum = np.sum(column_sums[:window_size])

    # 用于存储满足条件的窗口索引范围
    result_ranges = []

    # 滑动窗口
    for i in range(len(column_sums) - window_size + 1):
        if current_sum > threshold:
            result_ranges.append((i, i + window_size - 1))
        # 更新窗口和，向右滑动一列
        if i + window_size < len(column_sums):
            current_sum += column_sums[i + window_size]
            current_sum -= column_sums[i]

    return result_ranges

# filename = 'error_EUVL_saturation.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# value = ret['value']

# for i in range(200):
#     tValue = value[:, :, i]
#     print(find_large_sums_optimized(tValue))


