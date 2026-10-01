import unittest
from pds.core.runtime import DaphneBridge
try:
    import daphneV3_high_level_confs_pb2 as high
    import daphneV3_low_level_confs_pb2 as low
except ImportError:
    high = low = None


@unittest.skipIf(high is None, 'Generated server schemas are required')
class BridgeTests(unittest.TestCase):
    def test_physical_channel_mapping_and_gain(self):
        bridge = DaphneBridge.__new__(DaphneBridge)
        bridge.high, bridge.low = high, low
        captured = []
        def call(kind, request, response_type):
            captured.append((kind, request))
            response = response_type(success=True)
            if hasattr(response, 'trimValue'):
                response.trimValue = 123
            elif hasattr(response, 'offsetValue'):
                response.offsetValue = 123
            else:
                response.biasValue = 123
            return response
        bridge._call = call
        for variable in ('bias', 'trim', 'offset'):
            target = 1 if variable == 'bias' else 9
            self.assertEqual(bridge.write_setting({'variable': variable, 'target': target, 'value': 123, 'gain': True}), 123)
        self.assertEqual(captured[0][1].afeBlock, 4)
        self.assertEqual(captured[1][1].trimChannel, 33)
        self.assertTrue(captured[1][1].trimGain)
        self.assertEqual(captured[2][1].offsetChannel, 33)
        self.assertTrue(captured[2][1].offsetGain)


if __name__ == '__main__':
    unittest.main()
