function result = LargerThanThreshold(channel_key, threshold)
    % Read JSON data from file based on channel_key
    % Assuming channel_key is the filename
    raw_data = fileread(strcat(channel_key, '.json'));
    json_data = jsondecode(raw_data);

    % Extract X_value and Y_value from the JSON data
    X_value = json_data.X_value;
    Y_value = json_data.Y_value;

    % Replace all Y_value entries with absolute value less than threshold to 0
    Y_value(abs(Y_value) < threshold) = 0;

    % Prepare JSON output
    result_struct.X_value = X_value;
    result_struct.Y_value = Y_value;
    result = jsonencode(result_struct);
end
