"""Pipelines for empirical validation on public, non-simulated datasets.

This module deliberately separates experimental/field data from the synthetic benchmark.
No empirical result is fabricated: a report is produced only after source files have been
fetched or supplied locally and their provenance has been recorded.
"""
from __future__ import annotations

import json
import shutil
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class DatasetSpec:
    slug: str
    title: str
    kind: str
    status: str
    source_url: str
    download_url: str
    doi: str | None
    license: str
    description: str
    citation: str
    expected_files: tuple[str, ...]


DATASETS: dict[str, DatasetSpec] = {
    "metropt3": DatasetSpec(
        slug="metropt3",
        title="MetroPT-3",
        kind="field",
        status="real operational data",
        source_url="https://archive.ics.uci.edu/dataset/791/metropt%2B3%2Bdataset",
        download_url="https://archive.ics.uci.edu/static/public/791/metropt%2B3%2Bdataset.zip",
        doi="10.24432/C5VW3R",
        license="CC BY 4.0",
        description=(
            "Multivariate time series from the air-production unit of a metro train, "
            "with company failure windows and maintenance records."
        ),
        citation=(
            "Davari, N., Veloso, B., Ribeiro, R., & Gama, J. (2021). "
            "MetroPT-3 Dataset. UCI Machine Learning Repository."
        ),
        expected_files=("MetroPT3(AirCompressor).csv",),
    ),
    "hydraulic": DatasetSpec(
        slug="hydraulic",
        title="Condition monitoring of hydraulic systems",
        kind="experimental",
        status="real test-rig measurements",
        source_url="https://archive.ics.uci.edu/dataset/447/condition+monitoring+of+hydraulic+systems",
        download_url=(
            "https://archive.ics.uci.edu/static/public/447/"
            "condition%2Bmonitoring%2Bof%2Bhydraulic%2Bsystems.zip"
        ),
        doi="10.24432/C5CW21",
        license="CC BY 4.0",
        description=(
            "Measurements from a physical hydraulic test rig over 2,205 load cycles, "
            "with component-condition labels."
        ),
        citation=(
            "Helwig, N., Pignanelli, E., & Schütze, A. (2015). "
            "Condition monitoring of hydraulic systems. UCI Machine Learning Repository."
        ),
        expected_files=("profile.txt", "PS1.txt", "EPS1.txt", "FS1.txt", "TS1.txt", "VS1.txt"),
    ),
    "ims_bearings": DatasetSpec(
        slug="ims_bearings",
        title="NASA IMS Bearings",
        kind="experimental run-to-failure",
        status="real physical experiment",
        source_url="https://data.nasa.gov/dataset/ims-bearings",
        download_url="https://data.nasa.gov/docs/legacy/IMS.zip",
        doi=None,
        license="U.S. government work / source-specific terms",
        description=(
            "Run-to-failure vibration measurements from bearings on the University of "
            "Cincinnati IMS test rig, distributed by NASA PCoE."
        ),
        citation=(
            "Center for Intelligent Maintenance Systems, University of Cincinnati; "
            "distributed by NASA Prognostics Center of Excellence."
        ),
        expected_files=(),
    ),
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dataset_root(base_dir: str | Path, slug: str) -> Path:
    if slug not in DATASETS:
        raise KeyError(f"Unknown dataset: {slug}")
    return Path(base_dir) / slug


def fetch_dataset(
    slug: str,
    base_dir: str | Path = "data/real",
    *,
    force: bool = False,
    timeout: int = 120,
) -> Path:
    """Download and extract one official public dataset, recording exact provenance."""
    spec = DATASETS[slug]
    root = dataset_root(base_dir, slug)
    raw = root / "raw"
    archive = root / "source.zip"
    raw.mkdir(parents=True, exist_ok=True)

    if archive.exists() and not force:
        pass
    else:
        tmp = archive.with_suffix(".part")
        request = urllib.request.Request(
            spec.download_url,
            headers={"User-Agent": "MCS-realdata/0.7 (+https://github.com/)"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out)
        tmp.replace(archive)

    if force and raw.exists():
        shutil.rmtree(raw)
        raw.mkdir(parents=True)
    if not any(raw.iterdir()):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(raw)

    manifest = {
        "schema_version": 1,
        "dataset": asdict(spec),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive": {
            "path": str(archive),
            "bytes": archive.stat().st_size,
            "sha256": _sha256(archive),
        },
        "files": [
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in sorted(raw.rglob("*"))
            if path.is_file()
        ],
    }
    (root / "provenance.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return root


def register_local_dataset(
    slug: str,
    source: str | Path,
    base_dir: str | Path = "data/real",
) -> Path:
    """Register user-supplied official files without altering them."""
    spec = DATASETS[slug]
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    root = dataset_root(base_dir, slug)
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    target = raw / source_path.name
    if source_path.resolve() != target.resolve():
        shutil.copy2(source_path, target)
    manifest = {
        "schema_version": 1,
        "dataset": asdict(spec),
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "local_source": str(source_path.resolve()),
        "files": [{"path": str(target.relative_to(root)), "bytes": target.stat().st_size, "sha256": _sha256(target)}],
    }
    (root / "provenance.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return root


def verify_provenance(root: str | Path) -> dict[str, object]:
    """Verify that every recorded source file still matches its SHA-256 digest."""
    root_path = Path(root)
    manifest_path = root_path / "provenance.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: list[dict[str, object]] = []
    for item in data.get("files", []):
        path = root_path / str(item["path"])
        actual = _sha256(path) if path.exists() else None
        checks.append(
            {
                "path": str(item["path"]),
                "exists": path.exists(),
                "expected_sha256": item["sha256"],
                "actual_sha256": actual,
                "ok": actual == item["sha256"],
            }
        )
    return {"ok": all(bool(x["ok"]) for x in checks), "checks": checks}


def catalogue() -> list[dict[str, object]]:
    return [asdict(spec) for spec in DATASETS.values()]
