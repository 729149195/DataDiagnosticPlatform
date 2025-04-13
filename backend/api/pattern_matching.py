def match_pattern(normalized_query_pattern, channel_data_list):
    """
    在多个通道数据中查找与查询模式匹配的部分
    Args:
        normalized_query_pattern: 归一化后的查询模式点序列 [(x1, y1), (x2, y2), ...]
        channel_data_list: 通道数据列表，每个元素包含通道信息和数据
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
    # 提取查询模式的Y值
    # 由于x值在归一化后是均匀分布的，我们只需要使用y值进行匹配
    query_y = [y for _, y in normalized_query_pattern]
    
    results = []
    
    # 对每个通道数据进行模式匹配
    for channel_data in channel_data_list:
        if not channel_data or 'X_value' not in channel_data or 'Y_value' not in channel_data:
            continue
            
        x_values = channel_data['X_value']
        y_values = channel_data['Y_value']
        
        # 获取通道信息
        channel_info = {
            'channelName': channel_data.get('channel_name', ''),
            'shotNumber': channel_data.get('shot_number', '')
        }


    
    # 对所有结果按相似度排序
    results.sort(key=lambda x: x['confidence'], reverse=True)
    
    return results 