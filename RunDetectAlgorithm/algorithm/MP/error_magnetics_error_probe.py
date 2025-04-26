import numpy as np

# filename = 'error_magnetics_error_probe.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = np.array(ret['X_value'])
# Y_value_error = np.array(ret['Y_value_error'])
#
# print(np.sum((Y_value_error < 0.012) & (Y_value_error > -0.012)) == len(Y_value_error))

# 附近

def func(signal):
    signal = np.array(signal)
    if np.sum((signal < 0.012) & (signal > -0.012)) == len(signal):
        return [[0, len(signal)-1]]
    else:
        return []