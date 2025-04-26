import numpy as np

def func(value_correct, value_errorbar_correct):
    indices = []
    percent = (value_correct - value_errorbar_correct) / value_correct
    for i in range(len(percent)):
        start = i
        while percent[i] < 0.7:
            i+= 1
        if i != start:
            indices.append([start, i-1])
    return indices


# filename = 'error_cxrs_error_0f_fitting.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# value_correct = ret['Y_value_correct']
# value_errorbar_correct = ret['Y_value_errorbar_correct']
#
# percent = (value_correct - value_errorbar_correct) / value_correct
#
# indices = np.where(percent < 0.7)
#
# print(indices)




# key 并没有统一， CXRS 多了一个key是errorbar_correct， 不再有 error
# percent < 0.7???? 是误差较大吗