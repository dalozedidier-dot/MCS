"""Tests du noyau : definitions, cas limites (§ 5), zones (§ 4)."""

import math

import pytest

from mcs import core


class TestCapacity:
    def test_pure_product(self):
        assert core.capacity(1.0, 0.8, 0.5) == pytest.approx(0.4)

    def test_failure_of_one_loop_collapses_capacity(self):
        # Substituabilite nulle : B = 0 suffit a effondrer C
        assert core.capacity(10.0, 1.0, 0.0) == 0.0

    def test_substitutability_interpolation(self):
        R, B, theta = 0.9, 0.1, 1.0
        c0 = core.capacity(theta, R, B, s=0.0)
        c1 = core.capacity(theta, R, B, s=1.0)
        assert c0 == pytest.approx(R * B)
        assert c1 == pytest.approx((R + B) / 2)
        chalf = core.capacity(theta, R, B, s=0.5)
        assert c0 < chalf < c1

    def test_bounds_enforced(self):
        with pytest.raises(ValueError):
            core.capacity(0.0, 0.5, 0.5)     # Theta > 0
        with pytest.raises(ValueError):
            core.capacity(1.0, 1.5, 0.5)     # R dans [0,1]
        with pytest.raises(ValueError):
            core.capacity(1.0, 0.5, -0.1)    # B dans [0,1]


class TestMarginIndex:
    def test_no_load_max_margin(self):
        # A = 0 => M = 1, y compris si C = 0
        assert core.margin_index(0.0, 0.5) == 1.0
        assert core.margin_index(0.0, 0.0) == 1.0

    def test_critical_incapacity(self):
        # C = 0 et A > 0 : incapacite critique
        assert core.margin_index(0.3, 0.0) == -math.inf

    def test_zero_at_A_equals_C(self):
        assert core.margin_index(0.5, 0.5) == pytest.approx(0.0)

    def test_upper_bound_is_one(self):
        assert core.margin_index(1e-9, 1.0) <= 1.0

    def test_developed_form(self):
        # M = 1 - (L+D) / (Theta*R*B)
        M = core.margin(L=0.3, D=0.0, theta=1.0, R=0.85, B=0.9)
        assert M == pytest.approx(0.608, abs=1e-3)   # semaine 1, § 9.4


class TestBoundedIndex:
    def test_same_sign_and_zero_as_M(self):
        for A, C in [(0.2, 0.8), (0.5, 0.5), (0.9, 0.3)]:
            M = core.margin_index(A, C)
            Mb = core.bounded_margin_index(A, C)
            assert (M > 0) == (Mb > 0)
            assert (M == 0) == (Mb == 0)

    def test_bounded_in_open_interval(self):
        # M tres negatif reste lisible via M~
        Mb = core.bounded_margin_index(100.0, 0.01)
        assert -1.0 < Mb < 1.0
        assert core.bounded_margin_index(0.0, 1.0) == 1.0


class TestZones:
    def test_bands_cover_the_line_and_are_disjoint(self):
        cases = [(0.5, core.Zone.VIABLE), (0.31, core.Zone.VIABLE),
                 (0.30, core.Zone.TENSION), (0.2, core.Zone.TENSION),
                 (0.10, core.Zone.SATURATION), (0.07, core.Zone.SATURATION),
                 (0.05, core.Zone.PRE_RUPTURE), (0.0, core.Zone.PRE_RUPTURE),
                 (-0.05, core.Zone.PRE_RUPTURE), (-0.06, core.Zone.RUPTURE),
                 (-math.inf, core.Zone.RUPTURE)]
        for M, zone in cases:
            assert core.classify(M) == zone, M

    def test_hysteresis_filters_noise(self):
        h = core.HysteresisClassifier(k=3)
        assert h.update(0.5) == core.Zone.VIABLE
        # 2 excursions ne suffisent pas
        assert h.update(0.2) == core.Zone.VIABLE
        assert h.update(0.2) == core.Zone.VIABLE
        # retour : compteur remis a zero
        assert h.update(0.5) == core.Zone.VIABLE
        # k pas consecutifs confirment le changement
        h.update(0.2); h.update(0.2)
        assert h.update(0.2) == core.Zone.TENSION

    def test_uncertainty_near_threshold(self):
        # § 4 : pres du seuil, 10 % d'erreur sur un proxy ~ 0.1 sur M
        dM = core.margin_uncertainty(M=0.0, A=0.5, C=0.5, rel_err_R=0.10)
        assert dM == pytest.approx(0.10, abs=0.02)
