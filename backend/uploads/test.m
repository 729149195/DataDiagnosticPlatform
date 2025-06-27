function result = test(channel1,channel2)

json_data_1 = channel1;
json_data_2 = channel2;

X_value = json_data_1.X_value;
Y_value = json_data_1.Y_value;


% Prepare JSON output
result_struct.X_value = X_value;
result_struct.Y_value = Y_value;
result = jsonencode(result_struct);

end