import serial,time,sys
s=serial.Serial();s.port='/dev/serial/by-id/usb-Xilinx_DAPHNEMezz_FNALDMezz04-if01-port0';s.baudrate=115200;s.timeout=.15;s.exclusive=True;s.dtr=False;s.rts=False;s.open()
def command(c):
 s.write(c.encode()+b'\r');data=b'';end=time.monotonic()+20
 while time.monotonic()<end:
  p=s.read(8192);data+=p
  if p:sys.stdout.write(p.decode(errors='replace'));sys.stdout.flush()
  if data.rstrip().endswith(b'ZynqMP>'):return data
 raise RuntimeError('No U-Boot prompt after '+c)
try:
 assert b'ZynqMP>' in command('')
 result=command('setenv daphne14_legacy_bootcmd \'mmc dev 0; load mmc 0:1 ${kernel_addr_r} Image; load mmc 0:1 ${fdt_addr_r} system.dtb; load mmc 0:1 ${ramdisk_addr_r} ramdisk.cpio.gz.u-boot; setenv bootargs "console=ttyPS0,115200 earlycon"; booti ${kernel_addr_r} ${ramdisk_addr_r} ${fdt_addr_r}\'')
 result=command("setenv daphne14_trial_bootcmd 'mmc dev 0; if load mmc 0:1 0x18000000 /daphne14-trial-20261020/Image; then if load mmc 0:1 0x40000000 /daphne14-trial-20261020/system.dtb; then setenv bootargs earlycon console=ttyPS1,115200 root=/dev/mmcblk0p3 rootwait rw; booti 0x18000000 - 0x40000000; fi; fi'")
 result=command("setenv bootcmd 'run daphne14_trial_bootcmd'")
 result=command('saveenv')
 assert b'OK' in result or b'done' in result.lower(),result
 result=command('printenv bootcmd daphne14_legacy_bootcmd daphne14_trial_bootcmd')
 assert b'bootcmd=run daphne14_trial_bootcmd' in result
 print('SAVED_BOOT_CONFIGURATION',flush=True)
 s.write(b'reset\r');end=time.monotonic()+100;data=b''
 while time.monotonic()<end:
  p=s.read(8192);data+=p
  if p:sys.stdout.write(p.decode(errors='replace'));sys.stdout.flush()
  if b'login:' in data[-200:]:print('PERSISTENT_BOOT_LOGIN',flush=True);break
 else:raise RuntimeError('Persistent boot monitor timeout')
finally:s.close()
