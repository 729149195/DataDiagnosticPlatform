import numpy as np
# filename = 'error_magnetics_drift.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = np.array(ret['X_value'])

def func(Y_value_error):
    ret = []
    cur_max = np.max(Y_value_error[:100000])
    cur_min = np.min(Y_value_error[:100000])
    is_continue = False
    if cur_max - cur_min > 0.001:
        ret.append([0, 99999])
        is_continue = True

    for i in range(100000, 500001):
        cur_max = max(cur_max, Y_value_error[i])
        cur_min = min(cur_min, Y_value_error[i])
        if cur_max - cur_min > 0.001:
            if is_continue:
                ret[-1][1] = i
            else:
                ret.append([i-100000, i])
                is_continue = True
        else:
            is_continue = False
    return ret