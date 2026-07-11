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
| `docs/` | GitHub Pages : résultats, méthode, limites et reproductibilité | — |

## Ce que les tests vérifient déjà

- **D\* = (1−R)L(1−B)/(1−ρ)** : convergence numérique vers le niveau de repos de la dette, et croissance non bornée si ρ = 1.
- **Dans le modèle, la dette est un candidat indicateur avancé** : elle monte en zone viable dès que R < 1 ou B < 1.
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

## Simulateur interactif (Phase 4)

`docs/simulateur.html` — hébergé sur GitHub Pages — exécute **le même modèle** que ce dépôt : le moteur `docs/mcs-engine.js` est vérifié en CI contre le moteur Python, trajectoire par trajectoire, à 1e-9 près (`tests/test_js_parity.py`). Cinq scénarios du §7 préchargés, incertitude ±dM affichée, garde-fous du §9.8 dans l'interface.

## Démonstrations de cohérence interne (`mcs.experiments`)

```bash
python scripts/run_demo_dossier.py    # irreversibilite.png + carte_regime.png + demonstration.md
```

- **Irréversibilité** : sous rampe de charge aller-retour symétrique, M(L) ne repasse pas par le même chemin ; le témoin sans mémoire écrase la boucle — la trace vient de la dette et de l'usure de Θ.
- **Garde d'emballement** : la pente de la carte de dette, mesurée en simulation, suit exactement la frontière analytique α*(ρ) = (1−ρ)·D_crit/(Θ₀RB).

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
git init && git add . && git commit -m "MCS v0.6.0 - benchmark renforce, limites negatives et GitHub Pages responsive"
gh repo create mcs-model --public --source=. --push
# ou : créer le repo sur github.com puis
# git remote add origin https://github.com/<votre-compte>/mcs-model.git
# git push -u origin main
```

La CI (GitHub Actions) exécute désormais les garde-fous qualité sur Python 3.10–3.12 : Ruff, couverture de tests, génération des rapports et vérification du paquet.

## Publier la page de résultats avec GitHub Pages

La vitrine statique est dans `docs/`. Elle présente les résultats de robustesse, le harnais de falsification, la méthode et les limites sans confondre cohérence interne et validation empirique.

1. Pousser le dépôt sur la branche `main`.
2. Dans GitHub : **Settings → Pages → Build and deployment → Source → GitHub Actions**.
3. Lancer le workflow **Deploy GitHub Pages** ou pousser une modification dans `docs/`.

La page sera publiée à l’adresse fournie par GitHub Actions. Les liens vers le dépôt s’adaptent automatiquement à l’URL GitHub Pages.

## Licence

MIT — voir `LICENSE`.

## Validation sur données réelles — v0.7.0

Le dépôt distingue désormais strictement trois niveaux :

1. **tests analytiques** : vérification du code et des propriétés mathématiques ;
2. **benchmarks synthétiques** : essais contrôlés, jamais présentés comme preuve empirique ;
3. **données réelles** : mesures de terrain ou de banc physique, avec provenance, SHA-256 et événements externes.

Aucun score empirique n'est fourni sans données sources. La chaîne installée prend en charge :

- **MetroPT-3** : mesures opérationnelles d'un compresseur de métro et fenêtres de panne déclarées ;
- **UCI Hydraulic Systems** : 2 205 cycles mesurés sur un banc hydraulique physique avec états de composants ;
- **NASA IMS Bearings** : mesures vibratoires expérimentales jusqu'à défaillance.

```bash
pip install -e ".[real,viz]"
python scripts/fetch_real_data.py --list
python scripts/fetch_real_data.py metropt3
python scripts/fetch_real_data.py hydraulic
python scripts/fetch_real_data.py ims_bearings
```

Chaque acquisition crée `data/real/<dataset>/provenance.json` avec l'URL officielle, la date, la taille et le SHA-256 de chaque fichier. Les fichiers bruts sont exclus de Git ; seuls les protocoles, manifestes et résultats reproductibles peuvent être publiés.

La page `docs/donnees-reelles.html` expose le catalogue et indique explicitement lorsqu'aucun résultat empirique n'a encore été calculé.

### Évaluer un tableau réel déjà préparé

Le projet ne déduit pas automatiquement les proxys, car cela introduirait des choix cachés. Après gel d'un protocole de domaine, fournir un CSV chronologique contenant exactement :

```text
timestamp,L,R,B,event
```

`event` doit provenir d'une panne, d'une maintenance ou d'une annotation externe au MCS. L'évaluateur ne crée ni trajectoire, ni événement, ni donnée manquante :

```bash
python scripts/run_empirical_csv.py data/real/mon_etude/validation.csv \
  --output reports/mon_etude_empirique.json
```

Le résultat conserve le SHA-256 du CSV source afin qu'il soit impossible de remplacer silencieusement les données après calcul.

## Validation empirique stricte — v0.8.1

La branche **Real Data First** possède désormais une chaîne complète de preuve sur données mesurées :

1. téléchargement officiel et provenance SHA-256 ;
2. vérification d'intégrité avant toute analyse ;
3. adaptateurs spécifiques MetroPT-3, Hydraulic et NASA IMS ;
4. recettes de proxys explicites, ajustées sur la calibration uniquement ;
5. séparation chronologique calibration/validation ;
6. événements externes au MCS ;
7. seuils calibrés vers un même taux de fausses alertes cible ;
8. comparaison au MCS sans mémoire et à plusieurs baselines ;
9. sensibilité, précision, fausses alertes, délai d'alerte et gain apparié ;
10. intervalle bootstrap et contrôle négatif par décalage circulaire des événements ;
11. rapport JSON, chronologie graphique et page GitHub Pages dédiée ;
12. publication obligatoire des limites et des échecs.

Aucun résultat n'est prérempli. Si les fichiers réels ne sont pas présents ou ne passent pas le contrôle SHA-256, aucun chiffre empirique n'est produit.

```bash
pip install -e ".[real,viz]"
python scripts/fetch_real_data.py metropt3
python scripts/verify_real_data.py data/real/metropt3
python scripts/run_real_evidence.py metropt3
python scripts/build_real_evidence_site.py
```

La page `docs/preuves-reelles.html` lit uniquement `docs/data/real-evidence.json`, lui-même construit à partir des rapports réellement calculés.
