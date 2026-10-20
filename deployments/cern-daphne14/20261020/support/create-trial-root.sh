set -e
python3 -u - <<'PY'
import subprocess,json,pathlib
assert pathlib.Path('/sys/class/net/eth0/address').read_text().strip()=='ba:be:ba:d1:cb:ff'
b=pathlib.Path('/var/lib/daphne/deployments/20261020-os-trial');b.mkdir(parents=True,exist_ok=True)
r=json.loads(subprocess.check_output(['sfdisk','--json','/dev/mmcblk0']))['partitiontable']
assert len(r['partitions'])==2,r
assert [(p['start'],p['size']) for p in r['partitions']]==[(8,4194304),(4194312,8388608)],r
assert int(pathlib.Path('/sys/class/block/mmcblk0/size').read_text())==31080448
(b/'partitiontable-before.json').write_text(json.dumps(r,indent=2)+'\n')
(b/'partitiontable-before.sfdisk').write_bytes(subprocess.check_output(['sfdisk','--dump','/dev/mmcblk0']))
with open('/dev/mmcblk0','rb') as f:(b/'mbr-before.bin').write_bytes(f.read(512))
plan='start=12584960, size=16777216, type=83\n'
p=subprocess.run(['sfdisk','--no-reread','--append','/dev/mmcblk0'],input=plan,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);print(p.stdout,flush=True)
r=json.loads(subprocess.check_output(['sfdisk','--json','/dev/mmcblk0']))['partitiontable']
assert len(r['partitions'])==3 and r['partitions'][2]['start']==12584960 and r['partitions'][2]['size']==16777216,r
if not pathlib.Path('/dev/mmcblk0p3').exists():subprocess.run(['partx','-a','-n','3','/dev/mmcblk0'],check=True)
subprocess.run(['mkfs.ext4','-L','d14trialroot','/dev/mmcblk0p3'],check=True)
pathlib.Path('/mnt/d14trial').mkdir(exist_ok=True)
subprocess.run(['mount','/dev/mmcblk0p3','/mnt/d14trial'],check=True)
print('TRIAL_ROOT_READY',flush=True)
PY
