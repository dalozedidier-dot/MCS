# Changelog

## 0.4.0 — 2026-07-10

Axe démonstration.

### Simulateur interactif hébergé (Phase 4 partielle)
- `docs/mcs-engine.js` : portage JavaScript du noyau et des extensions 6.1–6.3 et 6.5, boucle de simulation dans l'ordre exact du §5.1. La fidélité n'est pas promise mais testée : `tests/test_js_parity.py` exécute le moteur sous Node et compare M, D, Θ, C, U, μ et les zones au moteur Python à 1e-9 près sur cinq configurations couvrant toutes les extensions (CI).
- `docs/simulateur.html` : simulateur autonome sans dépendance — curseurs, bande d'incertitude ±dM (§4), fonds de zones ordinales, hystérésis k = 3, D* affiché, 5 scénarios du §7 préchargés, garde-fous d'interprétation du §9.8 affichés dans l'interface (exigence de la Phase 4).

### `mcs.experiments` — démonstrations de cohérence interne
- `hysteresis_loop` : irréversibilité — sous rampe de charge aller-retour symétrique, M(L) ne revient pas par le même chemin ; l'aire de la boucle quantifie la mémoire du passage ; témoin sans mémoire (ρ = 0, Θ figé) à boucle écrasée prouvant que la trace vient de la dette et de l'usure.
- `perturbation_slope` / `regime_map` : la pente de la carte de dette mesurée à travers `simulate()` (deux dettes initiales voisines, régime de débordement non saturé) coïncide avec la valeur propre ρ + Θ₀RBα/D_crit à 1e-6 près, et le verdict amplification/amortissement suit la frontière analytique α*(ρ) à 100 % hors bande numérique.
- Figures `reports/irreversibilite.png` et `reports/carte_regime.png` (+ copies `docs/assets/`), synthèse `reports/demonstration.md`, script `scripts/run_demo_dossier.py` ajouté à la CI.
- Suite de tests : 76 → 87.


## 0.3.0 — 2026-07-10

### Cohérence des moteurs
- Le simulateur réseau applique désormais toutes les extensions du simulateur individuel : contrôle, remboursement, récupération évolutive et capacité Θ dynamique.
- Ajout d’un invariant testé : un réseau à un nœud sans couplage reproduit exactement `simulate()`.

### Validation et qualité
- Validation centralisée des domaines, seuils, séries temporelles, nombres de pas, paramètres d’extension, matrices de couplage et protocoles.
- Validation complète avant gel du protocole : proxys uniques, ancrages non vides, poids cohérents et strictement positifs, paramètres et seuils valides.
- Suite portée de 69 à 76 tests. Ajout de Ruff, couverture, Hypothesis, build et Twine aux outils de développement.
- CI renforcée : lint, couverture, rapports reproductibles et vérification du paquet.

### Diffusion
- Nouvelle page GitHub Pages dans `docs/` : résultats, graphiques de robustesse, méthode, limites et instructions de reproduction.
- Workflow `pages.yml` pour le déploiement automatique.

## 0.2.0 — 2026-07-10

Phases 1 à 3 de la ROADMAP.

### Phase 1 — `mcs.robustness` (§9.6)
- Bruit multiplicatif lognormal sur L, R, B ; Monte Carlo reproductible (quantiles, taux d'alerte, détection d'emballement numérique).
- Étude de fausses alertes : calibration de l'hystérésis k (suppression 81 % → 100 % pour k = 1 → 8).
- Détection d'oscillations près de la condition de viabilité μ\*.
- Jacobienne exacte de la carte de dette couplée, rayon spectral par itération de puissance (stdlib pure) ; la condition de petit gain du noyau est vérifiée comme majoration ; cartographie des cascades.
- Décomposition de sensibilité (tornado) cohérente avec `margin_uncertainty`.

### Phase 2 — `mcs.protocol` (§9.2–9.3)
- Protocole pré-enregistré : proxys avec ancrages 0/1, agrégation « du pire » ou pondérée, seuils, pas de temps ; gel par empreinte SHA-256 horodatée ; `compute_series` refuse tout protocole non gelé ou altéré.
- Normalisations du §9.3 (L/L_crit, R et B par temps cibles, D(0) par irritants pondérés par ancienneté), import CSV, rapport Markdown M(t) ± IC avec zones ordinales et vérification « dette = indicateur avancé ».

### Phase 3 — `mcs.baselines` (§9.7)
- Baselines naïves (seuil sur L, moyenne mobile sans fuite du futur), avance de signal, harnais de falsification F1–F3 (dégradation silencieuse, choc absorbé, avance sur rupture) avec rapport PASS/FAIL documentant les échecs.

### Divers
- Suite de tests : 45 → 69. Extras `[viz]` (matplotlib) et `[protocol]` (PyYAML). Scripts `run_robustness.py` et `run_protocol_demo.py` ; rapports et figures dans `reports/`.
- Constat documenté : ρ(J) < 1 garantit une dette bornée, pas une marge viable — les deux seuils diffèrent.

## 0.1.0

Noyau §3–5, extensions §6.1–6.5, réseau §6.4, simulateur anti-circularité §5.1, scénarios §7, table §9.4, prototype Streamlit §8, 45 tests, CI.
