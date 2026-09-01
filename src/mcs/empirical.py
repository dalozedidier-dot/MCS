"""Evaluation of MCS on externally observed time series and events.

The evaluator does not generate trajectories, labels, or proxy values. It only consumes
an already prepared, auditable table whose event labels are external to MCS.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .simulator import SimConfig, simulate


@dataclass(frozen=True)
class EmpiricalRecord:
    timestamp: str
    L: float
    R: float
    B: float
    event: bool


@dataclass(frozen=True)
class EmpiricalMetrics:
    n_rows: int
    n_events: int
    first_event_index: int | None
    first_alarm_index: int | None
    lead_steps: int | None
    alarm_before_event: bool | None
    false_alarm_before_first_event: bool
    source_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_event(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "oui"}


def load_empirical_csv(path: str | Path) -> list[EmpiricalRecord]:
    source = Path(path)
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "L", "R", "B", "event"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV columns required: {sorted(required)}")
        records = [
            EmpiricalRecord(
                timestamp=row["timestamp"],
                L=float(row["L"]),
                R=float(row["R"]),
                B=float(row["B"]),
                event=parse_event(row["event"]),
            )
            for row in reader
        ]
    validate_records(records)
    return records


def validate_records(records: list[EmpiricalRecord]) -> None:
    if not records:
        raise ValueError("The empirical table is empty")
    timestamps = [record.timestamp for record in records]
    if timestamps != sorted(timestamps):
        raise ValueError("Empirical rows must be sorted chronologically")
    for index, record in enumerate(records):
        if record.L < 0:
            raise ValueError(f"L must be non-negative at row {index}")
        if not 0 <= record.R <= 1:
            raise ValueError(f"R must be in [0, 1] at row {index}")
        if not 0 <= record.B <= 1:
            raise ValueError(f"B must be in [0, 1] at row {index}")


def evaluate_records(
    records: list[EmpiricalRecord],
    *,
    source_sha256: str,
    alarm_threshold: float = 0.0,
    config: SimConfig | None = None,
) -> tuple[EmpiricalMetrics, list[float]]:
    """Evaluate MCS against external event labels without creating any labels."""
    validate_records(records)
    cfg = config or SimConfig(
        L=[record.L for record in records],
        R=[record.R for record in records],
        B=[record.B for record in records],
    )
    result = simulate(cfg, n_steps=len(records))
    margins = list(result.M)
    event_indices = [i for i, record in enumerate(records) if record.event]
    alarm_indices = [i for i, value in enumerate(margins) if value <= alarm_threshold]
    first_event = event_indices[0] if event_indices else None
    first_alarm = alarm_indices[0] if alarm_indices else None
    lead = None
    before = None
    if first_event is not None and first_alarm is not None:
        lead = first_event - first_alarm
        before = first_alarm < first_event
    false_alarm = bool(
        first_alarm is not None and (first_event is None or first_alarm < first_event)
    )
    metrics = EmpiricalMetrics(
        n_rows=len(records),
        n_events=len(event_indices),
        first_event_index=first_event,
        first_alarm_index=first_alarm,
        lead_steps=lead,
        alarm_before_event=before,
        false_alarm_before_first_event=false_alarm,
        source_sha256=source_sha256,
    )
    return metrics, margins
