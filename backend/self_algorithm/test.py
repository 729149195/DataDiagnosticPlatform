import numpy as np


def evaluate_condition(condition_str, A):
    """
    评估给定条件字符串的布尔值结果。

    参数：
    - condition_str (str): 表示条件的字符串，例如 "A > 5" 或 "max(A) - min(A) <= 5"。
    - A (list or numpy array): 数组数据，用于在条件字符串中替代 "A"。

    返回：
    - bool 或 numpy.array: 条件的评估结果。
    """
    # 将 A 转换为 numpy 数组，确保计算的通用性
    A = np.array(A)

    # 在执行条件字符串前定义上下文，以便可以直接使用 A
    context = {'A': A, 'max': np.max, 'min': np.min, 'np': np}

    try:
        # 使用 eval 函数计算条件表达式
        result = eval(condition_str, {"__builtins__": None}, context)
        if isinstance(result, np.ndarray):
            return np.all(result)
        else:
            return result
    except Exception as e:
        raise ValueError(f"条件表达式无法评估: {e}")


# 示例用法
# if __name__ == "__main__":
#     condition_1 = "A > 4"
#     condition_2 = "max(A)- min(A) <= 5"
#     A = [5, 5, 7, 9]
#
#     print(evaluate_condition(condition_1, A))  # 输出: [False, False, True, True]
#     print(evaluate_condition(condition_2, A))  # 输出: True


import numpy as np

# 示例二维数组
array_2d = np.array([
    [0, 1, 2],
    [2, 1, 0]
])

# 定义映射数组，假设 array_2d 中的每个数值都是 mapping 的有效索引
mapping = np.array([10, 20, 30])

# 使用映射数组对 array_2d 进行映射
mapped_array = mapping[array_2d]

print(mapped_array)
