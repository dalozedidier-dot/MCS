"""Extensions modulaires du MCS (§ 6).

Chaque extension est independante et n'est activee que si le contexte
le justifie. Le noyau (core.py) reste simple.

6.1 Remboursement actif de la dette
6.2 Capacite nominale evolutive (usure / recuperation de Theta)
6.3 Surcharge de controle (effet non monotone sur B)
6.4 Systemes interconnectes (voir network.py)
6.5 Recuperation effective evolutive
"""

from __future__ import annotations

from dataclasses import dataclass

from .core import clip, leak, overflow


# ---------------------------------------------------------------------------
# 6.1 Remboursement actif de la dette
# ---------------------------------------------------------------------------

def normalized_debt(D: float, D_crit: float) -> float:
    """D_n(t) = min(1, D / D_crit)."""
    if D_crit <= 0:
        raise ValueError("D_crit doit etre strictement positif")
    return min(1.0, D / D_crit)


def repayment_rate(mu0: float, R_eff: float, D_n: float, gamma: float) -> float:
    """mu(t) = mu0 * R_eff / (1 + gamma * D_n).

    Piege de dette : plus la dette est haute, plus le remboursement
    devient difficile (choix pessimiste assume, § 6.1).
    """
    return mu0 * R_eff / (1.0 + gamma * D_n)


def debt_update_with_repayment(D: float, L: float, R: float, B: float,
                               C: float, rho: float, mu: float,
                               extra_repay: float = 0.0) -> float:
    """D(t+1) = max(0, rho*D + fuite + max(0,L-C) - (mu+extra)*max(0,C-L)).

    `extra_repay` permet d'ajouter le terme delta*U(t) du controle
    restaurateur (§ 6.3), dans la MEME equation pour eviter deux
    recuperations concurrentes.
    """
    slack = max(0.0, C - L)
    return max(0.0, rho * D + leak(L, R, B) + overflow(L, C)
               - (mu + extra_repay) * slack)


def viability_repayment_threshold(L: float, R: float, B: float,
                                  C: float) -> float:
    """Remboursement minimal pour enrayer la derive au point de
    fonctionnement : mu* tel que mu * max(0, C-L) = (1-R)L(1-B).

    Retourne float('inf') si C <= L (aucun slack : impossible de
    rembourser).
    """
    slack = max(0.0, C - L)
    if slack == 0.0:
        return float("inf")
    return leak(L, R, B) / slack


# ---------------------------------------------------------------------------
# 6.2 Capacite nominale evolutive
# ---------------------------------------------------------------------------

@dataclass
class ThetaParams:
    theta0: float = 1.0      # valeur de reference
    theta_min: float = 0.2   # plancher structurel
    alpha: float = 0.0       # sensibilite a la dette normalisee
    beta: float = 0.0        # sensibilite a la degradation des boucles
    tau: float = 1.0         # inertie (1 = modulation instantanee)


def theta_target(p: ThetaParams, D_n: float, B: float) -> float:
    """Theta_cible = max(Theta_min, Theta0 * (1 - alpha*D_n - beta*(1-B)))."""
    return max(p.theta_min, p.theta0 * (1.0 - p.alpha * D_n - p.beta * (1.0 - B)))


def theta_update(theta: float, p: ThetaParams, D_n: float, B: float) -> float:
    """Theta(t+1) = Theta(t) + tau * (Theta_cible - Theta(t))."""
    return theta + p.tau * (theta_target(p, D_n, B) - theta)


def alpha_runaway(rho: float, D_crit: float, theta0: float,
                  R: float, B: float) -> float:
    """Garde d'emballement : alpha* = (1-rho) * D_crit / (Theta0 * R * B).

    Valeur propre effective de la carte de dette : rho + Theta0*R*B*alpha/D_crit.
    Le cercle vicieux diverge (jusqu'au plancher Theta_min) des que
    alpha >= alpha*. Repere indicatif dans la limite sans inertie.
    """
    denom = theta0 * R * B
    if denom <= 0:
        return float("inf")
    return (1.0 - rho) * D_crit / denom


# ---------------------------------------------------------------------------
# 6.3 Surcharge de controle
# ---------------------------------------------------------------------------

@dataclass
class ControlParams:
    chi: float = 0.1      # cout du controle sur la charge
    kappa: float = 0.3    # effet restaurateur sur B
    eta: float = 0.4      # effet degradant (quadratique) sur B
    delta: float = 0.0    # remboursement induit par le controle
    u_max: float = 1.0    # borne maximale de la commande
    gain: float = 1.0     # gain du regulateur proportionnel sur (M_ref - M)
    m_ref: float = 0.1    # marge visee par le regulateur


def effective_load(L: float, U: float, p: ControlParams) -> float:
    """L_eff(t) = L(t) + chi * U(t)."""
    return L + p.chi * U


def effective_feedback(B: float, U: float, p: ControlParams) -> float:
    """B_eff(t) = clip(B * (1 + kappa*U - eta*U^2), 0, 1).

    Non monotone : a faible intensite le controle ameliore B,
    en exces il la degrade.
    """
    return clip(B * (1.0 + p.kappa * U - p.eta * U * U), 0.0, 1.0)


def optimal_control(p: ControlParams) -> float:
    """U* = kappa / (2*eta), intensite qui maximise B_eff.

    Si U* > u_max, l'optimum est hors domaine et le controle reste
    monotone sur la plage observee.
    """
    if p.eta <= 0:
        return float("inf")
    return p.kappa / (2.0 * p.eta)


def control_command(M_prev: float, p: ControlParams) -> float:
    """Commande proportionnelle U(t) = clip(gain*(m_ref - M(t-1)), 0, u_max).

    Reagit a M(t-1) et NON a M(t), pour eviter une equation implicite
    dans le meme pas (§ 5.1).
    """
    return clip(p.gain * (p.m_ref - M_prev), 0.0, p.u_max)


# ---------------------------------------------------------------------------
# 6.5 Recuperation effective evolutive
# ---------------------------------------------------------------------------

@dataclass
class RecoveryParams:
    delta_D: float = 0.0   # degradation sous dette chronique
    delta_B: float = 0.0   # degradation sous boucles < B_crit
    B_crit: float = 0.3    # seuil critique des boucles
    R_min: float = 0.05    # plancher de recuperation


def effective_recovery(R_brut: float, D_n: float, B_eff: float,
                       p: RecoveryParams) -> float:
    """R_eff(t+1) = clip(R_brut - delta_D*D_n - delta_B*max(0, B_crit - B_eff),
                         R_min, 1).

    Formalise la "recuperation en chambre" : du repos apparent peut mal
    recuperer si l'information vivante ne circule plus (B < B_crit).
    """
    return clip(R_brut - p.delta_D * D_n
                - p.delta_B * max(0.0, p.B_crit - B_eff),
                p.R_min, 1.0)


# ---------------------------------------------------------------------------
# Changement de pas de temps (§ 9.1)
# ---------------------------------------------------------------------------

def rescale_time_step(rho: float, rates: dict[str, float],
                      factor: float) -> tuple[float, dict[str, float]]:
    """Preserve la constante de temps de la memoire quand on change le pas.

    factor = nouveau_pas / ancien_pas. En divisant le pas par deux
    (factor = 0.5) : rho -> rho**0.5 et les taux par pas (fuite,
    remboursement) sont multiplies par 0.5.
    """
    if factor <= 0:
        raise ValueError("factor doit etre strictement positif")
    new_rho = rho ** factor
    new_rates = {k: v * factor for k, v in rates.items()}
    return new_rho, new_rates
