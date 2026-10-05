import math
from pds.core.runtime import channel_mask


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def validate_settings(afe, settings):
    seen = set()
    for setting in settings:
        variable, target, value = (setting[k] for k in ('variable', 'target', 'value'))
        if variable not in ('vgain', 'offset', 'bias', 'attenuation', 'trim'):
            raise ValueError('Unsupported setting')
        if not integer(target, 0, 31) or (target // 8 if variable in ('trim', 'offset') else target) != afe:
            raise ValueError('Setting outside the selected AFE')
        key = ('attenuation' if variable == 'vgain' else variable, target)
        if not integer(value, 0, 4095) or key in seen:
            raise ValueError('Invalid or duplicate DAC setting')
        if variable in ('trim', 'offset') and type(setting.get('gain')) is not bool:
            raise ValueError('Offset/trim requires an explicit gain flag')
        seen.add(key)


def compile_plan(plan):
    """Validate the complete request, including the explicit final state, before I/O."""
    afe, channels = plan['afe'], plan['channels']
    if channels == 'enabled' and type(afe) is int:
        channels = list(range(afe * 8, afe * 8 + 8))
    if type(afe) is not int or not channels or len(set(channels)) != len(channels):
        raise ValueError('Select unique channels within one AFE')
    channel_mask(afe, channels)
    if not isinstance(plan['scan_id'], str) or not plan['scan_id'] or not plan['board_endpoint'].startswith('tcp://'):
        raise ValueError('Scan ID and board endpoint are required')
    variable, values = plan['variable'], plan['values']
    if variable not in ('vgain', 'offset') or not values or any(not integer(v, 0, 4095) for v in values):
        raise ValueError('Scan vgain or offset using DAC codes 0..4095')
    if not integer(plan['settle_ms'], 0, 60000) or not integer(plan['capture_tail_ms'], 0, 60000):
        raise ValueError('Specify settling and capture-tail intervals in milliseconds')
    duration = plan['window_s']
    if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 < duration <= 3600:
        raise ValueError('Window length must be finite and in (0, 3600] seconds')
    if plan['daq_trigger_hz'] != 0.5 or not integer(plan['acquisition_timeout_s'], 3, 3600):
        raise ValueError('Specify 0.5 Hz DAQ triggers and a bounded acquisition timeout')
    if plan['acquisition_timeout_s'] <= duration + plan['capture_tail_ms'] / 1000:
        raise ValueError('Acquisition timeout must exceed the window and capture tail')
    sources = plan['source_ids']
    if not isinstance(sources, list) or not sources or len(set(sources)) != len(sources) or any(not integer(s, 0, 0xFFFFFFFF) for s in sources):
        raise ValueError('Specify unique DAQ source IDs for this board/AFE')
    timing = plan['timing']
    if timing['rate_hz'] != 6000 or not integer(timing['generator'], 0, 4) or not integer(timing['command_id'], 1, 255):
        raise ValueError('Specify a 6 kHz timing command and reserved generator channel')
    if not timing['master'] or not timing['connections']:
        raise ValueError('Timing master and connection file are required')
    steps = []
    for index, value in enumerate(values):
        targets = [afe] if variable == 'vgain' else channels
        settings = [{'variable': variable, 'target': target, 'value': value} for target in targets]
        if variable == 'offset':
            for setting in settings:
                setting['gain'] = plan.get('gain')
        validate_settings(afe, settings)
        steps.append({'step_id': index, 'value': value, 'settings': settings})
    final = plan['final']
    if final['mode'] == 'physics':
        validate_settings(afe, final['settings'])
        if not integer(final['settle_ms'], 0, 60000):
            raise ValueError('Explicit final settling interval is required')
    elif final['mode'] != 'paused':
        raise ValueError('Final mode must be physics with explicit settings, or paused')
    return steps
