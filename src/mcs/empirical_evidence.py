"""Strict empirical-evidence utilities for MCS.

This module never invents observations or event labels. It consumes measured proxy
series and externally supplied event windows, calibrates thresholds on an earlier
chronological segment, and evaluates on a later untouched segment.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np

from .simulator import SimConfig, simulate


@dataclass(frozen=True)
class EventWindow:
    start: int
    end: int
    label: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("invalid event window")


@dataclass(frozen=True)
class DetectorResult:
    name: str
    threshold: float
    sensitivity: float
    precision: float
    false_alarms_per_1000_steps: float
    event_hits: int
    n_events: int
    false_alarms: int
    n_alarms: int
    median_lead: float | None
    mean_lead: float | None
    useful_warning_rate: float
    late_or_missed_rate: float
    leads: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PairedComparison:
    challenger: str
    reference: str
    n_paired: int
    median_gain: float | None
    mean_gain: float | None
    win_rate: float | None
    tie_rate: float | None
    loss_rate: float | None
    ci95_low: float | None
    ci95_high: float | None
    ci_status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceReport:
    dataset: str
    source_sha256: str
    protocol_sha256: str
    n_steps: int
    calibration_end: int
    validation_start: int
    event_horizon: int
    target_fpr: float
    detectors: tuple[DetectorResult, ...]
    comparisons: tuple[PairedComparison, ...]
    negative_controls: dict[str, Any]
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "detectors": [x.as_dict() for x in self.detectors],
            "comparisons": [x.as_dict() for x in self.comparisons],
        }


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_unit(values: Iterable[float], fit_mask: np.ndarray | None = None) -> np.ndarray:
    """Map measured values to [0, 1] using calibration-only 5th/95th percentiles."""
    arr = np.asarray(list(values), dtype=float)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError("values must be a non-empty 1D sequence")
    fit = arr if fit_mask is None else arr[np.asarray(fit_mask, dtype=bool)]
    finite = fit[np.isfinite(fit)]
    if finite.size == 0:
        raise ValueError("no finite calibration values")
    lo, hi = np.quantile(finite, [0.05, 0.95])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.full(arr.shape, 0.5, dtype=float)
    out = (arr - lo) / (hi - lo)
    return np.asarray(np.clip(out, 0.0, 1.0), dtype=float)


def rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    if window < 1:
        raise ValueError("window must be >= 1")
    out = np.empty_like(values, dtype=float)
    total = 0.0
    for i, value in enumerate(values):
        total += float(value)
        if i >= window:
            total -= float(values[i - window])
        out[i] = total / min(i + 1, window)
    return out


def ewma(values: np.ndarray, alpha: float = 0.2) -> np.ndarray:
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    out = np.empty_like(values, dtype=float)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def mcs_score(L: np.ndarray, R: np.ndarray, B: np.ndarray, *, rho: float = 0.85) -> np.ndarray:
    cfg = SimConfig(L=L.tolist(), R=R.tolist(), B=B.tolist(), rho=rho)
    result = simulate(cfg, n_steps=len(L))
    # Empirical analyses use the bounded margin to prevent near-zero capacity from
    # producing arbitrarily large scores. Larger score = more anomalous.
    return -np.asarray(result.M_bounded, dtype=float)


def detector_scores(L: np.ndarray, R: np.ndarray, B: np.ndarray, *, rho: float = 0.85) -> dict[str, np.ndarray]:
    """Detectors derived only from measured proxies; no labels are generated here."""
    full = mcs_score(L, R, B, rho=rho)
    no_debt = -np.asarray(simulate(SimConfig(L=L.tolist(), R=R.tolist(), B=B.tolist(), rho=0.0), n_steps=len(L)).M_bounded)
    return {
        "mcs_complet": full,
        "mcs_sans_memoire": no_debt,
        "seuil_L": np.asarray(L, dtype=float),
        "ewma_L": ewma(np.asarray(L, dtype=float), 0.2),
        "moyenne_mobile_L": rolling_mean(np.asarray(L, dtype=float), 8),
        "perte_RB": 1.0 - 0.5 * (np.asarray(R, dtype=float) + np.asarray(B, dtype=float)),
    }


def _event_mask(n: int, events: list[EventWindow], horizon: int) -> np.ndarray:
    mask = np.zeros(n, dtype=bool)
    for event in events:
        start = max(0, event.start - horizon)
        mask[start : min(n, event.end + 1)] = True
    return mask


def calibrate_threshold(score: np.ndarray, calibration_mask: np.ndarray, target_fpr: float) -> float:
    if not 0 < target_fpr < 1:
        raise ValueError("target_fpr must be in (0, 1)")
    values = score[np.asarray(calibration_mask, dtype=bool)]
    values = values[np.isfinite(values)]
    if values.size < 20:
        raise ValueError("at least 20 calibration values are required")
    return float(np.quantile(values, 1.0 - target_fpr, method="higher"))


def _alarm_onsets(score: np.ndarray, threshold: float, *, confirmation: int = 2, cooldown: int = 1) -> list[int]:
    if confirmation < 1 or cooldown < 0:
        raise ValueError("invalid alarm settings")
    above = np.asarray(score >= threshold, dtype=bool)
    onsets: list[int] = []
    run = 0
    last = -10**12
    for i, flag in enumerate(above):
        run = run + 1 if flag else 0
        if run == confirmation:
            onset = i - confirmation + 1
            if onset - last > cooldown:
                onsets.append(onset)
                last = onset
    return onsets


def evaluate_detector(
    name: str,
    score: np.ndarray,
    threshold: float,
    events: list[EventWindow],
    *,
    validation_start: int,
    horizon: int,
    useful_min_lead: int = 1,
    confirmation: int = 2,
    cooldown: int = 1,
) -> DetectorResult:
    n = len(score)
    valid_events = [e for e in events if e.start >= validation_start]
    onsets = [x for x in _alarm_onsets(score, threshold, confirmation=confirmation, cooldown=cooldown) if x >= validation_start]
    used: set[int] = set()
    leads: list[int] = []
    for event in valid_events:
        candidates = [
            (idx, alarm)
            for idx, alarm in enumerate(onsets)
            if idx not in used and event.start - horizon <= alarm <= event.start
        ]
        if candidates:
            idx, alarm = max(candidates, key=lambda item: item[1])
            used.add(idx)
            leads.append(event.start - alarm)
    false_alarms = len(onsets) - len(used)
    hits = len(leads)
    sensitivity = hits / len(valid_events) if valid_events else math.nan
    precision = hits / len(onsets) if onsets else 0.0
    validation_steps = max(1, n - validation_start)
    useful = sum(useful_min_lead <= x <= horizon for x in leads)
    median = float(np.median(leads)) if leads else None
    mean = float(np.mean(leads)) if leads else None
    return DetectorResult(
        name=name,
        threshold=threshold,
        sensitivity=float(sensitivity),
        precision=float(precision),
        false_alarms_per_1000_steps=1000.0 * false_alarms / validation_steps,
        event_hits=hits,
        n_events=len(valid_events),
        false_alarms=false_alarms,
        n_alarms=len(onsets),
        median_lead=median,
        mean_lead=mean,
        useful_warning_rate=useful / len(valid_events) if valid_events else math.nan,
        late_or_missed_rate=1.0 - useful / len(valid_events) if valid_events else math.nan,
        leads=tuple(leads),
    )


def _bootstrap_median(values: np.ndarray, *, seed: int = 20260711, n_boot: int = 5000) -> tuple[float, float]:
    if values.size == 0:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    medians = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample = rng.choice(values, size=values.size, replace=True)
        medians[i] = np.median(sample)
    return float(np.quantile(medians, 0.025)), float(np.quantile(medians, 0.975))


def compare_detectors(challenger: DetectorResult, reference: DetectorResult) -> PairedComparison:
    n = min(len(challenger.leads), len(reference.leads))
    if n == 0:
        return PairedComparison(challenger.name, reference.name, 0, None, None, None, None, None, None, None, "not_estimable_no_paired_event")
    gains = np.asarray(challenger.leads[:n], dtype=float) - np.asarray(reference.leads[:n], dtype=float)
    if n < 2:
        lo, hi = None, None
        ci_status = "not_estimable_fewer_than_2_paired_events"
    else:
        lo, hi = _bootstrap_median(gains)
        ci_status = "estimated_bootstrap_95"
    return PairedComparison(
        challenger=challenger.name,
        reference=reference.name,
        n_paired=n,
        median_gain=float(np.median(gains)),
        mean_gain=float(np.mean(gains)),
        win_rate=float(np.mean(gains > 0)),
        tie_rate=float(np.mean(gains == 0)),
        loss_rate=float(np.mean(gains < 0)),
        ci95_low=lo,
        ci95_high=hi,
        ci_status=ci_status,
    )


def circular_shift_control(
    score: np.ndarray,
    events: list[EventWindow],
    threshold: float,
    *,
    validation_start: int,
    horizon: int,
    n_shifts: int = 200,
) -> dict[str, Any]:
    """Empirical label-timing null test using circular shifts, not simulated observations."""
    valid_len = len(score) - validation_start
    if valid_len <= 2 * horizon or not events:
        return {"status": "not_applicable", "reason": "insufficient validation span or events"}
    observed = evaluate_detector("observed", score, threshold, events, validation_start=validation_start, horizon=horizon).sensitivity
    rng = np.random.default_rng(20260711)
    null: list[float] = []
    valid_events = [e for e in events if e.start >= validation_start]
    for _ in range(n_shifts):
        shift = int(rng.integers(horizon + 1, max(horizon + 2, valid_len - horizon)))
        shifted = []
        for e in valid_events:
            start = validation_start + ((e.start - validation_start + shift) % valid_len)
            duration = e.end - e.start
            if start + duration < len(score):
                shifted.append(EventWindow(start, start + duration, e.label))
        if shifted:
            metric = evaluate_detector("shift", score, threshold, shifted, validation_start=validation_start, horizon=horizon)
            null.append(metric.sensitivity)
    if not null:
        return {"status": "not_applicable", "reason": "no valid shifted windows"}
    p_value = (1 + sum(x >= observed for x in null)) / (1 + len(null))
    return {
        "status": "ok",
        "observed_sensitivity": observed,
        "null_mean_sensitivity": float(np.mean(null)),
        "p_value_one_sided": float(p_value),
        "n_shifts": len(null),
    }


def build_evidence_report(
    *,
    dataset: str,
    source_sha256: str,
    protocol_sha256: str,
    L: np.ndarray,
    R: np.ndarray,
    B: np.ndarray,
    events: list[EventWindow],
    calibration_end: int,
    validation_start: int,
    horizon: int,
    target_fpr: float = 0.05,
    rho: float = 0.85,
    limitations: tuple[str, ...] = (),
) -> EvidenceReport:
    if not (0 < calibration_end <= validation_start < len(L)):
        raise ValueError("invalid chronological split")
    if not (len(L) == len(R) == len(B)):
        raise ValueError("proxy lengths differ")
    scores = detector_scores(L, R, B, rho=rho)
    calibration_event_mask = _event_mask(len(L), events, horizon)
    calibration_mask = np.zeros(len(L), dtype=bool)
    calibration_mask[:calibration_end] = True
    calibration_mask &= ~calibration_event_mask
    results: list[DetectorResult] = []
    for name, score in scores.items():
        threshold = calibrate_threshold(score, calibration_mask, target_fpr)
        results.append(
            evaluate_detector(
                name,
                score,
                threshold,
                events,
                validation_start=validation_start,
                horizon=horizon,
            )
        )
    by_name = {x.name: x for x in results}
    comparisons = tuple(
        compare_detectors(by_name["mcs_complet"], by_name[reference])
        for reference in ("mcs_sans_memoire", "seuil_L", "ewma_L", "moyenne_mobile_L", "perte_RB")
    )
    negative = circular_shift_control(
        scores["mcs_complet"],
        events,
        by_name["mcs_complet"].threshold,
        validation_start=validation_start,
        horizon=horizon,
    )
    return EvidenceReport(
        dataset=dataset,
        source_sha256=source_sha256,
        protocol_sha256=protocol_sha256,
        n_steps=len(L),
        calibration_end=calibration_end,
        validation_start=validation_start,
        event_horizon=horizon,
        target_fpr=target_fpr,
        detectors=tuple(results),
        comparisons=comparisons,
        negative_controls={"circular_event_shift": negative},
        limitations=limitations,
    )
