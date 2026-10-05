import argparse
import json
from pathlib import Path
import signal

from .plan import compile_plan


def main():
    parser = argparse.ArgumentParser(description='SC/CCM runtime calibration with an already running DAQ')
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
            nominal_waveforms_per_channel=plan['timing']['rate_hz'] * plan['window_s']), indent=2))
        return
    if args.input_dir is None or args.output_dir is None or args.journal is None:
        parser.error('run requires --input-dir, --output-dir and --journal')
    from pds.core.runtime import DaphneBridge, RuntimeControl
    from .acquisition import HDF5Acquisition
    from .coordinator import Coordinator
    from .journal import Journal
    from .timing import TimingSource
    def interrupt(signum, frame):
        raise KeyboardInterrupt('SC/CCM scan interrupted')
    signal.signal(signal.SIGTERM, interrupt)
    journal = Journal(args.journal)
    bridge = None
    timing = TimingSource(plan['timing'], plan['acquisition_timeout_s'] + 30)
    try:
        bridge = DaphneBridge(plan['board_endpoint'])
        acquisition = HDF5Acquisition(args.input_dir, args.output_dir, plan['source_ids'], plan['acquisition_timeout_s'])
        Coordinator(RuntimeControl(bridge), timing, acquisition, journal).run(plan)
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
