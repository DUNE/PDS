"""Bounded timing worker: survives caller failure long enough to stop its generator."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

PREFIX = b'PDS_TIMING '


def rate(clock_hz, divisor, prescale):
    if divisor != 0:
        raise RuntimeError("Timing divisor is not qualified; use the measured divisor-0 range")
    period = 256 * (prescale + 1)
    if prescale == 0:
        raise RuntimeError('Invalid timing prescale')
    return clock_hz / period, period


class TimingSource:
    def __init__(self, config, timeout_s):
        self.config, self.timeout_s = config, timeout_s
        self.process, self.buffer = None, b''

    @contextmanager
    def reserve(self):
        locks = Path.home() / '.pds' / 'locks'
        locks.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256((self.config['connections'] + ':' + self.config['master']).encode()).hexdigest()
        with open(locks / ('calibration-source-' + key), 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def _spawn(self, inspect=False):
        argv = [sys.executable, '-m', 'pds.calibration.timing', '--config', json.dumps(self.config),
            '--timeout', str(self.timeout_s)]
        if inspect:
            argv.append('--inspect')
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=None, bufsize=0)
        self.buffer = b''

    def _event(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            if b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                if line.startswith(PREFIX):
                    event = json.loads(line[len(PREFIX):])
                    if event['event'] == 'error':
                        raise RuntimeError(event['error'])
                    return event
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise TimeoutError('Timing worker acknowledgement timed out')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('Timing worker exited without acknowledgement')
            self.buffer += chunk

    def preflight(self):
        self._spawn(inspect=True)
        try:
            event = self._event(15)
            self.process.wait(timeout=5)
            if event['event'] != 'inspected' or self.process.returncode:
                raise RuntimeError('Timing preflight failed')
            return event
        finally:
            self.stop()

    def start(self):
        if self.process is not None:
            raise RuntimeError('Timing worker is already running')
        self._spawn()
        try:
            event = self._event(15)
            if event['event'] != 'started':
                raise RuntimeError('Timing generator did not start')
            return event
        except BaseException:
            self.stop()
            raise

    def stop(self):
        process = self.process
        if process is None:
            return None
        try:
            if process.poll() is None:
                try:
                    process.stdin.write(b'stop\n')
                    process.stdin.flush()
                except BrokenPipeError:
                    pass
                event = self._event(10)
                process.wait(timeout=5)
                if event['event'] != 'stopped' or process.returncode:
                    raise RuntimeError('Timing stop was not acknowledged')
                return event
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdin.close()
            process.stdout.close()
            self.process = None


def emit(event, **data):
    print(PREFIX.decode() + json.dumps(dict(event=event, **data)), flush=True)


def worker(config, timeout_s, inspect=False):
    import uhal
    import timing.core  # Registers the derived uHAL nodes.
    uhal.setLogLevelTo(uhal.LogLevel.ERROR)
    locks = Path.home() / '.pds' / 'locks'
    locks.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((config['connections'] + ':' + config['master']).encode()).hexdigest()
    with open(locks / ('timing-' + key), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cm = uhal.ConnectionManager('file://' + str(Path(config['connections']).resolve()))
        device = cm.getDevice(config['master'])
        device.setTimeoutPeriod(2000)
        master, top = device.getNode('master'), device.getNode('')
        generator = master.getNode('scmd_gen')
        def read(node):
            value = device.getNode(node).read()
            device.dispatch()
            return int(value)
        clock_hz = read('io.config.clock_frequency')
        n_channels = read('master.global.config.n_chan')
        if not 0 <= config['generator'] < n_channels:
            raise ValueError('Timing generator channel is unavailable')
        if not read('master.global.csr.stat.ts_valid') or not read('master.global.csr.ctrl.ts_en'):
            raise RuntimeError('Timing master timestamp broadcast is not ready')
        for channel in range(n_channels):
            generator.getNode('sel').write(channel)
            control = generator.getNode('chan_ctrl').read()
            device.dispatch()
            control = int(control)
            if control & 1 and (channel == config['generator'] or (control >> 8 & 255) == config['command_id']):
                raise RuntimeError('Timing generator or matching command is already active')
        def snapshot():
            accepted = generator.getNode('actrs').readBlock(16)
            rejected = generator.getNode('rctrs').readBlock(16)
            device.dispatch()
            return {'timestamp': int(master.read_timestamp()),
                'accepted': int(accepted[config['generator']]), 'rejected': int(rejected[config['generator']])}
        if inspect:
            emit('inspected', clock_hz=clock_hz, snapshot=snapshot())
            return
        started, stopped = False, None
        before = snapshot()
        def interrupt(signum, frame):
            raise KeyboardInterrupt('Timing worker interrupted')
        signal.signal(signal.SIGTERM, interrupt)
        try:
            # A timeout during programming has an unknown outcome; attempt stop too.
            started = True
            top.enable_periodic_fl_cmd(config['command_id'], config['generator'], config['rate_hz'], False)
            generator.getNode('sel').write(config['generator'])
            control = generator.getNode('chan_ctrl').read()
            device.dispatch()
            control = int(control)
            if not control & 1 or control >> 8 & 255 != config['command_id'] or control & 2:
                raise RuntimeError('Periodic command configuration mismatch')
            actual_rate, period_ticks = rate(clock_hz, control >> 24 & 15, control >> 16 & 255)
            emit('started', before=before, ready_tick=int(master.read_timestamp()),
                clock_hz=clock_hz, actual_rate_hz=actual_rate, period_ticks=period_ticks)
            if select.select([sys.stdin], [], [], timeout_s)[0]:
                os.read(sys.stdin.fileno(), 4096)  # STOP or caller EOF both stop acquisition.
            else:
                raise TimeoutError('Timing lease expired before DAQ receipt')
        finally:
            if started:
                master.disable_periodic_fl_cmd(config['generator'])
                stopped = snapshot()
                emit('stopped', before=before, after=stopped,
                    sent=(stopped['accepted'] - before['accepted']) & 0xFFFFFFFF,
                    rejected=(stopped['rejected'] - before['rejected']) & 0xFFFFFFFF)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--timeout', type=float, required=True)
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    try:
        worker(json.loads(args.config), args.timeout, args.inspect)
    except BaseException as error:
        emit('error', error=str(error))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
