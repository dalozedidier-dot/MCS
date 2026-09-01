# Changelog

## 0.8.5 — Boucle empirique testable sans dump officiel

- Recettes de proxys MetroPT-3 et Hydraulic extraites dans `mcs.proxy_recipes` et testées sur tables au schéma officiel.
- L'évaluateur CSV compte tous les événements (hits, manqués, leads), pas seulement le premier.
- Contrôle négatif par rotation circulaire des drapeaux d'événements externes, proxies figés.
- Comparaison des lois de dette et contrôle négatif publiés ensemble par `evaluate_table_bundle`.
- Pont `prepared_to_records` : série préparée → CSV officiel `timestamp,L,R,B,event` → évaluateur.
- La CI exécute `scripts/run_empirical_csv.py` sur la fixture de format.
- Ces fixtures ne sont pas MetroPT-3 / Hydraulic / IMS officiels. Aucun chiffre n'est présenté comme preuve de terrain.

## 0.8.4 — Fixture CSV empirique et lois de dette

- Chargeur `load_empirical_csv` et fixture `tests/fixtures/empirical_table.csv` au format officiel.
- Comparaison noyau vs variante sévère de la dette sur le même chemin observé.

## 0.8.3 — Données manquantes réelles et exécution multi-jeux résiliente

- MetroPT-3 applique désormais une politique complète-case après agrégation, sans inventer les fenêtres capteurs absentes.
- Le nombre de lignes écartées et la politique de données manquantes sont publiés dans les métadonnées.
- Le workflow `all` poursuit les autres jeux si un téléchargement, une vérification ou une évaluation échoue.
- Les statuts par jeu sont conservés dans `reports/real/workflow-status.tsv` et les artefacts sont toujours publiés.

See git history for 0.8.2 and earlier entries.
