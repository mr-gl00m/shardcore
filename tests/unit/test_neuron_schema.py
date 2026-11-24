"""The neuron pillar is stamped by the version its document declares."""

from __future__ import annotations

import json

from shardcore import read_bundle_document
from shardcore.brain import Brain
from shardcore.builder import build_bundle
from shardcore.bundle import read_bundle
from shardcore.core import build_files_info
from shardcore.diagnose import diagnose
from shardcore.registry import NEURON_SCHEMAS, PILLAR_SCHEMAS, SPEC_VERSION, schema_for_member

SOUL = {
    "name": "Tess",
    "identity": "A test soul.",
    "personality": "Even.",
    "stat_block": dict.fromkeys(
        ("STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS"), 5
    ),
}


def test_the_id_follows_the_document_and_falls_back_to_the_registry() -> None:
    assert (
        schema_for_member("neuronshard.json")
        == PILLAR_SCHEMAS["neuronshard.json"]
        == "shardcore/neuron@1.1"
    )
    assert schema_for_member("neuronshard.json", b'{"version": "1.1"}') == "shardcore/neuron@1.1"
    assert schema_for_member("neuronshard.json", b'{"version": "1.0"}') == "shardcore/neuron@1.0"
    for odd in (b"not json", b"[]", b'{"version": 1.1}', b'{"version": "9.9"}', b"\xff\xfe", b""):
        assert schema_for_member("neuronshard.json", odd) == "shardcore/neuron@1.1", odd
    assert (
        schema_for_member("soulshard.json", b'{"version": "1.1"}')
        == PILLAR_SCHEMAS["soulshard.json"]
    )
    assert set(NEURON_SCHEMAS) == {"1.0", "1.1"}


def test_a_written_bundle_carries_the_right_id_and_reads_back_clean(tmp_path) -> None:
    brain = json.dumps(Brain.build(SOUL, {}, 1).to_dict(), indent=2).encode()
    assert (
        build_files_info({"neuronshard.json": brain})["neuronshard.json"]["schema"]
        == "shardcore/neuron@1.1"
    )

    path = tmp_path / "tess.shard"
    build_bundle(
        path,
        shard_name="Tess",
        members={"soulshard.json": json.dumps(SOUL).encode(), "neuronshard.json": brain},
    )
    doc = read_bundle_document(path)
    assert doc.manifest()["files"]["neuronshard.json"]["schema"] == "shardcore/neuron@1.1"
    assert doc.json_member("neuronshard.json")["version"] == "1.1"
    report = diagnose(read_bundle(path), SPEC_VERSION)
    assert report.status == "current", [f.detail for f in report.findings]
