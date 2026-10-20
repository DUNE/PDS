import serial,time,sys
s=serial.Serial();s.port='/dev/serial/by-id/usb-Xilinx_DAPHNEMezz_FNALDMezz04-if01-port0';s.baudrate=115200;s.timeout=.1;s.exclusive=True;s.dtr=False;s.rts=False;s.open()
try:
 data=b'';end=time.monotonic()+100;stop=False;last=0
 while time.monotonic()<end:
  part=s.read(4096)
  if part:
   data+=part;sys.stdout.write(part.decode(errors='replace'));sys.stdout.flush()
  if b'U-Boot ' in data or b'Hit any key to stop autoboot' in data:stop=True
  if stop and time.monotonic()-last>.08:s.write(b' ');last=time.monotonic()
  if b'ZynqMP>' in data or b'ZynqMP >' in data:
   s.write(b'\rprintenv bootcmd boot_targets kernel_addr_r fdt_addr_r ramdisk_addr_r; mmc list\r');time.sleep(.7);sys.stdout.write(s.read(8192).decode(errors='replace'));sys.stdout.flush();print('\nUBOOT_CAUGHT',flush=True);break
 else:raise SystemExit('No U-Boot prompt caught')
finally:s.close()
