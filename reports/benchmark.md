# Benchmark aveugle multi-detecteurs

Trajectoires generees par 5 familles dynamiques etrangeres au MCS (etiquettes issues d'une capacite latente cachee). Calibration : 150 trajectoires ; validation : 300 (graines disjointes). Seuils calibres au meme taux de fausses alertes cible : 10%. Parametres des detecteurs pre-enregistres dans le code.

| detecteur | sensibilite | FPR observe | precision | delai median (pas) |
|---|---|---|---|---|
| mcs_sans_debordement | 1.00 | 0.11 | 0.92 | 15.0 |
| mcs_fuite_additive | 1.00 | 0.09 | 0.93 | 15.0 |
| cusum | 0.15 | 0.14 | 0.57 | 14.0 |
| mcs_complet | 1.00 | 0.09 | 0.93 | 11.0 |
| mcs_sans_dette | 0.86 | 0.12 | 0.90 | 5.0 |
| moyenne_mobile | 0.42 | 0.06 | 0.90 | 3.0 |
| ewma | 0.46 | 0.09 | 0.86 | 3.0 |
| seuil_L | 0.37 | 0.14 | 0.77 | 2.0 |
| pente_L | 0.26 | 0.14 | 0.70 | 1.0 |

**Critere principal.** gain median APPARIE de delai d'alerte du MCS complet sur la baseline la plus defavorable (detection manquee = avance nulle), a taux de fausses alertes calibre identique (10%).
Gains apparies par baseline : `seuil_L` +11.0, `moyenne_mobile` +11.0, `ewma` +11.0, `pente_L` +11.0, `cusum` +11.0.
Baseline la plus defavorable : `seuil_L`. **Gain median apparie : +11.0 pas** (sensibilite MCS 1.00, FPR observe 0.09).

## Ventilation par famille (MCS complet)

| famille | sensibilite | delai median | n evenements |
|---|---|---|---|
| ramp_to_break | 1.00 | 22.0 | 51 |
| regime_switch | 1.00 | 3.0 | 59 |
| silent_erosion | 1.00 | 12.0 | 57 |

Resultats publies tels quels, echecs compris. Un gain nul ou negatif est une information, pas un accident a masquer. Les FPR observes en validation peuvent depasser la cible : les seuils sont calibres sur un jeu fini (ecart de generalisation documente, non corrige a posteriori).