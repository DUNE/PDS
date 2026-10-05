import copy
import fcntl
import hashlib
from pathlib import Path
import time

from pds.core.runtime import MASK, PAUSE
from .plan import compile_plan


class Coordinator:
    """SC/CCM owns the full transaction; the board server stores no scan state."""
    def __init__(self, runtime, timing, acquisition, journal, sleep=time.sleep):
        self.runtime, self.timing, self.acquisition = runtime, timing, acquisition
        self.journal, self.sleep = journal, sleep
        self.started = False

    def run(self, plan):
        compile_plan(plan)
        locks = Path.home() / '.pds' / 'locks'
        locks.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(plan['board_endpoint'].encode()).hexdigest()
        self.journal.record('scan_requested', plan=plan)
        try:
            with self.timing.reserve(), open(locks / ('calibration-' + key), 'a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.runtime.lock:
                    return self._run(copy.deepcopy(plan))
        except BaseException as error:
            if not self.started:
                self.journal.record('preflight_failed', error=str(error))
            raise

    def _run(self, plan):
        bridge, afe = self.runtime.bridge, plan['afe']
        affected = 0xFF << (8 * afe)
        status = bridge.timing_status()
        if status['clock_source'] != 'endpoint' or not status['clocks_locked'] or status['endpoint_state'] != 8 or not status['timestamp_valid']:
            raise RuntimeError('Aligned endpoint clock and valid timestamps are required')
        self.runtime._check()
        if bridge.read32(MASK) & affected or bridge.read32(PAUSE) & affected:
            raise RuntimeError('AFE already has calibration/pause state; SC/CCM must reconcile it explicitly')
        if plan['channels'] == 'enabled':
            enabled = bridge.read32(0x94000020)
            plan['channels'] = [ch for ch in range(8 * afe, 8 * afe + 8) if enabled & (1 << ch)]
        steps = compile_plan(plan)
        if bridge.read32(0x94000020) & sum(1 << ch for ch in plan['channels']) != sum(1 << ch for ch in plan['channels']):
            raise ValueError('Selected channels must already be enabled')
        if bridge.read32(0x94000028) & 255 != plan['timing']['command_id']:
            raise ValueError('Board timing command does not match the plan')
        timing_status = self.timing.preflight()
        plan['clock_hz'] = timing_status['clock_hz']
        acquisition_status = self.acquisition.preflight(plan)
        self.journal.record('scan_started', plan=plan, board=status, timing=timing_status, acquisition=acquisition_status)
        self.started = True
        touched = False
        try:
            for step in steps:
                self.journal.record('step_requested', **step)
                touched = True
                ready = self.runtime.configure_afe(afe, step['settings'], timing_channels=plan['channels'],
                    paused_channels=[], settle_ms=plan['settle_ms'])
                self.journal.record('step_ready', step_id=step['step_id'], ready=ready)
                before = bridge.counters(plan['channels'])
                started = self.timing.start()
                self.journal.record('timing_started', step_id=step['step_id'], timing=started)
                metadata = dict(scan_id=plan['scan_id'], board_endpoint=plan['board_endpoint'], afe=afe,
                    channels=plan['channels'], step_id=step['step_id'], settings=step['settings'],
                    window_s=plan['window_s'], capture_tail_ms=plan['capture_tail_ms'])
                receipt = self.acquisition.collect(metadata, started)
                stopped = self.timing.stop()
                self.journal.record('timing_stopped', step_id=step['step_id'], timing=stopped)
                if stopped['rejected']:
                    raise RuntimeError('Timing master rejected commands')
                self.sleep(plan['capture_tail_ms'] / 1000)
                self.runtime.pause_afe(afe)
                after = bridge.counters(plan['channels'])
                delta = {ch: {name: after[ch][name] - before[ch][name] for name in before[ch]} for ch in before}
                if any(c['busy'] or c['full'] or c['records'] != stopped['sent'] for c in delta.values()):
                    raise RuntimeError('Board capture loss or unexpected triggers during the step')
                if receipt.get('verified') is not True:
                    raise RuntimeError('DAQ window is not verified')
                self.journal.record('step_complete', step_id=step['step_id'], receipt=receipt, counters=delta)
            final = plan['final']
            self.journal.record('final_requested', final=final)
            if final['mode'] == 'physics':
                self.runtime.configure_afe(afe, final['settings'], timing_channels=[], paused_channels=[],
                    settle_ms=final['settle_ms'])
            # Paused final state retains the last values and timing selection.
            self.journal.record('scan_complete', final=final)
        except BaseException as error:
            cleanup = {}
            try:
                cleanup['timing'] = self.timing.stop()
            except BaseException as stop_error:
                cleanup['timing_error'] = str(stop_error)
            if touched:
                try:
                    self.runtime.pause_afe(afe)
                    cleanup['afe_paused'] = True
                except BaseException as pause_error:
                    cleanup['pause_error'] = str(pause_error)
            self.journal.record('scan_failed', error=str(error), cleanup=cleanup)
            raise
