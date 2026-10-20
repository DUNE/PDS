import serial,time,sys
s=serial.Serial();s.port='/dev/serial/by-id/usb-Xilinx_DAPHNEMezz_FNALDMezz04-if01-port0';s.baudrate=115200;s.timeout=.15;s.exclusive=True;s.dtr=False;s.rts=False;s.open()
try:
 s.write(b'\r');time.sleep(.2);p=s.read(4096);print(p.decode(errors='replace'),flush=True)
 if b'ZynqMP>' not in p:raise SystemExit('Not at verified U-Boot prompt')
 command='mmc dev 0; if load mmc 0:1 0x18000000 /daphne14-trial-20261020/Image; then if load mmc 0:1 0x40000000 /daphne14-trial-20261020/system.dtb; then setenv bootargs earlycon console=ttyPS1,115200 root=/dev/mmcblk0p3 rootwait rw; booti 0x18000000 - 0x40000000; fi; fi'
 s.write(command.encode()+b'\r');end=time.monotonic()+100;data=b''
 while time.monotonic()<end:
  part=s.read(8192)
  if part:data+=part;sys.stdout.write(part.decode(errors='replace'));sys.stdout.flush()
  if b'login:' in data[-200:]:print('\nTRIAL_LOGIN_PROMPT',flush=True);break
 else:print('\nTRIAL_MONITOR_TIMEOUT',flush=True)
finally:s.close()
