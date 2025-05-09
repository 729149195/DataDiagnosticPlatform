"""
该模块用于从EXL50U数据库批量读取多通道色散仪（polychromator）原始数据，并按指定分段长度切片，返回五种不同波长的原始数据数组，便于后续数据分析和处理。
"""
import MDSplus # type: ignore
import numpy as np
import sys

def get_data(shot, nperseg=1024, total_polys=15):
    # 建立 MDSplus 数据库连接
    conn = MDSplus.Connection('192.168.20.11') # EXL50 database
    conn.openTree('exl50u', shot)

    # 获取某通道数据用于确定总数据点数
    temp = conn.get('value_of(\\EXL50U::TOP.AI:TS01_1_1064)')
    # print(conn.get(r"\{}".format(temp)).data())
    len_ = len(temp.data())

    # 计算脉冲数，如果数据点数不能整除 nperseg，则退出程序
    if len_ % nperseg == 0:
        pulse = int(len_ / nperseg)
    else:
        print('Errors in slicing raw data')
        sys.exit(1)

    # 初始化存储数组（使用 uint16 数据类型）
    raw_1064 = np.empty((total_polys, len_), dtype=np.uint16)
    raw_1058 = np.empty((total_polys, len_), dtype=np.uint16)
    raw_1046 = np.empty((total_polys, len_), dtype=np.uint16)
    raw_1022 = np.empty((total_polys, len_), dtype=np.uint16)
    raw_0928 = np.empty((total_polys, len_), dtype=np.uint16)

    # 构造各个色散仪（polychromator）的编号
    poly_index = [f"{i:02d}" for i in range(1, total_polys + 1)]

    # 循环读取各色散仪数据
    for i in poly_index:
        c1064 = 'EXL50U::TOP.AI:TS' + i + '_1_1064'
        c1058 = 'EXL50U::TOP.AI:TS' + i + '_5_1058'
        c1046 = 'EXL50U::TOP.AI:TS' + i + '_4_1046'
        c1022 = 'EXL50U::TOP.AI:TS' + i + '_3_1022'
        c0928 = 'EXL50U::TOP.AI:TS' + i + '_2_0928'

        temp = conn.get(r"\{}".format(c1064))
        a = temp.data()
        raw_1064[int(i)-1] = temp.data()

        temp = conn.get(r"\{}".format(c1058))
        raw_1058[int(i)-1] = temp.data()

        temp = conn.get(r"\{}".format(c1046))
        raw_1046[int(i)-1] = temp.data()

        temp = conn.get(r"\{}".format(c1022))
        raw_1022[int(i)-1] = temp.data()

        temp = conn.get(r"\{}".format(c0928))
        raw_0928[int(i)-1] = temp.data()

        # 返回重新调整形状后的数据
        return (
        raw_0928.reshape(total_polys, pulse, nperseg),
        raw_1022.reshape(total_polys, pulse, nperseg),
        raw_1046.reshape(total_polys, pulse, nperseg),
        raw_1058.reshape(total_polys, pulse, nperseg),
        raw_1064.reshape(total_polys, pulse, nperseg))
print(get_data(5550)[0])
