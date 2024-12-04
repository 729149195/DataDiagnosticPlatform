def filter_range(X_values, Y_values, time_begin, time_end, upper_bound, lower_bound):
    segments = []  # 用于保存符合条件的非连续段
    current_segment = {'X': [], 'Y': []}  # 当前的连续段

    for x, y in zip(X_values, Y_values):
        # 检查该点是否在时间和强度范围内
        if time_begin <= x <= time_end and lower_bound <= y <= upper_bound:
            # 如果在范围内，则添加到当前连续段
            current_segment['X'].append(x)
            current_segment['Y'].append(y)
        else:
            if current_segment['X']:
                segments.append(current_segment)
                current_segment = {'X': [], 'Y': []}  # 开始新的段

    if current_segment['X']:
        segments.append(current_segment)

    return segments

def merge_overlapping_intervals(intervals):
    if not intervals:
        return []
    # 按照 start_X 排序
    intervals.sort(key=lambda x: x['start_X'])
    merged = [intervals[0]]
    for current in intervals[1:]:
        prev = merged[-1]
        if current['start_X'] <= prev['end_X']:
            # 有重叠，合并
            prev['end_X'] = max(prev['end_X'], current['end_X'])
            # 更新相关系数为最大值
            prev['correlation'] = max(prev['correlation'], current['correlation'])
        else:
            merged.append(current)
    return merged