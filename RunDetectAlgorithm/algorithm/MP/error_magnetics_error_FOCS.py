import numpy as np

# filename = 'error_magnetics_error_FOCS.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = np.array(ret['X_value'])
# Y_value_error = np.array(ret['Y_value_error'])

def func(signal, threshold=0.05):
    ret = []
    if abs(signal[0]) > threshold:
        ret.append([0, len(signal)-1])
    return ret
    