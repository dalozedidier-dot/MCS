"""Tests des extensions 6.2, 6.3, 6.4, 6.5 et du changement de pas (§ 9.1)."""

import pytest

from mcs import core, extensions as ext
from mcs.network import NetworkConfig, saturation, simulate_network
from mcs.simulator import SimConfig, simulate


class TestEvolvingTheta:
    def test_target_floor(self):
        p = ext.ThetaParams(theta0=1.0, theta_min=0.3, alpha=2.0, beta=1.0)
        assert ext.theta_target(p, D_n=1.0, B=0.0) == 0.3

    def test_inertia(self):
        """tau faible : Theta conserve une histoire (usure lente)."""
        p_slow = ext.ThetaParams(theta0=1.0, theta_min=0.2,
                                 alpha=0.5, tau=0.1)
        p_fast = ext.ThetaParams(theta0=1.0, theta_min=0.2,
                                 alpha=0.5, tau=1.0)
        t_slow = ext.theta_update(1.0, p_slow, D_n=1.0, B=1.0)
        t_fast = ext.theta_update(1.0, p_fast, D_n=1.0, B=1.0)
        assert t_fast == pytest.approx(0.5)      # recalcul direct
        assert t_fast < t_slow < 1.0             # inertie amortit

    def test_recovery_toward_theta0(self):
        """Quand les conditions s'ameliorent, Theta remonte vers Theta0."""
        p = ext.ThetaParams(theta0=1.0, theta_min=0.2, alpha=0.5, tau=0.3)
        theta = 0.6
        for _ in range(50):
            theta = ext.theta_update(theta, p, D_n=0.0, B=1.0)
        assert theta == pytest.approx(1.0, abs=1e-4)

    def test_alpha_runaway_threshold(self):
        """Garde alpha* (§ 6.2), valable dans le REGIME ACTIF (L > C) :
        valeur propre rho + Theta0*R*B*alpha/D_crit. En deca de alpha*,
        la dette reste bornee et la capacite preservee ; au-dela, le
        cercle vicieux s'emballe jusqu'a saturation de la dette."""
        rho, D_crit, theta0, R, B, L = 0.9, 2.0, 1.0, 0.8, 0.8, 0.66
        assert L > theta0 * R * B  # regime actif des le depart
        a_star = ext.alpha_runaway(rho, D_crit, theta0, R, B)  # 0.3125

        def run(alpha, n=800):
            p = ext.ThetaParams(theta0=theta0, theta_min=0.2,
                                alpha=alpha, tau=1.0)
            cfg = SimConfig(L=L, R=R, B=B, rho=rho, D_crit=D_crit,
                            theta_params=p)
            r = simulate(cfg, n)
            return r.theta[-1], r.D[-1]

        th_lo, d_lo = run(0.5 * a_star)
        th_hi, d_hi = run(1.5 * a_star)
        assert d_lo / D_crit < 0.6 and th_lo > 0.9   # sous alpha* : borne
        assert d_hi >= D_crit and th_hi < 0.6        # au-dela : emballement
        # alpha tres grand : effondrement jusqu'au plancher Theta_min
        th_floor, _ = run(1.2)
        assert th_floor == pytest.approx(0.2, abs=1e-6)


class TestControl:
    def test_non_monotone_effect_on_B(self):
        p = ext.ControlParams(kappa=0.4, eta=0.5)
        u_star = ext.optimal_control(p)
        assert u_star == pytest.approx(0.4)
        b0 = ext.effective_feedback(0.5, 0.0, p)
        b_opt = ext.effective_feedback(0.5, u_star, p)
        b_over = ext.effective_feedback(0.5, 3.0 * u_star, p)
        assert b_opt > b0            # faible intensite : restaure
        assert b_over < b_opt        # exces : degrade
        # U* maximise B_eff sur une grille
        grid = [ext.effective_feedback(0.5, u / 100, p) for u in range(0, 200)]
        assert max(grid) == pytest.approx(b_opt, abs=1e-4)

    def test_control_adds_load(self):
        p = ext.ControlParams(chi=0.2)
        assert ext.effective_load(0.4, 1.0, p) == pytest.approx(0.6)

    def test_command_reacts_to_previous_margin(self):
        p = ext.ControlParams(gain=2.0, m_ref=0.1, u_max=1.0)
        assert ext.control_command(0.5, p) == 0.0      # marge confortable
        assert ext.control_command(-0.2, p) == pytest.approx(0.6)
        assert ext.control_command(-5.0, p) == 1.0     # borne u_max


class TestEvolvingRecovery:
    def test_chamber_recovery(self):
        """Repos apparent + boucles basses => R_eff se degrade (§ 6.5)."""
        p = ext.RecoveryParams(delta_D=0.3, delta_B=0.5,
                               B_crit=0.4, R_min=0.2)
        r_healthy = ext.effective_recovery(0.85, D_n=0.0, B_eff=0.8, p=p)
        r_chamber = ext.effective_recovery(0.85, D_n=0.5, B_eff=0.1, p=p)
        assert r_healthy == pytest.approx(0.85)
        assert r_chamber < r_healthy
        # plancher R_min
        r_floor = ext.effective_recovery(0.3, D_n=1.0, B_eff=0.0, p=p)
        assert r_floor == 0.2


class TestNetwork:
    def test_debt_propagates_as_load(self):
        """La dette du noeud fragile devient une charge pour son voisin."""
        fragile = SimConfig(L=0.5, R=0.6, B=0.55, rho=0.85, D_crit=0.5)
        healthy = SimConfig(L=0.3, R=0.9, B=0.9, rho=0.8, D_crit=0.5)
        coupled = NetworkConfig(nodes=[fragile, healthy],
                                coupling=[[0.0, 0.0], [0.5, 0.0]])
        alone = NetworkConfig(nodes=[fragile, healthy],
                              coupling=[[0.0, 0.0], [0.0, 0.0]])
        res_c = simulate_network(coupled, 40)
        res_a = simulate_network(alone, 40)
        assert res_c[1].M[-1] < res_a[1].M[-1]
        assert res_c[1].L_eff[-1] > res_a[1].L_eff[-1]

    def test_boundedness_via_normalization(self):
        """D_n dans [0,1] : la charge recue reste < L_propre + sum(lambda)."""
        a = SimConfig(L=0.8, R=0.3, B=0.3, rho=0.99, D_crit=0.2)
        b = SimConfig(L=0.2, R=0.9, B=0.9, rho=0.8, D_crit=0.5)
        net = NetworkConfig(nodes=[a, b], coupling=[[0.0, 0.0], [0.7, 0.0]])
        res = simulate_network(net, 200)
        assert max(res[1].L_eff) <= 0.2 + 0.7 + 1e-9

    def test_saturation_keeps_differentiation(self):
        s1, s2 = saturation(1.0, 0.5), saturation(10.0, 0.5)
        assert s1 < s2 < 1.0    # differencie les fortes dettes
      