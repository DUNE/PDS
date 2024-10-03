import json


'''
# Load the original JSON from a file
with open('original_channel_map.json', 'r') as file:
    data = json.load(file)

# Define a function to write JSON with a specific format
def format_json(data, indent=4):
    return json.dumps(data, indent=indent)

# Save the formatted JSON to a new file
with open('output.json', 'w') as file:
    file.write(format_json(data))

# Print the formatted JSON to the console (optional)
print(format_json(data))

'''


# Correlation between endpoint 104 channels (new configuration after 24/09/2024) and original 104, 105, 107 channels (before 24/07/2024)

new_104_channels = { 0: {'endpoint': 104, 'channel': 0},
                    1: {'endpoint': 104, 'channel': 1},
                    2: {'endpoint': 104, 'channel': 2},
                    3: {'endpoint': 104, 'channel': 3},
                    4: {'endpoint': 104, 'channel': 4},
                    5: {'endpoint': 104, 'channel': 5},
                    6: {'endpoint': 104, 'channel': 6},
                    7: {'endpoint': 104, 'channel': 7},#####
                    8: {'endpoint': 105, 'channel': 0},
                    9: {'endpoint': 105, 'channel': 1},
                    10: {'endpoint': 105, 'channel': 2},
                    11: {'endpoint': 105, 'channel': 3},
                    12: {'endpoint': 105, 'channel': 4},
                    13: {'endpoint': 105, 'channel': 5},
                    14: {'endpoint': 105, 'channel': 6},
                    15: {'endpoint': 105, 'channel': 7}, ####
                    16: {'endpoint': 105, 'channel': 8},
                    17: {'endpoint': 107, 'channel': 0},
                    18: {'endpoint': 105, 'channel': 10},
                    19: {'endpoint': 107, 'channel': 2},
                    20: {'endpoint': 107, 'channel': 5},
                    21: {'endpoint': 105, 'channel': 13},
                    22: {'endpoint': 107, 'channel': 7},
                    23: {'endpoint': 105, 'channel': 15}, ###
                    24: {'endpoint': 104, 'channel': 8},
                    25: {'endpoint': 104, 'channel': 9},
                    26: {'endpoint': 104, 'channel': 10},
                    27: {'endpoint': 104, 'channel': 11},
                    28: {'endpoint': 104, 'channel': 12},
                    29: {'endpoint': 104, 'channel': 13},
                    30: {'endpoint': 104, 'channel': 14},
                    31: {'endpoint': 104, 'channel': 15}, ####
                    32: {'endpoint': 105, 'channel': 17},
                    33: {'endpoint': 107, 'channel': 8},
                    34: {'endpoint': 105, 'channel': 19},
                    35: {'endpoint': 107, 'channel': 10},
                    36: {'endpoint': 107, 'channel': 13},
                    37: {'endpoint': 105, 'channel': 20},
                    38: {'endpoint': 107, 'channel': 15},
                    39: {'endpoint': 105, 'channel': 22}
                    }

with open(f'correlation_map_end104.json', "w") as fp:
        json.dump(new_104_channels, fp, indent=4)