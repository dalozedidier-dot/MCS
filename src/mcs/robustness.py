"""Phase 1 - Robustesse numerique du MCS (ROADMAP, § 9.6).

Objectif : explorer les bords du domaine, en deterministe et en
stochastique, pour distinguer la dynamique interpretable de
l'emballement numerique. Quatre outils :

1. Bruit multiplicatif sur les proxys L, R, B (`noisy`, `monte_carlo`)
2. Calibration de l'hysteresis k contre les fausses alertes
   (`false_alarm_study`)
3. Detection d'oscillations pres de la condition de viabilite mu*
   (`oscillation_score`)
4. Condition exacte de petit gain en reseau via le rayon spectral de la
   matrice jacobienne de la carte de dette (`debt_jacobian`,
   `spectral_radius`, `network_stability`), la et cartographie des
   cascades (`cascade_sweep`)

Plus la decomposition de sensibilite du § 4 (`sensitivity_tornado`) :
dM = -dA/C + (1 - M) * (dTheta/Theta + dR/R + dB/B).

Aucune dependance externe : stdlib uniquement (random, statistics).
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field, replace
from typing import Callable, Sequence

from . import core
from .core import Zone, classify, clip
from .simulator import SimConfig, SimResult, _at, simulate


# ---------------------------------------------------------------------------
# 1. Bruit multiplicatif et Monte Carlo
# ---------------------------------------------------------------------------

def noisy(base, sigma: float, rng: random.Random,
          lo: float = 0.0, hi: float | None = None) -> Callable[[int], float]:
    """Enveloppe une entree exogene d'un bruit multiplicatif lognormal.

    x_bruite(t) = x(t) * exp(sigma * eps_t), eps_t ~ N(0, 1), puis
    bornage dans [lo, hi]. Le bruit multiplicatif respecte la positivite
    des proxys ; hi = 1 pour R et B, None pour L.
    """
    def f(t: int) -> float:
        x = _at(base, t) * math.exp(sigma * rng.gauss(0.0, 1.0))
        return clip(x, lo, hi) if hi is not None else max(lo, x)
    return f


@dataclass
class MonteCarloSummary:
    """Statistiques sur n_runs trajectoires bruitees."""
    n_runs: int
    n_steps: int
    M_final: list[float]
    D_final: list[float]
    first_alert: list[int | None]     # 1er pas confirme hors zone viable
    diverged: int                      # runs avec |M| non borne ou nan

    def quantiles(self, xs: list[float], qs=(0.05, 0.5, 0.95)) -> list[float]:
        clean = sorted(x for x in xs if math.isfinite(x))
        if not clean:
            return [math.nan] * len(qs)
        return [clean[min(len(clean) - 1, int(q * len(clean)))] for q in qs]

    def as_dict(self) -> dict:
        return {
            "n_runs": self.n_runs,
            "M_final_q05_q50_q95": self.quantiles(self.M_final),
            "D_final_q05_q50_q95": self.quantiles(self.D_final),
            "alert_rate": sum(a is not None for a in self.first_alert)
                          / self.n_runs,
            "median_first_alert": statistics.median(
                [a for a in self.first_alert if a is not None]) if any(
                a is not None for a in self.first_alert) else None,
            "diverged": self.diverged,
        }


def monte_carlo(cfg: SimConfig, n_steps: int = 60, n_runs: int = 200,
                sigma_L: float = 0.0, sigma_R: float = 0.0,
                sigma_B: float = 0.0, seed: int = 0,
                alert_zone: Zone = Zone.SATURATION) -> MonteCarloSummary:
    """Simule n_runs trajectoires avec bruit multiplicatif independant.

    `first_alert` = premier pas ou la zone CONFIRMEE (hysteresis de cfg)
    atteint alert_zone ou pire. `diverged` compte les trajectoires ou M
    devient non fini (hors convention C=0), signe d'emballement numerique
    a documenter plutot qu'a interpreter.
    """
    order = [Zone.VIABLE, Zone.TENSION, Zone.SATURATION,
             Zone.PRE_RUPTURE, Zone.RUPTURE]
    rank = {z: i for i, z in enumerate(order)}
    out = MonteCarloSummary(n_runs, n_steps, [], [], [], 0)
    for r in range(n_runs):
        rng = random.Random(seed + r)
        c = replace(cfg,
                    L=noisy(cfg.L, sigma_L, rng),
                    R=noisy(cfg.R, sigma_R, rng, hi=1.0),
                    B=noisy(cfg.B, sigma_B, rng, hi=1.0))
        res = simulate(c, n_steps)
        out.M_final.append(res.M[-1])
        out.D_final.append(res.D[-1])
        if any(not math.isfinite(m) for m in res.M):
            out.diverged += 1
        alert = next((t for t, z in enumerate(res.zone)
                      if rank[z] >= rank[alert_zone]), None)
        out.first_alert.append(alert)
    return out


# ---------------------------------------------------------------------------
# 2. Calibration de l'hysteresis k contre les fausses alertes
# ---------------------------------------------------------------------------

@dataclass
class FalseAlarmRecord:
    k: int
    transitions_raw: float      # moyenne de changements de zone bruts
    transitions_confirmed: float  # moyenne apres hysteresis k
    suppression: float           # 1 - confirmes/bruts


def false_alarm_study(cfg: SimConfig, ks: Sequence[int] = (1, 2, 3, 5, 8),
                      n_steps: int = 80, n_runs: int = 100,
                      sigma: float = 0.10, seed: int = 0) -> list[FalseAlarmRecord]:
    """Mesure combien de transitions de zone l'hysteresis supprime.

    Sur un systeme STATIONNAIRE (la config passee doit etre en regime
    stable), toute transition est une fausse alerte due au bruit. On
    compare le nombre moyen de changements de zone de la lecture brute
    (k=1) a la lecture confirmee pour chaque k : la suppression doit
    croitre avec k, au prix d'un delai de detection (mesure ailleurs
    par monte_carlo.first_alert).
    """
    records = []
    for k in ks:
        raw_counts, conf_counts = [], []
        for r in range(n_runs):
            rng = random.Random(seed + r)
            c = replace(cfg, hysteresis_k=k,
                        L=noisy(cfg.L, sigma, rng),
                        R=noisy(cfg.R, sigma, rng, hi=1.0),
                        B=noisy(cfg.B, sigma, rng, hi=1.0))
            res = simulate(c, n_steps)
            raw = [classify(m, cfg.thresholds) for m in res.M]
            raw_counts.append(sum(raw[i] != raw[i - 1]
                                  for i in range(1, len(raw))))
            conf_counts.append(sum(res.zone[i] != res.zone[i - 1]
                                   for i in range(1, len(res.zone))))
        tr, tc = statistics.mean(raw_counts), statistics.mean(conf_counts)
        records.append(FalseAlarmRecord(
            k, tr, tc, 0.0 if tr == 0 else 1.0 - tc / tr))
    return records


# ---------------------------------------------------------------------------
# 3. Oscillations pres de mu*
# ---------------------------------------------------------------------------

def oscillation_score(series: Sequence[float], burn_in: int = 10,
                      tol: float = 1e-9) -> dict:
    """Detecte les oscillations d'une trajectoire apres transitoire.

    Compte les changements de signe de la difference premiere et mesure
    l'amplitude residuelle. Retourne {sign_changes, amplitude, period}
    (period = estimation naive 2*(longueur)/(changements), None si < 2).
    Pres de mu*, la concurrence remboursement/fuite peut produire des
    cycles : c'est ce qu'on cartographie au § 9.6.
    """
    xs = [x for x in series[burn_in:] if math.isfinite(x)]
    if len(xs) < 3:
        return {"sign_changes": 0, "amplitude": 0.0, "period": None}
    diffs = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    signs = [1 if d > tol else (-1 if d < -tol else 0) for d in diffs]
    nz = [s for s in signs if s != 0]
    changes = sum(nz[i] != nz[i - 1] for i in range(1, len(nz)))
    amp = (max(xs) - min(xs)) / 2.0
    period = 2.0 * len(xs) / changes if changes >= 2 else None
    return {"sign_changes": changes, "amplitude": amp, "period": period}


# ---------------------------------------------------------------------------
# 4. Reseau : rayon spectral exact et cartes de cascade
# ---------------------------------------------------------------------------

def debt_jacobian(rhos: Sequence[float], coupling: Sequence[Sequence[float]],
                  leak_gains: Sequence[float],
                  D_crits: Sequence[float]) -> list[list[float]]:
    """Jacobienne de la carte de dette couplee, linearisee en regime
    non sature et sans debordement :

        D_i(t+1) = rho_i D_i + (1-R_i)(1-B_i) * [L_i + sum_j lam_ij D_j/D_crit_j]

    => J[i][j] = rho_i * delta_ij + g_i * lam_ij / D_crit_j,  j != i,
       avec g_i = (1-R_i)(1-B_i) le gain de fuite du noeud i.

    La condition exacte de stabilite est rho(J) < 1 ; la condition de
    petit gain du noyau (somme de ligne) n'en est qu'une majoration.
    """
    n = len(rhos)
    J = [[0.0] * n for _ in range(n)]
    for i in range(n):
        J[i][i] = rhos[i]
        for j in range(n):
            if j != i:
                J[i][j] = leak_gains[i] * coupling[i][j] / D_crits[j]
    return J


def spectral_radius(A: Sequence[Sequence[float]], iters: int = 500,
                    tol: float = 1e-12, seed: int = 1) -> float:
    """Rayon spectral par iteration de puissance (matrice non negative :
    Perron-Frobenius garantit la convergence vers la valeur propre
    dominante reelle). Pure stdlib, pas de numpy."""
    n = len(A)
    rng = random.Random(seed)
    x = [rng.random() + 0.1 for _ in range(n)]
    lam = 0.0
    for _ in range(iters):
        y = [sum(A[i][j] * x[j] for j in range(n)) for i in range(n)]
        norm = math.sqrt(sum(v * v for v in y))
        if norm == 0.0:
            return 0.0
        y = [v / norm for v in y]
        lam_new = sum(y[i] * sum(A[i][j] * y[j] for j in range(n))
                      for i in range(n))
        if abs(lam_new - lam) < tol:
            return abs(lam_new)
        lam, x = lam_new, y
    return abs(lam)


def network_stability(rhos, coupling, R_list, B_list, D_crits) -> dict:
    """Verdict exact vs condition pedagogique de petit gain.

    Retourne {spectral_radius, stable, small_gain_rows} ou
    small_gain_rows liste, pour chaque noeud, la majoration
    rho_i + g_i * sum_j lam_ij / D_crit_j (le noyau declare stable
    si < 1 ; le rayon spectral tranche les cas intermediaires).
    """
    gains = [(1.0 - R_list[i]) * (1.0 - B_list[i]) for i in range(len(rhos))]
    J = debt_jacobian(rhos, coupling, gains, D_crits)
    sr = spectral_radius(J)
    rows = [rhos[i] + gains[i] * sum(coupling[i][j] / D_crits[j]
                                     for j in range(len(rhos)) if j != i)
            for i in range(len(rhos))]
    return {"spectral_radius": sr, "stable": sr < 1.0,
            "small_gain_rows": rows}


def cascade_sweep(base_nodes: list[SimConfig], pattern: list[list[float]],
                  strengths: Sequence[float], n_steps: int = 80) -> list[dict]:
    """Cartographie des cascades : pour chaque intensite de couplage
    (coupling = strength * pattern), simule le reseau et compte les
    noeuds finissant en pre-rupture ou rupture, plus le rayon spectral
    predit. Permet de verifier numeriquement que la bascule de cascade
    suit le seuil rho(J) = 1.
    """
    from .network import NetworkConfig, simulate_network
    records = []
    n = len(base_nodes)
    for s in strengths:
        coupling = [[s * pattern[i][j] for j in range(n)] for i in range(n)]
        rhos = [c.rho for c in base_nodes]
        R_list = [_at(c.R, 0) for c in base_nodes]
        B_list = [_at(c.B, 0) for c in base_nodes]
        D_crits = [c.D_crit for c in base_nodes]
        pred = network_stability(rhos, coupling, R_list, B_list, D_crits)
        results = simulate_network(
            NetworkConfig(nodes=base_nodes, coupling=coupling), n_steps)
        broken = sum(r.zone[-1] in (Zone.PRE_RUPTURE, Zone.RUPTURE)
                     for r in results)
        records.append({"strength": s, "spectral_radius":
                        pred["spectral_radius"], "predicted_stable":
                        pred["stable"], "nodes_broken": broken,
                        "M_final": [r.M[-1] for r in results]})
    return records


# ---------------------------------------------------------------------------
# Sensibilite (tornado) - decomposition du § 4
# ---------------------------------------------------------------------------

def sensitivity_tornado(L: float, D: float, theta: float, R: float,
                        B: float, s: float = 0.0,
                        rel_err: float = 0.10) -> dict:
    """Contributions au premier ordre de chaque proxy a dM, pour une
    erreur relative commune (10 % par defaut) :

        dM = -dA/C + (1 - M) * (dTheta/Theta + dR/R + dB/B)

    Retourne {M, contributions: {A, theta, R, B}, total} ; le total doit
    coincider avec core.margin_uncertainty (test de coherence).
    """
    A = core.total_load(L, D)
    C = core.capacity(theta, R, B, s)
    M = core.margin_index(A, C)
    contrib = {
        "A": abs(A / C) * rel_err if C > 0 else math.inf,
        "theta": abs(1.0 - M) * rel_err,
        "R": abs(1.0 - M) * rel_err,
        "B": abs(1.0 - M) * rel_err,
    }
    return {"M": M, "contributions": contrib,
            "total": sum(contrib.values())}
