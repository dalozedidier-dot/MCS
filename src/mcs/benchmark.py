"""Benchmark aveugle multi-detecteurs (audit v0.3.0, experience phare).

Question decisive : sur des trajectoires que le MCS n'a pas contribue a
definir, detecte-t-il mieux et plus tot les transitions utiles, a taux
de fausses alertes comparable, que des modeles plus simples ?

Trois disciplines structurent le module :

1. GENERATEUR ETRANGER AU MODELE. Les trajectoires (L, R, B observes)
   sont produites par cinq familles dynamiques qui n'utilisent ni la
   dette ni aucune equation du MCS. L'evenement est defini par un
   mecanisme cache (la charge excede une capacite latente K(t) pendant
   w pas consecutifs) : les etiquettes ne sont pas circulaires.

2. PARAMETRES PRE-ENREGISTRES. Chaque detecteur transforme la
   trajectoire observee en un score de danger croissant. Les parametres
   internes (rho, D_crit, fenetres...) sont fixes ici, dans le code,
   avant toute evaluation. Seul le SEUIL d'alerte est calibre - par la
   MEME regle pour tous : quantile des scores maximaux sur les
   trajectoires SANS evenement du jeu de calibration, pour atteindre un
   taux de fausses alertes cible identique.

3. SEPARATION STRICTE. Graines de calibration et de validation
   disjointes ; aucune metrique n'est calculee sur le jeu qui a fixe
   les seuils. Les resultats sont publies tels quels, echecs compris.

Critere principal : gain APPARIE de delai d'alerte du MCS complet sur
la baseline la plus defavorable, a taux de fausses alertes identique.
Apparie : sur chaque trajectoire a evenement, difference des avances,
une detection manquee comptant pour une avance nulle - un detecteur ne
peut donc pas "gagner au delai median" en ne tirant que sur les cas
faciles, ni en alertant tout le temps (le FPR est fixe).
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

from .core import capacity, leak, margin_index, total_load

# ---------------------------------------------------------------------------
# 1. Generateur de trajectoires - etranger au MCS
# ---------------------------------------------------------------------------

#: Fenetre du mecanisme cache : l'evenement est le premier pas ou la
#: charge latente excede la capacite latente depuis w pas consecutifs.
EVENT_WINDOW = 3


@dataclass
class Trajectory:
    """Series observees + verite cachee (a ne montrer qu'a l'evaluation)."""
    family: str
    seed: int
    L: list[float]
    R: list[float]
    B: list[float]
    event: int | None            # etiquette cachee


def _noisy(x: float, rng: random.Random, sigma: float,
           lo: float = 0.0, hi: float | None = None) -> float:
    v = x * math.exp(sigma * rng.gauss(0.0, 1.0))
    if hi is not None:
        v = min(hi, v)
    return max(lo, v)


def _hidden_event(load_true: list[float], K: list[float],
                  w: int = EVENT_WINDOW) -> int | None:
    run = 0
    for t, (x, k) in enumerate(zip(load_true, K, strict=True)):
        run = run + 1 if x > k else 0
        if run >= w:
            return t
    return None


def _ramp_to_break(rng: random.Random, n: int) -> Trajectory:
    """Charge en rampe stochastique contre capacite latente constante."""
    K0 = rng.uniform(0.7, 1.0)
    slope = rng.uniform(0.004, 0.012)
    load_true = [0.3 + slope * t for t in range(n)]
    L = [_noisy(x, rng, 0.08) for x in load_true]
    R = [_noisy(0.8, rng, 0.05, hi=1.0) for _ in range(n)]
    B = [_noisy(0.75, rng, 0.05, hi=1.0) for _ in range(n)]
    ev = _hidden_event(load_true, [K0] * n)
    return Trajectory("ramp_to_break", 0, L, R, B, ev)


def _regime_switch(rng: random.Random, n: int) -> Trajectory:
    """AR(1) sur la charge avec saut de moyenne a un instant cache."""
    t_star = rng.randint(n // 4, 3 * n // 4)
    K0 = rng.uniform(0.85, 1.05)
    mu_lo, mu_hi = 0.35, rng.uniform(1.0, 1.3)
    phi, x = 0.7, 0.35
    load_true = []
    for t in range(n):
        mu = mu_hi if t >= t_star else mu_lo
        x = mu + phi * (x - mu) + rng.gauss(0.0, 0.03)
        load_true.append(max(0.0, x))
    L = [_noisy(x, rng, 0.05) for x in load_true]
    R = [_noisy(0.8, rng, 0.05, hi=1.0) for _ in range(n)]
    B = [_noisy(0.7, rng, 0.05, hi=1.0) for _ in range(n)]
    ev = _hidden_event(load_true, [K0] * n)
    return Trajectory("regime_switch", 0, L, R, B, ev)


def _false_shock(rng: random.Random, n: int) -> Trajectory:
    """Pic transitoire de charge, boucles saines : aucun evenement."""
    t0 = rng.randint(5, n - 12)
    dur = rng.randint(2, 4)
    load_true = [0.9 if t0 <= t < t0 + dur else 0.35 for t in range(n)]
    K = [1.0] * n                                # jamais w pas au-dessus
    L = [_noisy(x, rng, 0.06) for x in load_true]
    R = [_noisy(0.9, rng, 0.04, hi=1.0) for _ in range(n)]
    B = [_noisy(0.85, rng, 0.04, hi=1.0) for _ in range(n)]
    dur = min(dur, EVENT_WINDOW - 1)             # garanti sans evenement
    load_true = [0.9 if t0 <= t < t0 + dur else 0.35 for t in range(n)]
    ev = _hidden_event(load_true, K)
    return Trajectory("false_shock", 0, L, R, B, ev)


def _silent_erosion(rng: random.Random, n: int) -> Trajectory:
    """Charge stationnaire ; R et B s'erodent lentement, la capacite
    latente K = K0 * R_vrai * B_vrai descend sous la charge."""
    decay_R = rng.uniform(0.003, 0.007)
    decay_B = rng.uniform(0.004, 0.009)
    K0 = rng.uniform(1.15, 1.35)
    load_true = [max(0.0, 0.45 + rng.gauss(0.0, 0.02)) for _ in range(n)]
    R_true = [max(0.15, 0.85 - decay_R * t) for t in range(n)]
    B_true = [max(0.15, 0.8 - decay_B * t) for t in range(n)]
    K = [K0 * r * b for r, b in zip(R_true, B_true, strict=True)]
    L = [_noisy(x, rng, 0.05) for x in load_true]
    R = [_noisy(r, rng, 0.04, hi=1.0) for r in R_true]
    B = [_noisy(b, rng, 0.04, hi=1.0) for b in B_true]
    ev = _hidden_event(load_true, K)
    return Trajectory("silent_erosion", 0, L, R, B, ev)


def _recovery(rng: random.Random, n: int) -> Trajectory:
    """Degradation amorcee puis retablissement : aucun evenement."""
    peak = rng.randint(n // 3, n // 2)
    load_true = [0.35 + 0.35 * min(t, 2 * peak - t) / peak if t < 2 * peak
                 else 0.35 for t in range(n)]
    K = [1.05] * n
    L = [_noisy(x, rng, 0.05) for x in load_true]
    R = [_noisy(0.85, rng, 0.04, hi=1.0) for _ in range(n)]
    B = [_noisy(0.8, rng, 0.04, hi=1.0) for _ in range(n)]
    ev = _hidden_event(load_true, K)
    return Trajectory("recovery", 0, L, R, B, ev)


FAMILIES: dict[str, Callable[[random.Random, int], Trajectory]] = {
    "ramp_to_break": _ramp_to_break,
    "regime_switch": _regime_switch,
    "false_shock": _false_shock,
    "silent_erosion": _silent_erosion,
    "recovery": _recovery,
}


def generate(seed: int, n_steps: int = 120) -> Trajectory:
    """Trajectoire deterministe par graine ; la famille est tiree de la
    graine elle-meme (le module d'evaluation ne choisit rien)."""
    rng = random.Random(seed)
    family = rng.choice(sorted(FAMILIES))
    traj = FAMILIES[family](rng, n_steps)
    traj.seed = seed
    return traj


# ---------------------------------------------------------------------------
# 2. Detecteurs - scores de danger, parametres pre-enregistres
# ---------------------------------------------------------------------------

#: Parametres MCS PRE-ENREGISTRES (fixes avant toute evaluation ; ne
#: doivent pas etre ajustes au vu des resultats du benchmark).
MCS_RHO = 0.85
MCS_DCRIT = 0.6
MA_WINDOW = 5
EWMA_LAMBDA = 0.3
SLOPE_WINDOW = 8
CUSUM_DRIFT = 0.05


def _score_mcs(traj: Trajectory, *, use_debt: bool = True,
               use_overflow: bool = True,
               additive_leak: bool = False) -> list[float]:
    """Score = -M(t) calcule sur les proxys observes. Les variantes
    ablatees retirent un mecanisme a la fois :
      use_debt=False      -> M sans dette (A = L seul)
      use_overflow=False  -> dette sans debordement (fuite seule)
      additive_leak=True  -> fuite additive ((1-R)+(1-B))L/2 au lieu
                             du produit (1-R)L(1-B)
    """
    D, out = 0.0, []
    for L, R, B in zip(traj.L, traj.R, traj.B, strict=True):
        C = capacity(1.0, R, B)
        A = total_load(L, D if use_debt else 0.0)
        out.append(-margin_index(A, C))
        if use_debt:
            if additive_leak:
                lk = 0.5 * ((1.0 - R) + (1.0 - B)) * L
            else:
                lk = leak(L, R, B)
            ov = max(0.0, L - C) if use_overflow else 0.0
            D = MCS_RHO * D + lk + ov
        else:
            D = 0.0
    return out


def _score_threshold(traj: Trajectory) -> list[float]:
    return list(traj.L)


def _score_moving_avg(traj: Trajectory) -> list[float]:
    out = []
    for t in range(len(traj.L)):
        lo = max(0, t - MA_WINDOW + 1)
        out.append(sum(traj.L[lo:t + 1]) / (t + 1 - lo))
    return out


def _score_ewma(traj: Trajectory) -> list[float]:
    s, out = traj.L[0], []
    for x in traj.L:
        s = EWMA_LAMBDA * x + (1.0 - EWMA_LAMBDA) * s
        out.append(s)
    return out


def _score_slope(traj: Trajectory) -> list[float]:
    """Pente locale de L (regression sur fenetre glissante), sans
    regarder le futur."""
    out = []
    for t in range(len(traj.L)):
        lo = max(0, t - SLOPE_WINDOW + 1)
        xs = list(range(lo, t + 1))
        ys = traj.L[lo:t + 1]
        m = len(xs)
        if m < 2:
            out.append(0.0)
            continue
        xb, yb = sum(xs) / m, sum(ys) / m
        num = sum((x - xb) * (y - yb) for x, y in zip(xs, ys, strict=True))
        den = sum((x - xb) ** 2 for x in xs)
        out.append(num / den if den else 0.0)
    return out


def _score_cusum(traj: Trajectory) -> list[float]:
    """CUSUM unilaterale sur L autour de sa moyenne initiale."""
    base = sum(traj.L[:10]) / min(10, len(traj.L))
    s, out = 0.0, []
    for x in traj.L:
        s = max(0.0, s + x - base - CUSUM_DRIFT)
        out.append(s)
    return out


DETECTORS: dict[str, Callable[[Trajectory], list[float]]] = {
    # baselines de charge
    "seuil_L": _score_threshold,
    "moyenne_mobile": _score_moving_avg,
    "ewma": _score_ewma,
    "pente_L": _score_slope,
    "cusum": _score_cusum,
    # ablation : proxys instantanes sans memoire de dette
    "mcs_sans_dette": lambda tr: _score_mcs(tr, use_debt=False),
    # ablations de la loi de dette
    "mcs_sans_debordement": lambda tr: _score_mcs(tr, use_overflow=False),
    "mcs_fuite_additive": lambda tr: _score_mcs(tr, additive_leak=True),
    # modele complet
    "mcs_complet": _score_mcs,
}

BASELINE_NAMES = ("seuil_L", "moyenne_mobile", "ewma", "pente_L", "cusum")


# ---------------------------------------------------------------------------
# 3. Calibration a taux de fausses alertes controle, puis evaluation
# ---------------------------------------------------------------------------

@dataclass
class DetectorResult:
    name: str
    threshold: float
    sensitivity: float           # evenements alertes AVANT l'evenement
    false_alarm_rate: float      # alertes sur trajectoires sans evenement
    precision: float
    recall: float
    median_lead: float | None    # delai median d'alerte (pas, >0 = avance)
    leads: list[int] = field(default_factory=list)
    lead_by_traj: dict[int, int] = field(default_factory=dict)
    by_family: dict[str, dict] = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d.pop("leads")
        d.pop("lead_by_traj")
        return d


def calibrate_threshold(scores_no_event: list[list[float]],
                        target_fpr: float) -> float:
    """Seuil = quantile (1 - target_fpr) des scores maximaux des
    trajectoires sans evenement. Meme regle pour tous les detecteurs."""
    maxima = sorted(max(s) for s in scores_no_event)
    idx = min(len(maxima) - 1,
              max(0, math.ceil((1.0 - target_fpr) * len(maxima)) - 1))
    return maxima[idx]


def first_alert(scores: list[float], threshold: float) -> int | None:
    return next((t for t, s in enumerate(scores) if s > threshold), None)


def evaluate_detector(name: str, thr: float,
                      validation: list[Trajectory]) -> DetectorResult:
    scorer = DETECTORS[name]
    tp = fp = fn = tn = 0
    leads: list[int] = []
    lead_by_traj: dict[int, int] = {}
    fam: dict[str, dict] = {}
    for traj in validation:
        alert = first_alert(scorer(traj), thr)
        f = fam.setdefault(traj.family,
                           {"tp": 0, "fp": 0, "fn": 0, "tn": 0,
                            "leads": []})
        if traj.event is None:
            if alert is None:
                tn += 1
                f["tn"] += 1
            else:
                fp += 1
                f["fp"] += 1
        else:
            if alert is not None and alert < traj.event:
                tp += 1
                f["tp"] += 1
                lead = traj.event - alert
                leads.append(lead)
                f["leads"].append(lead)
                lead_by_traj[traj.seed] = lead
            else:
                fn += 1
                f["fn"] += 1
                lead_by_traj[traj.seed] = 0     # manque = avance nulle
    n_pos, n_neg = tp + fn, fp + tn
    by_family = {}
    for k, f in fam.items():
        np_, nn_ = f["tp"] + f["fn"], f["fp"] + f["tn"]
        by_family[k] = {
            "sensitivity": f["tp"] / np_ if np_ else None,
            "false_alarm_rate": f["fp"] / nn_ if nn_ else None,
            "median_lead": (float(statistics.median(f["leads"]))
                            if f["leads"] else None),
            "n_event": np_, "n_no_event": nn_,
        }
    return DetectorResult(
        name=name, threshold=thr,
        sensitivity=tp / n_pos if n_pos else math.nan,
        false_alarm_rate=fp / n_neg if n_neg else math.nan,
        precision=tp / (tp + fp) if (tp + fp) else math.nan,
        recall=tp / n_pos if n_pos else math.nan,
        median_lead=float(statistics.median(leads)) if leads else None,
        leads=leads, lead_by_traj=lead_by_traj, by_family=by_family,
    )


def paired_median_gain(a: DetectorResult, b: DetectorResult) -> float | None:
    """Gain apparie de a sur b : mediane, sur les trajectoires a
    evenement, de lead_a - lead_b (detection manquee = avance 0)."""
    seeds = set(a.lead_by_traj) | set(b.lead_by_traj)
    if not seeds:
        return None
    diffs = [a.lead_by_traj.get(s, 0) - b.lead_by_traj.get(s, 0)
             for s in seeds]
    return float(statistics.median(diffs))


@dataclass
class BenchmarkResult:
    target_fpr: float
    n_calibration: int
    n_validation: int
    detectors: list[DetectorResult]
    headline: dict                 # critere principal

    def as_dict(self) -> dict:
        return {"target_fpr": self.target_fpr,
                "n_calibration": self.n_calibration,
                "n_validation": self.n_validation,
                "detectors": [d.as_dict() for d in self.detectors],
                "headline": self.headline}


def run_benchmark(calibration_seeds: range = range(0, 150),
                  validation_seeds: range = range(150, 450),
                  target_fpr: float = 0.10,
                  n_steps: int = 120) -> BenchmarkResult:
    """Pipeline complet : generation, calibration des seuils au FPR
    cible (memes trajectoires de calibration pour tous), evaluation sur
    graines disjointes, critere principal.

    Critere principal : gain median de delai d'alerte du MCS complet
    sur la MEILLEURE baseline de charge (celle au delai median le plus
    long), a taux de fausses alertes calibre identique. Publie tel
    quel, y compris s'il est nul ou negatif.
    """
    if set(calibration_seeds) & set(validation_seeds):
        raise ValueError("graines de calibration et de validation "
                         "doivent etre disjointes")
    cal = [generate(s, n_steps) for s in calibration_seeds]
    val = [generate(s, n_steps) for s in validation_seeds]

    results = []
    for name, scorer in DETECTORS.items():
        neg_scores = [scorer(tr) for tr in cal if tr.event is None]
        thr = calibrate_threshold(neg_scores, target_fpr)
        results.append(evaluate_detector(name, thr, val))

    by_name = {r.name: r for r in results}
    mcs = by_name["mcs_complet"]
    gains = {n: paired_median_gain(mcs, by_name[n])
             for n in BASELINE_NAMES}
    # baseline de reference = la plus DEFAVORABLE au MCS (gain minimal)
    defined = {n: g for n, g in gains.items() if g is not None}
    hardest = (min(defined, key=lambda n: defined[n])
               if defined else None)
    headline = {
        "critere": "gain median APPARIE de delai d'alerte du MCS complet "
                   "sur la baseline la plus defavorable (detection "
                   "manquee = avance nulle), a taux de fausses alertes "
                   f"calibre identique ({target_fpr:.0%})",
        "gains_apparies_par_baseline": gains,
        "baseline_la_plus_defavorable": hardest,
        "gain_median": gains.get(hardest) if hardest else None,
        "delai_median_mcs": mcs.median_lead,
        "sensibilite_mcs": mcs.sensitivity,
        "fpr_mcs_observe": mcs.false_alarm_rate,
    }
    return BenchmarkResult(target_fpr, len(cal), len(val),
                           results, headline)


def benchmark_markdown(res: BenchmarkResult) -> str:
    lines = [
        "# Benchmark aveugle multi-detecteurs",
        "",
        f"Trajectoires generees par 5 familles dynamiques etrangeres au "
        f"MCS (etiquettes issues d'une capacite latente cachee). "
        f"Calibration : {res.n_calibration} trajectoires ; validation : "
        f"{res.n_validation} (graines disjointes). Seuils calibres au "
        f"meme taux de fausses alertes cible : {res.target_fpr:.0%}. "
        "Parametres des detecteurs pre-enregistres dans le code.",
        "",
        "| detecteur | sensibilite | FPR observe | precision "
        "| delai median (pas) |",
        "|---|---|---|---|---|",
    ]
    for d in sorted(res.detectors,
                    key=lambda x: -(x.median_lead or -1)):
        lines.append(
            f"| {d.name} | {d.sensitivity:.2f} | {d.false_alarm_rate:.2f} "
            f"| {d.precision:.2f} | "
            f"{d.median_lead if d.median_lead is not None else '—'} |")
    h = res.headline
    lines += [
        "",
        f"**Critere principal.** {h['critere']}.",
        "Gains apparies par baseline : "
        + ", ".join(f"`{k}` {v:+.1f}" for k, v in
                    h["gains_apparies_par_baseline"].items()
                    if v is not None) + ".",
        f"Baseline la plus defavorable : `{h['baseline_la_plus_defavorable']}`. "
        f"**Gain median apparie : {h['gain_median']:+.1f} pas** "
        f"(sensibilite MCS {h['sensibilite_mcs']:.2f}, "
        f"FPR observe {h['fpr_mcs_observe']:.2f}).",
        "",
        "## Ventilation par famille (MCS complet)",
        "",
        "| famille | sensibilite | delai median | n evenements |",
        "|---|---|---|---|",
    ]
    mcs = next(d for d in res.detectors if d.name == "mcs_complet")
    for fam, s in sorted(mcs.by_family.items()):
        if s["n_event"]:
            lines.append(f"| {fam} | {s['sensitivity']:.2f} "
                         f"| {s['median_lead']} | {s['n_event']} |")
    lines += [
        "",
        "Resultats publies tels quels, echecs compris. Un gain nul ou "
        "negatif est une information, pas un accident a masquer. Les "
        "FPR observes en validation peuvent depasser la cible : les "
        "seuils sont calibres sur un jeu fini (ecart de generalisation "
        "documente, non corrige a posteriori).",
    ]
    return "\n".join(lines)
