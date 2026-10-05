"""Check the v4 rawdatautils ABI and benchmark decoding without HDF5 I/O."""
import ctypes,json,time,statistics,numpy as np,fddetdataformats
from rawdatautils.unpack import daphneeth as unpack
if fddetdataformats.DAPHNEEthFrame.sizeof()!=512:
    raise RuntimeError('Use fddetdataformats for 512-byte DAPHNE v4 frames')
frame=fddetdataformats.DAPHNEEthFrame();frame.set_timestamp(1791211145*62500000)
frame.set_channel(3)
expected=np.array([(i*197+31)&0x3fff for i in range(256)],dtype=np.uint16)
for i,v in enumerate(expected):frame.set_adc(i,int(v))
blob=frame.get_bytes()
# Bounded compatibility probe before using the pointer/count batch API.
probe=ctypes.create_string_buffer(blob+bytes(8192))
new=ctypes.pythonapi.PyCapsule_New;new.restype=ctypes.py_object;new.argtypes=(ctypes.c_void_p,ctypes.c_char_p,ctypes.c_void_p)
a=unpack.np_array_adc_data(new(ctypes.addressof(probe),None,None),1)
if a.shape!=(1,256) or a.dtype!=np.uint16 or not np.array_equal(a[0],expected):
    raise RuntimeError('Rebuild rawdatautils against the matching fddetdataformats')
n=16384;buffer=ctypes.create_string_buffer(blob*n);capsule=new(ctypes.addressof(buffer),None,None)
times=[]
for _ in range(9):
 start=time.perf_counter();a=unpack.np_array_adc_data(capsule,n);times.append(time.perf_counter()-start)
if a.shape!=(n,256) or not np.all(a==expected):
    raise RuntimeError('Batch decoding differs from the frame accessors')
median=statistics.median(times)
print(json.dumps(dict(frame_bytes=512,samples_per_frame=256,frames=n,dtype=str(a.dtype),verified=True,median_seconds=median,frames_per_second=n/median,samples_per_second=n*256/median,packed_frame_gbytes_per_second=n*512/median/1e9,repeats=len(times),unpacker=unpack.__name__),indent=2))
