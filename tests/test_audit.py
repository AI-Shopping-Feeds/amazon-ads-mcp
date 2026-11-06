from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

from amazon_ads_mcp.audit import AuditLog

from .conftest import audit_entries


def test_record_redacts_tokens(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.jsonl")
    log.record(
        op="x",
        resource="/x",
        method="PUT",
        url="u",
        request_body={"note": "Atza|secret-token", "access_token": "abc"},
    )
    [entry] = audit_entries(log.path)
    assert entry["request_body"] == {"note": "***", "access_token": "***"}


def test_find_and_tail(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.jsonl")
    ids = [log.record(op=f"op{i}", resource="/r", method="POST", url="u") for i in range(3)]
    assert log.find(ids[1])["op"] == "op1"
    assert [e["op"] for e in log.tail(2)] == ["op1", "op2"]
    assert log.find("nope") is None


def test_prune_drops_entries_past_retention(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.jsonl", retention_days=30)
    log.record(op="old", resource="/r", method="POST", url="u")
    log.record(op="new", resource="/r", method="POST", url="u")
    later = time.time() + 31 * 86400
    # Pretend the first entry is old by pruning from the future, then re-add.
    assert log.prune(now=later) == 2
    assert audit_entries(log.path) == []
    log.record(op="fresh", resource="/r", method="POST", url="u")
    assert log.prune() == 0
    assert [e["op"] for e in audit_entries(log.path)] == ["fresh"]


def test_zero_retention_keeps_everything(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.jsonl", retention_days=0)
    log.record(op="x", resource="/r", method="POST", url="u")
    assert log.prune(now=time.time() + 10_000 * 86400) == 0


def test_purge(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.jsonl")
    log.record(op="x", resource="/r", method="POST", url="u")
    assert log.purge() is True
    assert not log.path.exists()
    assert log.purge() is False


def test_log_file_and_new_folders_are_owner_only(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "new" / "logs" / "audit.jsonl", retention_days=1)
    log.record(op="x", resource="/r", method="PUT", url="u")
    old = {"audit_id": "old", "ts": time.time() - 5 * 86400}
    with log.path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(old) + "\n")
    assert log.prune() == 1
    if os.name == "posix":
        assert stat.S_IMODE(log.path.stat().st_mode) == 0o600
        assert stat.S_IMODE(log.path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE((tmp_path / "new").stat().st_mode) == 0o700
