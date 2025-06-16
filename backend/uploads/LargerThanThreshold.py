import numpy as np

def LargerThanThreshold(channel_key, threshold):
    """
    Find ranges of X_value where Y_value is greater than the threshold.
    
    Parameters:
    channel_key (dict): Dictionary containing 'X_value' and 'Y_value' arrays
    threshold (float): Threshold value to compare against
    
    Returns:
    str: JSON string containing the X_value ranges where Y_value > threshold
    """
    # Extract X_value and Y_value from the input data
    X_value = np.array(channel_key['X_value'])
    Y_value = np.array(channel_key['Y_value'])
    
    # Find where Y_value is above threshold
    above_threshold = np.abs(Y_value) > threshold
    ranges = []
    start_idx = -1
    
    for i in range(len(above_threshold)):
        if above_threshold[i] and start_idx == -1:
            # Start of a new range
            start_idx = i
        elif not above_threshold[i] and start_idx != -1:
            # End of the current range
            ranges.append([X_value[start_idx], X_value[i-1]])
            start_idx = -1
    
    # If the last value was above threshold, close the range
    if start_idx != -1:
        ranges.append([X_value[start_idx], X_value[-1]])
    
    # Prepare output
    result_struct = {'X_range': ranges}
    return result_struct