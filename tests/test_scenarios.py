"""Tests des scenarios (§ 7) et reproduction de la table § 9.4."""

import pytest

from mcs import Zone, scenarios


class TestProjectTeam94:
    """La micro-simulation equipe projet doit reproduire la table du
    document (Theta = 1, rho = 0.85, pas hebdomadaire, noyau pur)."""

    def test_debt_trajectory(self):
        res = scenarios.project_team()
        for week, (d_sim, d_doc) in enumerate(
                zip(res.D, scenarios.TEAM_EXPECTED_D), start=1):
            assert d_sim == pytest.approx(d_doc, abs=0.002), f"semaine {week}"

    def test_margin_trajectory(self):
        res = scenarios.project_team()
        for week, (m_sim, m_doc) in enumerate(
                zip(res.M, scenarios.TEAM_EXPECTED_M), start=1):
            assert m_sim == pytest.approx(m_doc, abs=0.005), f"semaine {week}"

    def test_week8_lesson(self):
        """La baisse de charge en semaine 8 ne suffit pas a revenir en
        zone viable : distinguer baisse de pression et recuperation."""
        res = scenarios.project_team()
        assert res.M[7] > 0                      # marge redevenue positive
        assert res.M[7] < 0.3                    # mais pas viable (tension)
        assert res.D[7] > res.D[4]               # la dette pese encore

    def test_zones_sequence(self):
        res = scenarios.project_team()
        from mcs.core import classify
        assert classify(res.M[0]) == Zone.VIABLE
        assert classify(res.M[3]) == Zone.SATURATION
        assert classify(res.M[4]) == Zone.RUPTURE


class TestPedagogicalScenarios:
    def test_progressive_recovery(self):
        res = scenarios.progressive_recovery()
        m_during_shock = min(res.M[5:12])
        assert res.M[-1] > m_during_shock        # M remonte apres le choc
        assert res.D[-1] < max(res.D)            # la dette a ete resorbee

    def test_slow_degradation_silent_slide(self):
        """A intrants constants, M glisse et Theta s'use : le systeme
        ne casse pas tout de suite, il glisse."""
        res = scenarios.slow_degradation()
        assert res.L[0] == res.L[-1]             # charge constante
        assert res.M[-1] < res.M[0] - 0.2        # perte de marge endogene
        assert res.theta[-1] < res.theta[0]      # usure de la capacite
        assert res.D[-1] > res.D[0]

    def test_chamber_recovery_despite_rest(self):
        """R_brut eleve mais boucles basses : R_eff se degrade et D monte."""
        res = scenarios.chamber_recovery()
        assert res.R_eff[-1] < 0.85              # sous le repos apparent
        assert res.D[-1] > 0.1

    def test_control_overshoot_worse_than_moderate(self):
        """Un controle sur-dimensionne finit avec une marge plus basse
        qu'un controle modere (branche pathologique au-dela de U*)."""
        moderate = scenarios.control_overshoot(gain=1.0)
        overshoot = scenarios.control_overshoot(gain=12.0)
        assert overshoot.M[-1] < moderate.M[-1]

    def test_cascade_propagation(self):
        """A fragile -> B -> C : la fragilite se propage en aval."""
        res = scenarios.coupled_cascade()
        a, b, c = res
        # le noeud amont accumule de la dette
        assert a.D[-1] > 0.1
        # les noeuds aval voient leur charge effective augmenter
        assert b.L_eff[-1] > b.L[-1]
        assert c.L_eff[-1] > c.L[-1]
        # et leur marge finale est entamee par rapport au depart
        assert b.M[-1] < b.M[0]
