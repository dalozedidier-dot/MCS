#!/usr/bin/env python3
"""Build a truthful, cumulative GitHub Pages data file from empirical reports only."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _summary(data: dict[str, Any], path: Path) -> dict[str, Any]:
    mcs = next((x for x in data.get("detectors", []) if x.get("name") == "mcs_complet"), None)
    return {
        "dataset": data.get("dataset"),
        "status": data.get("status", "evaluated"),
        "reason": data.get("reason"),
        "source_sha256": data.get("source_sha256"),
        "protocol_sha256": data.get("protocol_sha256"),
        "score_transform": data.get("score_transform"),
        "n_steps": data.get("n_steps"),
        "n_events": mcs.get("n_events") if mcs else None,
        "sensitivity": mcs.get("sensitivity") if mcs else None,
        "precision": mcs.get("precision") if mcs else None,
        "median_lead": mcs.get("median_lead") if mcs else None,
        "false_alarms_per_1000_steps": mcs.get("false_alarms_per_1000_steps") if mcs else None,
        "negative_controls": data.get("negative_controls"),
        "limitations": data.get("limitations", []),
        "report": path.as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", default="reports/real")
    parser.add_argument("--target", default="docs/data/real-evidence.json")
    parser.add_argument("--preserve-existing", action="store_true")
    args = parser.parse_args()

    target = Path(args.target)
    merged: dict[str, dict[str, Any]] = {}
    if args.preserve_existing and target.exists():
        previous = json.loads(target.read_text(encoding="utf-8"))
        for row in previous.get("results", []):
            if row.get("dataset"):
                merged[str(row["dataset"])] = row

    for path in sorted(Path(args.reports).glob("*_evidence.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        row = _summary(data, path)
        if row["dataset"]:
            merged[str(row["dataset"])] = row

    reports = [merged[key] for key in sorted(merged)]
    payload = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "empirical_results_available" if reports else "no_empirical_result_yet",
        "results": reports,
        "rule": "Only reports produced from verified local source files are included. Non-evaluable datasets remain explicit; no placeholder metric is generated.",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
