"""Verify Git LFS payloads against committed pointers and validate ZIP archives."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile

DATASETS = (
    "datasets/archive (3).zip",
    "datasets/archive (4).zip",
    "datasets/archive (5).zip",
    "datasets/jobs.zip",
    "datasets/db_31_0_csv.zip",
    "datasets/ESCO dataset - v1.2.1 - classification - fr - csv.zip",
)
POINTER_RE = re.compile(
    rb"version https://git-lfs.github.com/spec/v1\\n"
    rb"oid sha256:([0-9a-f]{64})\\n"
    rb"size ([0-9]+)\\n?"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def committed_pointer(path: str) -> tuple[str, int]:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        check=True,
        capture_output=True,
    )
    match = POINTER_RE.fullmatch(result.stdout)
    if match is None:
        raise ValueError(f"{path}: committed Git object is not a valid LFS pointer")
    return match.group(1).decode("ascii"), int(match.group(2))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest: dict[str, dict[str, str | int]] = {}
    failures: list[str] = []

    for relative in DATASETS:
        path = root / relative
        if not path.is_file():
            failures.append(f"missing dataset: {relative}")
            continue
        try:
            expected_hash, expected_size = committed_pointer(relative)
        except (subprocess.CalledProcessError, ValueError) as exc:
            failures.append(str(exc))
            continue

        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != expected_size:
            failures.append(
                f"{relative}: size mismatch (expected {expected_size}, got {actual_size})"
            )
        if actual_hash != expected_hash:
            failures.append(f"{relative}: SHA-256 mismatch (LFS payload absent or corrupted)")
        try:
            with ZipFile(path) as archive:
                bad_member = archive.testzip()
                if bad_member is not None:
                    failures.append(f"{relative}: corrupted ZIP member {bad_member}")
        except (BadZipFile, OSError) as exc:
            failures.append(f"{relative}: invalid ZIP archive ({exc})")

        manifest[relative] = {
            "size_bytes": actual_size,
            "sha256": actual_hash,
            "lfs_oid_verified": actual_hash == expected_hash,
        }

    output = root / "datasets" / "MANIFEST.json"
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\\n",
        encoding="utf-8",
    )
    if failures:
        print("\\n".join(failures), file=sys.stderr)
        return 1
    print(f"Verified {len(manifest)} Git LFS archives (SHA-256, size and ZIP integrity).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
