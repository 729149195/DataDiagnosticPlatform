import numpy as np
# filename = 'error_hxr_saturation_counts.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = ret['X_value']
# Y_value_error = np.array(ret['Y_value_correct'])
#
# avgV = np.average(Y_value_error[:50000])
# i = 0
#
# plt.plot(X_value, Y_value_error)
# plt.show()

def func(Y_value_error):
    ranges = []
    i = 0
    minV = abs(np.min(Y_value_error[100000:150000]) * 1.1)
    print(minV)
    while i < len(Y_value_error):
        if Y_value_error[i] < minV:
            start = i
            i += 1
            while i < len(Y_value_error) and Y_value_error[i] < minV:
                i += 1
            if i - start > 1:
                ranges.append([start, i-1])
        i += 1
    return ranges