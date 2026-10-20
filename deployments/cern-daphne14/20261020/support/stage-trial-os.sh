set -e
python3 -u - <<'PY'
import pathlib,tarfile,json,hashlib,shutil,os,subprocess
P=pathlib.Path;r=P('/mnt/d14trial');stage=P('/tmp/d14-reference');manifest=json.loads((stage/'manifest.json').read_text())
assert P('/sys/class/net/eth0/address').read_text().strip()=='ba:be:ba:d1:cb:ff'
assert subprocess.check_output(['findmnt','-n','-o','SOURCE','/mnt/d14trial']).decode().strip()=='/dev/mmcblk0p3'
for name in ['rootfs-reference.tar.gz','boot-reference.tar.gz']:
 f=stage/name;assert hashlib.sha256(f.read_bytes()).hexdigest()==manifest[name]['sha256'],name
print('EXTRACTING_ROOT',flush=True)
with tarfile.open(stage/'rootfs-reference.tar.gz') as a:
 for m in a.getmembers():assert not m.name.startswith('/') and '..' not in P(m.name).parts,m.name
 a.extractall(r,numeric_owner=True)
for name in ['proc','sys','dev','run','tmp','mnt','media','boot','home/petalinux','root']:(r/name).mkdir(parents=True,exist_ok=True)
(r/'tmp').chmod(0o1777);(r/'root').chmod(0o700);os.chown(r/'home/petalinux',1000,1000)
# Preserve this board's credentials locally; do not import another board's hashes/keys.
oldshadow={line.split(':',1)[0]:line for line in P('/etc/shadow').read_text().splitlines()}
users=[line.split(':',1)[0] for line in (r/'etc/passwd').read_text().splitlines()]
(r/'etc/shadow').write_text('\n'.join(oldshadow.get(u,u+':!:0:0:99999:7:::') for u in users)+'\n');(r/'etc/shadow').chmod(0o600)
for f in P('/etc/ssh').glob('ssh_host_*'):shutil.copy2(f,r/'etc/ssh'/f.name)
shutil.copytree('/home/petalinux/.ssh',r/'home/petalinux/.ssh',dirs_exist_ok=True)
for f in (r/'home/petalinux/.ssh').rglob('*'):os.chown(f,1000,1000)
os.chown(r/'home/petalinux/.ssh',1000,1000)
(r/'etc/hostname').write_text('NP04-DAPHNE-014\n');shutil.copy2('/etc/hosts',r/'etc/hosts');(r/'etc/machine-id').write_text('')
(r/'etc/daphne-board.env').write_text('ENDPOINT_ADDR_HEX=0x20\n')
(r/'etc/daphne-board-config.json').write_text(json.dumps({'version':1,'contract':'daphne.board-config','asset':{'asset_id':'NP04-DAPHNE-014'},'network':{'hostname':'NP04-DAPHNE-014','ipv4_address':'10.73.137.160','production_mac':'ba:be:ba:d1:cb:ff','mac_source':'preserved_observed_legacy_runtime','authorized':True},'runtime':{'timing_endpoint':'0x20'},'source':{'note':'Local migration configuration; no SOM UUID or factory MAC claim.'}},indent=2)+'\n')
network=r/'etc/systemd/network';network.mkdir(exist_ok=True)
for f in network.iterdir():
 if f.is_file() or f.is_symlink():f.unlink()
(network/'10-daphne14.link').write_text('[Match]\nPath=platform-ff0b0000.ethernet\n\n[Link]\nName=end0\nMACAddress=ba:be:ba:d1:cb:ff\n')
(network/'10-daphne14.network').write_text('[Match]\nName=end0\n\n[Network]\nAddress=10.73.137.160/24\nGateway=10.73.137.1\nDNS=137.138.16.5\nDNS=137.138.17.5\nDHCP=no\nLinkLocalAddressing=no\nIPv6AcceptRA=no\n')
# Retain this board's observed SGMII mode, rather than M2-004's SX optical override.
helper=r/'usr/local/sbin/daphne14-management-sgmii.sh'
helper.write_text('''#!/bin/sh
set -eu
test "$(cat /sys/class/net/end0/address)" = 'ba:be:ba:d1:cb:ff'
config=$(devmem 0xff0b0004 32)
devmem 0xff0b0004 32 "$(printf '0x%08x' "$((config | 0x08000000))")"
devmem 0xff0b0210 32 0x00000001
devmem 0xff0b0200 32 0x00000140
''');helper.chmod(0o755)
unit=r/'etc/systemd/system/daphne-management-optical.service'
unit.write_text('[Unit]\nDescription=DAPHNE14 preserved management SGMII configuration\nRequires=sys-subsystem-net-devices-end0.device\nAfter=systemd-networkd.service sys-subsystem-net-devices-end0.device\n\n[Service]\nType=oneshot\nExecStart=/usr/local/sbin/daphne14-management-sgmii.sh\nRemainAfterExit=yes\n\n[Install]\nWantedBy=multi-user.target\n')
# Trial migration does not update QSPI slot variables.
mask=r/'etc/systemd/system/daphne-boot-ok.service'
if mask.exists() or mask.is_symlink():mask.unlink()
mask.symlink_to('/dev/null')
boot=P('/boot/daphne14-trial-20261020');boot.mkdir(exist_ok=True)
with tarfile.open(stage/'boot-reference.tar.gz') as a:a.extractall(boot,numeric_owner=True)
# Fail on incompatible binaries before requesting any reboot.
subprocess.run(['chroot',str(r),'/usr/bin/python3','--version'],check=True)
env=dict(os.environ,LD_LIBRARY_PATH='/usr/lib/daphne-server')
subprocess.run(['chroot',str(r),'/opt/daphne-server/cal2-vst-frame-monitor-20261008/bin/daphneServer','--help'],env=env,check=True)
subprocess.run(['chroot',str(r),'/usr/sbin/daphne-gateware','list'],check=True)
(r/'var/lib/daphne').mkdir(parents=True,exist_ok=True)
(r/'var/lib/daphne/os-migration-20261020.json').write_text(json.dumps({'reference':manifest,'target':'NP04-DAPHNE-014','target_root':'/dev/mmcblk0p3','original_root_retained':'/dev/mmcblk0p2','original_boot_images_retained':True,'network_identity_retained':True,'trial_boot':True},indent=2)+'\n')
subprocess.run(['sync'],check=True);print('TRIAL_OS_STAGED',flush=True)
PY
