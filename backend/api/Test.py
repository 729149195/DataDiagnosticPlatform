import requests
import threading
import time
import json
import statistics
from concurrent.futures import ThreadPoolExecutor

# 服务器地址
BASE_URL = "http://localhost:8000"  # 修改为实际服务器地址

# 测试配置
NUM_REQUESTS = 100  # 总请求数
CONCURRENT_USERS = [1, 5, 10, 20, 50]  # 并发用户数
TEST_ENDPOINTS = {
    "get_channel_data": "/api/channel_data?channel_key=BO_CD_0087_39382",
    "get_error_data": "/api/error_data?channel_key=BO_CD_0087_39382&channel_type=analog&error_name=surge&error_index=0",
    "operator_strs": "/api/operator_strs"
}

# operator_strs接口的请求体
OPERATOR_PAYLOAD = {
    "anomaly_func_str": "BO_CD_0087_39382",
    "channel_mess": {
        "channel_name": "BO_CD_0087",
        "shot_number": "39382"
    }
}

def send_request(endpoint, payload=None, method="GET"):
    """发送请求并返回响应时间和状态"""
    url = f"{BASE_URL}{endpoint}"
    start_time = time.time()
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        else:
            response = requests.post(url, json=payload, timeout=10)
        elapsed = time.time() - start_time
        return elapsed, response.status_code
    except Exception as e:
        elapsed = time.time() - start_time
        return elapsed, f"Error: {str(e)}"

def test_endpoint(endpoint_name, endpoint, payload=None, method="GET", concurrency=1):
    """测试单个端点的并发性能"""
    results = []
    success_count = 0
    
    def worker():
        nonlocal success_count
        response_time, status = send_request(endpoint, payload, method)
        results.append(response_time)
        if status == 200:
            success_count += 1
        return response_time, status
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker) for _ in range(NUM_REQUESTS)]
        for future in futures:
            future.result()
    
    total_time = time.time() - start_time
    
    # 计算统计数据
    if results:
        avg_response_time = sum(results) / len(results)
        max_response_time = max(results)
        min_response_time = min(results)
        p95_response_time = sorted(results)[int(len(results) * 0.95)]
        success_rate = (success_count / NUM_REQUESTS) * 100
        requests_per_second = NUM_REQUESTS / total_time
    else:
        avg_response_time = max_response_time = min_response_time = p95_response_time = 0
        success_rate = 0
        requests_per_second = 0
    
    return {
        "endpoint": endpoint_name,
        "concurrency": concurrency,
        "total_requests": NUM_REQUESTS,
        "total_time": total_time,
        "avg_response_time": avg_response_time,
        "max_response_time": max_response_time,
        "min_response_time": min_response_time,
        "p95_response_time": p95_response_time,
        "success_rate": success_rate,
        "requests_per_second": requests_per_second
    }

def run_tests():
    """运行所有测试"""
    all_results = []
    
    for concurrency in CONCURRENT_USERS:
        print(f"\n测试并发用户数: {concurrency}")
        
        # 测试 get_channel_data
        print(f"测试 get_channel_data...")
        result = test_endpoint("get_channel_data", 
                              TEST_ENDPOINTS["get_channel_data"], 
                              concurrency=concurrency)
        all_results.append(result)
        print(f"完成: 平均响应时间 {result['avg_response_time']:.3f}s, "
              f"成功率 {result['success_rate']:.1f}%, "
              f"每秒请求 {result['requests_per_second']:.1f}")
        
        # 测试 get_error_data
        print(f"测试 get_error_data...")
        result = test_endpoint("get_error_data", 
                              TEST_ENDPOINTS["get_error_data"], 
                              concurrency=concurrency)
        all_results.append(result)
        print(f"完成: 平均响应时间 {result['avg_response_time']:.3f}s, "
              f"成功率 {result['success_rate']:.1f}%, "
              f"每秒请求 {result['requests_per_second']:.1f}")
        
        # 测试 operator_strs
        print(f"测试 operator_strs...")
        result = test_endpoint("operator_strs", 
                              TEST_ENDPOINTS["operator_strs"], 
                              payload=OPERATOR_PAYLOAD, 
                              method="POST", 
                              concurrency=concurrency)
        all_results.append(result)
        print(f"完成: 平均响应时间 {result['avg_response_time']:.3f}s, "
              f"成功率 {result['success_rate']:.1f}%, "
              f"每秒请求 {result['requests_per_second']:.1f}")
    
    # 保存结果到文件
    with open("performance_test_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    return all_results

if __name__ == "__main__":
    print("开始接口并发性能测试...")
    results = run_tests()
    print("\n测试完成，结果已保存到 performance_test_results.json")