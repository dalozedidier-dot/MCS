"""Phase 3 - Confrontation aux baselines naives (ROADMAP, § 9.7).

Question falsifiable : le MCS apporte-t-il un signal AVANCE que la
charge seule ne donne pas ? On compare trois detecteurs d'alerte sur
une meme trajectoire :

1. baseline_threshold : alerte quand L(t) depasse un seuil
2. baseline_moving_average : alerte quand la moyenne mobile de L depasse
   un seuil
3. mcs_alarm : alerte quand la zone MCS confirmee (hysteresis) atteint
   la saturation ou pire

et on mesure l'avance (lead) de chaque detecteur sur l'evenement de
rupture (M < seuil de rupture, confirme). Le harnais `falsification_run`
enregistre PASS/FAIL de la prediction centrale du modele :

    "un systeme dont B se degrade durablement doit voir D monter et M
     baisser PLUS TOT qu'un detecteur fonde sur la charge seule"

et documente les echecs au lieu de les masquer (§ 9.7 : chercher
activement des jeux de donnees ou les lois de mise a jour echouent).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .core import Zone
from .simulator import SimConfig, SimResult, simulate

_ORDER = [Zone.VIABLE, Zone.TENSION, Zone.SATURATION,
          Zone.PRE_RUPTURE, Zone.RUPTURE]
_RANK = {z: i for i, z in enumerate(_ORDER)}


# ---------------------------------------------------------------------------
# Detecteurs
# ---------------------------------------------------------------------------

def baseline_threshold(L: Sequence[float], threshold: float) -> int | None:
    """Premier pas ou L(t) > threshold. None si jamais."""
    return next((t for t, x in enumerate(L) if x > threshold), None)


def moving_average(L: Sequence[float], window: int) -> list[float]:
    """Moyenne mobile simple de fenetre `window` (bord : fenetre
    tronquee, pas de valeurs futures)."""
    if window < 1:
        raise ValueError("window >= 1")
    out = []
    for t in range(len(L)):
        lo = max(0, t - window + 1)
        out.append(sum(L[lo:t + 1]) / (t + 1 - lo))
    return out


def baseline_moving_average(L: Sequence[float], window: int,
                            threshold: float) -> int | None:
    """Premier pas ou la moyenne mobile de L depasse threshold."""
    return baseline_threshold(moving_average(L, window), threshold)


def mcs_alarm(result: SimResult,
              alert_zone: Zone = Zone.SATURATION) -> int | None:
    """Premier pas ou la zone CONFIRMEE atteint alert_zone ou pire."""
    return next((t for t, z in enumerate(result.zone)
                 if _RANK[z] >= _RANK[alert_zone]), None)


def rupture_time(result: SimResult) -> int | None:
    """Premier pas ou la zone confirmee est la rupture."""
    return mcs_alarm(result, Zone.RUPTURE)


# ---------------------------------------------------------------------------
# Comparaison et falsification
# ---------------------------------------------------------------------------

@dataclass
class ComparisonRecord:
    """Alertes et avances mesurees sur une meme trajectoire."""
    scenario: str
    event: int | None              # rupture (ou None : pas d'evenement)
    mcs: int | None
    naive_threshold: int | None
    naive_moving_avg: int | None
    lead_vs_threshold: float | None  # >0 : le MCS alerte plus tot (inf si baseline muette)
    lead_vs_moving_avg: float | None
    lead_vs_event: int | None      # avance de l'alerte sur l'evenement
    mcs_early_and_valid: bool      # alerte MCS avant l'evenement

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _lead(mcs: int | None, base: int | None) -> float | None:
    if mcs is None:
        return None
    if base is None:
        return math.inf  # la baseline n'alerte jamais : avance infinie
    return base - mcs


def compare_detectors(cfg: SimConfig, n_steps: int, scenario: str,
                      L_threshold: float, ma_window: int = 4,
                      alert_zone: Zone = Zone.SATURATION) -> ComparisonRecord:
    """Simule cfg et compare les trois detecteurs.

    Le seuil L_threshold est a fixer AU MEME NIVEAU d'exigence que
    l'alerte MCS (par ex. la charge critique) : comparer un detecteur
    laxiste a un detecteur severe n'aurait aucun sens.
    """
    res = simulate(cfg, n_steps)
    ev = rupture_time(res)
    m = mcs_alarm(res, alert_zone)
    b1 = baseline_threshold(res.L, L_threshold)
    b2 = baseline_moving_average(res.L, ma_window, L_threshold)
    return ComparisonRecord(
        scenario=scenario, event=ev, mcs=m,
        naive_threshold=b1, naive_moving_avg=b2,
        lead_vs_threshold=_lead(m, b1),
        lead_vs_moving_avg=_lead(m, b2),
        lead_vs_event=(ev - m) if (m is not None and ev is not None)
                      else None,
        mcs_early_and_valid=(m is not None
                             and (ev is None or m < ev)),
    )


@dataclass
class FalsificationRecord:
    """Resultat d'un test de la prediction centrale, PASS ou FAIL."""
    name: str
    prediction: str
    passed: bool
    details: dict


def falsification_run(records: list[ComparisonRecord] | None = None
                      ) -> list[FalsificationRecord]:
    """Harnais de falsification sur les scenarios canoniques.

    Trois predictions confrontees :

    F1 (degradation silencieuse) - a charge CONSTANTE sous la charge
       critique, aucun detecteur de charge ne peut alerter, mais si
       R < 1 et B < 1 la dette doit monter et le MCS doit alerter.
       FAIL si le MCS n'alerte pas, ou si un detecteur de charge alerte
       (ce qui indiquerait que le scenario ne teste rien).

    F2 (choc absorbe) - un choc de charge bref sur un systeme a boucles
       saines fait alerter les detecteurs de charge, mais le systeme
       revient en zone viable : le MCS ne doit PAS confirmer d'alerte
       durable (pas de faux positif structurel).

    F3a (avance sur BASELINE) - quand une rupture survient, l'alerte
        MCS precede ou egale l'alerte de charge naive :
        t_MCS <= t_baseline.

    F3b (avance sur EVENEMENT) - l'alerte MCS precede la rupture
        elle-meme d'au moins MIN_LEAD pas (avance minimale
        PRE-ENREGISTREE, fixee a la profondeur d'hysteresis k = 3
        avant execution). Une alerte simultanee a la rupture n'est
        pas un signal avance : F3a et F3b sont deux hypotheses
        distinctes, evaluees separement. Limite connue et documentee :
        sous degradation brutale (rampe raide), l'avance sur
        l'evenement s'effondre vers zero - le MCS ne devance que ce
        que la dynamique laisse a devancer.

    Chaque FAIL est documente dans details, pas ecarte.
    """
    MIN_LEAD = 3               # pre-enregistre : >= profondeur d'hysteresis
    out: list[FalsificationRecord] = []

    # F1 - degradation silencieuse : L constante et sous-critique
    cfg1 = SimConfig(L=0.25, R=0.7, B=0.6, rho=0.9, D_crit=0.6)
    rec1 = compare_detectors(cfg1, 80, "degradation_silencieuse",
                             L_threshold=1.0)
    ok1 = (rec1.mcs is not None
           and rec1.naive_threshold is None
           and rec1.naive_moving_avg is None)
    out.append(FalsificationRecord(
        "F1_degradation_silencieuse",
        "D monte et le MCS alerte alors que la charge seule reste muette",
        ok1, rec1.as_dict()))

    # F2 - choc bref absorbe par un systeme sain
    def choc(t):
        return 1.2 if 5 <= t < 8 else 0.35
    cfg2 = SimConfig(L=choc, R=0.95, B=0.9, rho=0.6,
                     mu0=0.6, D_crit=0.5, hysteresis_k=4)
    res2 = simulate(cfg2, 60)
    final_viable = res2.zone[-1] == Zone.VIABLE
    naive_fires = baseline_threshold(res2.L, 1.0) is not None
    ok2 = final_viable and naive_fires
    out.append(FalsificationRecord(
        "F2_choc_absorbe",
        "le detecteur de charge s'affole sur un choc bref ; le MCS "
        "revient en zone viable (l'hysteresis filtre le transitoire)",
        ok2, {"final_zone": res2.zone[-1].value,
              "naive_alerts": naive_fires,
              "M_final": res2.M[-1], "D_final": res2.D[-1]}))

    # F3 - rupture reelle sous degradation graduelle
    def montee(t):
        return 0.15 + 0.005 * t
    cfg3 = SimConfig(L=montee, R=0.7, B=0.65, rho=0.9, D_crit=0.6)
    rec3 = compare_detectors(cfg3, 240, "montee_vers_rupture",
                             L_threshold=1.0)
    ok3a = (rec3.event is not None and rec3.mcs is not None
            and rec3.lead_vs_threshold is not None
            and rec3.lead_vs_threshold >= 0)
    out.append(FalsificationRecord(
        "F3a_avance_sur_baseline",
        "en cas de rupture, l'alerte MCS precede l'alerte de charge "
        "(t_MCS <= t_baseline)",
        ok3a, rec3.as_dict()))
    ok3b = (rec3.lead_vs_event is not None
            and rec3.lead_vs_event >= MIN_LEAD)
    details3b = dict(rec3.as_dict(), min_lead=MIN_LEAD)
    out.append(FalsificationRecord(
        "F3b_avance_sur_evenement",
        f"l'alerte MCS precede la rupture d'au moins {MIN_LEAD} pas "
        "(avance minimale pre-enregistree) - une alerte simultanee a "
        "la rupture n'est pas un signal avance",
        ok3b, details3b))

    if records:
        for r in records:
            out.append(FalsificationRecord(
                f"externe_{r.scenario}",
                "alerte MCS anterieure a l'evenement et aux baselines",
                bool(r.mcs_early_and_valid), r.as_dict()))
    return out


def falsification_report(records: list[FalsificationRecord]) -> str:
    """Rapport Markdown PASS/FAIL, echecs documentes en clair."""
    lines = ["# Harnais de falsification MCS (§ 9.7)", ""]
    for r in records:
        badge = "PASS" if r.passed else "**FAIL**"
        lines.append(f"## {r.name} - {badge}")
        lines.append(f"Prediction : {r.prediction}")
        det = {k: (v.value if isinstance(v, Zone) else v)
               for k, v in r.details.items()}
        lines.append(f"Details : `{det}`")
        lines.append("")
    n_fail = sum(not r.passed for r in records)
    lines.append(f"Bilan : {len(records) - n_fail}/{len(records)} PASS. "
                 + ("Echecs a investiguer ci-dessus." if n_fail
                    else "Aucun echec sur ce jeu ; en chercher d'autres."))
    return "\n".join(lines)
