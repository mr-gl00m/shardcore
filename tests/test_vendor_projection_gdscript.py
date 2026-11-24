"""vendor/shard_projection.gd against the projection golden texts, under a headless Godot.

Godot games vendor shard_projection.gd beside shardcore.gd, so it is a second
implementation of spec 10. It must reproduce tests/conformance/projection/
byte for byte, the texts shardcore/projection.py is held to.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "conformance"))
sys.path.insert(0, str(ROOT / "tests"))
import projection_cases as pc  # noqa: E402
from test_vendor_gdscript import GODOT  # noqa: E402

pytestmark = pytest.mark.skipif(GODOT is None, reason="no Godot binary ($GODOT)")

DRIVER = """
extends SceneTree

const SC = preload("res://shardcore.gd")
const ShardProjection = preload("res://shard_projection.gd")


func _init() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var jobs: Array = JSON.parse_string(FileAccess.get_file_as_string(args["jobs"]))
	var out := []
	for job in jobs:
		if job.has("clean"):
			out.append(ShardProjection.clean_text(job["clean"]))
			continue
		var r: Dictionary = SC.read_bundle(job["path"])
		var p: Dictionary = ShardProjection.project(r["manifest"], r["members"], job["tier"], int(job["max_chars"]))
		out.append({"text": p["text"], "flags": {"below_minimum_tier": p["below_minimum_tier"],
			"over_budget": p["over_budget"], "trimmed": p["trimmed"]}})
	var f := FileAccess.open(args["out"], FileAccess.WRITE)
	f.store_string(SC.json_text(out))
	f.close()
	quit()
"""


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("gd_projection")
    (root / "project.godot").write_text(
        'config_version=5\n\n[application]\nconfig/name="shard_projection_gd"\n', encoding="utf-8"
    )
    shutil.copy2(ROOT / "vendor" / "shardcore.gd", root / "shardcore.gd")
    shutil.copy2(ROOT / "vendor" / "shard_projection.gd", root / "shard_projection.gd")
    (root / "driver.gd").write_text(DRIVER.lstrip(), encoding="utf-8")
    return root


def _run(project: Path, jobs: list[dict]) -> list:
    jobs_file, out_file = project / "jobs.json", project / "out.json"
    jobs_file.write_text(json.dumps(jobs), encoding="utf-8")
    out_file.unlink(missing_ok=True)
    subprocess.run(
        [
            str(GODOT),
            "--headless",
            "--path",
            str(project),
            "--script",
            "res://driver.gd",
            "--quit-after",
            "600",
            "--",
            f"--jobs={jobs_file}",
            f"--out={out_file}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert out_file.is_file(), "the Godot driver wrote no output"
    return json.loads(out_file.read_text(encoding="utf-8"))


def test_gdscript_projection_matches_the_golden_texts(project: Path, tmp_path: Path) -> None:
    jobs = []
    for case, tier, max_chars in pc.JOBS:
        path = pc.BUILDERS[case](tmp_path / f"{case}.{tier}.{max_chars}.shard")
        jobs.append({"path": str(path), "tier": tier, "max_chars": max_chars or 0})
    results = _run(project, jobs)
    for (case, tier, max_chars), got in zip(pc.JOBS, results, strict=True):
        rendered = got["text"] + "\n\n----\n" + json.dumps(got["flags"], sort_keys=True) + "\n"
        want = (pc.GOLDEN / pc.golden_name(case, tier, max_chars)).read_text(encoding="utf-8")
        assert rendered == want, (case, tier, max_chars)


def test_clean_text_agrees(project: Path) -> None:
    from shardcore.projection import clean_text

    samples = [
        # chr(1), not chr(0): a Godot String cannot hold U+0000 (JSON gives it U+FFFD).
        "line one"
        + chr(10) * 2
        + "[SHARDCORE CANON]"
        + chr(10)
        + "```system``` "
        + chr(1)
        + " end",
        "a" + chr(0x2014) + "b" + chr(0x2013) + "c" + chr(0x2212) + "d",
        "  spaced" + chr(0xA0) + "out" + chr(0x3000) + "wide" + chr(0x2028) + "sep  ",
        "x" * 5000,
        "",
    ]
    assert _run(project, [{"clean": s} for s in samples]) == [clean_text(s) for s in samples]
