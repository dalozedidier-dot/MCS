# MCS — Modèle de Cohérence Systémique

Implémentation Python de l'**Indice de Marge Systémique** M(t), de la **dette invisible** D(t) et de la dynamique de pré-rupture, d'après le document de travail *Modèle de Cohérence Systémique* (Didier Daloze).

> **Avertissement.** Cadre exploratoire, pédagogique et confrontable aux données. Ce n'est **pas** un outil de diagnostic clinique, psychologique ou organisationnel validé. M(t) se lit comme un indice **ordinal**, avec intervalle de confiance et hystérésis.

## L'idée en trois formules

```
A(t) = L(t) + D(t)                          charge totale effective
C(t) = Θ(t) · R(t) · B(t)                   capacité effective d'absorption
M(t) = 1 − A(t) / C(t)                      Indice de Marge Systémique
```

La dette accumule ce que le système ne récupère pas — **avant** toute rupture visible :

```
D(t+1) = ρ·D(t) + (1−R)·L·(1−B) + max(0, L−C)
```

Le contenu réfutable du modèle ne réside pas dans M(t) (une définition), mais dans les **lois de mise à jour** de la dette, de la récupération et de la capacité nominale. Ce sont elles que ce dépôt implémente et teste.

## Installation

```bash
git clone https://github.com/<votre-compte>/mcs-model.git
cd mcs-model
pip install -e ".[dev]"
pytest                      # vérifie les propriétés analytiques du modèle
```

## Démarrage rapide

```python
from mcs import SimConfig, simulate
from mcs.extensions import ThetaParams

# Dégradation lente : charge constante, mais la marge glisse en silence
cfg = SimConfig(L=0.4, R=0.7, B=0.65, rho=0.85,
                theta_params=ThetaParams(theta0=1.0, alpha=0.25, beta=0.15, tau=0.15))
res = simulate(cfg, n_steps=60)
print(res.M[0], "->", res.M[-1])       # la marge diminue à intrants constants
print(res.zone[-1])                    # zone systémique (avec hystérésis)
```

Simulateur interactif (§ 8 du document) :

```bash
pip install streamlit pandas
streamlit run app/streamlit_app.py
```

## Contenu du dépôt

| Chemin | Rôle | Section du document |
|---|---|---|
| `src/mcs/core.py` | Noyau : A, C, M, M̃, dette, D*, zones, hystérésis, incertitude | §3, §3.1, §4, §5 |
| `src/mcs/extensions.py` | Remboursement actif, Θ évolutif, contrôle, R_eff évolutive, rescalage du pas | §6.1–6.3, §6.5, §9.1 |
| `src/mcs/network.py` | Systèmes interconnectés, saturation, petit gain | §6.4 |
| `src/mcs/simulator.py` | Boucle discrète suivant l'ordre de calcul anti-circularité | §5.1 |
| `src/mcs/scenarios.py` | 5 scénarios pédagogiques + micro-simulation équipe projet | §7, §9.4 |
| `tests/` | Propriétés analytiques : D*, μ*, α*, U*, cas limites, table §9.4 | §5, §6, §9.4 |
| `app/streamlit_app.py` | Prototype interactif à curseurs | §8 |
| `src/mcs/robustness.py` | Phase 1 : Monte Carlo, calibration de k, oscillations près de μ\*, rayon spectral exact, cascades, tornado | §9.6 |
| `src/mcs/protocol.py` | Phase 2 : protocole pré-enregistré gelé (SHA-256), normalisations, import CSV, rapport M(t) ± IC | §9.2–9.3 |
| `src/mcs/baselines.py` | Phase 3 : baselines naïves, avance de signal, harnais de falsification | §9.7 |
| `scripts/` | Génération des rapports et figures (`reports/`) | — |
| `ROADMAP.md` | Plan complet du projet (phases 0 → 5) | — |

## Ce que les tests vérifient déjà

- **D\* = (1−R)L(1−B)/(1−ρ)** : convergence numérique vers le niveau de repos de la dette, et croissance non bornée si ρ = 1.
- **La dette est un indicateur avancé** : elle monte en zone viable dès que R < 1 ou B < 1.
- **Condition de viabilité du remboursement** : en deçà de μ\*, la dette dérive ; au-delà, elle se stabilise.
- **Garde d'emballement α\*** = (1−ρ)·D_crit/(Θ₀RB) : au-delà, Θ s'effondre jusqu'à Θ_min.
- **Optimum de contrôle U\*** = κ/(2η) : le contrôle restaure B puis la dégrade.
- **Table §9.4** reproduite semaine par semaine (ρ = 0,85, Θ = 1) : la baisse de charge en semaine 8 ne ramène pas l'équipe en zone viable.
- **Réseau** : bornitude des charges couplées et propagation de fragilité A → B → C.
- Cas limites du §5 : A = 0 ⇒ M = 1 ; C = 0 ⇒ incapacité critique ; bornes de R, B, ρ, Θ.
- **Rayon spectral** de la jacobienne de dette : la condition de petit gain du noyau majore bien le verdict exact ; la bascule de cascade suit ρ(J) = 1.
- **Hystérésis** : la suppression des fausses alertes croît avec k (95 % à k = 3 sur système stationnaire bruité).
- **Protocole** : refus de calculer M sans gel préalable, détection de toute altération post-gel, aller-retour YAML/JSON.
- **Falsification** : dégradation silencieuse détectée par le MCS et invisible à la charge seule ; choc bref absorbé sans alerte durable ; avance de signal sur la rupture.

## Phases 1–3 : robustesse, protocole, falsification

```bash
pip install -e ".[dev,viz,protocol]"
python scripts/run_robustness.py      # figures + reports/robustesse.md + falsification.md
python scripts/run_protocol_demo.py   # protocole gelé -> rapport M(t) ± IC
```

L'anti-circularité du §9.2 est appliquée **par le code** : `compute_series` refuse tout protocole non gelé (`freeze()` = empreinte SHA-256 + horodatage) ou modifié après gel. Le harnais de falsification (§9.7) confronte trois prédictions du modèle à des détecteurs de charge naïfs et documente les échecs en clair.

## Publier sur GitHub

```bash
cd mcs-model
git init && git add . && git commit -m "MCS v0.1.0 - noyau, extensions, tests, prototype"
gh repo create mcs-model --public --source=. --push
# ou : créer le repo sur github.com puis
# git remote add origin https://github.com/<votre-compte>/mcs-model.git
# git push -u origin main
```

La CI (GitHub Actions) lance `pytest` sur Python 3.10–3.12 à chaque push.

## Licence

MIT — voir `LICENSE`.
