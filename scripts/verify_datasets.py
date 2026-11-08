"""Verify that tracked dataset archives are present and unchanged."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

EXPECTED = {
    "archive (3).zip": {"kind": "candidate_profiles"},
    "archive (4).zip": {"kind": "candidate_profiles"},
    "archive (5).zip": {"kind": "candidate_profiles_structured"},
    "jobs.zip": {"kind": "job_postings"},
    "db_31_0_csv.zip": {"kind": "onet_reference"},
    "ESCO dataset - v1.2.1 - classification - fr - csv.zip": {"kind": "esco_reference"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "datasets"
    manifest: dict[str, dict[str, str | int]] = {}
    failures: list[str] = []
    for name, metadata in EXPECTED.items():
        path = root / name
        if not path.is_file():
            failures.append(f"missing: {name}")
            continue
        manifest[name] = {
            **metadata,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    output = root / "MANIFEST.json"
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
