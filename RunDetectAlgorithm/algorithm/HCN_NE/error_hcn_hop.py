def func(Y_value_error):
    ret = []
    cur_max = Y_value_error[0]
    cur_min = Y_value_error[24999]
    is_continue = False
    if cur_min - cur_max < -20 and Y_value_error[1] > cur_max:
        ret.append([0, 24999])
        is_continue = True

    for i in range(25000, len(Y_value_error)):
        cur_max = Y_value_error[i-24999]
        cur_min = Y_value_error[i]
        if cur_min - cur_max < -20 and Y_value_error[i-24999+1] > cur_max:
            if is_continue:
                ret[-1][1] = i
            else:
                if len(ret) > 0 and ret[-1][0] < i-24999 < ret[-1][1]:
                    ret[-1][1] = i
                else:
                    ret.append([i-24999, i])
                is_continue = True
        else:
            is_continue = False
    return ret