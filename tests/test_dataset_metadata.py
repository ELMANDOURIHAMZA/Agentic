from pathlib import Path
from zipfile import ZipFile

DATASETS = Path(__file__).resolve().parents[1] / "datasets"


def _names(archive: str) -> set[str]:
    with ZipFile(DATASETS / archive) as source:
        return {entry.filename for entry in source.infolist()}


def test_candidate_and_job_archives_have_separate_shapes() -> None:
    profile_names = _names("archive (3).zip")
    job_names = _names("jobs.zip")
    assert any(name.endswith(".pdf") for name in profile_names)
    assert "postings.csv" in {Path(name).name for name in job_names}
    assert not profile_names.intersection(job_names)


def test_reference_archives_are_csv_based() -> None:
    for archive in ("db_31_0_csv.zip", "ESCO dataset - v1.2.1 - classification - fr - csv.zip"):
        names = _names(archive)
        assert names
        files = {name for name in names if not name.endswith("/")}
        assert files
        assert all(Path(name).suffix.casefold() in {".csv", ".txt"} for name in files)
