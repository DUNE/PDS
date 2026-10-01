import unittest
from pds.core.runtime import RuntimeControl, MASK, APPLIED, CAPABILITY, PAUSE, PAUSED, DRAINED


class FakeBridge:
    def __init__(self):
        self.registers = {CAPABILITY: 0x43414C32, 0x88000034: 2, 0x94000020: 0xFFFFFFFF,
            0x94000028: 9, MASK: 0x10000, APPLIED: 0x10000, PAUSE: 0x80000000, PAUSED: 0x80000000}
        self.values, self.writes = {}, []
        self.blocked, self.failed = False, False

    def read32(self, address):
        if address == DRAINED:
            return 0 if self.blocked else self.registers[PAUSED]
        return self.registers[address]

    def write32(self, address, value):
        self.writes.append((address, value))
        self.registers[address] = value
        if address == PAUSE:
            self.registers[PAUSED] = value
        if address == MASK:
            self.registers[APPLIED] = value
        return value

    def write_setting(self, setting):
        assert self.registers[PAUSED] & 0xFF00 == 0xFF00
        if self.failed:
            raise RuntimeError('Injected DAC failure')
        self.values[setting['variable'], setting['target']] = setting['value']
        return setting['value']


class RuntimeTests(unittest.TestCase):
    def test_explicit_states_and_parameters(self):
        bridge = FakeBridge()
        sc = RuntimeControl(bridge, sleep=lambda _: None)
        result = sc.configure_afe(1, [{'variable': 'bias', 'target': 1, 'value': 1000}],
            timing_channels=[9], paused_channels=[8, 10, 11, 12, 13, 14, 15], settle_ms=100)
        self.assertEqual(result['calibration_mask'], 0x10200)
        self.assertEqual(result['pause_mask'], 0x8000FD00)
        sc.pause_afe(1)
        self.assertEqual(bridge.values['bias', 1], 1000)
        self.assertEqual(bridge.registers[MASK], 0x10200)
        # An explicit final request uses NEW values, not a saved original.
        sc.configure_afe(1, [{'variable': 'bias', 'target': 1, 'value': 1200}],
            timing_channels=[], paused_channels=[], settle_ms=100)
        self.assertEqual(bridge.values['bias', 1], 1200)
        self.assertEqual(bridge.registers[MASK], 0x10000)
        self.assertEqual(bridge.registers[PAUSE], 0x80000000)

    def test_failed_step_stays_paused_without_restore(self):
        bridge = FakeBridge()
        bridge.failed = True
        sc = RuntimeControl(bridge, sleep=lambda _: None)
        with self.assertRaises(RuntimeError):
            sc.configure_afe(1, [{'variable': 'bias', 'target': 1, 'value': 1000}],
                timing_channels=[9], paused_channels=[], settle_ms=0)
        self.assertEqual(bridge.registers[PAUSE] & 0xFF00, 0xFF00)
        self.assertEqual(bridge.registers[MASK], 0x10000)
        self.assertEqual(bridge.values, {})

    def test_no_setting_writes_before_drain(self):
        bridge = FakeBridge()
        bridge.blocked = True
        sc = RuntimeControl(bridge, timeout=0, sleep=lambda _: None)
        with self.assertRaises(TimeoutError):
            sc.configure_afe(1, [{'variable': 'bias', 'target': 1, 'value': 1000}],
                timing_channels=[9], paused_channels=[], settle_ms=0)
        self.assertEqual(bridge.values, {})

    def test_preflight_rejects_scope_and_old_firmware(self):
        for invalid in ('channel', 'setting', 'overlap', 'firmware'):
            bridge = FakeBridge()
            if invalid == 'firmware':
                bridge.registers[CAPABILITY] = 0x43414C31
            sc = RuntimeControl(bridge)
            with self.assertRaises((ValueError, RuntimeError)):
                sc.configure_afe(1, [{'variable': 'bias', 'target': 2 if invalid == 'setting' else 1, 'value': 1000}],
                    timing_channels=[17 if invalid == 'channel' else 9],
                    paused_channels=[9] if invalid == 'overlap' else [], settle_ms=0)
            self.assertEqual(bridge.writes, [])


if __name__ == '__main__':
    unittest.main()
