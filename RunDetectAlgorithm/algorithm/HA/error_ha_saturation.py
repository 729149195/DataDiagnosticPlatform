# filename = 'error_ha_saturation.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# error_sign = ret['Y_value_error']
# correct_sign = ret['Y_value_correct']

def func(error_sign):
    error_time = []
    i = 0
    while i < len(error_sign):
        if error_sign[i] > 10:
            # print(error_sign[i])
            start = i
            i += 1
            while i < len(error_sign) and error_sign[i] > 10:
                i += 1
            if i - start > 1:
                error_time.append([start, i-1])
        i += 1
    return error_time
