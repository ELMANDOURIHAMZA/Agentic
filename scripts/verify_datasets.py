"""Verify Git LFS payloads against committed pointers and expected metadata."""

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
EXPECTED = {
    "archive (3).zip": {
        "kind": "candidate_profiles",
        "size_bytes": 65529677,
        "sha256": "b12c4ab34df707ad2cc64312c016509cad9b6c93b0baed7a6a2c7cbd6b2b7aa4",
    },
    "archive (4).zip": {
        "kind": "candidate_profiles",
        "size_bytes": 2139570691,
        "sha256": "0532e7a54ad10c73fb242b4e607a683d8f52867d4d8131642f9dbea656b0b1a4",
    },
    "archive (5).zip": {
        "kind": "candidate_profiles_structured",
        "size_bytes": 39830263,
        "sha256": "6232e7c6f8552bf8e4b3ad1b5a60196fb377f18b97b5ff058731159a36f4769e",
    },
    "jobs.zip": {
        "kind": "job_postings",
        "size_bytes": 166472808,
        "sha256": "4890ecccfdbd6b7ec0e57af6012cae2e960ba74c10702f5957be365469acc7a4",
    },
    "db_31_0_csv.zip": {
        "kind": "onet_reference",
        "size_bytes": 16237378,
        "sha256": "55033fc68b4c13ec23e7f74dc6378660f6e854e75d55d6e333ae0a761d3987cd",
    },
    "ESCO dataset - v1.2.1 - classification - fr - csv.zip": {
        "kind": "esco_reference",
        "size_bytes": 9098505,
        "sha256": "84fe49774fad90bdfd27d080440ffb1fdef1fbd62939f6436d2fc21f4d58d4e8",
    },
}
POINTER_RE = re.compile(
    rb"version https://git-lfs.github.com/spec/v1\n"
    rb"oid sha256:([0-9a-f]{64})\n"
    rb"size ([0-9]+)\n?"
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
    manifest: dict[str, dict[str, str | int | bool]] = {}
    failures: list[str] = []

    for relative in DATASETS:
        name = Path(relative).name
        path = root / relative
        metadata = EXPECTED[name]
        if not path.is_file():
            failures.append(f"missing dataset: {relative}")
            continue
        try:
            pointer_hash, pointer_size = committed_pointer(relative)
        except (subprocess.CalledProcessError, ValueError) as exc:
            failures.append(str(exc))
            continue

        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        expected_size = metadata["size_bytes"]
        expected_hash = metadata["sha256"]
        if actual_size != pointer_size or actual_size != expected_size:
            failures.append(f"{relative}: size mismatch")
        if actual_hash != pointer_hash or actual_hash != expected_hash:
            failures.append(f"{relative}: SHA-256 mismatch (LFS payload absent or corrupted)")
        try:
            with ZipFile(path) as archive:
                bad_member = archive.testzip()
                if bad_member is not None:
                    failures.append(f"{relative}: corrupted ZIP member {bad_member}")
        except (BadZipFile, OSError) as exc:
            failures.append(f"{relative}: invalid ZIP archive ({exc})")

        manifest[name] = {
            **metadata,
            "size_bytes": actual_size,
            "sha256": actual_hash,
            "lfs_oid_verified": actual_hash == pointer_hash,
        }

    output = root / "datasets" / "MANIFEST.json"
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Verified {len(manifest)} Git LFS archives (SHA-256, size and ZIP integrity).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
