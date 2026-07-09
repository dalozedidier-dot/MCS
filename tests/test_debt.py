"""Tests de la dynamique de dette (§ 3.1) et du remboursement actif (§ 6.1)."""

import pytest

from mcs import core, extensions as ext


class TestDebtDynamics:
    def test_debt_rises_in_healthy_zone(self):
        """These centrale : la dette est un indicateur AVANCE.
        Elle monte des que R < 1 ou B < 1, meme si M(t) > 0."""
        L, R, B, theta, rho = 0.3, 0.85, 0.9, 1.0, 0.8
        C = core.capacity(theta, R, B)
        D = 0.0
        assert core.margin(L, D, theta, R, B) > 0.3   # zone viable
        D1 = core.debt_update(D, L, R, B, C, rho)
        assert D1 > 0.0                               # et pourtant D monte

    def test_no_debt_when_full_recovery(self):
        # R = 1 => fuite nulle ; pas de debordement => pas de dette
        C = core.capacity(1.0, 1.0, 0.5)
        assert core.debt_update(0.0, 0.4, 1.0, 0.5, C, 0.8) == 0.0

    def test_overflow_term(self):
        # L > C ajoute le debordement instantane
        L, R, B, rho = 0.9, 0.5, 0.5, 0.0
        C = core.capacity(1.0, R, B)   # 0.25
        D1 = core.debt_update(0.0, L, R, B, C, rho)
        assert D1 == pytest.approx(core.leak(L, R, B) + (L - C))

    def test_rest_level_fixed_point(self):
        """A intrants constants, D converge vers D* = (1-R)L(1-B)/(1-rho)."""
        L, R, B, rho, theta = 0.3, 0.8, 0.7, 0.6, 2.0
        C = core.capacity(theta, R, B)
        assert L < C                     # pas de debordement
        D = 0.0
        for _ in range(200):
            D = core.debt_update(D, L, R, B, C, rho)
        assert D == pytest.approx(core.debt_rest_level(L, R, B, rho), rel=1e-6)

    def test_rest_level_positive_iff_recovery_incomplete(self):
        assert core.debt_rest_level(0.5, 1.0, 0.5, 0.8) == 0.0
        assert core.debt_rest_level(0.5, 0.9, 0.9, 0.8) > 0.0

    def test_rho_one_unbounded_growth(self):
        """rho = 1 : aucune resorption passive, la dette croit sans borne
        si la fuite reste positive (§ 3.1, domaine de validite)."""
        L, R, B = 0.4, 0.8, 0.8
        C = core.capacity(5.0, R, B)
        D, prev = 0.0, -1.0
        for _ in range(100):
            prev, D = D, core.debt_update(D, L, R, B, C, rho=1.0)
        assert D > prev > 0
        with pytest.raises(ValueError):
            core.debt_rest_level(L, R, B, rho=1.0)

    def test_debt_never_negative(self):
        D = ext.debt_update_with_repayment(0.01, 0.1, 0.99, 0.99,
                                           C=5.0, rho=0.5, mu=10.0)
        assert D == 0.0


class TestActiveRepayment:
    def test_viability_condition(self):
        """En deca du seuil mu*, la dette derive ; au-dela, elle se
        stabilise (§ 6.1, condition de viabilite)."""
        L, R, B, theta, rho = 0.4, 0.7, 0.7, 1.2, 0.9
        C = core.capacity(theta, R, B)
        mu_star = ext.viability_repayment_threshold(L, R, B, C)

        def run(mu, n=400):
            D = 0.5
            for _ in range(n):
                D = ext.debt_update_with_repayment(D, L, R, B, C, rho, mu)
            return D

        assert run(mu=0.5 * mu_star) > run(mu=2.0 * mu_star)
        # au-dela du seuil, la dette reste bornee pres de zero
        assert run(mu=2.0 * mu_star) < 0.2

    def test_threshold_infinite_without_slack(self):
        # C <= L : aucun slack, remboursement impossible
        assert ext.viability_repayment_threshold(0.6, 0.5, 0.5, C=0.5) == float("inf")

    def test_debt_trap_slows_repayment(self):
        """mu decroit quand la dette monte : cercle du piege de dette."""
        lo = ext.repayment_rate(0.5, 0.8, D_n=0.1, gamma=2.0)
        hi = ext.repayment_rate(0.5, 0.8, D_n=1.0, gamma=2.0)
        assert hi < lo

    def test_normalized_debt_bounds(self):
        assert ext.normalized_debt(0.0, 1.0) == 0.0
        assert ext.normalized_debt(5.0, 1.0) == 1.0
