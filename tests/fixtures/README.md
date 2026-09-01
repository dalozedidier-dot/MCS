# Fixtures empiriques

`empirical_table.csv` est une **table au format officiel** (`timestamp,L,R,B,event`) pour la CI.

Ce n’est **pas** MetroPT-3, Hydraulic ou IMS. Les étiquettes `event` sont externes au MCS, figées dans le fichier. Aucun proxy n’est calculé ici.

Les tests `test_proxy_recipes.py` et `test_real_pipeline.py` construisent en mémoire des tables **au schéma** des sources officielles. Elles vérifient les recettes et la boucle adaptateur → CSV → évaluateur. Elles ne remplacent pas un dump UCI / NASA hashé.

Les jeux officiels se téléchargent avec :

```bash
python scripts/fetch_real_data.py metropt3
```

ou le workflow GitHub **Real empirical evidence**.
