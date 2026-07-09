"""Simulateur discret du MCS, suivant l'ordre de calcul du § 5.1.

Pseudo-code implemente :
1. Observer L(t), D(t), R(t), B(t), Theta(t) et U(t)         [U reagit a M(t-1)]
2. Calculer L_eff(t) et B_eff(t) si le module de controle est actif
3. Calculer C(t), A(t), puis M(t)
4. Choisir U(t+1) a partir de M(t)
5. Mettre a jour D(t+1), puis R_eff(t+1), B_eff(t+1) et Theta(t+1)
6. Passer au pas suivant

Cet ordre evite la circularite : M(t) est calcule avec les variables
disponibles au temps t, puis les etats sont mis a jour pour t+1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from . import core, extensions as ext


Series = Sequence[float] | Callable[[int], float] | float


def _at(x: Series, t: int) -> float:
    """Lit une entree exogene : constante, sequence ou fonction de t."""
    if callable(x):
        return float(x(t))
    if isinstance(x, (int, float)):
        return float(x)
    return float(x[min(t, len(x) - 1)])


@dataclass
class SimConfig:
    """Configuration d'une simulation.

    Entrees exogenes (constante, liste ou fonction de t) :
      L : charge par pas de temps
      R : recuperation brute (devient R_brut si recovery est actif)
      B : boucles de retour brutes
    """
    L: Series = 0.4
    R: Series = 0.8
    B: Series = 0.8

    # Noyau
    theta0: float = 1.0
    D0: float = 0.0
    rho: float = 0.8       # memoire de dette
    s: float = 0.0         # substituabilite R/B (0 = produit pur)

    # Extension 6.1 - remboursement actif (mu0 = 0 => desactive)
    mu0: float = 0.0
    gamma: float = 1.0
    D_crit: float = 1.0

    # Extension 6.2 - Theta evolutif (None => Theta constant)
    theta_params: ext.ThetaParams | None = None

    # Extension 6.3 - controle (None => desactive)
    control: ext.ControlParams | None = None

    # Extension 6.5 - recuperation effective evolutive (None => R_eff = R)
    recovery: ext.RecoveryParams | None = None

    # Lecture
    hysteresis_k: int = 3
    thresholds: dict | None = None


@dataclass
class SimResult:
    """Trajectoires simulees (listes de longueur n_steps)."""
    t: list[int] = field(default_factory=list)
    L: list[float] = field(default_factory=list)
    L_eff: list[float] = field(default_factory=list)
    D: list[float] = field(default_factory=list)
    R_eff: list[float] = field(default_factory=list)
    B_eff: list[float] = field(default_factory=list)
    theta: list[float] = field(default_factory=list)
    A: list[float] = field(default_factory=list)
    C: list[float] = field(default_factory=list)
    M: list[float] = field(default_factory=list)
    M_bounded: list[float] = field(default_factory=list)
    U: list[float] = field(default_factory=list)
    mu: list[float] = field(default_factory=list)
    zone: list[core.Zone] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in
             ("t", "L", "L_eff", "D", "R_eff", "B_eff", "theta",
              "A", "C", "M", "M_bounded", "U", "mu")}
        d["zone"] = [z.value for z in self.zone]
        return d


def simulate(cfg: SimConfig, n_steps: int = 52) -> SimResult:
    """Execute n_steps pas de simulation et retourne les trajectoires."""
    res = SimResult()
    classifier = core.HysteresisClassifier(k=cfg.hysteresis_k,
                                           thresholds=cfg.thresholds)

    D = cfg.D0
    theta = cfg.theta_params.theta0 if cfg.theta_params else cfg.theta0
    R_eff_state: float | None = None   # etat de l'extension 6.5
    U = 0.0                            # commande courante (reagit a M(t-1))

    for t in range(n_steps):
        # 1. Observer les entrees exogenes
        L = _at(cfg.L, t)
        R_brut = _at(cfg.R, t)
        B_brut = _at(cfg.B, t)
        R = R_eff_state if R_eff_state is not None else R_brut

        # 2. Effets du controle (charge et boucles effectives)
        if cfg.control is not None:
            L_eff = ext.effective_load(L, U, cfg.control)
            B_eff = ext.effective_feedback(B_brut, U, cfg.control)
        else:
            L_eff, B_eff = L, B_brut

        # 3. C(t), A(t), M(t)
        C = core.capacity(theta, R, B_eff, cfg.s)
        A = core.total_load(L_eff, D)
        M = core.margin_index(A, C)

        # Enregistrement
        res.t.append(t)
        res.L.append(L)
        res.L_eff.append(L_eff)
        res.D.append(D)
        res.R_eff.append(R)
        res.B_eff.append(B_eff)
        res.theta.append(theta)
        res.A.append(A)
        res.C.append(C)
        res.M.append(M)
        res.M_bounded.append(core.bounded_margin_index(A, C))
        res.U.append(U)
        res.zone.append(classifier.update(M))

        # 4. Commande du pas suivant, choisie a partir de M(t)
        if cfg.control is not None:
            U_next = ext.control_command(M, cfg.control)
        else:
            U_next = 0.0

        # 5. Mises a jour d'etat pour t+1
        D_n = ext.normalized_debt(D, cfg.D_crit)
        if cfg.mu0 > 0.0:
            mu = ext.repayment_rate(cfg.mu0, R, D_n, cfg.gamma)
            extra = (cfg.control.delta * U) if cfg.control else 0.0
            D = ext.debt_update_with_repayment(D, L_eff, R, B_eff, C,
                                               cfg.rho, mu, extra)
        else:
            mu = 0.0
            D = core.debt_update(D, L_eff, R, B_eff, C, cfg.rho)
        res.mu.append(mu)

        if cfg.recovery is not None:
            D_n_new = ext.normalized_debt(D, cfg.D_crit)
            R_eff_state = ext.effective_recovery(_at(cfg.R, t + 1),
                                                 D_n_new, B_eff,
                                                 cfg.recovery)
        if cfg.theta_params is not None:
            theta = ext.theta_update(theta, cfg.theta_params,
                                     ext.normalized_debt(D, cfg.D_crit),
                                     B_eff)
        U = U_next

    return res
