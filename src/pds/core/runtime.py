"""SC-side runtime operations. The DAPHNE server only forwards hardware access."""
import threading
import time

MASK, APPLIED, CAPABILITY = 0xA0010F00, 0xA0010F04, 0xA0010F08
PAUSE, PAUSED, DRAINED = 0xA0010F0C, 0xA0010F10, 0xA0010F14
PL_TO_BOARD = {0: 0, 1: 4, 2: 3, 3: 2}


def channel_mask(afe, channels):
    if type(afe) is not int or not 0 <= afe < 4:
        raise ValueError("Firmware AFE must be 0..3")
    mask = 0
    for channel in channels:
        if type(channel) is not int or not 0 <= channel < 32 or channel // 8 != afe:
            raise ValueError("Channel must belong to the selected firmware AFE")
        mask |= 1 << channel
    return mask


class RuntimeControl:
    """Owned by the SC/CCM; share one instance per board for arbitration."""
    def __init__(self, bridge, timeout=2, sleep=time.sleep):
        self.bridge, self.timeout, self.sleep = bridge, timeout, sleep
        self.lock = threading.RLock()

    def _wait(self, address, expected, mask=0xFFFFFFFF):
        deadline = time.monotonic() + self.timeout
        while self.bridge.read32(address) & mask != expected:
            if time.monotonic() >= deadline:
                raise TimeoutError("Hardware acknowledgement timed out")
            self.sleep(0.001)

    def _write_mask(self, address, acknowledgement, value):
        if self.bridge.write32(address, value) != value:
            raise RuntimeError("Hardware mask write mismatch")
        self._wait(acknowledgement, value)

    def _check(self):
        if self.bridge.read32(CAPABILITY) != 0x43414C32:
            raise RuntimeError("CAL2 firmware is required")
        if self.bridge.read32(0x88000034) != 2:
            raise RuntimeError("Board must be in xcorr mode")

    def _pause(self, affected):
        self._write_mask(PAUSE, PAUSED, self.bridge.read32(PAUSE) | affected)
        self._wait(DRAINED, affected, affected)

    def pause_afe(self, afe):
        affected = channel_mask(afe, range(8 * afe, 8 * afe + 8))
        with self.lock:
            self._check()
            self._pause(affected)

    def configure_afe(self, afe, settings, *, timing_channels, paused_channels, settle_ms):
        """Apply explicitly requested values and acquisition state; retain no snapshot."""
        timing = channel_mask(afe, timing_channels)
        paused = channel_mask(afe, paused_channels)
        affected = 0xFF << (8 * afe)
        settings = list(settings)
        if timing & paused or not isinstance(settle_ms, int) or not 0 <= settle_ms <= 60000:
            raise ValueError("Invalid timing/pause selection or settling interval")
        seen = set()
        for setting in settings:
            variable, target, value = setting['variable'], setting['target'], setting['value']
            if variable not in ('bias', 'sipm_bias', 'attenuation', 'vgain', 'trim', 'offset'):
                raise ValueError("Unsupported runtime variable")
            if type(target) is not int or (target // 8 if variable in ('trim', 'offset') else target) != afe:
                raise ValueError("Setting is outside the selected AFE")
            key = ({'vgain': 'attenuation', 'sipm_bias': 'bias'}.get(variable, variable), target)
            if type(value) is not int or not 0 <= value <= 4095 or key in seen:
                raise ValueError("Invalid or duplicate DAC setting")
            if variable in ('trim', 'offset') and not isinstance(setting.get('gain'), bool):
                raise ValueError("Trim/offset requires an explicit DAC gain flag")
            seen.add(key)
        with self.lock:
            self._check()
            if self.bridge.read32(0x94000020) & timing != timing:
                raise ValueError("Timing selection includes disabled channels")
            self._pause(affected)
            try:
                for setting in settings:
                    if self.bridge.write_setting(setting) != setting['value']:
                        raise RuntimeError("Programmed DAC value mismatch")
                self.sleep(settle_ms / 1000)
                desired = (self.bridge.read32(MASK) & ~affected) | timing
                self._write_mask(MASK, APPLIED, desired)
                desired_pause = (self.bridge.read32(PAUSE) & ~affected) | paused
                self._write_mask(PAUSE, PAUSED, desired_pause)
                return {'afe': afe, 'settings': settings, 'calibration_mask': desired,
                    'pause_mask': desired_pause, 'ready_unix_ns': time.time_ns(),
                    'command_id': self.bridge.read32(0x94000028) & 0xFF}
            except BaseException:
                # Do not restore parameters or switch back to self-trigger.
                try:
                    self._pause(affected)
                except Exception:
                    pass
                raise


class DaphneBridge:
    """v2 communication adapter; sequencing and arbitration stay in RuntimeControl."""
    def __init__(self, endpoint, timeout_ms=5000):
        import zmq
        import daphneV3_high_level_confs_pb2 as high
        import daphneV3_low_level_confs_pb2 as low
        self.zmq, self.high, self.low = zmq, high, low
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.connect(endpoint)
        self.timeout_ms, self.sequence = timeout_ms, 0

    def _call(self, kind, request, response_type):
        self.sequence += 1
        high = self.high
        envelope = high.ControlEnvelopeV2(version=2, dir=high.DIR_REQUEST, type=kind,
            msg_id=self.sequence, task_id=self.sequence, payload=request.SerializeToString())
        self.socket.send(envelope.SerializeToString())
        deadline = time.monotonic() + self.timeout_ms / 1000
        while True:
            remaining = int((deadline - time.monotonic()) * 1000)
            if remaining <= 0 or not self.socket.poll(remaining):
                raise TimeoutError("Server reply timed out; request outcome is unknown")
            reply = high.ControlEnvelopeV2.FromString(self.socket.recv())
            if reply.correl_id != envelope.msg_id:
                continue
            if reply.version != 2 or reply.dir != high.DIR_RESPONSE or reply.type != kind + 1:
                raise RuntimeError("Unexpected server envelope")
            response = response_type.FromString(reply.payload)
            if not response.success:
                raise RuntimeError(response.message)
            return response.value if isinstance(response, high.RuntimeRegisterResponse) else response

    def read32(self, address):
        return self._call(self.high.MT2_RUNTIME_REGISTER_REQ,
            self.high.RuntimeRegisterRequest(address=address), self.high.RuntimeRegisterResponse)

    def write32(self, address, value):
        return self._call(self.high.MT2_RUNTIME_REGISTER_REQ,
            self.high.RuntimeRegisterRequest(address=address, write=True, value=value), self.high.RuntimeRegisterResponse)

    def write_setting(self, setting):
        variable, target, value = setting['variable'], setting['target'], setting['value']
        high, low = self.high, self.low
        if variable == 'vgain':
            response = self._call(high.MT2_WRITE_AFE_VGAIN_REQ,
                low.cmd_writeAFEVGAIN(afeBlock=PL_TO_BOARD[target], vgainValue=value), low.cmd_writeAFEVGAIN_response)
            return response.vgainValue
        if variable in ('bias', 'sipm_bias'):
            response = self._call(high.MT2_WRITE_AFE_BIAS_SET_REQ,
                low.cmd_writeAFEBiasSet(afeBlock=PL_TO_BOARD[target], biasValue=value), low.cmd_writeAFEBiasSet_response)
            return response.biasValue
        if variable == 'attenuation':
            response = self._call(high.MT2_WRITE_AFE_ATTENUATION_REQ,
                low.cmd_writeAFEAttenuation(afeBlock=PL_TO_BOARD[target], attenuation=value), low.cmd_writeAFEAttenuation_response)
            return response.attenuation
        physical = PL_TO_BOARD[target // 8] * 8 + target % 8
        if variable == 'trim':
            response = self._call(high.MT2_WRITE_TRIM_CH_REQ,
                low.cmd_writeTrim_singleChannel(trimChannel=physical, trimValue=value, trimGain=setting['gain']),
                low.cmd_writeTrim_singleChannel_response)
            return response.trimValue
        if variable == 'offset':
            response = self._call(high.MT2_WRITE_OFFSET_CH_REQ,
                low.cmd_writeOFFSET_singleChannel(offsetChannel=physical, offsetValue=value, offsetGain=setting['gain']),
                low.cmd_writeOFFSET_singleChannel_response)
            return response.offsetValue
        raise ValueError("Unsupported runtime variable")

    def timing_status(self):
        control = self.read32(0x84000000)
        clocks = self.read32(0x84000004)
        endpoint = self.read32(0x8400000C)
        return {'clock_source': 'endpoint' if control & 4 else 'local',
            'clocks_locked': clocks & 3 == 3, 'endpoint_state': endpoint & 15,
            'timestamp_valid': bool(endpoint & 16), 'endpoint_address': self.read32(0x84000008) & 65535}

    def counters(self, channels):
        response = self._call(self.high.MT2_READ_TRIGGER_COUNTERS_REQ,
            self.high.ReadTriggerCountersRequest(channels=channels), self.high.ReadTriggerCountersResponse)
        result = {str(s.channel): {'records': s.record_count, 'busy': s.busy_count, 'full': s.full_count}
            for s in response.snapshots}
        if set(result) != {str(ch) for ch in channels}:
            raise RuntimeError('Incomplete trigger counter response')
        return result

    def close(self):
        self.socket.close()
        self.context.term()
