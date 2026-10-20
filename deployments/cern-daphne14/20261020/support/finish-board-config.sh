set -e
python3 - <<'PY'
from pathlib import Path
p=Path('/usr/local/sbin/daphne14-management-sgmii.sh');q=p.with_name('daphne14-management-optical.sh');p.rename(q)
p=Path('/etc/systemd/system/daphne-management-optical.service');p.write_text(p.read_text().replace('daphne14-management-sgmii.sh','daphne14-management-optical.sh'))
Path('/etc/daphne-board.env').write_text('ENDPOINT_ADDR_HEX=0x20\nTIMING_PROFILE=endpoint-sync-v14\nENDPOINT_WAIT_MS=3000\nENDPOINT_SUCCESS_STATES=0x6,0x8\n')
PY
systemctl daemon-reload
sync
