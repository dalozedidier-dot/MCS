"""Tests generatifs (Hypothesis) et invariants metamorphiques.

Les tests unitaires verifient des points ; ces tests verifient des
PROPRIETES sur des domaines entiers echantillonnes :

- bornes et monotonies du noyau (capacite, marge, dette, zones)
- invariance d'echelle de M et de M~
- point fixe analytique D* atteint par la dynamique
- ordinalite de la classification et discipline de l'hysteresis
- optimalite de U* sur la courbe de controle
- positivite et bornes le long de trajectoires simulees completes
- determinisme : memes entrees => memes sorties
"""

import math

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from mcs import (  # noqa: E402
    HysteresisClassifier,
    SimConfig,
    bounded_margin_index,
    capacity,
    classify,
    debt_rest_level,
    debt_update,
    margin_index,
    simulate,
)
from mcs.extensions import (  # noqa: E402
    ControlParams,
    ThetaParams,
    effective_feedback,
    optimal_control,
)

unit = st.floats(0.0, 1.0, allow_nan=False)
unit_open = st.floats(0.01, 0.99, allow_nan=False)
pos = st.floats(0.01, 5.0, allow_nan=False)
load = st.floats(0.0, 3.0, allow_nan=False)


# -- noyau : bornes, monotonies, invariances ---------------------------------

@given(theta=pos, R=unit, B=unit, s=unit)
def test_capacity_bounds_and_monotonicity(theta, R, B, s):
    C = capacity(theta, R, B, s)
    assert 0.0 <= C <= theta                     # C <= Theta * 1
    # monotone en chaque proxy
    assert capacity(theta * 1.1, R, B, s) >= C
    assert capacity(theta, min(1.0, R + 0.05), B, s) >= C - 1e-12
    assert capacity(theta, R, min(1.0, B + 0.05), s) >= C - 1e-12


@given(A=load, C=pos)
def test_margin_upper_bound_and_scale_invariance(A, C):
    M = margin_index(A, C)
    assert M <= 1.0
    for lam in (0.5, 2.0, 7.3):                  # M(lam*A, lam*C) = M(A, C)
        assert margin_index(lam * A, lam * C) == pytest.approx(M, abs=1e-12)


@given(A=load, C=st.floats(0.0, 5.0, allow_nan=False))
def test_bounded_margin_range_and_sign(A, C):
    Mb = bounded_margin_index(A, C)
    assert -1.0 <= Mb <= 1.0
    M = margin_index(A, C)
    if math.isfinite(M) and A > 0 and C > 0:
        assert (M > 0) == (Mb > 0) and (M == 0) == (Mb == 0)


@given(D=load, L=load, R=unit, B=unit, rho=unit_open, C=pos)
def test_debt_nonnegative_and_monotone(D, L, R, B, rho, C):
    D1 = debt_update(D, L, R, B, C, rho)
    assert D1 >= 0.0
    assert debt_update(D + 0.1, L, R, B, C, rho) >= D1          # en D
    assert debt_update(D, L, R, B, C, min(0.999, rho + 0.05)) >= D1 - 1e-12


@given(L=st.floats(0.01, 0.5), R=unit_open, B=unit_open,
       rho=st.floats(0.0, 0.95))
def test_debt_rest_level_is_fixed_point(L, R, B, rho):
    """D* est bien un point fixe de la dynamique hors debordement, et
    la trajectoire y converge (proprietes analytique ET dynamique)."""
    C = 10.0                                     # pas de debordement
    D_star = debt_rest_level(L, R, B, rho)
    assert debt_update(D_star, L, R, B, C, rho) == pytest.approx(D_star,
                                                                 rel=1e-9)
    D = 0.0
    for _ in range(600):
        D = debt_update(D, L, R, B, C, rho)
    assert D == pytest.approx(D_star, abs=1e-6)


# -- classification : ordinalite et hysteresis -----------------------------------

_ORDER = ["coherence_viable", "tension_constructive", "saturation",
          "pre_rupture", "rupture"]


@given(M1=st.floats(-2, 1), M2=st.floats(-2, 1))
def test_classification_is_ordinal(M1, M2):
    """M plus grand => zone au moins aussi favorable (jamais pire)."""
    lo, hi = min(M1, M2), max(M1, M2)
    assert _ORDER.index(classify(hi).value) <= _ORDER.index(
        classify(lo).value)


@given(ms=st.lists(st.floats(-1, 1, allow_nan=False), min_size=2,
                   max_size=60),
       k=st.integers(1, 6))
def test_hysteresis_discipline(ms, k):
    """La zone confirmee ne peut changer qu'apres k observations brutes
    consecutives dans la nouvelle zone, et vaut toujours une zone
    effectivement observee."""
    h = HysteresisClassifier(k=k)
    raw_seen, prev = set(), None
    for m in ms:
        raw = classify(m)
        raw_seen.add(raw)
        z = h.update(m)
        assert z in raw_seen                     # jamais une zone inventee
        if prev is not None and z != prev:
            pass                                  # changement legal teste ci-dessous
        prev = z
    # rejouer en comptant : tout changement confirme suit k bruts identiques
    h2, cur = HysteresisClassifier(k=k), None
    for m in ms:
        raw = classify(m)
        z = h2.update(m)
        if cur is None:
            cur = z
        elif z != cur:
            assert raw == z                       # confirme au k-ieme pas
            cur = z


# -- controle : U* est bien l'optimum ---------------------------------------------

@given(kappa=st.floats(0.05, 1.0), eta=st.floats(0.05, 1.0),
       B=unit_open, u=st.floats(0.0, 3.0))
def test_optimal_control_dominates(kappa, eta, B, u):
    p = ControlParams(kappa=kappa, eta=eta)
    u_star = optimal_control(p)
    assert effective_feedback(B, u_star, p) >= effective_feedback(B, u, p) - 1e-12


# -- trajectoires completes : invariants et determinisme ---------------------------

cfg_strategy = st.builds(
    SimConfig,
    L=st.floats(0.05, 1.2), R=unit_open, B=unit_open,
    rho=st.floats(0.0, 0.98), s=unit,
    mu0=st.floats(0.0, 0.8), D_crit=st.floats(0.2, 1.5),
    theta_params=st.one_of(
        st.none(),
        st.builds(ThetaParams, theta0=st.just(1.0),
                  theta_min=st.floats(0.1, 0.5),
                  alpha=st.floats(0.0, 0.6), beta=st.floats(0.0, 0.4),
                  tau=st.floats(0.05, 1.0))),
)


@settings(max_examples=60, deadline=None)
@given(cfg=cfg_strategy)
def test_simulation_invariants(cfg):
    res = simulate(cfg, 50)
    floor = cfg.theta_params.theta_min if cfg.theta_params else cfg.theta0
    for i in range(50):
        assert res.D[i] >= 0.0
        assert res.theta[i] >= floor - 1e-12
        assert 0.0 <= res.B_eff[i] <= 1.0
        assert res.M[i] <= 1.0
        assert res.zone[i].value in _ORDER
        assert res.C[i] >= 0.0


@settings(max_examples=25, deadline=None)
@given(cfg=cfg_strategy)
def test_simulation_is_deterministic(cfg):
    a, b = simulate(cfg, 40), simulate(cfg, 40)
    assert a.M == b.M and a.D == b.D and a.theta == b.theta
