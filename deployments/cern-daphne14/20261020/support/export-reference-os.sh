set -e
python3 -u - <<'PY'
import tarfile,pathlib,os,hashlib,json
out=pathlib.Path('/tmp/daphne14-reference-os-20261020');out.mkdir(exist_ok=True)
archive=out/'rootfs-reference.tar.gz'
excluded={'etc/shadow','etc/shadow-','etc/gshadow','etc/gshadow-','etc/machine-id','etc/daphne-board-config.json','etc/daphne-board.env','etc/hostname','etc/hosts','var/lib/systemd/random-seed'}
def filt(info):
 n=info.name.lstrip('./')
 if n in excluded or n.startswith(('etc/systemd/network/','etc/systemd/system/daphne-management-optical','etc/ssh/ssh_host_','home/','root/','var/log/','var/cache/','var/lib/dhcp/','var/lib/NetworkManager/')) or '/.ssh/' in '/'+n+'/' or 'krb5cc' in n:return None
 return info
with tarfile.open(archive,'w:gz',dereference=False) as a:
 for name in ['bin','sbin','lib','lib64','usr','etc','opt','var']:
  if pathlib.Path('/'+name).exists() or pathlib.Path('/'+name).is_symlink():a.add('/'+name,arcname=name,filter=filt)
with tarfile.open(out/'boot-reference.tar.gz','w:gz') as a:
 for name in ['Image','system.dtb']:a.add('/boot/'+name,arcname=name)
r={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.is_file() and p.name.endswith('.gz')}
r['provenance']={'kind':'runtime filesystem export; not an immutable build release','source_host':'daphne-004','source_ip':'10.73.137.113','kernel':os.uname().release,'source_boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'excluded':'machine identity, credentials, SSH keys, board/network configuration, mutable logs/cache'}
(out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2),flush=True)
PY
