"""Extension 6.4 - systemes interconnectes.

Dans un reseau, la dette d'un systeme devient une charge pour un autre :

    L_i(t) = L_i_propre(t) + sum_j lambda_ij * D_n,j(t)

La dette normalisee D_n dans [0,1] garantit la bornitude globale ; la
saturation continue sigma(D) = D / (D + D_seuil) conserve la
differenciation aux fortes dettes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import core, extensions as ext
from .simulator import SimConfig, SimResult, _at


def saturation(D: float, D_seuil: float) -> float:
    """sigma(D) = D / (D + D_seuil), saturation continue."""
    if D_seuil <= 0:
        raise ValueError("D_seuil doit etre strictement positif")
    return D / (D + D_seuil)


def small_gain_bound(rho: float, couplings_row_sum: float,
                     leak_gain: float) -> bool:
    """Condition suffisante de type petit gain (regime non sature) :
    persistance interne * gains de couplage < 1.

    Approximation pedagogique : pour des couplages asymetriques, la
    condition exacte porte sur le rayon spectral de la matrice de
    couplage (a verifier numeriquement, cf. tests).
    """
    return rho + leak_gain * couplings_row_sum < 1.0


@dataclass
class NetworkConfig:
    """Reseau de n systemes MCS couples par leur dette.

    nodes    : configurations individuelles (leurs extensions s'appliquent)
    coupling : matrice lambda[i][j] - poids de la dette du noeud j
               dans la charge du noeud i
    use_saturation : si True, utilise sigma(D_j) au lieu de D_n,j
    D_seuil  : echelle de saturation
    """
    nodes: list[SimConfig]
    coupling: list[list[float]]
    use_saturation: bool = False
    D_seuil: float = 1.0


def simulate_network(net: NetworkConfig, n_steps: int = 52) -> list[SimResult]:
    """Simulation couplee : a chaque pas, la charge de i est augmentee
    de la dette (normalisee ou saturee) de ses voisins au pas courant.
    """
    n = len(net.nodes)
    if len(net.coupling) != n or any(len(row) != n for row in net.coupling):
        raise ValueError("coupling doit etre une matrice n x n")

    results = [SimResult() for _ in range(n)]
    classifiers = [core.HysteresisClassifier(k=c.hysteresis_k,
                                             thresholds=c.thresholds)
                   for c in net.nodes]
    D = [c.D0 for c in net.nodes]
    theta = [c.theta_params.theta0 if c.theta_params else c.theta0
             for c in net.nodes]

    for t in range(n_steps):
        # Couplage : dette des voisins au debut du pas
        if net.use_saturation:
            debt_signal = [saturation(d, net.D_seuil) for d in D]
        else:
            debt_signal = [ext.normalized_debt(d, net.nodes[j].D_crit)
                           for j, d in enumerate(D)]

        D_next = []
        for i, cfg in enumerate(net.nodes):
            L_own = _at(cfg.L, t)
            L = L_own + sum(net.coupling[i][j] * debt_signal[j]
                            for j in range(n) if j != i)
            R = _at(cfg.R, t)
            B = _at(cfg.B, t)

            C = core.capacity(theta[i], R, B, cfg.s)
            A = core.total_load(L, D[i])
            M = core.margin_index(A, C)

            r = results[i]
            r.t.append(t); r.L.append(L_own); r.L_eff.append(L)
            r.D.append(D[i]); r.R_eff.append(R); r.B_eff.append(B)
            r.theta.append(theta[i]); r.A.append(A); r.C.append(C)
            r.M.append(M)
            r.M_bounded.append(core.bounded_margin_index(A, C))
            r.U.append(0.0)
            r.zone.append(classifiers[i].update(M))

            D_n = ext.normalized_debt(D[i], cfg.D_crit)
            if cfg.mu0 > 0.0:
                mu = ext.repayment_rate(cfg.mu0, R, D_n, cfg.gamma)
                d_new = ext.debt_update_with_repayment(D[i], L, R, B, C,
                                                       cfg.rho, mu)
            else:
                mu = 0.0
                d_new = core.debt_update(D[i], L, R, B, C, cfg.rho)
            r.mu.append(mu)
            D_next.append(d_new)

            if cfg.theta_params is not None:
                theta[i] = ext.theta_update(
                    theta[i], cfg.theta_params,
                    ext.normalized_debt(d_new, cfg.D_crit), B)

        D = D_next

    return results
