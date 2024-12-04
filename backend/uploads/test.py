import time

import matlab.engine               # import matlab引擎
# 启动一个新的MATLAB进程，并返回Python的一个变量，它是一个MatlabEngine对象，用于与MATLAB过程进行通信。
start = time.time()
eng = matlab.engine.start_matlab() # 可以调用matlab的内置函数。
d = eng.multiplication_matlab(3,2) # 可以调用matlab写的脚本函数
print('d', d, type(d))
eng.quit()

end = time.time()

print(end - start)
