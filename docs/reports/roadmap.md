# ROADMAP — tester le MCS au maximum

Plan de travail complet, organisé pour que chaque phase produise quelque chose de confrontable. Le principe directeur vient du document lui-même : *le contenu réfutable ne réside pas dans M(t), mais dans les lois de mise à jour* (§3, §9.7).

## Phase 0 — Socle (ce dépôt, fait ✅)

Noyau mathématique (§3–5), extensions 6.1–6.5, simulateur anti-circularité (§5.1), scénarios §7, reproduction de la table §9.4, tests des propriétés analytiques (D\*, μ\*, α\*, U\*, cas limites), prototype Streamlit (§8), CI GitHub Actions.

## Phase 1 — Robustesse numérique (§9.6) — fait ✅ (`robustness.py`, `scripts/run_robustness.py`, `reports/robustesse.md`)

Explorer les bords du domaine, idéalement en stochastique, pour distinguer dynamique interprétable et emballement numérique.

- Balayages de paramètres (grid + Monte Carlo) : Θ→Θmin, α→α\*, U>U\*, B≈0 avec production maintenue, R faible longue durée, couplages forts/asymétriques.
- Bruit multiplicatif sur les proxys L, R, B ; vérifier que l'hystérésis (k pas) supprime bien les fausses alertes ; calibrer k.
- Détection d'oscillations près de la condition de viabilité μ\* (§9.6).
- Condition de petit gain en réseau : vérifier numériquement le seuil via le rayon spectral de la matrice de couplage ; cartographier les cascades.
- Livrable : `notebooks/robustesse.ipynb` + rapport de sensibilité (tornado plot sur dM = −dA/C + (1−M)(dΘ/Θ + dR/R + dB/B)).

## Phase 2 — Protocole empirique minimal (§9.2–9.3) — fait ✅ (`protocol.py`, protocole YAML gelé, `scripts/run_protocol_demo.py`)

Rendre le modèle testable sur données réelles, sans circularité.

- Module `mcs/protocol.py` : déclaration **pré-enregistrée** des proxys (ancrages R=0/R=1, B=0/B=1, règle d'agrégation "du pire" vs moyenne pondérée), pas de temps, seuils — figée AVANT tout calcul de M (fichier YAML signé/daté).
- Import de données : CSV/tableur (agenda, tickets, incidents, délais signal→décision).
- Normalisations du §9.3 : L par charge critique, R = temps de régulation / temps cible, B = min(1, délai critique / délai observé), D(0) = irritants pondérés par ancienneté.
- Rapport automatique : M(t) ± intervalle de confiance, D(t) en indicateur avancé, zones ordinales avec hystérésis.

## Phase 3 — Confrontation aux données (§9.7) — harnais en place ✅ sur scénarios synthétiques (`baselines.py`, `reports/falsification.md`) ; reste : données réelles externes

- Rétro-prédiction sur cas connus de bascule ou de stabilisation (projets, équipes, incidents publics documentés) : un système dont B se dégrade durablement doit voir D monter et M baisser **plus tôt** qu'un système à boucles stables.
- Comparaison à des baselines naïves (moyenne mobile de L, seuil sur L seul) : le MCS apporte-t-il un signal avancé que la charge seule ne donne pas ?
- Falsification : chercher activement des jeux de données où les lois de mise à jour échouent ; documenter les échecs.
- Étude de calibration des paramètres prudents (§9.5) : ρ, μ₀, γ, α, β, χ, κ, η, δ, δ_D, δ_B, R_min, B_crit, s, D_seuil.

## Phase 4 — Diffusion — en cours ✅

- Page GitHub Pages de résultats, méthode et limites : **faite** (`docs/`, workflow `pages.yml`).
- Simulateur hébergé (Streamlit Community Cloud) avec les 5 scénarios §7 préchargés et les garde-fous d'interprétation (§9.8) affichés dans l'interface.
- Article/notice : positionnement vs charge allostatique, transitions critiques, viabilité, resilience engineering, dynamique des systèmes (§9.9).
- Publication PyPI (`pip install mcs-model`), documentation (mkdocs), DOI Zenodo pour citer le modèle.

## Phase 5 — Extensions de recherche

- Variante sévère max(0, A−C) du déclencheur de dette, à justifier empiriquement (§3.1).
- Estimation bayésienne des paramètres à partir de trajectoires observées ; identifiabilité.
- Réseaux réalistes (asymétriques, multi-échelles individu/équipe/organisation) et pas de temps mixtes via `rescale_time_step`.

## Garde-fous permanents (§9.8)

Jamais de diagnostic direct sur un M négatif isolé ; proxys définis avant calcul ; M rapporté avec incertitude ; pas de pilotage rigide — le modèle contient lui-même la mise en garde : trop de contrôle dégrade les boucles qu'il prétend restaurer.


## Priorités v0.4

- Ajouter des tests génératifs Hypothesis sur les invariants mathématiques.
- Comparer plusieurs lois candidates de dette sur les mêmes données.
- Construire une matrice de non-redondance des proxys pour limiter le double comptage.
- Publier l’empreinte des protocoles sur un registre externe (release GitHub, Zenodo ou OSF) afin d’établir l’antériorité, pas seulement l’intégrité locale.
