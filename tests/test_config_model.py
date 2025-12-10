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
