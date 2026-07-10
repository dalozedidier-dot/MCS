"""Experiences de demonstration scientifique du MCS.

Deux proprietes centrales du modele, rendues visibles et testables :

1. `hysteresis_loop` - IRREVERSIBILITE : sous une rampe de charge
   montee puis descente symetrique, la trajectoire M(L) ne revient pas
   par le meme chemin. La dette et l'usure de Theta gardent la trace du
   passage : a charge identique, la marge est plus basse au retour.
   L'aire de la boucle quantifie cette memoire (nulle sans dette ni
   usure, croissante avec rho et alpha).

2. `regime_map` - GARDE D'EMBALLEMENT : la valeur propre effective de
   la carte de dette en regime de debordement non sature est
   rho + Theta0*R*B*alpha/D_crit ; les perturbations de dette
   s'amplifient exactement quand alpha > alpha*(rho) =
   (1-rho)*D_crit/(Theta0*R*B). L'experience MESURE cette pente en
   simulant deux dettes initiales voisines a travers simulate() (pas la
   formule reevaluee : la machinerie complete) et compare le verdict
   croissance/amortissement a la frontiere analytique.

Ces experiences sont des demonstrations de COHERENCE INTERNE : elles
verifient que le code realise bien les proprietes annoncees par les
equations, pas que le monde s'y conforme (§ 9.7 pour cela).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .extensions import ThetaParams, alpha_runaway
from .simulator import SimConfig, simulate

# ---------------------------------------------------------------------------
# 1. Irreversibilite : boucle d'hysteresis M(L)
# ---------------------------------------------------------------------------

@dataclass
class HysteresisLoop:
    """Trajectoire aller-retour et mesure de la memoire du passage."""
    L: list[float]           # rampe complete (montee + descente)
    M_up: list[float]        # marge pendant la montee
    M_down: list[float]      # marge pendant la descente (ordre de L croissant)
    D_final: float           # dette residuelle en fin de descente
    theta_final: float       # capacite nominale residuelle
    gap_at_start: float      # M(retour a L initial) - M(depart) (<= 0)
    loop_area: float         # aire entre aller et retour (>= 0)


def load_ramp(L_min: float, L_max: float, n_up: int,
              plateau: int = 0) -> list[float]:
    """Rampe symetrique L_min -> L_max (-> plateau) -> L_min."""
    up = [L_min + (L_max - L_min) * i / (n_up - 1) for i in range(n_up)]
    return up + [L_max] * plateau + up[::-1]


def hysteresis_loop(cfg: SimConfig, L_min: float = 0.15,
                    L_max: float = 0.85, n_up: int = 40,
                    plateau: int = 10) -> HysteresisLoop:
    """Simule cfg sous rampe de charge aller-retour et mesure la boucle.

    La config passee fournit R, B, rho, mu0, theta_params... ; sa
    composante L est remplacee par la rampe. Aire par trapezes sur la
    grille commune de L (montee croissante).
    """
    ramp = load_ramp(L_min, L_max, n_up, plateau)
    res = simulate(replace(cfg, L=ramp), n_steps=len(ramp))
    up = res.M[:n_up]
    down = res.M[n_up + plateau:][::-1]          # remis en L croissant
    L_axis = ramp[:n_up]
    area = 0.0
    for i in range(1, n_up):
        dL = L_axis[i] - L_axis[i - 1]
        gap0 = up[i - 1] - down[i - 1]
        gap1 = up[i] - down[i]
        area += 0.5 * (gap0 + gap1) * dL
    return HysteresisLoop(
        L=ramp, M_up=up, M_down=down,
        D_final=res.D[-1], theta_final=res.theta[-1],
        gap_at_start=down[0] - up[0],
        loop_area=area,
    )


def memoryless_config(cfg: SimConfig) -> SimConfig:
    """Variante sans memoire du meme systeme : rho = 0, dette purgee a
    chaque pas impossible a annuler completement (la fuite instantanee
    demeure), Theta fige. Sert de temoin : la boucle doit s'ecraser."""
    return replace(cfg, rho=0.0, theta_params=None, D0=0.0)


# ---------------------------------------------------------------------------
# 2. Carte de regime (alpha, rho) vs frontiere analytique alpha*
# ---------------------------------------------------------------------------

@dataclass
class RegimeMap:
    alphas: list[float]
    rhos: list[float]
    growing: list[list[bool]]        # [i_rho][j_alpha] : perturbation amplifiee
    slopes: list[list[float]]        # pente empirique mesuree
    alpha_star: list[float]          # frontiere analytique par rho
    agreement: float                 # fraction de cases conformes


def perturbation_slope(rho: float, alpha: float, R: float, B: float,
                       theta0: float, theta_min: float, D_crit: float,
                       L: float, D0: float = 0.0,
                       eps: float = 1e-6) -> float:
    """Pente empirique de la carte de dette : deux simulations completes
    partant de D0 et D0 + eps, en regime de debordement (L > C) et non
    sature (D << D_crit).

    La pente est mesuree entre les pas 1 et 2 : au pas 0, Theta vaut
    encore Theta0 quel que soit D0 (le couplage Theta(D) ne s'exprime
    qu'apres la premiere mise a jour), donc l'ecart au pas 1 vaut
    rho*eps ; c'est entre 1 et 2 que la valeur propre complete
    rho + Theta0*R*B*alpha/D_crit agit, dans la region lineaire par
    morceaux (tau = 1) => mesure exacte, avant toute saturation."""
    def run(d0: float) -> list[float]:
        cfg = SimConfig(L=L, R=R, B=B, rho=rho, D_crit=D_crit, D0=d0,
                        theta_params=ThetaParams(theta0=theta0,
                                                 theta_min=theta_min,
                                                 alpha=alpha, beta=0.0,
                                                 tau=1.0))
        return simulate(cfg, 3).D
    Da, Db = run(D0), run(D0 + eps)
    gap1 = abs(Db[1] - Da[1])
    gap2 = abs(Db[2] - Da[2])
    return gap2 / gap1 if gap1 > 0 else 0.0


def regime_map(R: float = 0.9, B: float = 0.9, theta0: float = 1.0,
               theta_min: float = 0.05, D_crit: float = 0.5,
               n_alpha: int = 25, n_rho: int = 25,
               alpha_max: float = 0.9, rho_max: float = 0.95,
               margin_band: float = 0.05) -> RegimeMap:
    """Balaye (alpha, rho) et compare le verdict empirique (pente > 1)
    a la frontiere analytique alpha*(rho).

    Conditions d'application de l'analyse lineaire, imposees par
    construction : L = 1.2*Theta0*R*B garantit le debordement meme a
    Theta = Theta0 ; D0 = 0 et 3 pas gardent la dette loin de la
    saturation D_crit. `agreement` exclut une bande relative
    +-margin_band autour de alpha* (frontiere exacte a l'arithmetique
    flottante pres) ; hors bande, l'accord doit etre total.
    """
    alphas = [alpha_max * (j + 1) / n_alpha for j in range(n_alpha)]
    rhos = [rho_max * (i + 1) / n_rho for i in range(n_rho)]
    L = 1.2 * theta0 * R * B
    stars = [alpha_runaway(r, D_crit, theta0, R, B) for r in rhos]
    growing, slopes = [], []
    hits = total = 0
    for i, rho in enumerate(rhos):
        grow_row, slope_row = [], []
        for a in alphas:
            sl = perturbation_slope(rho, a, R, B, theta0, theta_min,
                                    D_crit, L)
            slope_row.append(sl)
            grow_row.append(sl > 1.0)
        growing.append(grow_row)
        slopes.append(slope_row)
        for j, a in enumerate(alphas):
            if abs(a - stars[i]) <= margin_band * stars[i]:
                continue
            total += 1
            hits += int(grow_row[j] == (a > stars[i]))
    return RegimeMap(alphas=alphas, rhos=rhos, growing=growing,
                     slopes=slopes, alpha_star=stars,
                     agreement=hits / total if total else 1.0)
