"""Evaluation of MCS on externally observed time series and events.

The evaluator does not generate trajectories, labels, or proxy values. It only consumes
an already prepared, auditable table whose event labels are external to MCS.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Sequence

from .debt_laws import compare_debt_laws
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
    n_alarms: int
    event_hits: int
    missed_events: int
    median_lead_all: float | None
    leads: tuple[int, ...]

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


def write_empirical_csv(path: str | Path, records: Sequence[EmpiricalRecord]) -> Path:
    validate_records(list(records))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "L", "R", "B", "event"])
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "timestamp": record.timestamp,
                    "L": f"{record.L:.8f}",
                    "R": f"{record.R:.8f}",
                    "B": f"{record.B:.8f}",
                    "event": "true" if record.event else "false",
                }
            )
    return target


def records_from_series(
    timestamps: Sequence[str],
    L: Sequence[float],
    R: Sequence[float],
    B: Sequence[float],
    events: Sequence[bool],
) -> list[EmpiricalRecord]:
    if not (len(timestamps) == len(L) == len(R) == len(B) == len(events)):
        raise ValueError("timestamps, proxies and events must have the same length")
    records = [
        EmpiricalRecord(str(ts), float(lt), float(rt), float(bt), bool(flag))
        for ts, lt, rt, bt, flag in zip(timestamps, L, R, B, events, strict=True)
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


def _match_leads(event_indices: list[int], alarm_indices: list[int]) -> list[int]:
    """Match each event to the latest unused alarm at or before the event."""
    leads: list[int] = []
    used: set[int] = set()
    for event in event_indices:
        candidates = [alarm for alarm in alarm_indices if alarm <= event and alarm not in used]
        if candidates:
            alarm = max(candidates)
            used.add(alarm)
            leads.append(event - alarm)
    return leads


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
    false_alarm = bool(first_alarm is not None and (first_event is None or first_alarm < first_event))
    leads = _match_leads(event_indices, alarm_indices)
    metrics = EmpiricalMetrics(
        n_rows=len(records),
        n_events=len(event_indices),
        first_event_index=first_event,
        first_alarm_index=first_alarm,
        lead_steps=lead,
        alarm_before_event=before,
        false_alarm_before_first_event=false_alarm,
        source_sha256=source_sha256,
        n_alarms=len(alarm_indices),
        event_hits=len(leads),
        missed_events=len(event_indices) - len(leads),
        median_lead_all=(sorted(leads)[len(leads) // 2] if leads else None),
        leads=tuple(leads),
    )
    return metrics, margins


def circular_shift_control(
    records: list[EmpiricalRecord],
    *,
    source_sha256: str,
    alarm_threshold: float = 0.0,
    n_shifts: int = 21,
) -> dict[str, Any]:
    """Timing-null test: rotate external event flags, keep measured proxies fixed."""
    observed, _ = evaluate_records(records, source_sha256=source_sha256, alarm_threshold=alarm_threshold)
    n = len(records)
    if observed.n_events == 0 or n < 6:
        return {"status": "not_applicable", "reason": "need events and at least 6 rows"}
    flags = [record.event for record in records]
    observed_hits = observed.event_hits
    null_hits: list[int] = []
    for shift in range(1, min(n_shifts, n)):
        rotated = flags[-shift:] + flags[:-shift]
        shifted = [
            EmpiricalRecord(row.timestamp, row.L, row.R, row.B, flag)
            for row, flag in zip(records, rotated, strict=True)
        ]
        metrics, _ = evaluate_records(
            shifted,
            source_sha256=source_sha256,
            alarm_threshold=alarm_threshold,
        )
        null_hits.append(metrics.event_hits)
    if not null_hits:
        return {"status": "not_applicable", "reason": "no shifts"}
    p_value = (1 + sum(hits >= observed_hits for hits in null_hits)) / (1 + len(null_hits))
    return {
        "status": "ok",
        "observed_event_hits": observed_hits,
        "null_mean_event_hits": sum(null_hits) / len(null_hits),
        "p_value_one_sided": p_value,
        "n_shifts": len(null_hits),
    }


def evaluate_table_bundle(
    records: list[EmpiricalRecord],
    *,
    source_sha256: str,
    alarm_threshold: float = 0.0,
    rho: float = 0.85,
) -> dict[str, Any]:
    """Single auditable payload: metrics, debt-law comparison, timing null."""
    metrics, margins = evaluate_records(
        records,
        source_sha256=source_sha256,
        alarm_threshold=alarm_threshold,
    )
    laws = compare_debt_laws(
        [row.L for row in records],
        [row.R for row in records],
        [row.B for row in records],
        rho=rho,
    )
    return {
        "status": "empirical_result_computed_from_external_csv",
        "metrics": metrics.as_dict(),
        "M": margins,
        "debt_laws": laws.as_dict(),
        "negative_control": circular_shift_control(
            records,
            source_sha256=source_sha256,
            alarm_threshold=alarm_threshold,
        ),
    }
