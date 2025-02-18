import json

# Load the template
with open('ssp_conf.json') as f: data = json.load(f)
# print(data['modules'][0]['data'].keys()) # general keys here
# Generate 100 JSON files changing the pulse_bias_percent_270nm from 0 to 100
width = data['modules'][0]['data']['pulse1_width_ticks'] 
for variable in ['pulse_bias_percent_270nm']:
    for i in range(100):
        # Change the variable in the data
        data['modules'][0]['data'][variable] = i 
        # Write the modified data to a new file
        with open(f'ssp_conf_width_{width}_{variable}_{i:02}.json', 'w') as f: json.dump(data, f, indent=4)