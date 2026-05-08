from pathlib import Path

from pds.core.config_model import ScanConfig
from pds.core.scans import _update_afe_bias, _update_attenuators, _update_offset, _update_trim


def _cfg(**kwargs):
    defaults = {
        "mode": "attscan",
        "drunc_working_dir": Path("/tmp"),
        "oks_file": "ok.xml",
        "daphne_details": "details.json",
    }
    defaults.update(kwargs)
    return ScanConfig(**defaults)


def _board_data():
    return {
        "61": {
            "bias_ctrl": 0,
            "channel_analog_conf": {
                "ids": [4, 5, 6],
                "offsets": [10, 11, 12],
                "trims": [0, 1, 2],
            },
            "afes": {
                "ids": [0, 1, 2],
                "attenuators": [100, 200, 300],
                "v_biases": [10, 20, 30],
            },
        },
        "62": {
            "channel_analog_conf": {
                "ids": [4],
                "offsets": [99],
                "trims": [9],
            },
            "afes": {
                "ids": [0],
                "attenuators": [900],
                "v_biases": [90],
            },
        },
    }


def test_board_keyed_attenuator_scan_respects_selectors():
    data = _board_data()
    cfg = _cfg(board_ids=["61"], afe_ids=[0, 1])

    _update_attenuators(data, 500, cfg)

    assert data["61"]["afes"]["attenuators"] == [500, 500, 300]
    assert data["62"]["afes"]["attenuators"] == [900]


def test_board_keyed_channel_scans_respect_selectors():
    data = _board_data()
    cfg = _cfg(board_ids=["61"], channel_ids=[4, 5])

    _update_offset(data, 2222, cfg)
    _update_trim(data, 7, cfg)

    assert data["61"]["channel_analog_conf"]["offsets"] == [2222, 2222, 12]
    assert data["61"]["channel_analog_conf"]["trims"] == [7, 7, 2]
    assert data["62"]["channel_analog_conf"]["offsets"] == [99]
    assert data["62"]["channel_analog_conf"]["trims"] == [9]


def test_board_keyed_afe_bias_scan_sets_bias_ctrl_and_fixed_afes():
    data = _board_data()
    cfg = _cfg(
        board_ids=["61"],
        afe_bias_ids=[0],
        fixed_afe_biases={1: 0},
        bias_ctrl=1300,
    )

    _update_afe_bias(data, 1195, cfg)

    assert data["61"]["bias_ctrl"] == 1300
    assert data["61"]["afes"]["v_biases"] == [1195, 0, 30]
    assert data["62"]["afes"]["v_biases"] == [90]
