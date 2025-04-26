

def func(signal, ip):
    ret = []
    ip = ip[::10]
    for i in range(len(signal)):
        if signal[i] == 0 and ip[i] < 1:
            if len(ret) > 0 and ret[-1][0] < i-4 < ret[-1][1]:
                ret[-1][1] = min(i+4, len(signal)-1)
            else:
                ret.append([max(0, i-4), min(i+4, len(signal)-1)])
    return ret