import numpy as np
# filename = 'error_magnetics_drift.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = np.array(ret['X_value'])

def func(Y_value_error):
    Ylen = len(Y_value_error)
    baseYlen = Ylen // 12
    ret = []
    cur_max = np.max(Y_value_error[:baseYlen])
    cur_min = np.min(Y_value_error[:baseYlen])
    is_continue = False
    if cur_max - cur_min > 0.001:
        ret.append([0, baseYlen-1])
        is_continue = True

    for i in range(baseYlen, baseYlen*5):
        cur_max = max(cur_max, Y_value_error[i])
        cur_min = min(cur_min, Y_value_error[i])
        if cur_max - cur_min > 0.001:
            if is_continue:
                ret[-1][1] = i
            else:
                ret.append([i-baseYlen, i])
                is_continue = True
        else:
            is_continue = False
    return ret