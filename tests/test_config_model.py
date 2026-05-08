from pathlib import Path

from pds.core.config_model import ScanConfig
from pds.core.plan import load_config


def test_threshold_fallbacks():
    cfg = ScanConfig(
        mode="thrscan",
        drunc_working_dir=Path("/tmp"),
        oks_file="ok.xml",
        daphne_details="details.json",
        min_self_trigger_threshold=10,
        max_self_trigger_threshold=12,
        self_trigger_threshold_step=2,
    )
    assert cfg.thresholds() == (10, 12, 2)


def test_threshold_deprecated_keys():
    cfg = ScanConfig(
        mode="thrscan",
        drunc_working_dir=Path("/tmp"),
        oks_file="ok.xml",
        daphne_details="details.json",
        min_corr=5,
        max_corr=9,
        corr_step=2,
    )
    assert cfg.thresholds() == (5, 9, 2)


def test_att_range_defaults():
    cfg = ScanConfig(
        mode="attscan",
        drunc_working_dir=Path("/tmp"),
        oks_file="ok.xml",
        daphne_details="details.json",
    )
    assert cfg.att_range() == (0, 0, 1)


def test_nested_sections_flattened():
    tmp_cfg = Path("tests/tmp_nested_conf.json")
    tmp_cfg.parent.mkdir(exist_ok=True)
    tmp_cfg.write_text(
        """
{
  "mode": "sthscan",
  "paths": {
    "drunc_working_dir": "/tmp/work",
    "daphne_details": "details.json",
    "oks_file": "ok.xml"
  },
  "scan": {
    "thresholds": {"min": 5, "max": 9, "step": 2},
    "mask_values": [3]
  }
}
"""
    )
    cfg = load_config(tmp_cfg)
    assert cfg.drunc_working_dir == Path("/tmp/work")
    assert cfg.thresholds() == (5, 9, 2)
    assert cfg.masks() == [3]
    tmp_cfg.unlink()


def test_led_intensity_scan_from_run_defaults():
    cfg = load_config(Path("configs/vd_coldbox/06_led_calib.json"))
    assert cfg.mode == "calibrun"
    assert cfg.masks() == [1, 2, 4, 8]
    assert cfg.led_intensities() == [3000, 3500, 4000, 4095]
    assert cfg.dailycalib_entries() == [
        {"mask": 1, "intensities": [3000, 3500, 4000, 4095]},
        {"mask": 2, "intensities": [3000, 3500, 4000, 4095]},
        {"mask": 4, "intensities": [3000, 3500, 4000, 4095]},
        {"mask": 8, "intensities": [3000, 3500, 4000, 4095]},
    ]


def test_run_defaults_infers_facility_from_path():
    cfg = load_config(Path("configs/vd_coldbox/02_run_defaults.json"), mode_override="calibrun")
    assert cfg.drunc_working_dir == Path("/nfs/sw/dunedaq/dunedaq-fddaq-v5.5.0-dev-pds")
    assert cfg.masks() == [4]


def test_afe_bias_scan_config_from_vd_coldbox_sample():
    cfg = load_config(Path("configs/vd_coldbox/10_afe_bias_led_scan_np02_ssp.json"))
    assert cfg.mode == "afebiasscan"
    assert cfg.board_ids == ["61"]
    assert cfg.afe_bias_ids == [0]
    assert cfg.fixed_afe_biases == {1: 0, 2: 0, 3: 0, 4: 0}
    assert cfg.bias_ctrl == 1300
    assert cfg.afe_biases() == [1143, 1169, 1195]
    assert cfg.dailycalib_entries() == [{"mask": 4, "intensities": [4095]}]
