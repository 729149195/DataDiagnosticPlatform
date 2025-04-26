import numpy as np
# filename = 'error_hxr_baseline_shift.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = ret['X_value']
# Y_value_error = np.array(ret['Y_value_error'])

def func(Y_value_error, threshold=0.01):
    avgV = np.average(Y_value_error[:50000])
    is_error = abs(avgV) > threshold
    if is_error:
        return [[0, 50000-1]]
    else:
        return []


# 阈值需要可储存