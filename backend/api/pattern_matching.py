def match_pattern(normalized_query_pattern, channel_data_list):
    """
    在多个通道数据channel_data_list中查找与查询模式normalized_query_pattern匹配的部分
    Args:
        normalized_query_pattern: 归一化后的查询模式点序列 [(x1, y1), (x2, y2), ...]
        channel_data_list: 通道数据列表，每个元素包含通道信息和数据
        
        ===== 数据格式信息 =====
        normalized_query_pattern 类型: <class 'list'>
        normalized_query_pattern 长度: 不定
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
    results = []
    
    return results 