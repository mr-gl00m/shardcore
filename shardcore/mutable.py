"""In-memory mutable view of a bundle, plus the atomic repack.

This is the library's writer. The full safety envelope (backup, verify,
restore-on-failure, audit log) belongs to a batch tool that wraps this layer;
on its own the writer guarantees two things: a repack is atomic (temp file +
os.replace in the target's own directory) and nothing is ever extracted to the
filesystem, so there is no zip-slip surface.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from .bundle import MAX_BUNDLE_BYTES


class MigrationError(Exception):
    """A migration cannot proceed without guessing or losing data."""


class MutableBundle:
    """Raw members of one bundle, mutated by the migration chain in memory."""

    def __init__(
        self, path: Path, members: dict[str, bytes], member_times: dict[str, tuple[int, ...]]
    ):
        self.path = path
        self.members = members
        # ZIP mtimes per member; 0012 uses them to pick the newest variant.
        self.member_times = member_times
        # Members removed from the bundle; the apply engine writes these next
        # to the backup. Nothing is ever deleted outright.
        self.displaced: dict[str, bytes] = {}
        # Human-readable trail of what each migration actually did.
        self.notes: list[str] = []

    @classmethod
    def load(cls, path: Path) -> MutableBundle:
        if path.stat().st_size > MAX_BUNDLE_BYTES:
            raise MigrationError("bundle exceeds size cap")
        with zipfile.ZipFile(path, "r") as archive:
            infos = [i for i in archive.infolist() if not i.filename.endswith("/")]
            members = {i.filename: archive.read(i.filename) for i in infos}
            times: dict[str, tuple[int, ...]] = {i.filename: tuple(i.date_time) for i in infos}
        if "manifest.json" not in members:
            raise MigrationError("no manifest.json")
        return cls(path, members, times)

    def get_json(self, name: str) -> Any:
        data = self.members.get(name)
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MigrationError(f"{name} is not valid JSON: {exc}") from exc

    def put_json(self, name: str, obj: Any) -> None:
        self.members[name] = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")

    def manifest(self) -> dict[str, Any]:
        doc = self.get_json("manifest.json")
        if not isinstance(doc, dict):
            raise MigrationError("manifest.json is not a JSON object")
        return doc

    def rename(self, old: str, new: str) -> None:
        self.members[new] = self.members.pop(old)
        if old in self.member_times:
            self.member_times[new] = self.member_times.pop(old)

    def displace(self, name: str) -> None:
        self.displaced[name] = self.members.pop(name)

    def note(self, message: str) -> None:
        self.notes.append(message)


def repack_atomic(bundle: MutableBundle, target: Path) -> None:
    """Write the mutated members as a new .shard, atomically, over target.

    manifest.json is written first (first file read on load), then the rest
    in sorted order so repeated repacks of the same content are byte-stable.
    """
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", bundle.members["manifest.json"])
            for name in sorted(bundle.members):
                if name == "manifest.json":
                    continue
                archive.writestr(name, bundle.members[name])
        _replace_with_retry(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _replace_with_retry(src: Path, dst: Path) -> None:
    # shortcut: fixed three-try backoff for AV/cloud-sync locks on Windows
    # (spec section 9 save discipline); a scheduler-aware retry is not worth it here.
    for delay in (0.2, 0.8, None):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if delay is None:
                raise
            time.sleep(delay)
