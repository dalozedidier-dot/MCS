from __future__ import annotations

from pathlib import Path

import pytest

from mcs.debt_laws import compare_debt_laws, severe_debt_update
from mcs.empirical import evaluate_records, file_sha256, load_empirical_csv

FIXTURE = Path(__file__).parent / "fixtures" / "empirical_table.csv"


def test_load_empirical_csv_reads_external_events() -> None:
    records = load_empirical_csv(FIXTURE)
    assert len(records) == 11
    assert records[0].event is False
    assert records[-1].event is True
    assert records[-2].event is True


def test_evaluate_records_binds_sha_to_source_file() -> None:
    records = load_empirical_csv(FIXTURE)
    digest = file_sha256(FIXTURE)
    metrics, margins = evaluate_records(records, source_sha256=digest, alarm_threshold=0.0)
    assert metrics.source_sha256 == digest
    assert metrics.n_events == 2
    assert metrics.first_event_index == 9
    assert len(margins) == 11
    assert all(isinstance(value, float) for value in margins)


def test_load_empirical_csv_rejects_bad_header(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("t,L,R,B\n1,0.1,0.9,0.9\n", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV columns required"):
        load_empirical_csv(bad)


def test_debt_laws_run_on_the_same_observed_path() -> None:
    records = load_empirical_csv(FIXTURE)
    cmp = compare_debt_laws(
        [row.L for row in records],
        [row.R for row in records],
        [row.B for row in records],
    )
    assert cmp.n_steps == 11
    assert cmp.final_D_kernel >= 0.0
    assert cmp.final_D_severe >= 0.0
    assert cmp.max_abs_gap >= 0.0


def test_severe_debt_update_is_nonnegative() -> None:
    assert severe_debt_update(0.2, 0.5, 0.4, 0.85) >= 0.0
