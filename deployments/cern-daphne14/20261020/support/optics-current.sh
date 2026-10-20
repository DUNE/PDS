set -e
python3 -u - <<'PY'
import subprocess,json,math

def run(a):return subprocess.check_output(a,stderr=subprocess.STDOUT,timeout=4).decode().strip()
def read(addr,offset,n):
 out=b''
 for pos in range(offset,offset+n,16):
  count=min(16,offset+n-pos)
  out+=bytes(int(x,16) for x in run(['i2ctransfer','-y','1','w1@'+hex(addr),hex(pos),'r'+str(count)]).split())
 return out
original=run(['i2cget','-y','1','0x72'])
for name,ch in [('timing',3),('data0',2),('data1',1),('management',5)]:
 result={'port':name,'mux_channel':ch}
 try:
  run(['i2cset','-y','1','0x72',hex(1<<ch)])
  result['mux_readback']=run(['i2cget','-y','1','0x72'])
  v=read(0x50,0,96)
  result.update(identifier=hex(v[0]),vendor=v[20:36].decode(errors='replace').strip(),part=v[40:56].decode(errors='replace').strip(),serial=v[68:84].decode(errors='replace').strip(),diagnostic_flags=hex(v[92]),checksum_base_ok=sum(v[:63])%256==v[63],checksum_extended_ok=sum(v[64:95])%256==v[95])
  if v[92]&0x40:
   d=read(0x51,96,24)
   result.update(rx_los=bool(d[14]&2),tx_fault=bool(d[14]&4),tx_disabled=bool(d[14]&128),diagnostics_hex=d.hex())
   if v[92]&0x20:
    power=int.from_bytes(d[8:10],'big')*.0001
    result.update(rx_power_mW=power,rx_power_dBm=10*math.log10(power) if power else None)
 except Exception as e:result['error']=str(e)
 finally:
  try:
   run(['i2cset','-y','1','0x72',original]);result['mux_restored']=run(['i2cget','-y','1','0x72'])
  except Exception as e:result['restore_error']=str(e)
 print(json.dumps(result),flush=True)
 if 'restore_error' in result:break
print('CLOCK_REGISTER',run(['i2cget','-y','1','0x70','0xe6']),flush=True)
PY
