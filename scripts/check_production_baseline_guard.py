#!/usr/bin/env python3
"""Read-only accidental-change guard for TAS[N]IM production baseline.

These are the approved baseline Git-blob hashes at the start of candidate
infra/field-data hardening. This detects *accidental* file drift, not a
malicious contributor who also edits this guard. Review explicitly before
changing a frozen baseline; NEVER auto-deploy LIVE from this check.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN_GIT_BLOBS = {
    "database.rules.json": "999512e5568d5ab67ef8010b15b4c558bdd889ea",
    "firebase.json": "6231afded8dc61b03a062ef4bd5b4473d19dc74a",
    "tasnim.config.json": "b5b0044164d87288e5c3aec9a354a042e813fa5d",
    "src/services/firebase.js": "057045359175d58b0317b76845b38c85d4be7a01",
}


class ProductionBaselineChanged(RuntimeError):
    """A protected production file has drifted from its reviewed baseline."""


def git_blob_hash(data: bytes) -> str:
    """Compute Git's content hash without invoking shell, network or Git."""
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
    ).hexdigest()


def verify_production_baseline(root: Path = ROOT) -> tuple[str, ...]:
    """Read-only; fail if any protected file is missing, linked, or changed."""
    verified = []
    for relative, expected_sha in FROZEN_GIT_BLOBS.items():
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ProductionBaselineChanged(
                "production_baseline:missing_or_symlink:" + relative
            )
        if git_blob_hash(path.read_bytes()) != expected_sha:
            raise ProductionBaselineChanged(
                "production_baseline:unexpected_change:" + relative
            )
        verified.append(relative)
    return tuple(verified)


if __name__ == "__main__":
    checked = verify_production_baseline()
    print("[PASS] Frozen production file baseline unchanged:", len(checked))
    print("[SAFE] Read-only; no Firebase LIVE access, deploy or firmware changes")
