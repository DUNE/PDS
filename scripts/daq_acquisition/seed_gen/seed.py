import json

with open('map.json') as f:
    map = json.load(f)
with open('bias.json') as g:
    bias = json.load(g)
with open('details.json') as h:
    details = json.load(h)

endpoints = [4, 5, 7, 9, 11, 12, 13]
order = [0,2,5,7,1,3,4,6,8, 10, 13, 15, 9, 11, 12, 14, 16, 18, 21, 23, 17, 19, 20, 22]
details = {"details":
           [{"id": i, "value":
             {"self_trigger_threshold": 600 if i>8 else 0,
              "full_stream_channels": sorted(map[f'10.73.137.{100+i}']['id'], key=order.index) if i<8 else [8],
              "channels": {
                  "gains": [{"id": j, "value": 1} for j in map[f'10.73.137.{100+i}']["id"]],
                  "offsets": [{"id": j, "value": 2200} for j in map[f'10.73.137.{100+i}']["id"]],
                  "trims": [{"id": j, "value": 0} for j in map[f'10.73.137.{100+i}']["id"]]},
              "afes": {
                  "v_gains": [{"id": afe, "value": 2318} for afe in range(5)],
                  "v_biases": [{"id": afe, "value": biasv} for afe, biasv in enumerate(bias[f'10.73.137.{100+i}']["bias"])],
                  "adcs": [{"id": afe, "value": {"resolution": False, "output_format": True, "SB_first": False}}for afe in range(5)],
                  "pgas": [{"id": afe, "value": {"lpf_cut_frequnecy": 0, "integrator_disable": False, "gain": True}}for afe in range(5)],
                  "lnas": [{"id": afe, "value": {"clamp": 1, "integrator_disable": False, "gain": 1}}for afe in range(5)]
              }
              }}
            for i in endpoints]}
print(json.dumps(details, sort_keys=True, indent=4))
# Convert and write JSON object to file
with open("seed.json", "w") as outfile:
    json.dump(details, outfile)
