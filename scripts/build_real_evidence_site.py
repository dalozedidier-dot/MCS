#!/usr/bin/env python3
"""Build a truthful GitHub Pages data file from empirical reports only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    reports = []
    for path in sorted(Path("reports/real").glob("*_evidence.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        mcs = next((x for x in data.get("detectors", []) if x.get("name") == "mcs_complet"), None)
        reports.append({
            "dataset": data.get("dataset"),
            "source_sha256": data.get("source_sha256"),
            "protocol_sha256": data.get("protocol_sha256"),
            "n_steps": data.get("n_steps"),
            "n_events": mcs.get("n_events") if mcs else None,
            "sensitivity": mcs.get("sensitivity") if mcs else None,
            "precision": mcs.get("precision") if mcs else None,
            "median_lead": mcs.get("median_lead") if mcs else None,
            "false_alarms_per_1000_steps": mcs.get("false_alarms_per_1000_steps") if mcs else None,
            "negative_controls": data.get("negative_controls"),
            "limitations": data.get("limitations", []),
            "report": str(path),
        })
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "empirical_results_available" if reports else "no_empirical_result_yet",
        "results": reports,
        "rule": "Only reports produced from verified local source files are included. Missing datasets remain missing; no placeholder metric is generated.",
    }
    target = Path("docs/data/real-evidence.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
