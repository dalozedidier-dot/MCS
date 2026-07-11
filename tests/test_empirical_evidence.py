from __future__ import annotations

import numpy as np

from mcs.empirical_evidence import (
    EventWindow,
    calibrate_threshold,
    compare_detectors,
    detector_scores,
    evaluate_detector,
    robust_unit,
)


def test_robust_unit_uses_calibration_mask() -> None:
    values = np.array([0.0, 1.0, 2.0, 100.0])
    mask = np.array([True, True, True, False])
    out = robust_unit(values, mask)
    assert out[0] == 0.0
    assert out[-1] == 1.0


def test_detector_scores_have_common_length() -> None:
    L = np.linspace(0.2, 0.8, 60)
    R = np.linspace(0.9, 0.5, 60)
    B = np.linspace(0.9, 0.6, 60)
    scores = detector_scores(L, R, B)
    assert scores
    assert {len(x) for x in scores.values()} == {60}


def test_threshold_and_event_evaluation() -> None:
    score = np.r_[np.zeros(50), np.ones(20)]
    calibration = np.zeros(70, dtype=bool)
    calibration[:50] = True
    threshold = calibrate_threshold(score, calibration, 0.05)
    result = evaluate_detector(
        "x",
        score,
        threshold + 0.5,
        [EventWindow(60, 60, "external")],
        validation_start=50,
        horizon=15,
        confirmation=2,
    )
    assert result.event_hits == 1
    assert result.sensitivity == 1.0
    assert result.median_lead == 10.0


def test_comparison_is_explicit_when_no_pairs() -> None:
    empty = evaluate_detector(
        "empty",
        np.zeros(30),
        1.0,
        [EventWindow(25, 25, "event")],
        validation_start=20,
        horizon=5,
    )
    comparison = compare_detectors(empty, empty)
    assert comparison.n_paired == 0
    assert comparison.median_gain is None


def test_empirical_mcs_scores_are_bounded() -> None:
    L = np.full(80, 1.0)
    R = np.r_[np.full(40, 0.8), np.full(40, 0.001)]
    B = np.r_[np.full(40, 0.8), np.full(40, 0.001)]
    score = detector_scores(L, R, B)["mcs_complet"]
    assert np.all(np.isfinite(score))
    assert np.all(score >= -1.0)
    assert np.all(score <= 1.0)


def test_single_paired_event_does_not_claim_bootstrap_interval() -> None:
    score_a = np.r_[np.zeros(20), np.ones(10)]
    score_b = np.r_[np.zeros(22), np.ones(8)]
    event = [EventWindow(27, 27, "event")]
    a = evaluate_detector("a", score_a, 0.5, event, validation_start=15, horizon=10, confirmation=1)
    b = evaluate_detector("b", score_b, 0.5, event, validation_start=15, horizon=10, confirmation=1)
    comparison = compare_detectors(a, b)
    assert comparison.n_paired == 1
    assert comparison.ci95_low is None
    assert comparison.ci95_high is None
    assert comparison.ci_status == "not_estimable_fewer_than_2_paired_events"
