import numpy as np
# filename = 'error_magnetics_error_acq.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = np.array(ret['X_value'])
# Y_value_error = np.array(ret['Y_value_error'])
#
# print(np.sum((Y_value_error < 10.50) & (Y_value_error > 10.46)) == len(Y_value_error))

def func(signal):
    signal = np.array(signal)
    if np.sum(np.logical_or(signal==10.48, signal == -10.48)) == len(signal):
        return [[0, len(signal)-1]]
    else:
        return []
