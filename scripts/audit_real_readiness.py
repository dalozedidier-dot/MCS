#!/usr/bin/env python3
"""Audit what is physically present before any empirical claim is allowed."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from mcs.realdata import DATASETS, verify_provenance


def main() -> None:
    rows = []
    for slug, spec in DATASETS.items():
        root = Path("data/real") / slug
        provenance = root / "provenance.json"
        if not provenance.exists():
            rows.append({"dataset": slug, "status": "missing_provenance", "ready": False})
            continue
        manifest = json.loads(provenance.read_text(encoding="utf-8"))
        recorded = len(manifest.get("files", []))
        present = sum((root / str(item["path"])).exists() for item in manifest.get("files", []))
        try:
            integrity = verify_provenance(root)
            ok = bool(integrity["ok"])
        except FileNotFoundError:
            ok = False
        rows.append({
            "dataset": slug,
            "title": spec.title,
            "status": "ready" if ok else "provenance_only_or_incomplete",
            "ready": ok,
            "recorded_files": recorded,
            "present_files": present,
            "source_url": spec.source_url,
            "provenance": provenance.as_posix(),
        })
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rule": "ready=true only when every recorded raw file exists and matches its recorded SHA-256",
        "datasets": rows,
    }
    target = Path("reports/real/readiness.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
