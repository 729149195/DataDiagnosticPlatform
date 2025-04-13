def match_pattern(normalized_query_pattern, channel_data_list):
    """
    在多个通道数据channel_data_list中查找与查询模式normalized_query_pattern匹配的部分
    Args:
        normalized_query_pattern: 归一化后的查询模式点序列 [(x1, y1), (x2, y2), ...]
        channel_data_list: 通道数据列表，每个元素包含通道信息和数据
        
        ===== 数据格式信息 =====
        normalized_query_pattern 类型: <class 'list'>
        normalized_query_pattern 长度: 不定（数据量一般几十到上百）
        normalized_query_pattern 示例元素类型: <class 'tuple'>
        normalized_query_pattern 结构: 点序列 [(x1, y1), (x2, y2), ...]
        channel_data_list 类型: <class 'list'>
        channel_data_list 长度: 不定
        channel_data_list 元素类型: <class 'dict'>
        channel_data_list 结构示例:
        元素包含的键: ['channel_number', 'X_value', 'Y_value', 'X_unit', 'Y_unit', 'is_downsampled', 'is_upsampled', 'points', 'originalFrequency', 'stats', 'is_digital', 'Y_normalized', 'channel_name', 'shot_number']
        其中X_value和Y_value是列表, 列表中每个元素是float, 数据量根据采样率的不同从几万到几百万不等
        ========================
        
    Returns:
        匹配结果列表，每个元素包含通道信息、匹配范围和相似度
        格式为：
        [
            { // 每个通道对应的匹配到的结果
                range: range, //匹配到的原始X值范围(归一化前，可能有多段[[x1,x2],[x3,x4],...])
                channelName: channelName, //通道名称
                shotNumber: shotNumber, //炮号
                confidence: confidence, //该相似度
            },
            ......
        ]
    """
    import math
    import numpy as np
    from collections import defaultdict
    import concurrent.futures
    
    # 定义参数常量
    PARAMETERS = {
        'DIVIDE_SECTION_MIN_HEIGHT_QUERY': 0.05,
        'DIVIDE_SECTION_MIN_HEIGHT_DATA': 0.05,
        'VALUE_DIFFERENCE_WEIGHT': 0.7,
        'RESCALING_COST_WEIGHT': 0.3,
        'SMOOTH_ITERATIONS_STEPS': 5,
        'SMOOTH_MAXIMUM_ATTEMPTS': 5,  # 减少平滑迭代次数以提高速度
        'MAX_WINDOW_SIZE': 5,          # 限制窗口大小
        'SAMPLING_RATIO': 0.1,         # 对大数据集进行降采样的比率
        'MIN_SAMPLES': 1000,           # 最小采样点数
        'MAX_SAMPLES': 10000,          # 最大采样点数
    }
    
    # =====================================================
    # 数据平滑和处理工具函数 - 优化版本
    # =====================================================
    
    def calculate_tangent(p1, p2, flip_y=False):
        """计算两点间的切线 - 向量化版本"""
        if isinstance(p1, np.ndarray) and isinstance(p2, np.ndarray):
            dx = p2[:, 0] - p1[:, 0]
            dy = p2[:, 1] - p1[:, 1] if not flip_y else p1[:, 1] - p2[:, 1]
            # 避免除以零
            dx[dx == 0] = 1e-10
            return dy / dx
        else:
            return (p1[1] - p2[1] if flip_y else p2[1] - p1[1]) / (p2[0] - p1[0]) if p2[0] != p1[0] else 0
    
    def count_sign_variations(data):
        """计算切线符号变化次数 - 优化版本"""
        if len(data) < 2:
            return 0
            
        # 使用numpy进行向量化计算
        points = np.array(data)
        # 计算连续点之间的切线
        x_diff = points[1:, 0] - points[:-1, 0]
        y_diff = points[1:, 1] - points[:-1, 1]
        # 避免除以零
        x_diff[x_diff == 0] = 1e-10
        tangents = y_diff / x_diff
        # 计算符号
        signs = np.sign(tangents)
        # 计算符号变化
        sign_changes = np.diff(signs) != 0
        # 移除零交叉点
        non_zero_changes = sign_changes & (signs[1:] != 0)
        
        return np.sum(non_zero_changes)
    
    def smooth_data(data, window_size=3, iterations=1):
        """平滑数据点序列 - 优化版本，使用卷积核实现"""
        if len(data) < window_size or window_size < 2:
            return data
            
        # 转换为numpy数组以加速计算
        points = np.array(data)
        x_vals = points[:, 0].copy()  # 保持x值不变
        y_vals = points[:, 1].copy()
        
        # 创建卷积核
        kernel = np.ones(window_size) / window_size
        
        for _ in range(iterations):
            # 添加头尾填充
            pad_size = window_size // 2
            padded_y = np.pad(y_vals, (pad_size, pad_size), mode='edge')
            
            # 使用卷积进行平滑
            # 不使用完整的numpy.convolve以避免边缘效应
            for i in range(len(y_vals)):
                y_vals[i] = np.sum(padded_y[i:i+window_size] * kernel)
        
        # 重建点列表
        return [(x_vals[i], y_vals[i]) for i in range(len(x_vals))]
    
    def data_height(data):
        """计算数据点的高度范围 - 优化版本"""
        if not data:
            return 0
        # 使用numpy函数加速
        points = np.array(data)
        return np.max(points[:, 1]) - np.min(points[:, 1])
    
    def extract_tangents(points):
        """提取点序列的切线 - 优化版本"""
        if len(points) < 2:
            return []
            
        # 使用numpy进行向量化计算
        pts = np.array(points)
        
        # 计算相邻点之间的切线
        x_diff = pts[1:, 0] - pts[:-1, 0]
        y_diff = pts[1:, 1] - pts[:-1, 1]
        
        # 避免除以零
        x_diff[x_diff == 0] = 1e-10
        
        tangents = y_diff / x_diff
        # 复制最后一个切线以保持长度一致
        tangents = np.append(tangents, tangents[-1])
        
        return tangents.tolist()
    
    def find_curve_sections(tangents, points, min_height_ratio=0.05):
        """将曲线分段 - 优化版本"""
        if len(points) < 2 or len(tangents) < 2:
            return []
            
        # 转换为numpy数组
        if not isinstance(tangents, np.ndarray):
            tangents = np.array(tangents)
        
        # 找出符号变化点
        signs = np.sign(tangents)
        sign_changes = np.where(np.diff(signs) != 0)[0]
        
        # 计算曲线总高度以用于最小高度比例计算
        total_height = data_height(points)
        min_height = total_height * min_height_ratio
        
        sections = []
        start_idx = 0
        
        # 遍历符号变化点
        for idx in sign_changes:
            if idx + 1 >= len(points):
                continue
                
            # 检查这段的高度是否足够
            segment_points = points[start_idx:idx+2]  # 包含当前变化点
            segment_height = data_height(segment_points)
            
            if segment_height >= min_height:
                section = {
                    'points': segment_points,
                    'tangents': tangents[start_idx:idx+2].tolist(),
                    'height': segment_height,
                    'next': []
                }
                sections.append(section)
                start_idx = idx + 1
        
        # 处理最后一段
        if start_idx < len(points) - 1:
            segment_points = points[start_idx:]
            segment_height = data_height(segment_points)
            
            if segment_height >= min_height:
                section = {
                    'points': segment_points,
                    'tangents': tangents[start_idx:].tolist(),
                    'height': segment_height,
                    'next': []
                }
                sections.append(section)
        
        # 建立段之间的连接关系
        for i in range(len(sections) - 1):
            sections[i]['next'].append({'section': sections[i+1], 'times': 1})
            
        return sections
    
    def normalize_points(points):
        """对点序列进行归一化处理 - 优化版本"""
        if not points:
            return []
            
        # 转换为numpy数组
        pts = np.array(points)
        
        # 计算最小值和范围
        x_min, x_max = np.min(pts[:, 0]), np.max(pts[:, 0])
        y_min, y_max = np.min(pts[:, 1]), np.max(pts[:, 1])
        
        x_range = x_max - x_min
        y_range = y_max - y_min if y_max > y_min else 1.0
        
        # 归一化到[0,1]范围
        normalized = pts.copy()
        normalized[:, 0] = (pts[:, 0] - x_min) / x_range if x_range else 0
        normalized[:, 1] = (pts[:, 1] - y_min) / y_range if y_range else 0
        
        return normalized.tolist()
    
    def downsample_data(data, target_size):
        """降采样数据点以提高处理速度"""
        if len(data) <= target_size:
            return data
            
        # 选择采样点（均匀分布）
        indices = np.linspace(0, len(data)-1, target_size, dtype=int)
        return [data[i] for i in indices]
    
    def calculate_points_match(query_sections, data_sections, partial_query=False):
        """计算两组曲线段的匹配度 - 优化版本"""
        if not query_sections or not data_sections:
            return None
            
        matched_points = []
        point_differences_cost = 0
        rescaling_cost = 0
        
        # 对每个段进行匹配
        for si in range(min(len(query_sections), len(data_sections))):
            query_sect = query_sections[si]
            data_sect = data_sections[si]
            
            # 计算缩放比例
            query_height = data_height(query_sect['points'])
            data_height_val = data_height(data_sect['points'])
            
            height_ratio = data_height_val / query_height if query_height > 0 else 1
            
            # 使用插值匹配点数
            q_points = normalize_points(query_sect['points'])
            d_points = normalize_points(data_sect['points'])
            
            # 确保两边点数匹配（使用线性插值）
            if len(q_points) != len(d_points):
                if len(q_points) > len(d_points):
                    # 对data_points进行插值
                    d_points_np = np.array(d_points)
                    q_points_np = np.array(q_points)
                    
                    # 创建插值函数
                    x_old = np.linspace(0, 1, len(d_points))
                    x_new = np.linspace(0, 1, len(q_points))
                    
                    # 对y值进行插值
                    y_interpolated = np.interp(x_new, x_old, d_points_np[:, 1])
                    
                    # 创建新的点集
                    d_points = [(x_new[i], y_interpolated[i]) for i in range(len(x_new))]
                else:
                    # 对query_points进行插值
                    d_points_np = np.array(d_points)
                    q_points_np = np.array(q_points)
                    
                    # 创建插值函数
                    x_old = np.linspace(0, 1, len(q_points))
                    x_new = np.linspace(0, 1, len(d_points))
                    
                    # 对y值进行插值
                    y_interpolated = np.interp(x_new, x_old, q_points_np[:, 1])
                    
                    # 创建新的点集
                    q_points = [(x_new[i], y_interpolated[i]) for i in range(len(x_new))]
            
            # 计算点差异（向量化方式）
            q_arr = np.array(q_points)
            d_arr = np.array(d_points)
            
            # L1距离(曼哈顿距离)
            diffs = np.abs(q_arr[:, 1] - d_arr[:, 1])
            sum_diff = np.sum(diffs)
            num_points = len(diffs)
                
            # 添加匹配点到结果
            matched_points.extend(data_sect['points'])
            
            # 汇总这个段的匹配结果
            if num_points > 0:
                point_differences_cost += sum_diff / num_points
                
            # 计算缩放成本
            rescaling_cost += abs(1 - height_ratio) if height_ratio > 1 else abs(1 - 1/height_ratio)
        
        # 最终匹配成本 = 点差异成本*权重 + 缩放成本*权重
        match_cost = (point_differences_cost * PARAMETERS['VALUE_DIFFERENCE_WEIGHT'] + 
                     rescaling_cost * PARAMETERS['RESCALING_COST_WEIGHT'])
        
        return {
            'match': match_cost,
            'matchedPoints': matched_points
        }
    
    # =====================================================
    # 匹配算法主体 - 优化版本
    # =====================================================
    
    def execute_query(query_pattern, channel_data):
        """执行查询匹配 - 优化版本"""
        matches = []
        
        # 从通道数据提取x和y值
        data_x = channel_data['X_value']
        data_y = channel_data['Y_value']
        
        # 确保数据点足够
        if len(data_x) < 2 or len(data_y) < 2:
            return []
            
        # 构建数据点列表
        data_points = list(zip(data_x, data_y))
        
        # 对大数据集进行降采样提高性能
        target_size = max(PARAMETERS['MIN_SAMPLES'], 
                          min(PARAMETERS['MAX_SAMPLES'], 
                              int(len(data_points) * PARAMETERS['SAMPLING_RATIO'])))
                              
        data_points = downsample_data(data_points, target_size)
        
        # 提取查询特征 - 只需计算一次
        query_tangents = extract_tangents(query_pattern)
        query_sections = find_curve_sections(query_tangents, query_pattern, PARAMETERS['DIVIDE_SECTION_MIN_HEIGHT_QUERY'])
        
        # 对数据进行预处理和平滑
        # 创建多个平滑级别的数据
        smoothed_data_iterations = []
        smoothed_data_iterations.append(data_points)  # 原始数据作为第一个元素
        
        for i in range(PARAMETERS['SMOOTH_MAXIMUM_ATTEMPTS']):
            # 创建新的平滑数据副本
            last_data = smoothed_data_iterations[-1]
            window_size = min(PARAMETERS['MAX_WINDOW_SIZE'], max(3, len(last_data) // 200))  # 动态计算窗口大小
            smoothed = smooth_data(last_data, window_size, i+1)
            
            # 如果平滑后的符号变化不再显著减少，则停止
            if count_sign_variations(smoothed) >= count_sign_variations(last_data) * 0.9:
                break
                
            smoothed_data_iterations.append(smoothed)
        
        # 对每个平滑级别执行匹配
        for smooth_iteration, current_smooth_data in enumerate(smoothed_data_iterations):
            # 提取特征
            data_tangents = extract_tangents(current_smooth_data)
            data_sections = find_curve_sections(data_tangents, current_smooth_data, PARAMETERS['DIVIDE_SECTION_MIN_HEIGHT_DATA'])
            
            # 如果查询段数大于数据段数，则跳过
            if len(query_sections) > len(data_sections):
                continue
                
            # 优化：如果段太多，可以先评估段的相似性来过滤明显不匹配的位置
            valid_starting_positions = []
            
            # 尝试在所有可能的位置匹配
            for i in range(len(data_sections) - len(query_sections) + 1):
                # 快速检查：先比较第一段的高度比例，如果差异太大，直接跳过
                first_query_height = data_height(query_sections[0]['points'])
                first_data_height = data_height(data_sections[i]['points'])
                
                height_ratio = first_data_height / first_query_height if first_query_height > 0 else 1
                if height_ratio > 3 or height_ratio < 0.33:  # 快速过滤
                    continue
                
                valid_starting_positions.append(i)
            
            # 仅在有效的起始位置进行完整匹配
            for i in valid_starting_positions:
                potential_match_sections = data_sections[i:i+len(query_sections)]
                
                # 计算匹配度
                match_result = calculate_points_match(query_sections, potential_match_sections)
                
                if match_result:
                    # 提取匹配点的范围
                    matched_points = match_result['matchedPoints']
                    if matched_points:
                        min_x = matched_points[0][0]
                        max_x = matched_points[-1][0]
                        
                        # 创建匹配结果
                        match = {
                            'snum': channel_data.get('shot_number', 0),
                            'smoothIteration': smooth_iteration,  # 保存平滑迭代级别
                            'match': match_result['match'],  # 较低的值表示更好的匹配
                            'points': matched_points,
                            'minPos': min_x,
                            'maxPos': max_x
                        }
                        
                        # 如果是更好的匹配，则添加到结果
                        duplicate_idx = next((i for i, m in enumerate(matches) 
                                            if abs(m['minPos'] - match['minPos']) <= 10 and 
                                               abs(m['maxPos'] - match['maxPos']) <= 10), -1)
                                               
                        if duplicate_idx == -1:
                            match['id'] = len(matches)
                            matches.append(match)
                        elif matches[duplicate_idx]['match'] > match['match']:
                            match['id'] = len(matches)
                            matches.append(match)
                            match['id'] = matches[duplicate_idx]['id']
                            matches[duplicate_idx] = match
        
        return matches
    
    # =====================================================
    # 多通道并行处理
    # =====================================================
    
    def process_channel(channel_data):
        """处理单个通道数据"""
        channel_matches = execute_query(normalized_query_pattern, channel_data)
        
        if not channel_matches:
            return []
            
        # 获取通道信息
        channel_name = channel_data.get('channel_name', '')
        shot_number = channel_data.get('shot_number', 0)
        
        # 只保留最好的几个匹配（比如前3个）
        channel_matches.sort(key=lambda m: m['match'])
        best_matches = channel_matches[:3]
        
        results = []
        # 将匹配范围转换为所需格式
        for match in best_matches:
            # 使用指数衰减函数计算置信度
            match_value = match['match']
            confidence = math.exp(-match_value)
            
            # 创建匹配范围
            match_range = [[match['minPos'], match['maxPos']]]
            
            # 添加到结果
            results.append({
                'range': match_range,
                'channelName': channel_name,
                'shotNumber': shot_number,
                'confidence': confidence,
                'smoothLevel': match['smoothIteration']  # 添加平滑度级别信息
            })
            
        return results
    
    # =====================================================
    # 主函数逻辑
    # =====================================================
    
    # 优化：使用并行处理多个通道
    results = []
    
    # 避免创建太多线程，最多8个并行
    num_workers = min(8, len(channel_data_list))
    
    if num_workers > 1:
        # 使用线程池并行处理通道数据
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            channel_results = list(executor.map(process_channel, channel_data_list))
            
            # 合并结果
            for result_list in channel_results:
                results.extend(result_list)
    else:
        # 串行处理
        for channel_data in channel_data_list:
            results.extend(process_channel(channel_data))
    
    # 按置信度排序
    results.sort(key=lambda r: r['confidence'], reverse=True)
    
    return results 