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
