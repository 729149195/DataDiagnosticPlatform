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


# filename = 'error_hxr_saturation_amplitude.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = ret['X_value']
# Y_value_error = ret['Y_value_error']
# print(find_constant_sequences(Y_value_error))

# 什么叫做维持不变