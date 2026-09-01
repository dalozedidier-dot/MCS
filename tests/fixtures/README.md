# Fixtures empiriques

`empirical_table.csv` est une **table au format officiel** (`timestamp,L,R,B,event`) pour la CI.

Ce n’est **pas** MetroPT-3, Hydraulic ou IMS. Les étiquettes `event` sont externes au MCS, figées dans le fichier. Aucun proxy n’est calculé ici.

Les jeux officiels se téléchargent avec :

```bash
python scripts/fetch_real_data.py metropt3
```

ou le workflow GitHub **Real empirical evidence**.
