import argparse
import json
from pathlib import Path
import signal

from .plan import compile_plan


def main():
    parser = argparse.ArgumentParser(description='PDS calibration matrices with an already running DAQ')
    parser.add_argument('action', choices=['plan', 'run'])
    parser.add_argument('plan', type=Path)
    parser.add_argument('--input-dir', type=Path, help='DAQ directory containing closed .hdf5 files')
    parser.add_argument('--output-dir', type=Path, help='New directory for selected waveform datasets')
    parser.add_argument('--journal', type=Path, help='New JSONL scan journal')
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    steps = compile_plan(plan)
    if args.action == 'plan':
        print(json.dumps(dict(plan=plan, steps=steps,
            point_count=len(steps),
            waveforms_per_channel=plan.get('waveforms_per_channel', 10000 if 'axes' in plan else None),
            nominal_waveforms_per_channel=plan['timing']['rate_hz'] * plan['window_s'],
            nominal_counting_s=plan.get('waveforms_per_channel', 10000) / plan['timing']['rate_hz'],
            note='Nominal rate only; measure the master rate. DAQ cadence and file closure add latency.'), indent=2))
        return
    if args.input_dir is None or args.output_dir is None or args.journal is None:
        parser.error('run requires --input-dir, --output-dir and --journal')
    def interrupt(signum, frame):
        raise KeyboardInterrupt('PDS scan interrupted')
    signal.signal(signal.SIGTERM, interrupt)
    if 'illumination' in plan:
        parser.error('Optical matrices require a PDS settings callback; use run_scan(..., apply_optical=...)')
    run_scan(plan, args.input_dir, args.output_dir, args.journal)


def run_scan(plan, input_dir, output_dir, journal_path, apply_optical=None):
    from pds.core.runtime import DaphneBridge, RuntimeControl
    from .acquisition import HDF5Acquisition
    from .coordinator import Coordinator
    from .journal import Journal
    from .timing import TimingSource
    journal = Journal(journal_path)
    bridge = None
    timing = TimingSource(plan['timing'], plan['acquisition_timeout_s'] + 30)
    try:
        bridge = DaphneBridge(plan['board_endpoint'])
        acquisition = HDF5Acquisition(input_dir, output_dir, plan['source_ids'], plan['acquisition_timeout_s'])
        Coordinator(RuntimeControl(bridge), timing, acquisition, journal, apply_optical=apply_optical).run(plan)
    finally:
        try:
            timing.stop()
        finally:
            try:
                if bridge is not None:
                    bridge.close()
            finally:
                journal.close()


if __name__ == '__main__':
    main()
