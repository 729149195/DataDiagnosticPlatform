def func(arr):
    ranges = []
    threshold = 10
    start = None  # 开始位置的索引
    i = 0
    while i < len(arr):
        if arr[i] > threshold:
            i += 1
            start = i
            while i < len(arr) and arr[i] > 10:
                i += 1
            if i - start > 1:
                ranges.append([start, i-1])
        i += 1

    return ranges


# filename = 'error_axuv_saturation.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# error_sign = ret['Y_value_error']
# correct_sign = ret['Y_value_correct']
#
# print(find_consecutive_duplicates(correct_sign))


# 多久算是维持不变，维持不变需要多文档的数值