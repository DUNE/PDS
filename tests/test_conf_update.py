import json
from pathlib import Path

from pds.core.conf_update import apply_updates, update_conf_file


def test_apply_updates_supports_dotted_keys():
    cfg = {"a": {"b": 1}}
    result = apply_updates(cfg, {"a.b": "42", "new": "true"})
    assert result["a"]["b"] == 42
    assert result["new"] is True


def test_update_conf_file_writes_pretty_json(tmp_path):
    conf_path = tmp_path / "conf.json"
    conf_path.write_text('{"a":{"b":1}}')

    update_conf_file(
        conf_path,
        updates={"a.c": "2", "mode": "cosmics"},
        backup=True,
    )

    updated = json.loads(conf_path.read_text())
    assert updated["a"]["c"] == 2
    assert conf_path.with_suffix(".json.bak").exists()
