import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import norm


def gaussian(x, a, mu, sigma):
    """高斯函数定义"""
    return a * np.exp(-(x - mu) ** 2 / (2 * sigma ** 2))


def func(time_series, time_points, significance_level=0.05):
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
    mask1 = (time_points >= 0) & (time_points <= 1.5)
    mask2 = (time_points >= 2.5) & (time_points <= 4.0)

    max_val1 = np.max(time_series[mask1])
    max_val2 = np.max(time_series[mask2])

    # 计算峰值 = (max_val1 + max_val2) * 3 + 500
    peak_value = 1000 #max(max_val1, max_val2) #* 3 + 500

    # 2. 检测150ns-250ns是否存在宽度为20ns的类高斯曲线
    mask_middle = (time_points >= 1.5) & (time_points <= 2.5)
    x_data = time_points[mask_middle]
    y_data = time_series[mask_middle]

    if np.max(y_data) < peak_value:
        return [[x_data[0], x_data[-1]]]
    else:
        return []