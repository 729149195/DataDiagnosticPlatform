

def func(data, ecrh_list):# ECRH0_UA
    i = 0
    ret = []
    while i < len(ecrh_list):
        if ecrh_list[i] > 2:
            start = i
            i += 1
            while ecrh_list[i] > 2:
                i += 1
            end = i
            if len(list(filter(lambda d: d<0, data[start:end]))) > 0.9 * (end-start):
                ret.append([start, end-1])
        i += 1
    return ret  # 未找到符合条件的区间

# filename = 'error_axuv_Detector_channel_damage.mat'
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
#
# error_sign = ret['Y_value_error']
# correct_sign = ret['Y_value_correct']
#
# print(detect_drop_with_slope(error_sign))

# 回到零点附近就算结束吗，以为看图中有一段其实不是负值。如果是需要给“零点附近”的判定阈值
#
