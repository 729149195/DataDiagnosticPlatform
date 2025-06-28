def match_pattern(
    normalized_query_pattern, channel_data_list,
    lowpass_amplitude=None,
    x_filter_range=None,
    y_filter_range=None,
    pattern_repeat_count=None,
    max_match_per_channel=None,
    amplitude_limit_range=None,  # 新增：指标幅度区间限制
    time_span_limit_range=None   # 新增：时间跨度区间限制
):
    """
    在多个通道数据channel_data_list中查找与查询模式normalized_query_pattern匹配的部分
    Args:
        normalized_query_pattern: 归一化后的查询模式点序列 [(x1, y1), (x2, y2), ...]
        channel_data_list: 通道数据列表，每个元素包含通道信息和数据
        lowpass_amplitude: 低通滤波幅度（0.0001~0.1），过滤该幅度内的扰动
        x_filter_range: X过滤区间（默认"ALL"）
        y_filter_range: Y过滤区间（默认"ALL"）
        pattern_repeat_count: 模式重复数量（默认0），所需要匹配的手绘模式的连续重复数量
        max_match_per_channel: 单通道获取匹配最大数量（默认100）
        amplitude_limit_range: 匹配区间Y值幅度区间限制 [min, max]（新增）
        time_span_limit_range: 匹配区间X值跨度区间限制 [min, max]（新增）
        
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
    
    # ========== 新增：查询模式重复 ==========
    repeat_count = pattern_repeat_count if pattern_repeat_count and pattern_repeat_count > 0 else 1
    if repeat_count > 1:
        pattern = normalized_query_pattern
        if len(pattern) < 2:
            pass  # 点数太少无法重复
        else:
            x_offset = pattern[-1][0] - pattern[0][0]
            repeated = []
            for i in range(repeat_count):
                for pt in pattern:
                    repeated.append((pt[0] + i * x_offset, pt[1]))
            normalized_query_pattern = repeated
    
    # 定义Qetch算法参数，完全匹配原始JavaScript实现
    Parameters = {
        'DEBUG': False,  # 是否开启调试模式，输出调试信息
        'MAX_REGEX_IT': 25,  # 正则匹配最大递归深度，防止死循环
        'GROUPING_EQUAL_MATCH_TOLERANCE': 10,  # 匹配去重时允许的起止点误差
        
        'VALUE_DIFFERENCE_WEIGHT': 0.9,  # 点差异权重，控制点差异对总分的影响
        'RESCALING_COST_WEIGHT': 0.1,  # 缩放成本权重，控制缩放因子对总分的影响
        'RESCALING_Y': True,  # 是否对y轴进行缩放（True为y轴独立缩放，False为跟随x轴）
        
        'QUERYLENGTH_SLIDING_WINDOW_STEP': 1,  # 滑动窗口步长，单位为查询长度的百分比
        
        'START_END_CUT_IN_SUBPARTS': True,  # 是否对首尾段进行子段切分以提升拟合
        'START_END_CUT_IN_SUBPARTS_IN_RESULTS': True,  # 匹配结果中是否对子段进行切分
        
        'DIVIDE_SECTION_MIN_HEIGHT_DATA': 0.01,  # 数据分段的最小高度比例，防止噪声产生过多段
        'DIVIDE_SECTION_MIN_HEIGHT_QUERY': 0.01,  # 查询分段的最小高度比例
        
        'QUERY_SIGN_MAXIMUM_TOLERABLE_DIFFERENT_SIGN_SECTIONS': 0.5,  # 匹配时允许的最大符号不一致段比例
        'MATCH_METRIC_MAXIMUM_VALUE': 100,  # 匹配分数最大阈值，超过则视为不匹配
        'CHECK_QUERY_COMPATIBILITY': True,  # 是否检查段兼容性（符号、数量等）
        'REMOVE_EQUAL_MATCHES': False  # 是否去除重复匹配（起止点相近的只保留最优）
    }
    
    # =====================================================
    # Qetch点、切线和段的数据结构
    # =====================================================
    
    class Point:
        """与Qetch.Point完全对应的Python实现"""
        def __init__(self, x, y, origX=None, origY=None):
            self.x = x
            self.y = y
            self.origX = origX if origX is not None else x
            self.origY = origY if origY is not None else y
            
        def copy(self):
            return Point(self.x, self.y, self.origX, self.origY)
            
        def translate_x_copy(self, offset_x, offset_orig_x):
            return Point(
                self.x + offset_x,
                self.y,
                self.origX + offset_orig_x,
                self.origY
            )
            
        def __str__(self):
            return f"({self.x},{self.y})"
    
    class Section:
        """与Qetch.Section完全对应的Python实现"""
        def __init__(self, sign):
            self.points = []  # 段中的点数组
            self.tangents = []  # 段中包含的切线数组
            self.sign = sign  # 段的符号 1, -1 或 0
            self.next = []  # 之后的段数组（在重复情况下，下一个可能是前一个）
            self.id = None
            
        def concat(self, section):
            """将另一个段的所有点添加到当前段"""
            for i in range(len(section.points)):
                self.points.append(section.points[i])
                self.tangents.append(section.tangents[i])
                
        def translate_x_copy(self, offset_x, offset_orig_x):
            """创建偏移副本"""
            ns = Section(self.sign)
            ns.tangents = self.tangents
            ns.next = None
            ns.id = self.id
            for i in range(len(self.points)):
                ns.points.append(self.points[i].translate_x_copy(offset_x, offset_orig_x))
            return ns
            
        def copy(self):
            """创建副本"""
            ns = Section(self.sign)
            ns.tangents = self.tangents
            ns.next = None
            ns.id = self.id
            for i in range(len(self.points)):
                ns.points.append(self.points[i].copy())
            return ns
            
        def size(self):
            """获取段的宽度"""
            return self.points[-1].x - self.points[0].x
            
        def size_eucl(self):
            """获取段的欧氏尺寸"""
            return math.sqrt(
                math.pow(self.points[-1].x - self.points[0].x, 2) + 
                math.pow(self.points[-1].y - self.points[0].y, 2)
            )
    
    # =====================================================
    # Qetch核心算法实现
    # =====================================================
    
    def tangent(p1, p2):
        """计算两点间的切线斜率"""
        if p2.x == p1.x:
            return 0  # 避免除以零
        return (p2.y - p1.y) / (p2.x - p1.x)
    
    def extract_tangents(points):
        """提取点序列的切线 - 与原始Qetch一致"""
        if len(points) < 2:
            return []
            
        tangents = [tangent(points[0], points[1])]
        for i in range(1, len(points)):
            tangents.append(tangent(points[i-1], points[i]))
            
        return tangents
    
    def find_curve_sections(tangents, points, min_height_perc):
        """将曲线分段 - 与原始Qetch一致"""
        if len(points) < 2:
            return []
            
        # 计算曲线总高度
        min_y = min(p.y for p in points)
        max_y = max(p.y for p in points)
        total_height = max_y - min_y
        min_height = total_height * min_height_perc
        
        sections = []
        last_tg = None
        last_pt = None
        
        for i, tg in enumerate(tangents):
            sign = 1 if tg > 0 else (-1 if tg < 0 else 0)
            pt = points[i]
            
            if len(sections) == 0:
                # 创建第一个段
                sections.append(Section(sign))
            elif sign != 0:
                last_sect = sections[-1]
                if last_sect.sign != sign:
                    # 符号变化，考虑结束当前段
                    last_sect_height = max(p.y for p in last_sect.points) - min(p.y for p in last_sect.points)
                    if len(last_sect.points) > 1 and (min_height_perc <= 0 or last_sect_height / total_height > min_height_perc):
                        # 创建新段
                        new_section = Section(sign)
                        sections.append(new_section)
                        new_section.points.append(last_pt)
                        new_section.tangents.append(last_tg)
                        
            # 添加当前点和切线到当前段
            last_sect = sections[-1]
            last_sect.points.append(pt)
            last_sect.tangents.append(tg)
            last_tg = tg
            last_pt = pt
        
        # 为每个段分配ID并建立连接关系
        count = 0
        prev = None
        for s in sections:
            s.id = count
            count += 1
            if prev is not None:
                prev.next.append({"dest": s, "times": 1})
            prev = s
        
        if prev is not None:
            prev.next = []
            
        return sections
    
    def are_compatible_sections(query_sections, data_sections, check_length=True):
        """检查查询段与数据段的兼容性"""
        if len(query_sections) != len(data_sections):
            return False
            
        incompatible_sections = 0
        for i in range(len(query_sections)):
            if query_sections[i].sign != 0 and query_sections[i].sign != data_sections[i].sign:
                incompatible_sections += 1
                
        return (incompatible_sections / len(query_sections) <= 
                Parameters['QUERY_SIGN_MAXIMUM_TOLERABLE_DIFFERENT_SIGN_SECTIONS'])
    
    def get_bounds(sections, start_idx, end_idx):
        """获取段集合的边界"""
        if sections is None:
            return None
            
        bounds = {
            'minX': float('inf'), 'maxX': float('-inf'),
            'minY': float('inf'), 'maxY': float('-inf')
        }
        
        bounds['minX'] = sections[start_idx].points[0].x
        bounds['maxX'] = sections[end_idx].points[-1].x
        
        for i in range(start_idx, end_idx+1):
            local_min_y = min(p.y for p in sections[i].points)
            local_max_y = max(p.y for p in sections[i].points)
            
            if local_min_y < bounds['minY']:
                bounds['minY'] = local_min_y
            if local_max_y > bounds['maxY']:
                bounds['maxY'] = local_max_y
                
        return bounds
    
    def reduce_sections(sections, n):
        """减少段数量到n，与原始Qetch一致"""
        if n >= len(sections) or n < 1:
            return sections
            
        new_sections = []
        for i in range(len(sections)):
            new_sections.append(sections[i].copy())
            
        while n < len(new_sections):
            # 找出最小段
            smallest_section = None
            section_size_avg = 0
            
            for i in range(len(new_sections)):
                section_size_avg += new_sections[i].size_eucl()
                if smallest_section is None or new_sections[smallest_section].size_eucl() > new_sections[i].size_eucl():
                    smallest_section = i
                    
            section_size_avg /= len(new_sections)
            if new_sections[smallest_section].size_eucl() > section_size_avg * 0.8:
                return None
                
            # 合并最小段
            if smallest_section == 0:
                new_sections[smallest_section].concat(new_sections[1])
                new_sections.pop(1)
            elif smallest_section == len(new_sections) - 1:
                new_sections[len(new_sections) - 2].concat(new_sections[len(new_sections) - 1])
                new_sections.pop(len(new_sections) - 1)
            elif new_sections[smallest_section - 1].size_eucl() <= new_sections[smallest_section + 1].size_eucl():
                new_sections[smallest_section - 1].concat(new_sections[smallest_section])
                new_sections.pop(smallest_section)
            else:
                new_sections[smallest_section].concat(new_sections[smallest_section + 1])
                new_sections.pop(smallest_section + 1)
                
        return new_sections
    
    def expand_sections(sections, n):
        """增加段数量到n，与原始Qetch一致"""
        if n <= len(sections):
            return sections
            
        new_sections = []
        for i in range(len(sections) - 1):
            new_sections.append(sections[i].copy())
            
        for i in range(len(sections), n+1):
            new_sections.append(sections[len(sections) - 1].copy())
            
        return new_sections
    
    def calculate_points_match(query_sections, matched_sections, partial_query=False):
        """计算点匹配度 - 与原始Qetch一致"""
        reduced = False
        expanded = False
        
        # 检查兼容性或调整段数
        if Parameters['CHECK_QUERY_COMPATIBILITY']:
            if not are_compatible_sections(query_sections, matched_sections, not partial_query):
                return None
        else:
            if len(query_sections) > len(matched_sections):
                matched_sections = expand_sections(matched_sections, len(query_sections))
                expanded = True
            elif len(query_sections) < len(matched_sections):
                matched_sections = reduce_sections(matched_sections, len(query_sections))
                reduced = True
                
            if matched_sections is None:
                return None
                
            if not are_compatible_sections(query_sections, matched_sections, not partial_query):
                return None
                
        # 计算边界和缩放因子
        matched_sec_bounds = get_bounds(
            matched_sections,
            (1 if len(matched_sections) > 2 else 0),
            len(matched_sections) - (2 if len(matched_sections) > 2 else 1)
        )
        
        query_bounds = get_bounds(
            query_sections,
            (1 if len(query_sections) > 2 else 0),
            len(query_sections) - (2 if len(query_sections) > 2 else 1)
        )
        
        sub_sequence_scale_factor_x = (matched_sec_bounds['maxX'] - matched_sec_bounds['minX']) / (query_bounds['maxX'] - query_bounds['minX'])
        sub_sequence_scale_factor_y = (matched_sec_bounds['maxY'] - matched_sec_bounds['minY']) / (query_bounds['maxY'] - query_bounds['minY'])
        
        debug_lines = []
        point_differences_cost = 0
        rescaling_cost = 0
        matched_points = []
        errors = []
        
        # 对每个段计算差异
        for si in range(len(query_sections)):
            data_sect = {}
            query_sect = {}
            res = {'sum': 0, 'num': 0}
            
            # 获取查询段信息
            query_sect['points'] = query_sections[si].points
            query_sect['width'] = query_sect['points'][-1].x - query_sect['points'][0].x
            query_sect['height'] = max(p.y for p in query_sect['points']) - min(p.y for p in query_sect['points'])
            
            if query_sect['height'] == 0:
                continue
                
            # 获取数据段信息
            if si == 0 and len(query_sections) > 2 and Parameters['START_END_CUT_IN_SUBPARTS']:
                data_sect['points'] = section_end_subpart_points(
                    matched_sections[si], 
                    query_sect['width'] * sub_sequence_scale_factor_x
                )
            elif si == len(query_sections) - 1 and len(query_sections) > 2 and Parameters['START_END_CUT_IN_SUBPARTS_IN_RESULTS']:
                data_sect['points'] = section_start_subpart_points(
                    matched_sections[si], 
                    query_sect['width'] * sub_sequence_scale_factor_x
                )
            else:
                data_sect['points'] = matched_sections[si].points
                
            data_sect['width'] = data_sect['points'][-1].x - data_sect['points'][0].x
            data_sect['height'] = max(p.y for p in data_sect['points']) - min(p.y for p in data_sect['points'])
            
            if data_sect['height'] == 0:
                continue
                
            # 计算缩放因子
            scale_factor_x = data_sect['width'] / (query_sect['width'] * sub_sequence_scale_factor_x)
            if Parameters['RESCALING_Y']:
                scale_factor_y = data_sect['height'] / (query_sect['height'] * sub_sequence_scale_factor_y)
            else:
                scale_factor_y = data_sect['height'] / (query_sect['height'] * sub_sequence_scale_factor_x)
                
            # 计算缩放成本 - 添加防御性检查
            if scale_factor_x > 0 and scale_factor_y > 0:  # 确保值大于0
                rescaling_cost += math.pow(math.log(scale_factor_x), 2) + math.pow(math.log(scale_factor_y), 2)
            else:
                # 使用安全的默认值，比如1（log(1)=0）避免错误
                safe_x = max(scale_factor_x, 1e-10) if scale_factor_x != 0 else 1e-10
                safe_y = max(scale_factor_y, 1e-10) if scale_factor_y != 0 else 1e-10
                rescaling_cost += math.pow(math.log(safe_x), 2) + math.pow(math.log(safe_y), 2)
                
            if Parameters['DEBUG'] and not partial_query:
                errors.append({'cx': math.pow(math.log(scale_factor_x), 2), 'cy': math.pow(math.log(scale_factor_y), 2)})
                
            # 计算质心对齐
            data_sect['centroid_y'] = sum(p.y for p in data_sect['points']) / len(data_sect['points'])
            
            query_sect['centroid_y'] = 0
            scale_y = (sub_sequence_scale_factor_y if Parameters['RESCALING_Y'] else sub_sequence_scale_factor_x) * scale_factor_y
            
            for i in range(len(query_sect['points'])):
                query_sect['centroid_y'] += query_sect['points'][i].y * scale_y
                
            query_sect['centroid_y'] /= len(query_sect['points'])
            centroid_difference = query_sect['centroid_y'] - data_sect['centroid_y']
            
            # 将第一个点对齐
            centroid_difference = query_sect['points'][0].y * scale_y - data_sect['points'][0].y
            
            # 采样点比较
            query_pts_step = len(query_sect['points']) / len(data_sect['points'])
            
            # 计算点距离差异
            for i in range(len(data_sect['points'])):
                data_pt = data_sect['points'][i]
                query_idx = min(int(i * query_pts_step), len(query_sect['points'])-1)
                query_pt = query_sect['points'][query_idx]
                
                if Parameters['DEBUG'] and not partial_query:
                    debug_lines.append({
                        'x1': data_pt.x,
                        'y1': query_pt.y * scale_y - centroid_difference,
                        'x2': data_pt.x,
                        'y2': data_pt.y
                    })
                    
                # 确保差值和高度为正值
                normalized_diff = abs((query_pt.y * scale_y - centroid_difference) - data_pt.y)
                safe_height = max(data_sect['height'], 1e-10)  # 避免除以零
                res['sum'] += normalized_diff / safe_height
                res['num'] += 1
                
            # 收集匹配点
            if not partial_query:
                if Parameters['START_END_CUT_IN_SUBPARTS_IN_RESULTS']:
                    matched_points.extend(data_sect['points'])
                else:
                    matched_points.extend(matched_sections[si].points)
                    
            # 添加到点差异成本
            if res['num'] > 0:
                point_differences_cost += res['sum'] / res['num']
                
        # 计算最终匹配度
        return {
            'match': point_differences_cost * Parameters['VALUE_DIFFERENCE_WEIGHT'] + rescaling_cost * Parameters['RESCALING_COST_WEIGHT'],
            'matchedPoints': matched_points,
            'debugLines': debug_lines,
            'errors': errors,
            'reduced': reduced,
            'expanded': expanded
        }
    
    def section_start_subpart_points(section, width):
        """获取段开始部分的子部分点"""
        start_x = section.points[0].x
        points = []
        
        for pi in range(len(section.points)):
            points.append(section.points[pi])
            if section.points[pi].x - start_x >= width:
                break
                
        return points
    
    def section_end_subpart_points(section, width):
        """获取段结束部分的子部分点"""
        end_x = section.points[-1].x
        points = []
        
        for pi in range(len(section.points) - 1, -1, -1):
            points.insert(0, section.points[pi])
            if end_x - section.points[pi].x >= width:
                break
                
        return points
    
    def search_equal_match(target_match, matches):
        """查找与目标匹配起止位置相同的匹配，返回索引，未找到返回-1"""
        target_start_x = target_match['points'][0].x
        target_end_x = target_match['points'][-1].x
        
        for idx in range(len(matches)):
            if (abs(target_start_x - matches[idx]['points'][0].x) <= 10 and
                abs(target_end_x - matches[idx]['points'][-1].x) <= 10):
                return idx
                
        return -1
    
    def calculate_match_time_span(start_point, end_point):
        """计算匹配的时间跨度"""
        value = end_point.origX - start_point.origX
        
        # 为时间跨度创建字符串表示
        if value < 1000:
            str_val = f"{round(value)} ms"
        elif value < (1000 * 60):
            str_val = f"{(value / 1000):.3f} s"
        elif value < (1000 * 3600):
            str_val = f"{(value / (1000 * 60)):.3f} min"
        elif value < (1000 * 3600 * 24):
            str_val = f"{round(value / (1000 * 3600))} hrs"
        elif value < (1000 * 3600 * 24 * 365):
            str_val = f"{round(value / (1000 * 3600 * 24))} days"
        else:
            str_val = f"{((value / (1000 * 3600 * 24 * 365)) * 100) / 100:.1f} years"
            
        return {'value': value, 'str': str_val}
    
    def execute_query(query_pattern, channel_data):
        """执行查询匹配 - 遵循原始Qetch算法逻辑"""
        # 处理查询模式
        query_points = [Point(p[0], p[1], p[0], p[1]) for p in query_pattern]
        query_tangents = extract_tangents(query_points)
        query_sections = find_curve_sections(
            query_tangents, 
            query_points, 
            Parameters['DIVIDE_SECTION_MIN_HEIGHT_QUERY']
        )
        
        # 未能创建有效的查询段
        if not query_sections:
            return []
            
        # 准备数据集
        matches = []
        datasets_num = 1  # 每个通道视为一个数据集
        
        for dataset_idx in range(datasets_num):
            # 获取数据值
            x_values = channel_data.get('X_value', [])
            y_values = channel_data.get('Y_normalized', channel_data.get('Y_value', []))
            
            if not x_values or not y_values:
                continue
                
            # 创建数据点
            data_points = []
            for i in range(len(x_values)):
                # 创建点 (x, y, origX, origY)
                data_points.append(Point(i, y_values[i], x_values[i], y_values[i]))
                
            # 数据集大小
            dataset_size = data_points[-1].x - data_points[0].x
            
            # 提取切线和段
            data_tangents = extract_tangents(data_points)
            data_sections = find_curve_sections(
                data_tangents, 
                data_points, 
                Parameters['DIVIDE_SECTION_MIN_HEIGHT_DATA']
            )
            
            # 匹配处理
            for dsi in range(len(data_sections)):
                # 重置查询段状态
                for i in range(len(query_sections)):
                    for j in range(len(query_sections[i].next)):
                        query_sections[i].next[j]['times'] = 1
                        
                # 执行匹配
                match_in(query_sections[0], data_sections, dsi, [], {
                    'matches': matches,
                    'snum': dataset_idx,
                    'smoothIteration': lowpass_amplitude,
                    'datasetSize': dataset_size,
                    'dataPoints': data_points,
                    'shotNumber': channel_data.get('shot_number', 0),
                    'channelName': channel_data.get('channel_name', '')
                }, query_sections[-1])
        
        return matches
    
    def match_in(curr_sect, data_sections, dsi, q_sections, query_ctx, last_query_sect):
        """递归匹配段序列 - 与原始Qetch一致"""
        if len(q_sections) > Parameters['MAX_REGEX_IT']:
            return False
            
        match_value = None
        sects_block = [curr_sect]
        
        # 将查询转换为段数组（甚至在没有重复时）
        # 直到只有一个下一个元素
        while len(curr_sect.next) == 1 and curr_sect != last_query_sect:
            curr_sect = curr_sect.next[0]['dest']
            sects_block.append(curr_sect)
            
        if dsi + len(sects_block) + len(q_sections) > len(data_sections):
            return False  # 下一组对于剩余的数据段太长
            
        # 处理重复的新段
        if len(q_sections) > 0:
            last_q_sections_sect_pt = q_sections[-1].points[-1]
            first_sects_block_pt = sects_block[0].points[0]
            
            if first_sects_block_pt.x < last_q_sections_sect_pt.x:
                offset = -first_sects_block_pt.x + last_q_sections_sect_pt.x
                offset_o = -first_sects_block_pt.origX + last_q_sections_sect_pt.origX
                
                for i in range(len(sects_block)):
                    sects_block[i] = sects_block[i].translate_x_copy(offset, offset_o)
                    
        new_q_sections = q_sections + sects_block
        data_sects_for_q = data_sections[dsi:dsi + len(new_q_sections)]
        
        # 如果我们到达了查询的末尾，我们可以实际使用它
        if (curr_sect == last_query_sect and
            (len(curr_sect.next) == 0 or not curr_sect.next[0].get('size', False) or 
             curr_sect.next[0].get('size', 0) == curr_sect.next[0].get('times', 0))):
            
            match_value = calculate_match(data_sects_for_q, new_q_sections, query_ctx, False)
            
            if match_value is not None:
                # 如果在不同的平滑迭代中选择了相同的区域，则仅保留一个（最佳）匹配
                duplicate_match_idx = search_equal_match(match_value, query_ctx['matches']) if Parameters['REMOVE_EQUAL_MATCHES'] else -1
                
                if duplicate_match_idx == -1:
                    match_value['id'] = len(query_ctx['matches'])  # 为新匹配创建新的id
                    query_ctx['matches'].append(match_value)
                elif query_ctx['matches'][duplicate_match_idx]['match'] > match_value['match']:
                    match_value['id'] = query_ctx['matches'][duplicate_match_idx]['id']  # 保留旧id
                    query_ctx['matches'][duplicate_match_idx] = match_value
                    
        # 处理下一个段
        if len(curr_sect.next) >= 1:
            back_link = False
            
            # 迭代重复和之后的直接链接
            for i in range(len(curr_sect.next) - 1, -1, -1):
                next_item = curr_sect.next[i]
                
                if curr_sect == last_query_sect or i > 0:  # 是一个回链
                    if not next_item.get('size', False):
                        match_in(next_item['dest'], data_sections, dsi, new_q_sections, query_ctx, last_query_sect)
                    elif next_item.get('times', 0) < next_item.get('size', 0):
                        next_item['times'] += 1
                        back_link = True  # 只有在有严格重复时才排除直接链接
                        match_in(next_item['dest'], data_sections, dsi, new_q_sections, query_ctx, last_query_sect)
                elif not back_link:
                    match_in(next_item['dest'], data_sections, dsi, new_q_sections, query_ctx, last_query_sect)
                    
        return True
    
    def calculate_match(matched_sections, query_sections, query_ctx, partial_query):
        """计算匹配度 - 与原始Qetch一致"""
        points_match_res = calculate_points_match(query_sections, matched_sections, partial_query)
        
        if points_match_res is None:
            return None
            
        if points_match_res['match'] > Parameters['MATCH_METRIC_MAXIMUM_VALUE']:
            return None
            
        if partial_query:
            return {'match': points_match_res['match']}
            
        matched_pts = points_match_res['matchedPoints']
        min_pos = matched_pts[0].x
        max_pos = matched_pts[-1].x
        match_size = (max_pos - min_pos) / query_ctx['datasetSize']
        match_pos = ((max_pos + min_pos) / 2) / query_ctx['datasetSize']
        match_time_span = calculate_match_time_span(matched_pts[0], matched_pts[-1])
        
        return {
            'snum': query_ctx['snum'],
            'smoothIteration': query_ctx['smoothIteration'],
            'match': points_match_res['match'],
            'size': match_size,
            'matchPos': match_pos,
            'timespan': match_time_span,
            'points': matched_pts,
            'minPos': min_pos,
            'maxPos': max_pos,
            'sections': matched_sections,
            'debugLines': points_match_res['debugLines'],
            'errors': points_match_res['errors'],
            'channelName': query_ctx['channelName'],
            'shotNumber': query_ctx['shotNumber']
        }
    
    def fast_savitzky_golay_smooth(x_arr, y_arr, width, passes=2):
        """
        对输入的x_arr和y_arr进行Savitzky-Golay平滑，width为窗口宽度，passes为平滑次数。
        """
        def lower_bound(arr, value):
            left, right = 0, len(arr)
            while left < right:
                mid = (left + right) // 2
                if arr[mid] < value:
                    left = mid + 1
                else:
                    right = mid
            return left

        def upper_bound(arr, value):
            left, right = 0, len(arr)
            while left < right:
                mid = (left + right) // 2
                if arr[mid] <= value:
                    left = mid + 1
                else:
                    right = mid
            return left

        def adaptive_poly_order(window_point_count, total_point_count):
            ratio = window_point_count / total_point_count
            if ratio < 0.05:
                return 2
            elif ratio < 0.1:
                return 3
            elif ratio < 0.2:
                return 4
            else:
                return 5

        def dynamic_max_points(y_win, min_points=100, max_points=2000):
        # 如果窗口为空或方差不可用，返回最小点数
            if len(y_win) == 0:
                return min_points
            var = np.var(y_win)
            if not np.isfinite(var):
                return min_points
            max_var = 1.0  # 可根据实际数据调整
            norm_var = min(var / max_var, 1.0)
            return int(min_points + (max_points - min_points) * norm_var)


        # 定义单次平滑内部函数，消除细微相移与切线振动
        def _single_pass(x_arr_in, y_arr_in):
            result = []
            total_count = len(x_arr_in)
            for i in range(total_count):
                x0 = x_arr_in[i]
                left = lower_bound(x_arr_in, x0 - width / 2)
                right = upper_bound(x_arr_in, x0 + width / 2)
                x_win = [x - x0 for x in x_arr_in[left:right]]
                y_win = y_arr_in[left:right]
                cur_max = dynamic_max_points(y_win)
                if len(x_win) > cur_max:
                    step = int(np.ceil(len(x_win) / cur_max))
                    x_win = x_win[::step]
                    y_win = y_win[::step]
                poly = adaptive_poly_order(len(x_win), total_count)
                if len(x_win) < poly + 1:
                    result.append([float(x_arr_in[i]), float(y_arr_in[i])])
                    continue
                X = np.vander(x_win, poly + 1, increasing=True)
                a = np.linalg.solve(X.T @ X, X.T @ y_win)
                result.append([float(x_arr_in[i]), float(a[0])])
            return np.array([d[0] for d in result]), np.array([d[1] for d in result])

        # 前向平滑
        x_forward, y_forward = np.array(x_arr), np.array(y_arr)
        for _ in range(passes):
            x_forward, y_forward = _single_pass(x_forward, y_forward)
        # 反向平滑
        x_back, y_back = x_forward[::-1], y_forward[::-1]
        for _ in range(passes):
            x_back, y_back = _single_pass(x_back, y_back)
        # 返回零相位零切线振动结果
        return [[float(x), float(y)] for x, y in zip(x_back[::-1], y_back[::-1])]
    
    def process_channel(channel_data):
        """处理单个通道数据"""
        # 如果需要平滑，先对Y数据进行平滑处理
        x_arr = channel_data.get('X_value', None)
        y_arr = channel_data.get('Y_normalized', channel_data.get('Y_value', None))
        if x_arr is not None and y_arr is not None and lowpass_amplitude is not None:
            window_width = lowpass_amplitude * 0.4
            # 保证输入为numpy数组
            x_np = np.array(x_arr)
            y_np = np.array(y_arr)
            # 排序，保证x单调递增
            sort_idx = np.argsort(x_np)
            x_sorted = x_np[sort_idx]
            y_sorted = y_np[sort_idx]
            smooth_result = fast_savitzky_golay_smooth(x_sorted, y_sorted, window_width, passes=2)
            # 只取y平滑结果，x与原始一致
            y_smooth = [pt[1] for pt in smooth_result]
            channel_data['Y_normalized'] = y_smooth
        # 调用查询执行
        channel_matches = execute_query(normalized_query_pattern, channel_data)
        if not channel_matches:
            return []

        channel_name = channel_data.get('channel_name', '')
        shot_number = channel_data.get('shot_number', 0)
        results = []
        for match in sorted(channel_matches, key=lambda m: m['match']):
            confidence = math.exp(-match['match'])
            orig_min_pos = match['points'][0].origX
            orig_max_pos = match['points'][-1].origX
            match_range = [[orig_min_pos, orig_max_pos]]
            # 计算指标幅度和时间跨度
            y_vals = [pt.origY if hasattr(pt, 'origY') else pt.get('origY', None) for pt in match['points']]
            y_vals = [y for y in y_vals if y is not None]
            amplitude = max(y_vals) - min(y_vals) if y_vals else None
            time_span = orig_max_pos - orig_min_pos
            results.append({
                'range': match_range,
                'channelName': channel_name,
                'shotNumber': shot_number,
                'confidence': confidence,
                'smoothLevel': match['smoothIteration'],
                'points': match['points'],  # 保留points用于y过滤
                'amplitude': amplitude,     # 新增：指标幅度
                'timeSpan': time_span       # 新增：时间跨度
            })

        # ========== 新增：X/Y过滤 ==========
        # x_filter_range/y_filter_range 形如 [min, max]，可能为 None
        def in_x_range(result):
            if not x_filter_range or x_filter_range[0] is None or x_filter_range[1] is None:
                return True
            r_min, r_max = result['range'][0]
            f_min, f_max = x_filter_range
            return not (r_max < f_min or r_min > f_max)

        def in_y_range(result):
            if not y_filter_range or y_filter_range[0] is None or y_filter_range[1] is None:
                return True
            f_min, f_max = y_filter_range
            # points 里只要有一个y在区间内就保留
            for pt in result['points']:
                y = getattr(pt, 'origY', None)
                if y is None and isinstance(pt, dict):
                    y = pt.get('origY', None)
                if y is not None and f_min <= y <= f_max:
                    return True
            return False

        results = [r for r in results if in_x_range(r) and in_y_range(r)]

        # ========== 新增：指标幅度和时间跨度区间过滤 ==========
        if amplitude_limit_range is not None and len(amplitude_limit_range) == 2:
            min_amp, max_amp = amplitude_limit_range
            if min_amp is not None and max_amp is not None:
                if min_amp == max_amp:
                    # 当起始值和结束值相同时，作为绝对定值处理（小于等于该值）
                    results = [r for r in results if r['amplitude'] is not None and r['amplitude'] <= min_amp]
                else:
                    # 区间过滤
                    results = [r for r in results if r['amplitude'] is not None and min_amp <= r['amplitude'] <= max_amp]
            elif min_amp is not None:
                # 只有最小值
                results = [r for r in results if r['amplitude'] is not None and r['amplitude'] >= min_amp]
            elif max_amp is not None:
                # 只有最大值
                results = [r for r in results if r['amplitude'] is not None and r['amplitude'] <= max_amp]
        
        if time_span_limit_range is not None and len(time_span_limit_range) == 2:
            min_time, max_time = time_span_limit_range
            if min_time is not None and max_time is not None:
                if min_time == max_time:
                    # 当起始值和结束值相同时，作为绝对定值处理（小于等于该值）
                    results = [r for r in results if r['timeSpan'] is not None and r['timeSpan'] <= min_time]
                else:
                    # 区间过滤
                    results = [r for r in results if r['timeSpan'] is not None and min_time <= r['timeSpan'] <= max_time]
            elif min_time is not None:
                # 只有最小值
                results = [r for r in results if r['timeSpan'] is not None and r['timeSpan'] >= min_time]
            elif max_time is not None:
                # 只有最大值
                results = [r for r in results if r['timeSpan'] is not None and r['timeSpan'] <= max_time]

        # ========== 数量过滤 ==========
        if max_match_per_channel is not None:
            results = results[:max_match_per_channel]

        # 去掉points字段，防止前端报错
        for r in results:
            r.pop('points', None)

        return results
    
    # =====================================================
    # 主函数逻辑
    # =====================================================
    
    # 处理所有通道
    results = []
    for channel_data in channel_data_list:
        results.extend(process_channel(channel_data))
    # 按置信度排序
    results.sort(key=lambda r: r['confidence'], reverse=True)
    
    return results 