set -e
hostname
uname -a
cat /etc/os-release
cat /proc/cmdline
python3 - <<'PY'
from pathlib import Path
print('ROOT_MOUNT',[s for s in Path('/proc/mounts').read_text().splitlines() if s.split()[1]=='/'])
print('MGMT_MAC',Path('/sys/class/net/end0/address').read_text().strip())
PY
ip -brief address
systemctl --failed --no-pager
/usr/sbin/daphne-gateware status
/usr/sbin/daphne-gateware list
cat /etc/daphne-board.env
i2cdetect -l
sha256sum /opt/daphne-server/cal2-vst-frame-monitor-20261008/bin/daphneServer /usr/bin/hermes_udp_srv /boot/daphne14-trial-20261020/Image /boot/daphne14-trial-20261020/system.dtb
