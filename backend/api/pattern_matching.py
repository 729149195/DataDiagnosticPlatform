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
    
    # 定义参数常量，对应Qetch项目中的Parameters对象
    PARAMETERS = {
        'DIVIDE_SECTION_MIN_HEIGHT_QUERY': 0.05,
        'DIVIDE_SECTION_MIN_HEIGHT_DATA': 0.05,
        'VALUE_DIFFERENCE_WEIGHT': 0.7,
        'RESCALING_COST_WEIGHT': 0.3,
        'SMOOTH_ITERATIONS_STEPS': 5,
        'SMOOTH_MAXIMUM_ATTEMPTS': 10,
    }
    
    # =====================================================
    # 数据平滑和处理工具函数 (从dataUtilsAPI.js移植)
    # =====================================================
    
    def calculate_tangent(p1, p2, flip_y=False):
        """计算两点间的切线"""
        return (p1[1] - p2[1] if flip_y else p2[1] - p1[1]) / (p2[0] - p1[0]) if p2[0] != p1[0] else 0
    
    def count_sign_variations(data):
        """计算切线符号变化次数"""
        if len(data) < 2:
            return 0
            
        variations = 0
        last_sign = math.copysign(1, calculate_tangent(data[0], data[1]))
        
        for i in range(1, len(data) - 1):
            curr_sign = math.copysign(1, calculate_tangent(data[i], data[i+1]))
            if last_sign != curr_sign and curr_sign != 0:
                variations += 1
            last_sign = curr_sign
        
        return variations
    
    def smooth_data(data, window_size=3, iterations=1):
        """平滑数据点序列"""
        if len(data) < window_size:
            return data
            
        smoothed_data = data.copy()
        for _ in range(iterations):
            padded_data = [(smoothed_data[0][0], smoothed_data[0][1])] * (window_size//2) + smoothed_data + [(smoothed_data[-1][0], smoothed_data[-1][1])] * (window_size//2)
            for i in range(len(smoothed_data)):
                # 移动平均
                window = padded_data[i:i+window_size]
                y_sum = sum(p[1] for p in window)
                smoothed_data[i] = (smoothed_data[i][0], y_sum / len(window))
                
        return smoothed_data
    
    def data_height(data):
        """计算数据点的高度范围"""
        if not data:
            return 0
        min_y = min(p[1] for p in data)
        max_y = max(p[1] for p in data)
        return max_y - min_y
    
    # =====================================================
    # 特征提取函数 (从qetchQueryAPI.js移植)
    # =====================================================
    
    def extract_tangents(points):
        """提取点序列的切线"""
        if len(points) < 2:
            return []
            
        tangents = []
        for i in range(len(points) - 1):
            tangent = calculate_tangent(points[i], points[i+1])
            tangents.append(tangent)
            
        # 复制最后一个切线以保持长度一致
        tangents.append(tangents[-1])
        return tangents
    
    def find_curve_sections(tangents, points, min_height_ratio=0.05):
        """
        将曲线分段
        根据切线的符号变化识别曲线的不同部分
        """
        if len(points) < 2 or len(tangents) < 2:
            return []
            
        sections = []
        section_points = []
        section_tangents = []
        
        current_sign = math.copysign(1, tangents[0]) if tangents[0] != 0 else 0
        section_points.append(points[0])
        section_tangents.append(tangents[0])
        
        # 计算曲线总高度以用于最小高度比例计算
        total_height = data_height(points)
        min_height = total_height * min_height_ratio
        
        for i in range(1, len(points)):
            next_sign = math.copysign(1, tangents[i]) if tangents[i] != 0 else current_sign
            
            # 添加点到当前段
            section_points.append(points[i])
            section_tangents.append(tangents[i])
            
            # 如果符号变化且当前段高度足够，则创建新段
            if next_sign != current_sign and next_sign != 0:
                section_height = data_height(section_points)
                
                if section_height >= min_height:
                    section = {
                        'points': section_points,
                        'tangents': section_tangents,
                        'height': section_height,
                        'next': []
                    }
                    sections.append(section)
                    
                    # 开始新段，但保留交叉点
                    section_points = [points[i]]
                    section_tangents = [tangents[i]]
                
                current_sign = next_sign
        
        # 处理最后一段
        if section_points and len(section_points) > 1:
            section_height = data_height(section_points)
            if section_height >= min_height:
                section = {
                    'points': section_points,
                    'tangents': section_tangents,
                    'height': section_height,
                    'next': []
                }
                sections.append(section)
        
        # 建立段之间的连接关系
        for i in range(len(sections) - 1):
            sections[i]['next'].append({'section': sections[i+1], 'times': 1})
            
        return sections
    
    def normalize_points(points):
        """对点序列进行归一化处理"""
        if not points:
            return []
            
        # 提取x和y值
        x_values = [p[0] for p in points]
        y_values = [p[1] for p in points]
        
        # 计算最小值和范围
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        
        x_range = x_max - x_min
        y_range = y_max - y_min if y_max > y_min else 1.0
        
        # 归一化到[0,1]范围
        normalized = []
        for x, y in points:
            norm_x = (x - x_min) / x_range if x_range else 0
            norm_y = (y - y_min) / y_range if y_range else 0
            normalized.append((norm_x, norm_y))
            
        return normalized
    
    def calculate_points_match(query_sections, data_sections, partial_query=False):
        """计算两组曲线段的匹配度"""
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
            
            # 计算段内点的匹配度
            sum_diff = 0
            num_points = 0
            
            q_points = normalize_points(query_sect['points'])
            d_points = normalize_points(data_sect['points'])
            
            # 插值以确保点的数量匹配
            if len(q_points) != len(d_points):
                # 简单的线性插值
                if len(q_points) > len(d_points):
                    # 对data_points进行插值
                    step = (len(q_points) - 1) / (len(d_points) - 1)
                    new_d_points = []
                    for i in range(len(q_points)):
                        idx = i / step if step > 0 else 0
                        idx_floor = math.floor(idx)
                        idx_ceil = math.ceil(idx)
                        
                        if idx_ceil >= len(d_points):
                            new_d_points.append(d_points[-1])
                        elif idx_floor == idx_ceil:
                            new_d_points.append(d_points[idx_floor])
                        else:
                            weight = idx - idx_floor
                            x = d_points[idx_floor][0] * (1 - weight) + d_points[idx_ceil][0] * weight
                            y = d_points[idx_floor][1] * (1 - weight) + d_points[idx_ceil][1] * weight
                            new_d_points.append((x, y))
                    d_points = new_d_points
                else:
                    # 对query_points进行插值
                    step = (len(d_points) - 1) / (len(q_points) - 1)
                    new_q_points = []
                    for i in range(len(d_points)):
                        idx = i / step if step > 0 else 0
                        idx_floor = math.floor(idx)
                        idx_ceil = math.ceil(idx)
                        
                        if idx_ceil >= len(q_points):
                            new_q_points.append(q_points[-1])
                        elif idx_floor == idx_ceil:
                            new_q_points.append(q_points[idx_floor])
                        else:
                            weight = idx - idx_floor
                            x = q_points[idx_floor][0] * (1 - weight) + q_points[idx_ceil][0] * weight
                            y = q_points[idx_floor][1] * (1 - weight) + q_points[idx_ceil][1] * weight
                            new_q_points.append((x, y))
                    q_points = new_q_points
            
            # 计算点差异
            for i in range(len(q_points)):
                diff = abs(q_points[i][1] - d_points[i][1])
                sum_diff += diff
                num_points += 1
                
                # 添加匹配点到结果
                matched_points.append(data_sect['points'][min(i, len(data_sect['points'])-1)])
            
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
    # 匹配算法主体 (从qetchQueryAPI.js移植)
    # =====================================================
    
    def execute_query(query_pattern, channel_data):
        """执行查询匹配"""
        matches = []
        
        # 从通道数据提取x和y值
        data_x = channel_data['X_value']
        data_y = channel_data['Y_value']
        
        # 确保数据点足够
        if len(data_x) < 2 or len(data_y) < 2:
            return []
            
        # 构建数据点列表
        data_points = [(data_x[i], data_y[i]) for i in range(len(data_x))]
        
        # 对数据进行预处理和平滑
        # 创建多个平滑级别的数据
        smoothed_data_iterations = []
        smoothed_data_iterations.append(data_points)  # 原始数据作为第一个元素
        
        for i in range(PARAMETERS['SMOOTH_MAXIMUM_ATTEMPTS']):
            # 创建新的平滑数据副本
            last_data = smoothed_data_iterations[-1]
            window_size = min(5, max(3, len(last_data) // 100))  # 动态计算窗口大小
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
            
            # 提取查询特征
            query_tangents = extract_tangents(query_pattern)
            query_sections = find_curve_sections(query_tangents, query_pattern, PARAMETERS['DIVIDE_SECTION_MIN_HEIGHT_QUERY'])
            
            # 如果查询段数大于数据段数，则跳过
            if len(query_sections) > len(data_sections):
                continue
                
            # 尝试在所有可能的位置匹配
            for i in range(len(data_sections) - len(query_sections) + 1):
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
                            'smoothIteration': smooth_iteration,
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
    # 主函数逻辑
    # =====================================================
    
    results = []
    
    # 处理每个通道数据
    for channel_data in channel_data_list:
        channel_matches = execute_query(normalized_query_pattern, channel_data)
        
        # 获取通道信息
        channel_name = channel_data.get('channel_name', '')
        shot_number = channel_data.get('shot_number', 0)
        
        # 处理匹配结果
        if channel_matches:
            # 只保留最好的几个匹配（比如前3个）
            channel_matches.sort(key=lambda m: m['match'])
            best_matches = channel_matches[:3]
            
            # 将匹配范围转换为所需格式
            for match in best_matches:
                # 使用指数衰减函数将任意范围的匹配成本转换为0-1之间的置信度
                # 匹配成本越小，置信度越高
                match_value = match['match']
                confidence = math.exp(-match_value)  # 使用指数衰减，确保永远在0-1之间
                
                # 创建匹配范围
                match_range = [[match['minPos'], match['maxPos']]]
                
                # 添加到结果
                results.append({
                    'range': match_range,
                    'channelName': channel_name,
                    'shotNumber': shot_number,
                    'confidence': confidence
                })
    
    # 按置信度排序
    results.sort(key=lambda r: r['confidence'], reverse=True)
    
    return results 