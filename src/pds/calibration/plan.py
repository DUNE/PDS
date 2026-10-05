import math
from itertools import product
from pds.core.runtime import channel_mask


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def canonical(variable):
    return {'attenuation': 'vgain', 'bias': 'sipm_bias'}.get(variable, variable)


def validate_settings(afe, settings):
    seen = set()
    for setting in settings:
        variable, target, value = (setting[k] for k in ('variable', 'target', 'value'))
        if canonical(variable) not in ('vgain', 'offset', 'sipm_bias', 'trim'):
            raise ValueError('Unsupported setting')
        if not integer(target, 0, 31) or (target // 8 if variable in ('trim', 'offset') else target) != afe:
            raise ValueError('Setting outside the selected AFE')
        key = (canonical(variable), target)
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
    hz = timing['rate_hz']
    if type(hz) not in (int, float) or not math.isfinite(hz) or not 6000 <= hz <= 244000 or not integer(timing['generator'], 0, 4) or not integer(timing['command_id'], 1, 255):
        raise ValueError('Specify a timing rate in [6000, 244000] Hz and reserved generator channel')
    if 'domain' in timing and (not isinstance(timing['domain'], str) or not timing['domain']):
        raise ValueError('DAPHNE timing domain must be a nonempty label')
    if not timing['master'] or not timing['connections']:
        raise ValueError('Timing master and connection file are required')
    steps = matrix_steps(plan, channels)
    final = plan['final']
    if final['mode'] == 'physics':
        validate_settings(afe, final['settings'])
        if not integer(final['settle_ms'], 0, 60000):
            raise ValueError('Explicit final settling interval is required')
    elif final['mode'] != 'paused':
        raise ValueError('Final mode must be physics with explicit settings, or paused')
    if 'waveforms_per_channel' in plan and not integer(plan['waveforms_per_channel'], 1, 10000000):
        raise ValueError('Waveforms per channel must be 1..10000000')
    if 'illumination' in plan:
        light = plan['illumination']
        if not isinstance(light, dict) or set(light) != {'settings', 'timing'}:
            raise ValueError('Illumination requires settings and its independent timing description')
        validate_light(light['settings'])
        optical_timing = light['timing']
        if not isinstance(optical_timing, dict) or not isinstance(optical_timing.get('domain'), str) or not optical_timing['domain'] or not integer(optical_timing.get('command_id'), 7, 7):
            raise ValueError('Describe the optical clock domain and command 7')
        if optical_timing['domain'] == timing.get('domain', 'daphne'):
            raise ValueError('Optical and DAPHNE timing domains must be distinct for this scan')
    return steps


OPTICAL = {'led_bias_270nm': 4095, 'led_bias_367nm': 4095,
    'led_width_ticks': 255, 'led_channel_mask': 4095,
    'led_second_width_ticks': 255, 'led_double_pulse_delay_ticks': 4095,
    'led_burst_count': 0x1FFFF}


def matrix_steps(plan, channels):
    afe = plan['afe']
    axes = plan.get('axes')
    if axes is None:
        if 'variable' in plan:
            axes = [dict(variable=plan['variable'], values=plan['values'], gain=plan.get('gain'))]
        else:
            axes = []
    elif 'variable' in plan or 'values' in plan:
        raise ValueError('Specify axes or a single variable/values scan')
    if not isinstance(axes, list) or (not axes and not plan.get('settings')):
        raise ValueError('Specify matrix axes or fixed detector settings')
    names = []
    for axis in axes:
        name, values = axis['variable'], axis['values']
        key = canonical(name)
        if name not in OPTICAL and canonical(name) not in ('vgain', 'sipm_bias', 'offset', 'trim'):
            raise ValueError('Unsupported matrix axis: ' + name)
        if key in names or not isinstance(values, list) or not values:
            raise ValueError('Axes must have unique hardware controls and nonempty values')
        high = OPTICAL.get(name, 4095)
        if any(not integer(v, 1 if name == 'led_burst_count' else 0, high) for v in values) or len(set(values)) != len(values):
            raise ValueError('Invalid or duplicate axis values: ' + name)
        if name in ('offset', 'trim') and type(axis.get('gain')) is not bool:
            raise ValueError('Offset/trim axes require an explicit gain flag')
        names.append(key)
    point_count = 1
    for axis in axes:
        point_count *= len(axis['values'])
    if point_count > 100000:
        raise ValueError('Split matrices larger than 100000 points')
    fixed = plan.get('settings', [])
    validate_settings(afe, fixed)
    varied = set(names)
    if any(canonical(s['variable']) in varied for s in fixed):
        raise ValueError('A fixed control cannot also be a matrix axis')
    optical = plan.get('illumination', {}).get('settings')
    if any(a['variable'] in OPTICAL for a in axes) and optical is None:
        raise ValueError('Optical axes require explicit SSP settings')
    steps = []
    for index, values in enumerate(product(*(a['values'] for a in axes))):
        coordinates = {canonical(a['variable']): v for a, v in zip(axes, values)}
        settings = [dict(s, variable=canonical(s['variable'])) for s in fixed]
        light = dict(optical) if optical is not None else None
        for axis, value in zip(axes, values):
            name = canonical(axis['variable'])
            if name in OPTICAL:
                light[name] = value
                continue
            targets = channels if name in ('offset', 'trim') else [afe]
            for target in targets:
                setting = dict(variable=name, target=target, value=value)
                if name in ('offset', 'trim'):
                    setting['gain'] = axis['gain']
                settings.append(setting)
        validate_settings(afe, settings)
        step = dict(step_id=index, coordinates=coordinates, settings=settings)
        if len(axes) == 1:
            step['value'] = values[0]
        if light is not None:
            step['illumination'] = light
        steps.append(step)
    return steps


def validate_light(settings):
    required = {'led_bias_270nm', 'led_bias_367nm', 'led_width_ticks', 'led_channel_mask'}
    if not isinstance(settings, dict) or not required <= set(settings) or not set(settings) <= set(OPTICAL):
        raise ValueError('Specify both LED bias codes, first width and mask; use supported optical controls')
    if any(not integer(v, 1 if k == 'led_burst_count' else 0, OPTICAL[k]) for k, v in settings.items()):
        raise ValueError('Invalid illumination code, width or mask')
