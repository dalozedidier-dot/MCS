"""Tests Phase 1 - robustesse numerique (§ 9.6)."""

import math

import pytest

from mcs import SimConfig
from mcs.core import margin_uncertainty
from mcs.robustness import (
    cascade_sweep,
    debt_jacobian,
    false_alarm_study,
    monte_carlo,
    network_stability,
    oscillation_score,
    sensitivity_tornado,
    spectral_radius,
)

# -- rayon spectral ---------------------------------------------------------

def test_spectral_radius_diagonal():
    A = [[0.5, 0.0], [0.0, 0.9]]
    assert spectral_radius(A) == pytest.approx(0.9, abs=1e-6)


def test_spectral_radius_known_2x2():
    # [[2, 1], [1, 2]] : valeurs propres 1 et 3
    assert spectral_radius([[2.0, 1.0], [1.0, 2.0]]) == pytest.approx(3.0,
                                                                      abs=1e-6)


def test_debt_jacobian_structure():
    J = debt_jacobian(rhos=[0.8, 0.7],
                      coupling=[[0.0, 0.4], [0.2, 0.0]],
                      leak_gains=[0.12, 0.2], D_crits=[1.0, 0.5])
    assert J[0][0] == 0.8 and J[1][1] == 0.7
    assert J[0][1] == pytest.approx(0.12 * 0.4 / 0.5)
    assert J[1][0] == pytest.approx(0.2 * 0.2 / 1.0)


def test_small_gain_is_upper_bound_of_spectral_radius():
    """La condition de ligne du noyau majore le verdict exact : un
    reseau declare stable par petit gain l'est aussi au sens spectral."""
    v = network_stability(rhos=[0.7, 0.7],
                          coupling=[[0.0, 0.1], [0.1, 0.0]],
                          R_list=[0.8, 0.8], B_list=[0.8, 0.8],
                          D_crits=[1.0, 1.0])
    assert max(v["small_gain_rows"]) < 1.0
    assert v["spectral_radius"] <= max(v["small_gain_rows"]) + 1e-9
    assert v["stable"]


def test_cascade_follows_spectral_threshold():
    """La bascule de cascade suit le seuil rho(J) = 1 : sous le seuil
    aucun noeud ne casse, tres au-dessus des noeuds cassent."""
    nodes = [SimConfig(L=0.2, R=0.8, B=0.7, rho=0.9, D_crit=0.3)
             for _ in range(3)]
    pattern = [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
    recs = cascade_sweep(nodes, pattern, strengths=[0.0, 0.05, 1.2],
                         n_steps=120)
    assert recs[0]["spectral_radius"] < 1.0    # isole : stable
    assert recs[0]["nodes_broken"] == 0        # et effectivement viable
    assert recs[-1]["spectral_radius"] > 1.0   # fort couplage : instable
    assert recs[-1]["nodes_broken"] == 3       # cascade complete


# -- Monte Carlo et hysteresis ----------------------------------------------

def test_monte_carlo_reproducible_and_bounded():
    cfg = SimConfig(L=0.4, R=0.8, B=0.8, rho=0.7)
    a = monte_carlo(cfg, n_steps=40, n_runs=50, sigma_L=0.1,
                    sigma_R=0.05, sigma_B=0.05, seed=42)
    b = monte_carlo(cfg, n_steps=40, n_runs=50, sigma_L=0.1,
                    sigma_R=0.05, sigma_B=0.05, seed=42)
    assert a.M_final == b.M_final          # meme graine => memes runs
    assert a.diverged == 0                 # regime sain : pas d'emballement
    q = a.as_dict()["M_final_q05_q50_q95"]
    assert q[0] <= q[1] <= q[2]


def test_noise_free_monte_carlo_matches_deterministic():
    from mcs import simulate
    cfg = SimConfig(L=0.4, R=0.8, B=0.8, rho=0.7)
    mc = monte_carlo(cfg, n_steps=30, n_runs=3)
    det = simulate(cfg, 30)
    for m in mc.M_final:
        assert m == pytest.approx(det.M[-1])


def test_hysteresis_suppresses_false_alarms_monotonically():
    """Sur un systeme stationnaire bruite, la suppression des
    transitions doit croitre (au sens large) avec k."""
    # Regime stationnaire proche d'un seuil de zone : bruit => flicker
    cfg = SimConfig(L=0.55, R=0.85, B=0.85, rho=0.5)
    recs = false_alarm_study(cfg, ks=(1, 3, 6), n_steps=60, n_runs=40,
                             sigma=0.12, seed=7)
    assert recs[0].transitions_raw > 0
    supp = [r.suppression for r in recs]
    assert supp == sorted(supp)
    assert recs[-1].suppression > recs[0].suppression


# -- oscillations -------------------------------------------------------------

def test_oscillation_score_flat_vs_periodic():
    flat = [1.0] * 50
    per = [math.sin(0.8 * t) for t in range(60)]
    assert oscillation_score(flat)["sign_changes"] == 0
    s = oscillation_score(per)
    assert s["sign_changes"] > 5
    assert s["amplitude"] == pytest.approx(1.0, abs=0.1)


# -- tornado -------------------------------------------------------------------

def test_tornado_total_matches_margin_uncertainty():
    """La somme des contributions doit coincider avec la propagation
    d'incertitude du noyau (§ 4) - coherence interne du modele."""
    L, D, theta, R, B = 0.4, 0.2, 1.0, 0.8, 0.7
    t = sensitivity_tornado(L, D, theta, R, B, rel_err=0.1)
    A = L + D
    C = theta * R * B
    ref = margin_uncertainty(t["M"], A, C, rel_err_A=0.1,
                             rel_err_theta=0.1, rel_err_R=0.1,
                             rel_err_B=0.1)
    assert t["total"] == pytest.approx(ref)
