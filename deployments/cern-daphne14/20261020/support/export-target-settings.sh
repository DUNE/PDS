set -e
python3 - <<'PY'
from pathlib import Path
import tarfile,hashlib,json
paths=['etc/daphne-board.env','etc/daphne-board-config.json','etc/hostname','etc/systemd/network/10-daphne14.link','etc/systemd/network/10-daphne14.network','etc/systemd/system/daphne-management-optical.service','etc/systemd/system/daphne-boot-ok.service','usr/local/sbin/daphne14-management-optical.sh','var/lib/daphne/os-migration-20261020.json']
out=Path('/tmp/daphne14-settings-20261020.tar.gz')
with tarfile.open(out,'w:gz',dereference=False) as a:
 for name in paths:a.add('/'+name,arcname=name,recursive=False)
print('SETTINGS_SHA256',hashlib.sha256(out.read_bytes()).hexdigest())
PY
