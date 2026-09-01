"""Candidate debt update laws compared on the same observed (L, R, B, C) path.

Default kernel (§3.1):
    D(t+1) = ρ D + (1-R) L (1-B) + max(0, L-C)

Severe variant (§3.1 optional):
    D(t+1) = ρ D + max(0, A-C)   with A = L+D

Neither law is declared true here. The module only measures how they diverge
on a frozen series.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .core import capacity, debt_update, leak, overflow, total_load


@dataclass(frozen=True)
class DebtLawComparison:
    n_steps: int
    rho: float
    final_D_kernel: float
    final_D_severe: float
    max_abs_gap: float
    kernel_reaches_overflow: bool
    severe_grows_faster: bool

    def as_dict(self) -> dict[str, float | int | bool]:
        return asdict(self)


def severe_debt_update(D: float, L: float, C: float, rho: float) -> float:
    if not (0.0 <= rho <= 1.0):
        raise ValueError("rho must be in [0, 1]")
    return rho * D + max(0.0, total_load(L, D) - C)


def compare_debt_laws(
    L: list[float],
    R: list[float],
    B: list[float],
    *,
    rho: float = 0.85,
    theta: float = 1.0,
    s: float = 0.0,
    D0: float = 0.0,
) -> DebtLawComparison:
    if not (len(L) == len(R) == len(B)):
        raise ValueError("L, R and B must have the same length")
    Dk = Ds = D0
    max_gap = 0.0
    overflow_seen = False
    for Lt, Rt, Bt in zip(L, R, B, strict=True):
        C = capacity(theta, Rt, Bt, s)
        overflow_seen = overflow_seen or overflow(Lt, C) > 0.0
        Dk = debt_update(Dk, Lt, Rt, Bt, C, rho)
        Ds = severe_debt_update(Ds, Lt, C, rho)
        max_gap = max(max_gap, abs(Dk - Ds))
    return DebtLawComparison(
        n_steps=len(L),
        rho=rho,
        final_D_kernel=Dk,
        final_D_severe=Ds,
        max_abs_gap=max_gap,
        kernel_reaches_overflow=overflow_seen,
        severe_grows_faster=Ds >= Dk - 1e-12,
    )


def leak_term(L: float, R: float, B: float) -> float:
    return leak(L, R, B)
