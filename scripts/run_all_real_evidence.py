#!/usr/bin/env python3
"""Run every empirical dataset that is locally available and verified."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

DATASETS = ["metropt3", "hydraulic", "ims_bearings_1st_test", "ims_bearings_2nd_test", "ims_bearings_3rd_test"]


def main() -> None:
    results = []
    for dataset in DATASETS:
        base = "ims_bearings" if dataset.startswith("ims_bearings") else dataset
        root = Path("data/real") / base
        if not (root / "provenance.json").exists():
            results.append({"dataset": dataset, "status": "missing", "reason": "provenance.json absent"})
            continue
        cmd = [sys.executable, "scripts/run_real_evidence.py", dataset]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        results.append({
            "dataset": dataset,
            "status": "ok" if proc.returncode == 0 else "failed",
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        })
    Path("reports/real").mkdir(parents=True, exist_ok=True)
    Path("reports/real/run_summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if any(x["status"] == "failed" for x in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
