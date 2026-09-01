"""Explicit proxy recipes used by the real-data adapters.

These functions contain only the engineering hypotheses that map measured
columns onto (L, R, B). They do not download data, invent labels, or claim
empirical proof. Official adapters call them after integrity checks.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .empirical_evidence import EventWindow, robust_unit

METROPT3_REQUIRED = ("Motor_current", "TP2", "TP3", "DV_pressure")


def metropt3_proxies(numeric: pd.DataFrame, fit_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build (L, R, B) from a resampled MetroPT-3 numeric table."""
    missing = [name for name in METROPT3_REQUIRED if name not in numeric.columns]
    if missing:
        raise ValueError(f"MetroPT-3 required columns missing: {missing}")
    fit = np.asarray(fit_mask, dtype=bool)
    motor = robust_unit(numeric["Motor_current"].to_numpy(), fit)
    duty_source = numeric["COMP"].to_numpy() if "COMP" in numeric.columns else motor
    duty = robust_unit(duty_source, fit)
    pressure_work = robust_unit((numeric["TP2"] - numeric["TP3"]).abs().to_numpy(), fit)
    load = np.clip(0.55 * motor + 0.25 * duty + 0.20 * pressure_work, 0, 1)

    pressure_deficit = robust_unit(
        (numeric["TP3"].rolling(4, min_periods=1).max() - numeric["TP3"]).abs().to_numpy(),
        fit,
    )
    if "Oil_temperature" in numeric.columns:
        thermal = robust_unit(numeric["Oil_temperature"].to_numpy(), fit)
    else:
        thermal = np.zeros(len(numeric))
    recovery = np.clip(1.0 - (0.65 * pressure_deficit + 0.35 * thermal), 0, 1)

    control = numeric["COMP"].to_numpy() if "COMP" in numeric.columns else duty
    response = numeric["TP2"].diff().fillna(0).to_numpy()
    mismatch = np.abs(robust_unit(control, fit) - robust_unit(response, fit))
    instability = robust_unit(
        numeric["DV_pressure"].rolling(4, min_periods=1).std().fillna(0).to_numpy(),
        fit,
    )
    feedback = np.clip(1.0 - (0.65 * mismatch + 0.35 * instability), 0, 1)
    return load, recovery, feedback


def hydraulic_proxies(
    sensors: Mapping[str, np.ndarray],
    fit_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build (L, R, B) from cycle-aggregated hydraulic sensors."""
    required = ("PS1", "EPS1", "FS1", "TS1", "VS1", "CE", "SE")
    missing = [name for name in required if name not in sensors]
    if missing:
        raise ValueError(f"hydraulic required sensors missing: {missing}")
    fit = np.asarray(fit_mask, dtype=bool)
    pressure = robust_unit(sensors["PS1"], fit)
    power = robust_unit(sensors["EPS1"], fit)
    vibration = robust_unit(sensors["VS1"], fit)
    load = np.clip(0.45 * pressure + 0.40 * power + 0.15 * vibration, 0, 1)
    cooling = robust_unit(sensors["CE"], fit)
    temp = robust_unit(sensors["TS1"], fit)
    recovery = np.clip(0.65 * cooling + 0.35 * (1.0 - temp), 0, 1)
    flow = robust_unit(sensors["FS1"], fit)
    efficiency = robust_unit(sensors["SE"], fit)
    feedback = np.clip(1.0 - np.abs(flow - efficiency), 0, 1)
    return load, recovery, feedback


def hydraulic_events_from_profile(profile: np.ndarray) -> tuple[EventWindow, ...]:
    """External component-condition windows from profile.txt, not from MCS."""
    if profile.ndim != 2 or profile.shape[1] < 4:
        raise ValueError("unexpected hydraulic profile format")
    abnormal = (
        (profile[:, 0] != 100)
        | (profile[:, 1] != 100)
        | (profile[:, 2] != 0)
        | (profile[:, 3] != 130)
    )
    events: list[EventWindow] = []
    start: int | None = None
    n = len(profile)
    for i, flag in enumerate(abnormal):
        if flag and start is None:
            start = i
        if start is not None and (not flag or i == n - 1):
            end = i if flag and i == n - 1 else i - 1
            events.append(EventWindow(start, end, "component_condition_not_nominal"))
            start = None
    return tuple(events)


def complete_case_numeric(
    numeric: pd.DataFrame,
    columns: list[str],
) -> tuple[pd.DataFrame, int]:
    """Drop incomplete resampled rows. Never impute a missing sensor value."""
    before = len(numeric)
    cleaned = numeric.replace([np.inf, -np.inf], np.nan).dropna(subset=columns)
    return cleaned, before - len(cleaned)
