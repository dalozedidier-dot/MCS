from __future__ import annotations

import pytest

from mcs.empirical import EmpiricalRecord, evaluate_records, validate_records


def test_empirical_evaluator_uses_external_event_without_creating_it() -> None:
    records = [
        EmpiricalRecord(str(i).zfill(3), 0.2, 0.9, 0.9, i == 4)
        for i in range(6)
    ]
    metrics, margins = evaluate_records(records, source_sha256="abc", alarm_threshold=-1.0)
    assert metrics.n_events == 1
    assert metrics.first_event_index == 4
    assert metrics.first_alarm_index is None
    assert len(margins) == len(records)


def test_empirical_records_must_be_chronological() -> None:
    records = [
        EmpiricalRecord("002", 0.2, 0.9, 0.9, False),
        EmpiricalRecord("001", 0.2, 0.9, 0.9, True),
    ]
    with pytest.raises(ValueError, match="chronologically"):
        validate_records(records)


def test_empirical_proxy_domains_are_enforced() -> None:
    with pytest.raises(ValueError, match="R must"):
        validate_records([EmpiricalRecord("001", 0.2, 1.2, 0.9, False)])
