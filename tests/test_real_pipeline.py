from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from mcs.empirical import (
    evaluate_table_bundle,
    file_sha256,
    load_empirical_csv,
    write_empirical_csv,
)
from mcs.empirical_evidence import EventWindow, build_evidence_report
from mcs.proxy_recipes import hydraulic_events_from_profile, hydraulic_proxies, metropt3_proxies
from mcs.real_adapters import PreparedRealSeries, export_and_audit, prepared_to_records


def test_metropt3_schema_roundtrip_to_official_csv(tmp_path: Path) -> None:
    n = 64
    index = pd.date_range("2020-02-29T00:00:00Z", periods=n, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "Motor_current": np.linspace(0.4, 1.6, n),
            "TP2": np.linspace(1.8, 2.6, n),
            "TP3": np.linspace(1.1, 0.8, n),
            "DV_pressure": np.linspace(0.1, 0.7, n),
            "COMP": np.r_[np.ones(32), np.zeros(32)],
            "Oil_temperature": np.linspace(38.0, 52.0, n),
        },
        index=index,
    )
    split = 32
    fit = np.arange(n) < split
    L, R, B = metropt3_proxies(frame, fit)
    events = (EventWindow(50, 55, "fixture_external_window"),)
    prepared = PreparedRealSeries(
        dataset="metropt3_format_fixture",
        timestamps=tuple(ts.isoformat() for ts in index),
        L=L,
        R=R,
        B=B,
        events=events,
        calibration_end=split,
        validation_start=split,
        source_sha256="fixture-not-official",
        metadata={"kind": "schema_fixture", "not_official_evidence": True},
    )
    records = prepared_to_records(prepared)
    csv_path = write_empirical_csv(tmp_path / "metropt3_format.csv", records)
    loaded = load_empirical_csv(csv_path)
    assert len(loaded) == n
    assert sum(row.event for row in loaded) == 6
    digest = file_sha256(csv_path)
    bundle = evaluate_table_bundle(loaded, source_sha256=digest, alarm_threshold=0.15)
    assert bundle["metrics"]["source_sha256"] == digest
    assert bundle["metrics"]["n_events"] == 6
    assert bundle["debt_laws"]["n_steps"] == n
    assert bundle["negative_control"]["status"] == "ok"
    report = build_evidence_report(
        dataset=prepared.dataset,
        source_sha256=prepared.source_sha256,
        protocol_sha256="fixture-protocol",
        L=prepared.L,
        R=prepared.R,
        B=prepared.B,
        events=list(prepared.events),
        calibration_end=prepared.calibration_end,
        validation_start=prepared.validation_start,
        horizon=8,
        target_fpr=0.20,
        limitations=("Format fixture only. Not an official MetroPT-3 result.",),
    )
    assert report.n_steps == n
    assert report.detectors
    payload = tmp_path / "bundle.json"
    payload.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    assert payload.exists()


def test_hydraulic_schema_pipeline_uses_profile_labels() -> None:
    n = 80
    sensors = {
        "PS1": np.linspace(1.0, 4.0, n),
        "EPS1": np.linspace(0.4, 3.0, n),
        "FS1": np.linspace(0.9, 0.3, n),
        "TS1": np.linspace(18.0, 45.0, n),
        "VS1": np.linspace(0.05, 1.2, n),
        "CE": np.linspace(0.95, 0.2, n),
        "SE": np.linspace(0.9, 0.25, n),
    }
    profile = np.column_stack(
        [
            np.r_[np.full(50, 100.0), np.full(30, 3.0)],
            np.full(n, 100.0),
            np.zeros(n),
            np.full(n, 130.0),
            np.ones(n),
        ]
    )
    fit = np.arange(n) < 40
    L, R, B = hydraulic_proxies(sensors, fit)
    events = hydraulic_events_from_profile(profile)
    prepared = PreparedRealSeries(
        dataset="hydraulic_format_fixture",
        timestamps=tuple(str(i).zfill(4) for i in range(n)),
        L=L,
        R=R,
        B=B,
        events=events,
        calibration_end=40,
        validation_start=40,
        source_sha256="fixture-not-official",
        metadata={"kind": "schema_fixture", "not_official_evidence": True},
    )
    records = prepared_to_records(prepared)
    assert records[49].event is False
    assert records[50].event is True
    assert records[-1].event is True
    bundle = evaluate_table_bundle(records, source_sha256="fixture-not-official")
    assert bundle["metrics"]["n_events"] == 30
    assert bundle["debt_laws"]["final_D_kernel"] >= 0.0


def test_export_and_audit_binds_sha_and_debt_laws(tmp_path: Path) -> None:
    n = 40
    prepared = PreparedRealSeries(
        dataset="audit_fixture",
        timestamps=tuple(str(i).zfill(4) for i in range(n)),
        L=np.linspace(0.2, 0.9, n),
        R=np.linspace(0.9, 0.3, n),
        B=np.linspace(0.85, 0.35, n),
        events=(EventWindow(30, 34, "external"),),
        calibration_end=20,
        validation_start=20,
        source_sha256="fixture",
        metadata={"not_official_evidence": True},
    )
    audit = export_and_audit(prepared, tmp_path / "audit.csv")
    assert Path(audit["official_csv"]).exists()
    assert audit["metrics"]["n_events"] == 5
    assert audit["metrics"]["source_sha256"]
    assert audit["debt_laws"]["n_steps"] == n
    assert audit["negative_control"]["status"] == "ok"
