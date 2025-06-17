import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import norm

def func(time_series, time_points):
    """
    检测类高斯曲线的算法

    参数:
    - time_series: 时间序列的幅值数据
    - time_points: 对应的时间点(ns)
    - significance_level: 显著性水平(默认0.05)

    返回:
    - peak_value: 计算的峰值
    - has_gaussian: 是否检测到类高斯曲线
    - fit_params: 高斯拟合参数(如果检测到)
    """
    # 1. 计算0-150ns和250ns-400ns的最大幅值
    time_points = np.array(time_points)
    time_series = np.array(time_series)
    mask = (time_points >= 0) & (time_points <= 4.0)

    cur_time_series = time_series[mask]

    i = 0
    n = len(cur_time_series)
    round = 0
    while i < n:
        if cur_time_series[i] > 2500:
            while i < n and cur_time_series[i] > 2500:
                i += 1
            round += 1
        i += 1

    if round > 1:
        return [[time_points[0], time_points[n-1]]]
    else:
        return []