from __future__ import annotations

from pathlib import Path

from mcs.real_adapters import _extract_rar


def test_extract_rar_requires_available_tool(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("mcs.real_adapters.shutil.which", lambda _: None)
    rar = tmp_path / "x.rar"
    rar.write_bytes(b"not a real rar")
    try:
        _extract_rar(rar, tmp_path / "out")
    except RuntimeError as exc:
        assert "7z or unrar" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_prepare_metropt3_drops_incomplete_resampled_rows_without_imputation(tmp_path: Path, monkeypatch) -> None:
    import json

    import pandas as pd

    from mcs.real_adapters import prepare_metropt3

    root = tmp_path / "metropt3"
    raw = root / "raw"
    raw.mkdir(parents=True)
    timestamps = pd.date_range("2020-01-01", periods=48, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "Motor_current": [1.0] * 48,
            "TP2": [2.0] * 48,
            "TP3": [1.0] * 48,
            "DV_pressure": [0.2] * 48,
            "COMP": [1.0] * 48,
            "Oil_temperature": [40.0] * 48,
        }
    )
    frame.loc[10, "Motor_current"] = float("nan")
    frame.to_csv(raw / "MetroPT3(AirCompressor).csv", index=False)
    (root / "provenance.json").write_text(
        json.dumps({"archive": {"sha256": "abc"}, "files": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("mcs.real_adapters.verify_provenance", lambda _: {"ok": True})

    prepared = prepare_metropt3(root)

    assert len(prepared.L) == 47
    assert prepared.metadata["rows_dropped_missing"] == 1
    assert prepared.metadata["missing_data_policy"] == "complete_case_after_resampling_no_value_imputation"
    assert all(float(x) == float(x) for x in prepared.L)
