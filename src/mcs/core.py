"""Noyau mathematique du Modele de Coherence Systemique (MCS).

Implemente les sections 3, 3.1, 4 et 5 du document de travail :
- charge totale effective A(t) = L(t) + D(t)
- capacite effective C(t) = Theta(t) * (s*(R+B)/2 + (1-s)*R*B)
- Indice de Marge Systemique M(t) = 1 - A/C
- indice borne complementaire M~(t) = (C - A) / (C + A)
- dynamique de la dette D(t+1) = rho*D + (1-R)*L*(1-B) + max(0, L-C)
- zones systemiques avec hysteresis (lecture ordinale, non cardinale)

Toutes les grandeurs suivent les conventions du document :
R, B dans [0, 1] ; Theta > 0 ; D >= 0 ; L exprimee par pas de temps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


def clip(x: float, lo: float, hi: float) -> float:
    """Borne x dans [lo, hi]."""
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# Noyau : A, C, M, M~
# ---------------------------------------------------------------------------

def total_load(L: float, D: float) -> float:
    """A(t) = L(t) + D(t), charge actuelle augmentee de la dette accumulee."""
    if L < 0 or D < 0:
        raise ValueError("L et D doivent etre positifs ou nuls")
    return L + D


def capacity(theta: float, R: float, B: float, s: float = 0.0) -> float:
    """C(t), capacite effective d'absorption.

    s = 0 (defaut, noyau) : produit pur  C = Theta * R * B
        (substituabilite nulle : la defaillance de R ou B suffit
        a effondrer la capacite).
    s = 1 : moyenne arithmetique C = Theta * (R + B) / 2.
    0 < s < 1 : interpolation  C = Theta * (s*(R+B)/2 + (1-s)*R*B).
    """
    if theta <= 0:
        raise ValueError("Theta doit rester strictement positive")
    if not (0.0 <= R <= 1.0 and 0.0 <= B <= 1.0):
        raise ValueError("R et B doivent etre bornes entre 0 et 1")
    if not (0.0 <= s <= 1.0):
        raise ValueError("s doit etre borne entre 0 et 1")
    return theta * (s * (R + B) / 2.0 + (1.0 - s) * R * B)


def margin_index(A: float, C: float) -> float:
    """M(t) = 1 - A/C, avec les conventions de cas limites du § 5.

    - A = 0  =>  M = 1 (y compris si C = 0) : absence de charge et de
      dette definit la marge maximale.
    - C = 0 et A > 0 : incapacite critique d'absorption => -inf.
    """
    if A == 0.0:
        return 1.0
    if C == 0.0:
        return -math.inf
    return 1.0 - A / C


def bounded_margin_index(A: float, C: float) -> float:
    """M~(t) = (C - A) / (C + A), a valeurs dans (-1, 1].

    Meme signe et meme zero que M(t). Sert a comparer visuellement des
    situations tres degradees, quand M(t) devient tres negatif.
    """
    if A == 0.0:
        return 1.0
    if C == 0.0 and A > 0.0:
        return -1.0
    return (C - A) / (C + A)


def margin(L: float, D: float, theta: float, R: float, B: float,
           s: float = 0.0) -> float:
    """Forme developpee M(t) = 1 - (L+D) / C(Theta, R, B, s)."""
    return margin_index(total_load(L, D), capacity(theta, R, B, s))


# ---------------------------------------------------------------------------
# Dynamique de la dette (§ 3.1)
# ---------------------------------------------------------------------------

def leak(L: float, R: float, B: float) -> float:
    """Fuite de sous-recuperation : (1 - R) * L * (1 - B).

    Active des que R < 1 ou B < 1 : c'est elle qui fait de la dette
    un indicateur AVANCE (elle monte dans les zones saines).
    """
    return (1.0 - R) * L * (1.0 - B)


def overflow(L: float, C: float) -> float:
    """Debordement instantane de la charge fraiche : max(0, L - C)."""
    return max(0.0, L - C)


def debt_update(D: float, L: float, R: float, B: float, C: float,
                rho: float) -> float:
    """D(t+1) = rho*D(t) + (1-R)L(1-B) + max(0, L - C).  (noyau, sans
    remboursement actif ; voir extensions.debt_update_with_repayment)."""
    if not (0.0 <= rho <= 1.0):
        raise ValueError("rho doit etre borne entre 0 et 1")
    return rho * D + leak(L, R, B) + overflow(L, C)


def debt_rest_level(L: float, R: float, B: float, rho: float) -> float:
    """Niveau de repos D* = (1-R)L(1-B) / (1-rho).

    Valide pour 0 <= rho < 1 et en l'absence de debordement. Strictement
    positif des que la recuperation est incomplete : tension chronique
    qui abaisse la marge sans qu'aucune variable observable ne bouge.
    """
    if not (0.0 <= rho < 1.0):
        raise ValueError("D* n'est defini que pour 0 <= rho < 1")
    return leak(L, R, B) / (1.0 - rho)


# ---------------------------------------------------------------------------
# Zones systemiques (§ 4) - lecture ordinale avec hysteresis
# ---------------------------------------------------------------------------

class Zone(str, Enum):
    VIABLE = "coherence_viable"          # M > 0.30
    TENSION = "tension_constructive"     # 0.10 < M <= 0.30
    SATURATION = "saturation"            # 0.05 < M <= 0.10
    PRE_RUPTURE = "pre_rupture"          # -0.05 <= M <= 0.05
    RUPTURE = "rupture"                  # M < -0.05


#: Seuils pedagogiques par defaut - hypotheses de lecture, PAS des
#: verites universelles. A calibrer par domaine (§ 4, § 9.2).
DEFAULT_THRESHOLDS = {"viable": 0.30, "tension": 0.10,
                      "saturation": 0.05, "pre_rupture": -0.05}


def classify(M: float, thresholds: dict | None = None) -> Zone:
    """Classe une valeur de M dans une zone systemique (sans hysteresis)."""
    th = thresholds or DEFAULT_THRESHOLDS
    if M > th["viable"]:
        return Zone.VIABLE
    if M > th["tension"]:
        return Zone.TENSION
    if M > th["saturation"]:
        return Zone.SATURATION
    if M >= th["pre_rupture"]:
        return Zone.PRE_RUPTURE
    return Zone.RUPTURE


@dataclass
class HysteresisClassifier:
    """Classification avec hysteresis : le changement de zone n'est
    confirme qu'apres k pas consecutifs dans la nouvelle zone (§ 4),
    pour eviter les alertes prematurees dues au bruit multiplicatif.
    """
    k: int = 3
    thresholds: dict | None = None
    _current: Zone | None = field(default=None, repr=False)
    _candidate: Zone | None = field(default=None, repr=False)
    _count: int = field(default=0, repr=False)

    def update(self, M: float) -> Zone:
        raw = classify(M, self.thresholds)
        if self._current is None:
            self._current = raw
            return raw
        if raw == self._current:
            self._candidate, self._count = None, 0
        elif raw == self._candidate:
            self._count += 1
            if self._count >= self.k:
                self._current = raw
                self._candidate, self._count = None, 0
        else:
            self._candidate, self._count = raw, 1
        return self._current


def margin_uncertainty(M: float, A: float, C: float,
                       rel_err_A: float = 0.0, rel_err_theta: float = 0.0,
                       rel_err_R: float = 0.0, rel_err_B: float = 0.0) -> float:
    """Propagation d'incertitude au premier ordre (§ 4) :

    dM = -dA/C + (1 - M) * (dTheta/Theta + dR/R + dB/B)

    Retourne une demi-largeur d'intervalle (somme des valeurs absolues,
    lecture prudente). Au voisinage du seuil, 10 % d'erreur sur un proxy
    deplace M d'environ 0.1 : la largeur d'une bande entiere.
    """
    if C == 0.0:
        return math.inf
    return (abs(A / C) * rel_err_A
            + abs(1.0 - M) * (rel_err_theta + rel_err_R + rel_err_B))
