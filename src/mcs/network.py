"""Extension 6.4 - systemes MCS interconnectes.

Chaque noeud conserve exactement la dynamique du simulateur individuel ;
le couplage ajoute seulement une charge issue de la dette des voisins.
Un reseau a un noeud sans couplage est donc equivalent a ``simulate``.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import core
from . import extensions as ext
from .simulator import SimConfig, SimResult, _at
from .validation import non_negative, positive


def saturation(D: float, D_seuil: float) -> float:
    """sigma(D) = D / (D + D_seuil), saturation continue."""
    non_negative("D", D)
    positive("D_seuil", D_seuil)
    return D / (D + D_seuil)


def small_gain_bound(rho: float, couplings_row_sum: float, leak_gain: float) -> bool:
    """Condition suffisante pedagogique de type petit gain."""
    return rho + leak_gain * couplings_row_sum < 1.0


@dataclass
class NetworkConfig:
    """Reseau de systemes MCS couples par leur dette normalisee."""

    nodes: list[SimConfig]
    coupling: list[list[float]]
    use_saturation: bool = False
    D_seuil: float = 1.0

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("nodes ne peut pas etre vide")
        n = len(self.nodes)
        if len(self.coupling) != n or any(len(row) != n for row in self.coupling):
            raise ValueError("coupling doit etre une matrice n x n")
        for i, row in enumerate(self.coupling):
            for j, value in enumerate(row):
                non_negative(f"coupling[{i}][{j}]", value)
        positive("D_seuil", self.D_seuil)


def simulate_network(net: NetworkConfig, n_steps: int = 52) -> list[SimResult]:
    """Simule le reseau sans simplifier les extensions des noeuds.

    Le couplage est calcule sur la dette au debut du pas. Il s'ajoute a la
    charge exogene avant les effets du controle. Controle, remboursement,
    recuperation evolutive, Theta evolutif et hysteresis restent identiques
    au moteur individuel.
    """
    if n_steps < 1:
        raise ValueError("n_steps doit etre superieur ou egal a 1")

    n = len(net.nodes)
    results = [SimResult() for _ in range(n)]
    classifiers = [
        core.HysteresisClassifier(k=c.hysteresis_k, thresholds=c.thresholds) for c in net.nodes
    ]
    D = [c.D0 for c in net.nodes]
    theta = [c.theta_params.theta0 if c.theta_params else c.theta0 for c in net.nodes]
    recovery_state: list[float | None] = [None] * n
    U = [0.0] * n

    for t in range(n_steps):
        if net.use_saturation:
            debt_signal = [saturation(d, net.D_seuil) for d in D]
        else:
            debt_signal = [ext.normalized_debt(d, net.nodes[j].D_crit) for j, d in enumerate(D)]

        D_next: list[float] = []
        theta_next = list(theta)
        recovery_next = list(recovery_state)
        U_next: list[float] = []

        for i, cfg in enumerate(net.nodes):
            L_own = _at(cfg.L, t)
            coupled_load = sum(net.coupling[i][j] * debt_signal[j] for j in range(n) if j != i)
            L_input = L_own + coupled_load
            R_brut = _at(cfg.R, t)
            B_brut = _at(cfg.B, t)
            rec_i = recovery_state[i]
            R = rec_i if rec_i is not None else R_brut

            if cfg.control is not None:
                L_eff = ext.effective_load(L_input, U[i], cfg.control)
                B_eff = ext.effective_feedback(B_brut, U[i], cfg.control)
            else:
                L_eff, B_eff = L_input, B_brut

            C = core.capacity(theta[i], R, B_eff, cfg.s)
            A = core.total_load(L_eff, D[i])
            M = core.margin_index(A, C)

            r = results[i]
            r.t.append(t)
            r.L.append(L_own)
            r.L_eff.append(L_eff)
            r.D.append(D[i])
            r.R_eff.append(R)
            r.B_eff.append(B_eff)
            r.theta.append(theta[i])
            r.A.append(A)
            r.C.append(C)
            r.M.append(M)
            r.M_bounded.append(core.bounded_margin_index(A, C))
            r.U.append(U[i])
            r.zone.append(classifiers[i].update(M))

            U_i_next = ext.control_command(M, cfg.control) if cfg.control else 0.0
            U_next.append(U_i_next)

            D_n = ext.normalized_debt(D[i], cfg.D_crit)
            if cfg.mu0 > 0.0:
                mu = ext.repayment_rate(cfg.mu0, R, D_n, cfg.gamma)
                extra = cfg.control.delta * U[i] if cfg.control else 0.0
                d_new = ext.debt_update_with_repayment(D[i], L_eff, R, B_eff, C, cfg.rho, mu, extra)
            else:
                mu = 0.0
                d_new = core.debt_update(D[i], L_eff, R, B_eff, C, cfg.rho)
            r.mu.append(mu)
            D_next.append(d_new)

            if cfg.recovery is not None:
                recovery_next[i] = ext.effective_recovery(
                    _at(cfg.R, t + 1),
                    ext.normalized_debt(d_new, cfg.D_crit),
                    B_eff,
                    cfg.recovery,
                )
            if cfg.theta_params is not None:
                theta_next[i] = ext.theta_update(
                    theta[i], cfg.theta_params, ext.normalized_debt(d_new, cfg.D_crit), B_eff
                )

        D = D_next
        theta = theta_next
        recovery_state = recovery_next
        U = U_next

    return results
