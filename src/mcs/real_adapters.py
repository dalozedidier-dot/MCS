"""Dataset-specific adapters for public measured datasets.

Proxy recipes are explicit engineering hypotheses. They are fitted on calibration data
only and must be frozen in a protocol before validation results are interpreted.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .empirical import EmpiricalRecord, records_from_series
from .empirical_evidence import EventWindow, robust_unit
from .proxy_recipes import (
    complete_case_numeric,
    hydraulic_events_from_profile,
    hydraulic_proxies,
    metropt3_proxies,
)
from .realdata import verify_provenance


@dataclass(frozen=True)
class PreparedRealSeries:
    dataset: str
    timestamps: tuple[str, ...]
    L: np.ndarray
    R: np.ndarray
    B: np.ndarray
    events: tuple[EventWindow, ...]
    calibration_end: int
    validation_start: int
    source_sha256: str
    metadata: dict[str, Any]


def prepared_to_records(prepared: PreparedRealSeries) -> list[EmpiricalRecord]:
    """Project a prepared series onto the official empirical CSV schema.

    Event flags are the externally documented windows already attached to the
    prepared series. No new label is created here.
    """
    flags = [False] * len(prepared.L)
    for event in prepared.events:
        for index in range(event.start, min(event.end + 1, len(flags))):
            flags[index] = True
    return records_from_series(
        prepared.timestamps,
        prepared.L.tolist(),
        prepared.R.tolist(),
        prepared.B.tolist(),
        flags,
    )


def _require_integrity(root: Path) -> dict[str, Any]:
    result = verify_provenance(root)
    if not bool(result["ok"]):
        raise ValueError(f"provenance verification failed for {root}")
    loaded = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("invalid provenance manifest")
    return loaded


def _archive_sha(manifest: dict[str, Any]) -> str:
    archive = manifest.get("archive") or {}
    value = archive.get("sha256")
    if not value:
        files = manifest.get("files", [])
        value = files[0]["sha256"] if files else "unknown"
    return str(value)


def _find_one(root: Path, pattern: str) -> Path:
    matches = sorted(root.rglob(pattern))
    if not matches:
        raise FileNotFoundError(f"{pattern} not found below {root}")
    return matches[0]


def prepare_metropt3(root: str | Path, *, freq: str = "15min") -> PreparedRealSeries:
    root_path = Path(root)
    manifest = _require_integrity(root_path)
    csv_path = _find_one(root_path / "raw", "MetroPT3*.csv")
    df = pd.read_csv(csv_path)
    if "timestamp" not in df.columns:
        raise ValueError("MetroPT-3 timestamp column not found")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").set_index("timestamp")
    numeric = df.select_dtypes(include=["number"]).resample(freq).mean()
    required = {"Motor_current", "TP2", "TP3", "DV_pressure"}
    missing = sorted(required - set(numeric.columns))
    if missing:
        raise ValueError(f"MetroPT-3 required columns missing: {missing}")

    used_columns = sorted(
        required
        | ({"COMP"} if "COMP" in numeric.columns else set())
        | ({"Oil_temperature"} if "Oil_temperature" in numeric.columns else set())
    )
    numeric, rows_dropped_missing = complete_case_numeric(numeric, used_columns)
    if len(numeric) < 40:
        raise ValueError("MetroPT-3 has too few complete resampled observations")

    split_time = pd.Timestamp("2020-03-01T00:00:00Z")
    fit = np.asarray(numeric.index < split_time, dtype=bool)
    L, R, B = metropt3_proxies(numeric, fit)

    event_specs = [
        ("2020-04-18T00:00:00Z", "2020-04-18T23:59:59Z", "air_leak_high_stress"),
        ("2020-05-29T23:30:00Z", "2020-05-30T06:00:00Z", "air_leak_high_stress"),
        ("2020-06-05T10:00:00Z", "2020-06-07T14:30:00Z", "air_leak_high_stress"),
        ("2020-07-15T14:30:00Z", "2020-07-15T19:00:00Z", "air_leak_high_stress"),
    ]
    events: list[EventWindow] = []
    for start, end, label in event_specs:
        start_i = int(numeric.index.searchsorted(pd.Timestamp(start)))
        end_i = int(numeric.index.searchsorted(pd.Timestamp(end), side="right") - 1)
        if 0 <= start_i < len(numeric):
            events.append(EventWindow(start_i, min(end_i, len(numeric) - 1), label))
    split_idx = int(numeric.index.searchsorted(split_time))
    return PreparedRealSeries(
        dataset="metropt3",
        timestamps=tuple(x.isoformat() for x in numeric.index),
        L=L,
        R=R,
        B=B,
        events=tuple(events),
        calibration_end=split_idx,
        validation_start=split_idx,
        source_sha256=_archive_sha(manifest),
        metadata={
            "frequency": freq,
            "proxy_recipe": "metropt3_v1_engineering_hypothesis",
            "raw_rows": int(len(df)),
            "prepared_rows": int(len(numeric)),
            "rows_dropped_missing": int(rows_dropped_missing),
            "missing_data_policy": "complete_case_after_resampling_no_value_imputation",
            "columns_used": used_columns,
            "event_source": "company failure windows published with the dataset",
        },
    )


def prepare_hydraulic(root: str | Path) -> PreparedRealSeries:
    root_path = Path(root)
    manifest = _require_integrity(root_path)
    raw = root_path / "raw"
    profile = np.loadtxt(_find_one(raw, "profile.txt"))
    if profile.ndim != 2 or profile.shape[1] < 5:
        raise ValueError("unexpected hydraulic profile format")
    sensors: dict[str, np.ndarray] = {}
    for name in ("PS1", "EPS1", "FS1", "TS1", "VS1", "CE", "CP", "SE"):
        path = _find_one(raw, f"{name}.txt")
        values = np.loadtxt(path)
        sensors[name] = values.mean(axis=1) if values.ndim == 2 else values
    n = len(profile)
    if any(len(x) != n for x in sensors.values()):
        raise ValueError("hydraulic sensor/profile length mismatch")
    split = int(round(n * 0.5))
    fit = np.arange(n) < split
    L, R, B = hydraulic_proxies(sensors, fit)
    events = list(hydraulic_events_from_profile(profile))
    return PreparedRealSeries(
        dataset="hydraulic",
        timestamps=tuple(str(i) for i in range(n)),
        L=L,
        R=R,
        B=B,
        events=tuple(events),
        calibration_end=split,
        validation_start=split,
        source_sha256=_archive_sha(manifest),
        metadata={
            "proxy_recipe": "hydraulic_v1_cycle_aggregates",
            "prepared_rows": n,
            "columns_used": sorted(sensors),
            "event_source": "profile.txt component-condition labels",
            "interpretation_warning": "cycles are ordered measurements; this is state-transition/discrimination evidence, not a natural run-to-failure chronology",
        },
    )


def _extract_rar(path: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    commands = []
    if shutil.which("7z"):
        commands.append(["7z", "x", "-y", f"-o{target}", str(path)])
    if shutil.which("unrar"):
        commands.append(["unrar", "x", "-o+", str(path), str(target)])
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return
    raise RuntimeError("IMS .rar extraction requires 7z or unrar")


def prepare_ims_bearings(root: str | Path, *, test_name: str = "2nd_test") -> PreparedRealSeries:
    root_path = Path(root)
    manifest = _require_integrity(root_path)
    rar = _find_one(root_path / "raw", f"{test_name}.rar")
    extracted = root_path / "extracted" / test_name
    if not any(extracted.rglob("*")):
        _extract_rar(rar, extracted)
    files = [p for p in extracted.rglob("*") if p.is_file() and not p.name.startswith(".")]
    if not files:
        raise FileNotFoundError("no IMS measurement files extracted")
    rows: list[tuple[str, float, float, float]] = []
    for path in sorted(files, key=lambda p: p.name):
        try:
            data = np.loadtxt(path)
        except (ValueError, OSError):
            continue
        if data.ndim == 1:
            data = data[:, None]
        rms_value = float(np.mean(np.sqrt(np.mean(np.square(data), axis=0))))
        peak_value = float(np.mean(np.max(np.abs(data), axis=0)))
        crest_value = peak_value / max(rms_value, 1e-12)
        if data.shape[1] > 1:
            corr = np.corrcoef(data.T)
            upper = corr[np.triu_indices_from(corr, k=1)]
            agreement = float(np.nanmean(np.abs(upper))) if upper.size else 1.0
        else:
            agreement = 1.0
        rows.append((path.name, rms_value, crest_value, agreement))
    if len(rows) < 50:
        raise ValueError("too few IMS measurements after extraction")
    names = tuple(x[0] for x in rows)
    rms_values = np.asarray([x[1] for x in rows], dtype=float)
    crest_values = np.asarray([x[2] for x in rows], dtype=float)
    agreement_values = np.asarray([x[3] for x in rows], dtype=float)
    split = int(round(len(rows) * 0.5))
    fit = np.arange(len(rows)) < split
    L = robust_unit(rms_values, fit)
    R = np.asarray(np.clip(1.0 - robust_unit(crest_values, fit), 0, 1), dtype=float)
    B = np.asarray(np.clip(robust_unit(agreement_values, fit), 0, 1), dtype=float)
    end = len(rows) - 1
    events = (EventWindow(end, end, f"documented_{test_name}_run_termination"),)
    return PreparedRealSeries(
        dataset=f"ims_bearings_{test_name}",
        timestamps=names,
        L=L,
        R=R,
        B=B,
        events=events,
        calibration_end=split,
        validation_start=split,
        source_sha256=_archive_sha(manifest),
        metadata={
            "proxy_recipe": "ims_v1_vibration_features",
            "prepared_rows": len(rows),
            "test_name": test_name,
            "event_source": "documented run-to-failure experiment termination",
            "interpretation_warning": "the precise onset of damage is not used as a label; only the externally documented endpoint is used",
        },
    )
