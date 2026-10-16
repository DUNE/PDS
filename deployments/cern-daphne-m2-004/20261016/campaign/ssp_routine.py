"""Campaign SSP register-control exercise; optical coupling is explicitly absent."""
import time
from ssp_led_control import SSPClient,LEDRunConfig,configure_run,stop_run,PDTS_STATUS
from pds.calibration.timing import TimingSource
class SSPRoutine:
 def __init__(self):
  self.client=None;self.lease=None
  self.timing=TimingSource({'master':'BOREAS_TLU_NP04','connections':'/nfs/sw/dunedaq/timing/connections.xml','generator':1,'command_id':7,'rate_hz':6000},600)
 def connect(self):
  if self.client is None:
   self.client=SSPClient('10.73.137.61',55002,8)
   self.lease=self.timing.reserve();self.lease.__enter__()
   self.timing.preflight()
  return self.client
 def telemetry(self):
  c=self.connect();s=c.read(PDTS_STATUS)
  return {'pdts_status':hex(s),'endpoint_state':s&15,'timestamp_ready':bool(s&0x1000),'command7_count':c.read(0x8000091c),'clock_control':hex(c.read(0x80000520)),'master_logic_control':hex(c.read(0x80000500))}
 def __call__(self,settings):
  c=self.connect();previous_stop=self.timing.stop();before=self.telemetry()
  assert before['endpoint_state']==8 and before['timestamp_ready'],'SSP timing endpoint not ready'
  cfg=LEDRunConfig(number_channels=12,channel_mask=settings['led_channel_mask'],pulse_mode='single',burst_count=settings.get('led_burst_count',1),double_pulse_delay_ticks=settings.get('led_double_pulse_delay_ticks',0),pulse1_width_ticks=settings['led_width_ticks'],pulse2_width_ticks=settings.get('led_second_width_ticks',0),pulse_bias_percent_270nm=settings['led_bias_270nm'],pulse_bias_percent_367nm=settings['led_bias_367nm'])
  configure_run(c,cfg)
  bias=[];timing=[]
  for i in range(12):
   expected_bias=0;expected_timing=0
   if cfg.channel_mask&(1<<i):
    expected_bias=0x40000+(cfg.pulse_bias_percent_270nm if i<6 else cfg.pulse_bias_percent_367nm//2)
    expected_timing=0xf0000000+cfg.pulse1_width_ticks+(cfg.pulse2_width_ticks<<8)+(cfg.double_pulse_delay_ticks<<16)
   if i==6 and cfg.channel_mask&(1<<7) and not cfg.channel_mask&(1<<6):expected_bias=0x40000+cfg.pulse_bias_percent_367nm//2
   v=c.read(0x40000340+4*i);w=c.read(0x800003c0+4*i)
   assert (v,w)==(expected_bias,expected_timing),('SSP readback mismatch',i,hex(v),hex(w))
   bias.append(hex(v));timing.append(hex(w))
  assert c.read(0x80000448)==1 and c.read(0x80000464)==0x2e7
  started=self.timing.start();time.sleep(.1);after=self.telemetry()
  delta=(after['command7_count']-before['command7_count'])&0xffffffff
  assert delta>0,'SSP command7 counter did not respond to BOREAS_TLU_NP04'
  return {'previous_timing_stopped':previous_stop,'timing_started':started,'command7_count_increased':delta,'verified':True,'settings':dict(settings),'verification_scope':'SSP configuration transactions and register readback; no optical coupling to DAPHNE004 and no measured optical output','endpoint':'10.73.137.61:55002','before':before,'after':after,'bias_registers':bias,'duration_registers':timing,'unix_ns':time.time_ns()}
 def stop(self):
  if self.client is None:return {'control_session_opened':False}
  try:
   stopped=self.timing.stop()
   stop_run(self.client)
   assert all(self.client.read(0x40000340+4*i)==0 and self.client.read(0x800003c0+4*i)==0 for i in range(12))
   return {'led_registers_disabled':True,'timing_stopped':stopped,'telemetry':self.telemetry()}
  finally:
   self.client.close();self.client=None
   if self.lease is not None:self.lease.__exit__(None,None,None);self.lease=None

