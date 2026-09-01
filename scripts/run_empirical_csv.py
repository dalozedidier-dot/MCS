#!/usr/bin/env python3
"""Run MCS on a real, externally prepared CSV; never creates proxies or labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcs.empirical import evaluate_table_bundle, file_sha256, load_empirical_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--output", default="reports/empirical_result.json")
    parser.add_argument("--alarm-threshold", type=float, default=0.0)
    args = parser.parse_args()
    source = Path(args.csv_path)
    records = load_empirical_csv(source)
    digest = file_sha256(source)
    payload = evaluate_table_bundle(
        records,
        source_sha256=digest,
        alarm_threshold=args.alarm_threshold,
    )
    payload["source"] = str(source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
