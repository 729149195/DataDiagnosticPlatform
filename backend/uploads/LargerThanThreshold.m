function result = LargerThanThreshold(channel_key, threshold)
    % Read JSON data from file based on channel_key
    % Assuming channel_key is the filename
    % 动态生成 URL 和查询参数
    % url = sprintf('https://localhost:5000/api/channel-data/?channel_key=%s', channel_key);
    
    % 设置请求选项
    % options = weboptions('ContentType', 'json');
    
    % 发送 GET 请求
    %json_data = webread(url, options);
    %fprintf('运行时间：%.4f 秒\n', elapsedTime);
    json_data = channel_key

    % Extract X_value and Y_value from the JSON data
    X_value = json_data.X_value;
    Y_value = json_data.Y_value;

    % Find the ranges of X_value where Y_value is greater than the threshold
    above_threshold = abs(Y_value) > threshold;
    ranges = [];
    start_idx = -1;

    for i = 1:length(above_threshold)
        if above_threshold(i) && start_idx == -1
            % Start of a new range
            start_idx = i;
        elseif ~above_threshold(i) && start_idx ~= -1
            % End of the current range
            ranges = [ranges; X_value(start_idx), X_value(i-1)];
            start_idx = -1;
        end
    end

    % If the last value was above threshold, close the range
    if start_idx ~= -1
        ranges = [ranges; X_value(start_idx), X_value(end)];
    end

    % Prepare JSON output
    result_struct.X_range = ranges;
    result = jsonencode(result_struct);
end
