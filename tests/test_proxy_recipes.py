from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mcs.proxy_recipes import (
    complete_case_numeric,
    hydraulic_events_from_profile,
    hydraulic_proxies,
    metropt3_proxies,
)


def _metropt3_frame(n: int = 48) -> pd.DataFrame:
    index = pd.date_range("2020-02-29", periods=n, freq="15min", tz="UTC")
    ramp = np.linspace(0.2, 1.4, n)
    return pd.DataFrame(
        {
            "Motor_current": ramp,
            "TP2": 2.0 + 0.1 * ramp,
            "TP3": 1.0 + 0.02 * ramp,
            "DV_pressure": 0.2 + 0.05 * ramp,
            "COMP": np.where(np.arange(n) % 4 == 0, 1.0, 0.2),
            "Oil_temperature": 40.0 + 0.2 * np.arange(n),
        },
        index=index,
    )


def test_metropt3_recipe_returns_bounded_proxies() -> None:
    frame = _metropt3_frame()
    fit = np.zeros(len(frame), dtype=bool)
    fit[:24] = True
    L, R, B = metropt3_proxies(frame, fit)
    assert L.shape == R.shape == B.shape == (48,)
    assert np.all((L >= 0) & (L <= 1))
    assert np.all((R >= 0) & (R <= 1))
    assert np.all((B >= 0) & (B <= 1))
    assert L[-1] > L[0]


def test_metropt3_recipe_rejects_missing_columns() -> None:
    frame = _metropt3_frame().drop(columns=["TP2"])
    with pytest.raises(ValueError, match="required columns"):
        metropt3_proxies(frame, np.ones(len(frame), dtype=bool))


def test_complete_case_does_not_impute() -> None:
    frame = _metropt3_frame()
    frame.iloc[3, 0] = np.nan
    cleaned, dropped = complete_case_numeric(frame, list(frame.columns))
    assert dropped == 1
    assert len(cleaned) == 47
    assert not cleaned.isna().any().any()


def test_hydraulic_recipe_and_external_events() -> None:
    n = 60
    sensors = {
        "PS1": np.linspace(1.0, 3.0, n),
        "EPS1": np.linspace(0.5, 2.5, n),
        "FS1": np.linspace(0.8, 0.4, n),
        "TS1": np.linspace(20.0, 40.0, n),
        "VS1": np.linspace(0.1, 0.9, n),
        "CE": np.linspace(0.9, 0.3, n),
        "SE": np.linspace(0.85, 0.2, n),
    }
    fit = np.arange(n) < 30
    L, R, B = hydraulic_proxies(sensors, fit)
    assert np.all((L >= 0) & (L <= 1))
    profile = np.column_stack(
        [
            np.r_[np.full(30, 100), np.full(30, 20)],
            np.full(n, 100),
            np.zeros(n),
            np.full(n, 130),
            np.ones(n),
        ]
    )
    events = hydraulic_events_from_profile(profile)
    assert len(events) == 1
    assert events[0].start == 30
    assert events[0].end == 59
    assert events[0].label == "component_condition_not_nominal"
