"""The read-only attribute is the write-protect tab: repack refuses it."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from conftest import current_bundle

from shardcore.mutable import MutableBundle, repack_atomic


def test_repack_refuses_a_read_only_target(tmp_path: Path) -> None:
    shard = current_bundle(tmp_path / "locked.shard")
    before = shard.read_bytes()
    bundle = MutableBundle.load(shard)
    os.chmod(shard, stat.S_IREAD)
    try:
        with pytest.raises(PermissionError, match="read-only"):
            repack_atomic(bundle, shard)
        assert shard.read_bytes() == before
        assert list(tmp_path.glob("*.tmp")) == []
    finally:
        os.chmod(shard, stat.S_IREAD | stat.S_IWRITE)
