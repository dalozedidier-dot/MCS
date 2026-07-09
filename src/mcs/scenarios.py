"""Scenarios pedagogiques (§ 7) et micro-simulation equipe projet (§ 9.4).

Chaque scenario retourne (SimConfig, n_steps) ou directement un resultat.
Ce sont des illustrations, pas des validations empiriques.
"""

from __future__ import annotations

from . import extensions as ext
from .network import NetworkConfig, simulate_network
from .simulator import SimConfig, SimResult, simulate


def progressive_recovery(n_steps: int = 40) -> SimResult:
    """Un choc augmente L, puis R reste eleve et B fonctionne :
    la dette diminue et M remonte progressivement."""
    def L(t):
        return 0.75 if 5 <= t < 10 else 0.35
    cfg = SimConfig(L=L, R=0.9, B=0.85, rho=0.7, mu0=0.5, D_crit=0.5)
    return simulate(cfg, n_steps)


def slow_degradation(n_steps: int = 60) -> SimResult:
    """Meme a charge moderee et constante, la dette de sous-recuperation
    monte, la capacite nominale s'use, et M glisse sans bruit."""
    cfg = SimConfig(
        L=0.4, R=0.7, B=0.65, rho=0.85, D_crit=0.6,
        theta_params=ext.ThetaParams(theta0=1.0, theta_min=0.3,
                                     alpha=0.25, beta=0.15, tau=0.15),
    )
    return simulate(cfg, n_steps)


def control_overshoot(n_steps: int = 60, gain: float = 4.0) -> SimResult:
    """U(t) augmente quand M baisse. Sous U*, le controle restaure B et
    la marge remonte ; au-dela, il remplace le retour vivant et aggrave."""
    cfg = SimConfig(
        L=0.45, R=0.7, B=0.6, rho=0.8, mu0=0.3, D_crit=0.6,
        control=ext.ControlParams(chi=0.15, kappa=0.4, eta=0.5,
                                  delta=0.05, u_max=1.5,
                                  gain=gain, m_ref=0.2),
    )
    return simulate(cfg, n_steps)


def chamber_recovery(n_steps: int = 60) -> SimResult:
    """Recuperation en chambre : repos apparent (R_brut eleve) mais
    boucles basses -> la recuperation effective se degrade et D monte."""
    cfg = SimConfig(
        L=0.4, R=0.85, B=0.25, rho=0.8, D_crit=0.6,
        recovery=ext.RecoveryParams(delta_D=0.3, delta_B=0.5,
                                    B_crit=0.4, R_min=0.2),
    )
    return simulate(cfg, n_steps)


def coupled_cascade(n_steps: int = 60) -> list[SimResult]:
    """Trois systemes A -> B -> C : la dette de A devient une charge
    pour B, puis pour C. Propagation d'une fragilite."""
    a = SimConfig(L=0.5, R=0.6, B=0.55, rho=0.85, D_crit=0.5)   # fragile
    b = SimConfig(L=0.35, R=0.8, B=0.8, rho=0.8, D_crit=0.5)
    c = SimConfig(L=0.3, R=0.85, B=0.85, rho=0.8, D_crit=0.5)
    coupling = [
        [0.0, 0.0, 0.0],
        [0.4, 0.0, 0.0],   # B recoit la dette de A
        [0.0, 0.4, 0.0],   # C recoit la dette de B
    ]
    return simulate_network(NetworkConfig(nodes=[a, b, c],
                                          coupling=coupling), n_steps)


# ---------------------------------------------------------------------------
# § 9.4 - Micro-simulation fictive : equipe projet (pas = semaine)
# ---------------------------------------------------------------------------

#: Entrees hebdomadaires du tableau § 9.4 (valeurs normalisees).
TEAM_WEEKS = {
    "L": [0.30, 0.35, 0.40, 0.45, 0.45, 0.42, 0.38, 0.32],
    "R": [0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.65, 0.75],
    "B": [0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.70, 0.80],
}

#: Trajectoires attendues du document (D en debut de semaine, M).
TEAM_EXPECTED_D = [0.000, 0.005, 0.014, 0.032, 0.061, 0.099, 0.173, 0.187]
TEAM_EXPECTED_M = [0.608, 0.479, 0.309, 0.082, -0.123, -0.331, -0.216, 0.155]


def project_team(rho: float = 0.85) -> SimResult:
    """Reproduit la micro-simulation du § 9.4 (Theta = 1, noyau pur).

    La baisse de charge en semaine 8 ne suffit pas a revenir en zone
    viable : la dette accumulee continue de peser.
    """
    cfg = SimConfig(L=TEAM_WEEKS["L"], R=TEAM_WEEKS["R"], B=TEAM_WEEKS["B"],
                    theta0=1.0, D0=0.0, rho=rho, hysteresis_k=1)
    return simulate(cfg, n_steps=8)


ALL_SCENARIOS = {
    "recuperation_progressive": progressive_recovery,
    "degradation_lente": slow_degradation,
    "controle_qui_s_emballe": control_overshoot,
    "recuperation_en_chambre": chamber_recovery,
    "equipe_projet_9_4": project_team,
}
