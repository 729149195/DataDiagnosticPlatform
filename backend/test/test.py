import numpy as np
# import matplotlib.pyplot as plt

def FFTnoise_over_time(x, Fs, window_length=0.1, step=0.1):
    N = int(window_length * Fs) #每个窗囗的采样点数
    step_samples = int(step * Fs) # 步长对应的采样点数
    total_samples = len(x)
    t_list =[]
    Y_list =[]
    max_f_list =[]

    #准备频率数组(对于固定窗口长度，频率数组是相同的)
    f = np.fft.fftfreg(N, d=1/Fs)