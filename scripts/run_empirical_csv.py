#!/usr/bin/env python3
"""Run MCS on a real, externally prepared CSV; never creates proxies or labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcs.debt_laws import compare_debt_laws
from mcs.empirical import evaluate_records, file_sha256, load_empirical_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--output", default="reports/empirical_result.json")
    parser.add_argument("--alarm-threshold", type=float, default=0.0)
    args = parser.parse_args()
    source = Path(args.csv_path)
    records = load_empirical_csv(source)
    digest = file_sha256(source)
    metrics, margins = evaluate_records(
        records,
        source_sha256=digest,
        alarm_threshold=args.alarm_threshold,
    )
    laws = compare_debt_laws(
        [row.L for row in records],
        [row.R for row in records],
        [row.B for row in records],
    )
    payload = {
        "status": "empirical_result_computed_from_external_csv",
        "source": str(source),
        "metrics": metrics.as_dict(),
        "M": margins,
        "debt_laws": laws.as_dict(),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
