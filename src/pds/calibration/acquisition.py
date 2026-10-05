"""Collect a complete stable DAQ window from closed HDF5 files."""
import hashlib
import json
from pathlib import Path
import struct
import time


def audit_payload(payload, channels, window, period_ticks):
    if len(payload) % 512:
        raise RuntimeError('Truncated DAPHNE frame')
    timestamps = {str(ch): [] for ch in channels}
    frames = bytearray()
    begin, end = window
    for offset in range(0, len(payload), 512):
        daq, tick, header = struct.unpack_from('<3Q', payload, offset)
        channel = header >> 56
        if str(channel) not in timestamps or not begin <= tick < end:
            continue
        if (header >> 52 & 15) != 4 or (daq >> 52 & 4095) != 63 or (daq >> 26 & 255) != channel // 8:
            raise RuntimeError('Unexpected waveform format or stream ID')
        if (header >> 46 & 3) != 2 or (header >> 51 & 1):
            raise RuntimeError('Selected channel contains non-timing or continuation data')
        timestamps[str(channel)].append(tick)
        frames.extend(payload[offset:offset + 512])
    reference = None
    for channel, ticks in timestamps.items():
        ticks.sort()
        if not ticks or len(set(ticks)) != len(ticks):
            raise RuntimeError('Missing channel or duplicate waveform: ' + channel)
        if ticks[0] - begin > period_ticks + 4 or end - ticks[-1] > period_ticks + 4:
            raise RuntimeError('Incomplete waveform coverage at window boundary: ' + channel)
        if any(abs(b - a - period_ticks) > 4 for a, b in zip(ticks, ticks[1:])):
            raise RuntimeError('Timing waveform gap or unexpected trigger: ' + channel)
        if reference is not None and ticks != reference:
            raise RuntimeError('Selected channels have different timing events')
        reference = ticks
    return bytes(frames), {ch: len(ticks) for ch, ticks in timestamps.items()}


class HDF5Acquisition:
    """The DAQ remains running; files must rotate within the acquisition timeout."""
    def __init__(self, input_dir, output_dir, source_ids, timeout_s, sleep=time.sleep):
        self.input_dir, self.output_dir = Path(input_dir), Path(output_dir)
        self.source_ids, self.timeout_s, self.sleep = set(source_ids), timeout_s, sleep
        if not self.source_ids or not self.input_dir.is_dir():
            raise ValueError('Readable DAQ directory and source IDs are required')
        self.used = set()
        self.minimum_mtime = time.time() - timeout_s

    def preflight(self, plan):
        import hdf5libs
        import daqdataformats
        if self.output_dir.exists():
            raise FileExistsError('Dataset directory already exists')
        deadline = time.monotonic() + self.timeout_s
        expected_width = round(plan['window_s'] * plan['clock_hz'])
        while True:
            recent = sorted(self.input_dir.glob('*.hdf5'), key=lambda p: p.stat().st_mtime, reverse=True)
            ready = False
            for path in recent:
                if time.time() - path.stat().st_mtime > self.timeout_s:
                    break
                try:
                    raw = hdf5libs.HDF5RawDataFile(str(path))
                except (OSError, RuntimeError):
                    continue
                records = sorted(raw.get_all_record_ids())
                if not records:
                    continue
                for fragment_path in raw.get_fragment_dataset_paths(records[-1]):
                    header = raw.get_frag(fragment_path).get_header()
                    if header.fragment_type == daqdataformats.FragmentType.kDAPHNEEth.value and header.element_id.id in self.source_ids:
                        if header.window_end - header.window_begin != expected_width:
                            raise RuntimeError('Configure the DAQ readout window before starting the scan')
                        ready = True
                if ready:
                    break
            if ready:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('No fresh closed DAQ file with the selected source IDs')
            self.sleep(0.25)
        self.output_dir.mkdir(parents=True)
        return {'input_dir': str(self.input_dir), 'source_ids': sorted(self.source_ids),
            'requested_daq_trigger_hz': plan['daq_trigger_hz'], 'window_s': plan['window_s']}

    def collect(self, metadata, started):
        import hdf5libs
        import daqdataformats
        guard = max(started['period_ticks'] * 2,
            round(metadata['capture_tail_ms'] * started['clock_hz'] / 1000))
        earliest = started['ready_tick'] + guard
        expected_width = round(metadata['window_s'] * started['clock_hz'])
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            for path in sorted(self.input_dir.glob('*.hdf5')):
                if path.stat().st_mtime < self.minimum_mtime:
                    continue
                # DUNE writers use a .writing suffix until the file is closed.
                try:
                    raw = hdf5libs.HDF5RawDataFile(str(path))
                except (RuntimeError, OSError):
                    continue
                for record in raw.get_all_record_ids():
                    key = (str(path), str(record))
                    if key in self.used:
                        continue
                    fragments = []
                    for fragment_path in raw.get_fragment_dataset_paths(record):
                        fragment = raw.get_frag(fragment_path)
                        header = fragment.get_header()
                        if header.fragment_type == daqdataformats.FragmentType.kDAPHNEEth.value and header.element_id.id in self.source_ids:
                            fragments.append(fragment)
                    if not fragments:
                        continue
                    windows = {(f.get_header().window_begin, f.get_header().window_end) for f in fragments}
                    if len(windows) != 1:
                        raise RuntimeError('Selected fragments have different readout windows')
                    begin, end = next(iter(windows))
                    if begin < earliest:
                        self.used.add(key)
                        continue
                    if end - begin != expected_width:
                        raise RuntimeError('DAQ window does not match the scan plan')
                    if any(f.get_header().status_bits for f in fragments):
                        raise RuntimeError('DAQ reported a fragment error')
                    payload = b''.join(f.get_data_bytes() for f in fragments)
                    frames, counts = audit_payload(payload, metadata['channels'], (begin, end), started['period_ticks'])
                    dataset = self.output_dir / ('step-{:03d}.bin'.format(metadata['step_id']))
                    with open(dataset, 'xb') as output:
                        output.write(frames)
                        output.flush()
                        import os
                        os.fsync(output.fileno())
                    receipt = dict(metadata, file=str(path), record_id=str(record),
                        window_begin=begin, window_end=end, received_counts=counts,
                        actual_rate_hz=started['actual_rate_hz'], dataset=str(dataset),
                        sha256=hashlib.sha256(frames).hexdigest(), frame_bytes=512,
                        expected_per_channel=(end - begin) / started['period_ticks'], verified=True)
                    with open(dataset.with_suffix('.json'), 'x') as output:
                        json.dump(receipt, output, indent=2)
                    self.used.add(key)
                    return receipt
            self.sleep(0.25)
        raise TimeoutError('No complete stable DAQ window arrived before the deadline')
