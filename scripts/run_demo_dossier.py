"""Dossier de demonstration : irreversibilite et garde d'emballement.

Genere :
- reports/irreversibilite.png : boucle d'hysteresis M(L) sous rampe de
  charge aller-retour, avec temoin sans memoire (la boucle s'ecrase)
- reports/carte_regime.png : pente empirique de la carte de dette sur
  la grille (alpha, rho), frontiere analytique alpha*(rho) superposee
- reports/demonstration.md : synthese chiffree
- copies des figures dans docs/assets/ pour le site

Usage : python scripts/run_demo_dossier.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mcs import SimConfig
from mcs.experiments import hysteresis_loop, memoryless_config, regime_map
from mcs.extensions import ThetaParams

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"
ASSETS = ROOT / "docs" / "assets"
OUT.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

# 1. Irreversibilite ----------------------------------------------------------
cfg = SimConfig(R=0.7, B=0.65, rho=0.9, D_crit=0.6, mu0=0.15,
                theta_params=ThetaParams(theta0=1.0, theta_min=0.4,
                                         alpha=0.3, beta=0.1, tau=0.2))
loop = hysteresis_loop(cfg)
temoin = hysteresis_loop(memoryless_config(cfg))
n_up = len(loop.M_up)
L_axis = loop.L[:n_up]

fig, ax = plt.subplots(figsize=(7, 4.4))
ax.plot(L_axis, loop.M_up, color="#2f6b4f", lw=2.2, label="montée de charge")
ax.plot(L_axis, loop.M_down, color="#b8892b", lw=2.2,
        label="descente (même charge)")
ax.fill_between(L_axis, loop.M_up, loop.M_down, color="#2f6b4f",
                alpha=0.12, label=f"mémoire du passage (aire {loop.loop_area:.3f})")
ax.plot(L_axis, temoin.M_up, color="grey", lw=1, ls=":")
ax.plot(L_axis, temoin.M_down, color="grey", lw=1, ls=":",
        label="témoin sans mémoire (ρ = 0, Θ figé)")
ax.axhline(0, color="grey", lw=0.6)
ax.set_xlabel("charge L")
ax.set_ylabel("marge M")
ax.set_title("Irréversibilité : la trajectoire ne repasse pas par le même chemin")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "irreversibilite.png", dpi=150)
plt.close(fig)

# 2. Carte de regime ------------------------------------------------------------
rm = regime_map(n_alpha=40, n_rho=40)
fig, ax = plt.subplots(figsize=(7, 4.8))
im = ax.imshow(rm.slopes, origin="lower", aspect="auto",
               extent=[rm.alphas[0], rm.alphas[-1], rm.rhos[0], rm.rhos[-1]],
               cmap="RdYlGn_r", vmin=0.6, vmax=1.4)
ax.plot(rm.alpha_star, rm.rhos, color="#10201a", lw=2.2,
        label="frontière analytique α*(ρ) = (1−ρ)·D_crit / (Θ₀RB)")
ax.set_xlim(rm.alphas[0], rm.alphas[-1])
ax.set_xlabel("sensibilité d'usure α")
ax.set_ylabel("mémoire de dette ρ")
ax.set_title("Garde d'emballement : pente mesurée de la carte de dette "
             f"(accord {rm.agreement:.1%})")
fig.colorbar(im, label="pente empirique (>1 : perturbations amplifiées)")
ax.legend(fontsize=8, loc="upper right")
fig.tight_layout()
fig.savefig(OUT / "carte_regime.png", dpi=150)
plt.close(fig)

# 3. Synthese + copies ------------------------------------------------------------
md = f"""# Dossier de démonstration

## Irréversibilité (trace)
Sous une rampe de charge aller-retour strictement symétrique, la marge ne
revient pas par le même chemin : à charge identique, M est plus basse au
retour (écart au point de départ : {loop.gap_at_start:+.3f}), la dette
résiduelle vaut {loop.D_final:.3f} et la capacité nominale est usée à
Θ = {loop.theta_final:.3f}. Aire de la boucle : {loop.loop_area:.3f}.
Le témoin sans mémoire (ρ = 0, Θ figé) écrase la boucle
(aire {temoin.loop_area:.4f}) : l'irréversibilité vient de la dette et
de l'usure, pas de la rampe.

## Garde d'emballement (α*)
La pente de la carte de dette, MESURÉE en simulant deux dettes initiales
voisines à travers le simulateur complet, suit la frontière analytique
α*(ρ) avec un accord de {rm.agreement:.1%} hors bande numérique de ±5 %.
La valeur propre effective ρ + Θ₀RBα/D_crit gouverne exactement
l'amplification des perturbations en régime de débordement.

## Statut épistémique
Ces deux résultats sont des démonstrations de **cohérence interne** :
le code réalise les propriétés annoncées par les équations. Ils ne
disent rien de la validité empirique du modèle, qui relève du protocole
gelé (§9.2) et du harnais de falsification (§9.7).
"""
(OUT / "demonstration.md").write_text(md, encoding="utf-8")

for name in ("irreversibilite.png", "carte_regime.png"):
    shutil.copy(OUT / name, ASSETS / name)
print("Dossier de démonstration écrit :", OUT)
print(f"  boucle: aire={loop.loop_area:.3f} (témoin {temoin.loop_area:.4f}), "
      f"accord carte={rm.agreement:.1%}")
