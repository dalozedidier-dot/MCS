"""Tests des experiences de demonstration (irreversibilite, carte de regime)."""

import pytest

from mcs import SimConfig
from mcs.experiments import (
    hysteresis_loop,
    load_ramp,
    memoryless_config,
    regime_map,
)
from mcs.extensions import ThetaParams

MEMORY_CFG = SimConfig(
    R=0.7, B=0.65, rho=0.9, D_crit=0.6, mu0=0.15,
    theta_params=ThetaParams(theta0=1.0, theta_min=0.4,
                             alpha=0.3, beta=0.1, tau=0.2))


def test_load_ramp_symmetric():
    r = load_ramp(0.1, 0.9, n_up=5, plateau=2)
    assert len(r) == 12
    assert r[0] == r[-1] == 0.1
    assert max(r) == 0.9
    assert r[5] == r[6] == 0.9          # plateau


def test_irreversibility_loop_is_open():
    """Avec memoire (dette + usure), le retour ne repasse pas par le
    meme chemin : aire positive et marge plus basse a charge egale."""
    loop = hysteresis_loop(MEMORY_CFG)
    assert loop.loop_area > 0.01
    assert loop.gap_at_start < -0.01     # M(retour) < M(depart)
    assert loop.D_final > 0.0
    assert loop.theta_final < 1.0        # trace dans la capacite nominale
    # la montee domine la descente point a point (au sens large)
    assert all(u >= d - 1e-9 for u, d in zip(loop.M_up, loop.M_down, strict=True))


def test_memoryless_control_closes_the_loop():
    """Temoin : sans memoire (rho = 0, Theta fige), la boucle s'ecrase
    - l'irreversibilite vient bien de la dette et de l'usure, pas de la
    rampe elle-meme."""
    open_loop = hysteresis_loop(MEMORY_CFG)
    closed = hysteresis_loop(memoryless_config(MEMORY_CFG))
    assert closed.loop_area < open_loop.loop_area / 5
    assert abs(closed.gap_at_start) < 0.02


def test_regime_map_matches_alpha_star():
    """Hors bande d'ambiguite, le verdict empirique (perturbation
    amplifiee) doit suivre la frontiere analytique alpha*(rho)."""
    rm = regime_map(n_alpha=15, n_rho=15)
    assert rm.agreement >= 0.99
    flat = [c for row in rm.growing for c in row]
    assert any(flat) and not all(flat)      # carte non triviale


def test_measured_slope_matches_eigenvalue():
    """La pente MESUREE a travers simulate() doit coincider avec la
    valeur propre theorique rho + Theta0*R*B*alpha/D_crit."""
    from mcs.experiments import perturbation_slope
    rho, a, R, B, th0, Dc = 0.7, 0.3, 0.9, 0.9, 1.0, 0.5
    sl = perturbation_slope(rho, a, R, B, th0, 0.05, Dc,
                            L=1.2 * th0 * R * B)
    assert sl == pytest.approx(rho + th0 * R * B * a / Dc, rel=1e-6)


def test_regime_map_monotone_in_alpha():
    """A rho fixe, la pente croit avec alpha : si une perturbation
    s'amplifie, elle s'amplifie aussi pour tout alpha superieur."""
    rm = regime_map(n_alpha=12, n_rho=6)
    for row in rm.growing:
        seen_true = False
        for c in row:
            if seen_true:
                assert c
            seen_true = seen_true or c
