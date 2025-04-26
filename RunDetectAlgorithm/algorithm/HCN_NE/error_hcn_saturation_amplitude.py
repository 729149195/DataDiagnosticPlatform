
# ret = utils.data_processing(filename)
#
# print(ret['error_description'])
# print(ret.keys())
#
# error_sign = ret['Y_value_error']

def func(error_sign):
    i = 1
    error = []
    # plt.plot(ret['X_value'], error_sign)
    # plt.show()

    while i < len(error_sign):
        if error_sign[i] == error_sign[i-1]:
            start = i-1
            i += 1
            while i < len(error_sign) and error_sign[i] == error_sign[i-1]:
                i += 1
            if i-start-1 >= 500:
                error.append([start, i-1])
        i += 1
    return error

# error 数据中并没有检测到该异常