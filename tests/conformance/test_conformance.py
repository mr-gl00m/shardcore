"""Drive the reference conformance suite (spec section 13) through this reader."""

from __future__ import annotations

from pathlib import Path

import pytest
from cases import CASES, SPEC_VERSION, Case

from shardcore.bundle import read_bundle
from shardcore.diagnose import diagnose


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_conformance_case(case: Case, tmp_path: Path) -> None:
    shard = case.build(tmp_path / f"{case.name}.shard")
    state = read_bundle(shard)
    assert state.readable == case.readable, f"{case.name}: readable={state.readable}"

    diag = diagnose(state, SPEC_VERSION)
    codes = {f.code for f in diag.findings}

    if case.status is not None:
        assert diag.status == case.status, f"{case.name}: status={diag.status}, findings={codes}"
    if case.findings_empty:
        drift = {f.code for f in diag.findings if f.severity != "info"}
        assert not drift, f"{case.name}: expected no drift findings, got {drift}"
    missing = case.codes_include - codes
    assert not missing, f"{case.name}: expected findings absent: {missing}"
    forbidden = case.codes_exclude & codes
    assert not forbidden, f"{case.name}: forbidden findings present: {forbidden}"


def test_emit_writes_every_fixture(tmp_path: Path) -> None:
    from cases import emit_all

    written = emit_all(tmp_path / "fixtures")
    names = {p.name for p in written}
    assert "expectations.json" in names
    assert len([n for n in names if n.endswith(".shard")]) == len(CASES)
