"""Rapport de robustesse Phase 1 + falsification Phase 3 (ROADMAP).

Genere dans reports/ :
- tornado.png            : decomposition de sensibilite dM (§ 4)
- monte_carlo.png        : eventail de M(t) sous bruit multiplicatif
- hysteresis_k.png       : calibration de k contre les fausses alertes
- cascade.png            : noeuds casses vs rayon spectral rho(J)
- oscillations.png       : amplitude d'oscillation autour de mu*
- robustesse.md          : synthese chiffree
- falsification.md       : PASS/FAIL du harnais § 9.7

Usage : python scripts/run_robustness.py
Requiert : pip install -e ".[viz]"
"""

from __future__ import annotations

import random
import statistics
from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mcs import SimConfig, simulate
from mcs.baselines import falsification_report, falsification_run
from mcs.extensions import viability_repayment_threshold
from mcs.robustness import (
    cascade_sweep, false_alarm_study, monte_carlo, noisy,
    oscillation_score, sensitivity_tornado,
)

OUT = Path(__file__).resolve().parent.parent / "reports"
OUT.mkdir(exist_ok=True)
lines = ["# Rapport de robustesse MCS - Phase 1", ""]


# 1. Tornado -----------------------------------------------------------------
t = sensitivity_tornado(L=0.4, D=0.2, theta=1.0, R=0.8, B=0.7, rel_err=0.10)
names = list(t["contributions"])
vals = [t["contributions"][k] for k in names]
fig, ax = plt.subplots(figsize=(6, 3))
ax.barh(names, vals, color="#2f6b4f")
ax.set_xlabel("|contribution a dM| pour 10 % d'erreur relative")
ax.set_title(f"Sensibilite au point M = {t['M']:+.2f} (§ 4)")
fig.tight_layout(); fig.savefig(OUT / "tornado.png", dpi=150); plt.close(fig)
lines += [f"## Sensibilite (tornado)",
          f"Au point de fonctionnement (M = {t['M']:+.2f}), 10 % d'erreur "
          f"par proxy deplace M de {t['total']:.3f} au total - plus d'une "
          "bande de zone entiere : M doit toujours etre rapporte avec IC.", ""]

# 2. Monte Carlo -------------------------------------------------------------
cfg = SimConfig(L=0.4, R=0.7, B=0.65, rho=0.85, D_crit=0.6)
mc = monte_carlo(cfg, n_steps=60, n_runs=300, sigma_L=0.10,
                 sigma_R=0.05, sigma_B=0.05, seed=11)
fig, ax = plt.subplots(figsize=(7, 4))
for r in range(40):
    rng = random.Random(11 + r)
    c = replace(cfg, L=noisy(cfg.L, 0.10, rng),
                R=noisy(cfg.R, 0.05, rng, hi=1.0),
                B=noisy(cfg.B, 0.05, rng, hi=1.0))
    res = simulate(c, 60)
    ax.plot(res.t, res.M, color="#2f6b4f", alpha=0.15)
det = simulate(cfg, 60)
ax.plot(det.t, det.M, color="#b8892b", lw=2, label="deterministe")
for y, lbl in ((0.30, "viable"), (0.10, "tension"), (0.05, "saturation"),
               (-0.05, "pre-rupture")):
    ax.axhline(y, color="grey", ls=":", lw=0.7)
ax.set_xlabel("t"); ax.set_ylabel("M(t)")
ax.set_title("Degradation lente sous bruit multiplicatif (300 runs)")
ax.legend()
fig.tight_layout(); fig.savefig(OUT / "monte_carlo.png", dpi=150)
plt.close(fig)
d = mc.as_dict()
lines += ["## Monte Carlo (bruit multiplicatif L 10 %, R/B 5 %)",
          f"M final q05/q50/q95 = {['%+.3f' % q for q in d['M_final_q05_q50_q95']]}, "
          f"taux d'alerte = {d['alert_rate']:.0%}, "
          f"pas median de premiere alerte = {d['median_first_alert']}, "
          f"trajectoires divergentes = {d['diverged']}/300.", ""]

# 3. Calibration de k ---------------------------------------------------------
cfg_st = SimConfig(L=0.55, R=0.85, B=0.85, rho=0.5)
recs = false_alarm_study(cfg_st, ks=(1, 2, 3, 5, 8), n_steps=80,
                         n_runs=120, sigma=0.12, seed=7)
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.plot([r.k for r in recs], [r.suppression * 100 for r in recs],
        "o-", color="#2f6b4f")
ax.set_xlabel("k (pas de confirmation)")
ax.set_ylabel("fausses alertes supprimees (%)")
ax.set_title("Calibration de l'hysteresis (systeme stationnaire bruite)")
fig.tight_layout(); fig.savefig(OUT / "hysteresis_k.png", dpi=150)
plt.close(fig)
lines += ["## Hysteresis",
          "| k | transitions brutes | confirmees | suppression |",
          "|---|---|---|---|"]
lines += [f"| {r.k} | {r.transitions_raw:.1f} | {r.transitions_confirmed:.1f} "
          f"| {r.suppression:.0%} |" for r in recs]
k3 = next(r for r in recs if r.k == 3)
lines += ["", f"k = 3 (defaut) supprime deja {k3.suppression:.0%} des "
          "fausses alertes ; le cout est le delai de detection mesure "
          "par le pas median de premiere alerte ci-dessus.", ""]

# 4. Cascades vs rayon spectral ------------------------------------------------
nodes = [SimConfig(L=0.2, R=0.8, B=0.7, rho=0.9, D_crit=0.3)
         for _ in range(3)]
pattern = [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
strengths = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2]
casc = cascade_sweep(nodes, pattern, strengths, n_steps=120)
fig, ax1 = plt.subplots(figsize=(7, 4))
ax1.plot([c["strength"] for c in casc],
         [c["spectral_radius"] for c in casc], "o-", color="#b8892b",
         label="rho(J)")
ax1.axhline(1.0, color="grey", ls="--", lw=0.8)
ax1.set_xlabel("intensite de couplage"); ax1.set_ylabel("rayon spectral")
ax2 = ax1.twinx()
ax2.bar([c["strength"] for c in casc], [c["nodes_broken"] for c in casc],
        width=[max(0.004, s * 0.15) for s in strengths],
        color="#2f6b4f", alpha=0.5, label="noeuds en (pre-)rupture")
ax2.set_ylabel("noeuds casses / 3")
ax1.set_title("Cascade : la bascule suit le seuil rho(J) = 1 (§ 6.4)")
fig.tight_layout(); fig.savefig(OUT / "cascade.png", dpi=150); plt.close(fig)
lines += ["## Reseau : condition exacte de petit gain",
          "| couplage | rho(J) | stable (prediction) | noeuds casses |",
          "|---|---|---|---|"]
lines += [f"| {c['strength']} | {c['spectral_radius']:.3f} "
          f"| {c['predicted_stable']} | {c['nodes_broken']} |" for c in casc]
lines += ["", "Le verdict spectral (exact) raffine la condition de somme "
          "de ligne du noyau, qui n'est qu'une majoration. Nuance "
          "importante revelee par le balayage : rho(J) < 1 garantit une "
          "dette BORNEE, pas une marge viable - entre les deux seuils "
          "(ici couplage 0.1-0.2), la dette converge vers un niveau de "
          "repos assez haut pour casser les noeuds. La stabilite de la "
          "carte de dette et la viabilite de M sont deux questions "
          "distinctes.", ""]

# 5. Oscillations pres de mu* ---------------------------------------------------
base = SimConfig(L=0.30, R=0.7, B=0.6, rho=0.9, D_crit=0.6, gamma=1.0)
C0 = 1.0 * 0.7 * 0.6
mu_star = viability_repayment_threshold(0.30, 0.7, 0.6, C0)
mus = [mu_star * f for f in (0.5, 0.8, 0.95, 1.0, 1.05, 1.2, 1.5, 2.0)]
amps = []
for mu in mus:
    res = simulate(replace(base, mu0=mu), 200)
    amps.append(oscillation_score(res.D, burn_in=60)["amplitude"])
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.plot([m / mu_star for m in mus], amps, "o-", color="#2f6b4f")
ax.set_xlabel("mu0 / mu*"); ax.set_ylabel("amplitude residuelle de D")
ax.set_title("Comportement autour de la condition de viabilite mu* (§ 9.6)")
fig.tight_layout(); fig.savefig(OUT / "oscillations.png", dpi=150)
plt.close(fig)
lines += ["## Autour de mu*",
          f"mu* = {mu_star:.3f} au point de fonctionnement. Amplitudes "
          "residuelles de D apres transitoire : "
          + ", ".join(f"{m/mu_star:.2f}x -> {a:.4f}"
                      for m, a in zip(mus, amps)) + ".", ""]

(OUT / "robustesse.md").write_text("\n".join(lines), encoding="utf-8")

# 6. Falsification (Phase 3) -----------------------------------------------------
recs = falsification_run()
(OUT / "falsification.md").write_text(falsification_report(recs),
                                      encoding="utf-8")
print("Rapports ecrits dans", OUT)
for r in recs:
    print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'}")
