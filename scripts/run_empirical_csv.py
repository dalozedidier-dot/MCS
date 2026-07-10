#!/usr/bin/env python3
"""Run MCS on a real, externally prepared CSV; never creates proxies or labels."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from mcs.empirical import EmpiricalRecord, evaluate_records, file_sha256


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "oui"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--output", default="reports/empirical_result.json")
    parser.add_argument("--alarm-threshold", type=float, default=0.0)
    args = parser.parse_args()
    source = Path(args.csv_path)
    records: list[EmpiricalRecord] = []
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "L", "R", "B", "event"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV columns required: {sorted(required)}")
        for row in reader:
            records.append(
                EmpiricalRecord(
                    timestamp=row["timestamp"],
                    L=float(row["L"]),
                    R=float(row["R"]),
                    B=float(row["B"]),
                    event=parse_bool(row["event"]),
                )
            )
    metrics, margins = evaluate_records(
        records,
        source_sha256=file_sha256(source),
        alarm_threshold=args.alarm_threshold,
    )
    payload = {
        "status": "empirical_result_computed_from_external_csv",
        "source": str(source),
        "metrics": metrics.as_dict(),
        "M": margins,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
