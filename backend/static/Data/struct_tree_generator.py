import os
import json
from collections import defaultdict


def generate_json_from_directory(base_directory, output_file):
    result = []
    shot_number_index = defaultdict(list)
    channel_type_index = defaultdict(list)
    channel_name_index = defaultdict(list)
    errors_name_index = defaultdict(list)
    error_origin_index = defaultdict(list)
    idx = 0
    for root, dirs, files in os.walk(base_directory):
        path_parts = root.split(os.sep)
        if len(path_parts) == 3:
            shot_number = path_parts[0][2:]  # First level directory name
            channel_type = path_parts[1]  # Second level directory name
            channel_name = path_parts[2]
            error_name = dirs[0]
            error_root = os.path.join(root, error_name)
            error_files = [f for f in os.listdir(error_root) if os.path.isfile(os.path.join(error_root, f))]
            error_origin = [False, False, True]
            data = {
                "shot_number": shot_number,
                "channel_type": channel_type,
                "channel_name": channel_name,
                "error_name": error_name,
                "error_origin": error_origin
            }
            result.append(data)

            # Update indexes
            shot_number_index[shot_number].append(idx)
            channel_type_index[channel_type].append(idx)
            channel_name_index[channel_name].append(idx)
            errors_name_index[error_name].append(idx)
            true_indices = [i for i in range(len(error_origin)) if error_origin[i] == True]
            false_indices = [i for i in range(len(error_origin)) if error_origin[i] == False]
            if len(true_indices) > 0:
                error_origin_index['true'].append([idx, true_indices])
            if len(false_indices) > 0:
                error_origin_index['false'].append([idx, false_indices])
            idx += 1

    # Write the result data to the output JSON file
    with open(output_file, 'w', encoding='utf-8') as json_file:
        json.dump(result, json_file, ensure_ascii=False)

    # Write index files
    with open('../IndexFile/shot_number_index.json', 'w', encoding='utf-8') as json_file:
        json.dump(shot_number_index, json_file, ensure_ascii=False)
    with open('../IndexFile/channel_type_index.json', 'w', encoding='utf-8') as json_file:
        json.dump(channel_type_index, json_file, ensure_ascii=False)
    with open('../IndexFile/channel_name_index.json', 'w', encoding='utf-8') as json_file:
        json.dump(channel_name_index, json_file, ensure_ascii=False)
    with open('../IndexFile/errors_name_index.json', 'w', encoding='utf-8') as json_file:
        json.dump(errors_name_index, json_file, ensure_ascii=False)
    with open('../IndexFile/error_origin_index.json', 'w', encoding='utf-8') as json_file:
        json.dump(error_origin_index, json_file, ensure_ascii=False)


if __name__ == "__main__":
    base_directory = "./"  # Set the base directory to root
    output_file = "StructTree.json"  # Set the output file to StructTree.json
    generate_json_from_directory(base_directory, output_file)
