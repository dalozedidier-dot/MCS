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
