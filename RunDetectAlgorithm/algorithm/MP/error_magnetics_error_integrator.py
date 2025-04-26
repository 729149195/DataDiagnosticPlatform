import numpy as np
# filename = 'error_magnetics_error_integrator.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# X_value = np.array(ret['X_value'])
# Y_value_error = np.array(ret['Y_value_error'])
#
# X_value_special_time = X_value[(X_value <6) & (X_value > -2.5)]
# Y_value_error_special_time = Y_value_error[(X_value <6) & (X_value > -2.5)]
#
#
#
# # plt.plot(X_value_special_time, Y_value_error_special_time)
# # plt.show()
#
# threshold = 0.04
# print(np.sum((Y_value_error_special_time < 8 + threshold) & (Y_value_error_special_time > 8 - threshold)) == len(Y_value_error_special_time))


def func(signal, threshold=0.005):
    signal = np.array(signal)
    special_time = (signal < 6) & (signal > -2.5)
    special_time_signal = signal[special_time]
    ret = []
    d_index = 0
    for i in range(len(special_time_signal)):
        if 8.03-threshold < special_time_signal[i+d_index] < 8.03+threshold:
            start_index = i
            i += 1
            while 8.03-threshold < special_time_signal[i+d_index] < 8.03+threshold:
                i += 1
            ret.append([start_index+d_index, i-1+d_index])
    return ret
