# 优先将目前的所有异常给对标一下
# 参数类别：
# 通道名： AXUV 需要根据名称去提取数据
# 时段/滑动窗口范围：[-4, 5]
# 条件："Y > 5"
# 滑动窗口大小：“5s”
import json

import numpy as np


def StructTreeFindPath(StructTree, channel_name):
    for channel_type_Data in StructTree:
        for channel_Data in channel_type_Data['channels']:
            if channel_Data['channel_name'] == channel_name:
                return channel_Data['channel']['path']
    return None

def find_true_segments(bool_array):
    # 找出数组中的边界
    # 在 `True` 到 `False` 的转换点插入 `1`，在 `False` 到 `True` 的转换点插入 `-1`
    diffs = np.diff(bool_array.astype(int))
    starts = np.where(diffs == 1)[0] + 1  # 找出开始的索引
    ends = np.where(diffs == -1)[0]  # 找出结束的索引

    # 如果开头就是一个连续的True段
    if bool_array[0] == True:
        starts = np.insert(starts, 0, 0)
    # 如果结尾是一个连续的True段
    if bool_array[-1] == True:
        ends = np.append(ends, len(bool_array)-1)

    # 返回所有连续为 True 的段 (start, end)
    return list(zip(starts, ends))

# a. 通道读取函数
def channel_read(channel_mess):
    # 读 static/Data/StructTree.json
    channel_name = channel_mess['channel_name']
    shot_number = channel_mess['shot_number']
    channel_type = channel_mess['channel_type']
    with open('static/Data/StructTree.json', 'r', encoding='utf-8') as stf:
        StructTree = json.load(stf)
        channel_path = f'static/Data/{shot_number}/{channel_type}/{channel_name}/{channel_name}.json' #StructTreeFindPath(shot_number, channel_type, channel_name)
        print(channel_path)
        if channel_path is None:
            return None
        with open(channel_path, 'r', encoding='utf-8') as cf:
            channel_data = json.load(cf)
            return channel_data


# 可能的 condition
# 1. Y >=< V
# 2. max(Y) - min(Y) >=< V
# 3. .....

def condition_judge(data, condition, mode):
    Y = np.array(data)

    # 在执行条件字符串前定义上下文，以便可以直接使用 A
    context = {'Y': Y, 'max': np.max, 'min': np.min, 'np': np}

    try:
        # 使用 eval 函数计算条件表达式
        result = eval(condition, {"__builtins__": None}, context)
        if isinstance(result, np.ndarray):
            if mode == 'global':
                return [[0, len(Y)-1]] if np.all(result) else []
            else:
                return find_true_segments(result)
        else:
            return result
    except Exception as e:
        raise ValueError(f"条件表达式无法评估: {e}")

def data_convert(data):
    X = data['X_value']
    Y = data['Y_value']
    return X, Y


def period2Index(period, X):
    [l, r] = period
    left_find = right_find = False
    li = 0
    ri = len(X)-1
    for i, v in enumerate(X):
        if l <= v and not left_find:
            li = i
            left_find = True
        if r < v and not right_find:
            ri = i-1
            right_find = True

    return [li, ri]

# 1. 时段条件异常
# 输入：指标名， 时段 和 条件，满足条件的判定为异常
def period_condition_anomaly(channel_name, period, condition, mode, channel_mess):
    data = channel_read(channel_mess)
    X, Y = data_convert(data)
    print(period)
    print('xxx')
    period_index = period2Index(period, X)
    print('xxx')
    period_data = Y[period_index[0]:period_index[1]+1]
    print('xxx')
    anomaly_time_index = condition_judge(period_data, condition, mode)
    anomaly_time = np.array(X[period_index[0]:period_index[1]+1])[anomaly_time_index]
    print('xxx')
    return anomaly_time

# 2. 滑动窗口条件异常
# 输入： 指标名， 滑动窗口范围、大小，条件，满足条件的判定为异常
def window_condition_anomaly(channel_name, window_scope, window_size, condition):
    data = channel_read(channel_name)
    # ..... data to X、Y、unit

    # period_index = period2Index(period)
    window_scope_left = window_scope[0]
    window_scope_right = window_scope[1]
    is_continue = False
    anomaly_time = []
    for i in range(window_scope_left, window_scope_right-window_size+1):
        window_data = data[i:i+window_size+1]
        is_anomaly = condition_judge(window_data, condition)
        if is_anomaly:
            if not is_continue:
                anomaly_time.append([i, i + window_size])
            else:
                anomaly_time[-1][1] += 1
            is_continue = True
        else:
            is_continue = False
    return anomaly_time




# 3. 指标变动类异常
def indicator_changes_anomaly():
    pass

# 4. 特殊形式类
def special_anomaly():
    pass

# 5. FFT类
def FFT_anomaly():
    pass

# 6. 特殊标记类
def special_tag_anomaly():
    pass


