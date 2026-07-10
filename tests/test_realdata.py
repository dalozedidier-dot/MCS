from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcs.realdata import (
    DATASETS,
    catalogue,
    dataset_root,
    register_local_dataset,
    verify_provenance,
)


def test_catalogue_contains_only_declared_real_sources() -> None:
    assert set(DATASETS) == {"metropt3", "hydraulic", "ims_bearings"}
    assert all("real" in spec.status for spec in DATASETS.values())
    assert all(spec.source_url.startswith("https://") for spec in DATASETS.values())
    assert len(catalogue()) == 3


def test_unknown_dataset_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        dataset_root(tmp_path, "invented")


def test_local_registration_is_hashed_and_verifiable(tmp_path: Path) -> None:
    source = tmp_path / "measurement.csv"
    source.write_text("timestamp,value\n2020-01-01,1.2\n", encoding="utf-8")
    root = register_local_dataset("metropt3", source, tmp_path / "real")
    manifest = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    assert manifest["dataset"]["slug"] == "metropt3"
    assert manifest["files"][0]["sha256"]
    assert verify_provenance(root)["ok"] is True


def test_provenance_detects_modified_source(tmp_path: Path) -> None:
    source = tmp_path / "measurement.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    root = register_local_dataset("hydraulic", source, tmp_path / "real")
    copied = root / "raw" / source.name
    copied.write_text("a,b\n1,999\n", encoding="utf-8")
    assert verify_provenance(root)["ok"] is False
