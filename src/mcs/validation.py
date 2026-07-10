"""Validation centralisee des configurations et domaines du MCS."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from . import core


def finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} doit etre un nombre fini")
    return value


def non_negative(name: str, value: float) -> float:
    value = finite(name, value)
    if value < 0:
        raise ValueError(f"{name} doit etre positif ou nul")
    return value


def positive(name: str, value: float) -> float:
    value = finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} doit etre strictement positif")
    return value


def unit_interval(name: str, value: float) -> float:
    value = finite(name, value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} doit etre borne entre 0 et 1")
    return value


def validate_thresholds(thresholds: Mapping[str, float] | None) -> dict[str, float]:
    th = dict(core.DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    required = ("viable", "tension", "saturation", "pre_rupture")
    missing = [key for key in required if key not in th]
    if missing:
        raise ValueError(f"seuils manquants : {missing}")
    for key in required:
        finite(f"thresholds[{key}]", th[key])
    if not (th["viable"] > th["tension"] > th["saturation"]
            > th["pre_rupture"]):
        raise ValueError(
            "les seuils doivent respecter viable > tension > saturation > pre_rupture"
        )
    return th


def validate_series(name: str, value) -> None:
    """Valide les constantes et sequences sans evaluer les callables."""
    if callable(value):
        return
    if isinstance(value, (int, float)):
        non_negative(name, value)
        return
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{name} doit etre un nombre, une sequence ou une fonction")
    if len(value) == 0:
        raise ValueError(f"{name} ne peut pas etre une sequence vide")
    for index, item in enumerate(value):
        non_negative(f"{name}[{index}]", item)
