set -e
python3 - <<'PY'
from pathlib import Path
p=Path('/usr/local/sbin/daphne14-management-sgmii.sh')
s=p.read_text().replace('config | 0x08000000','config & ~0x08000000').replace('32 0x00000001','32 0x00000020').replace('32 0x00000140','32 0x00001340')
p.write_text(s);p.chmod(0o755)
p=Path('/etc/systemd/system/daphne-management-optical.service');p.write_text(p.read_text().replace('DAPHNE14 preserved management SGMII configuration','DAPHNE14 management optical 1000BASE-X configuration'))
PY
systemctl daemon-reload
systemctl restart daphne-management-optical.service
/usr/sbin/daphne-gateware status
uname -a
ip -brief address
cat /etc/os-release
