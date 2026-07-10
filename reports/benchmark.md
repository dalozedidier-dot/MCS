# Benchmark aveugle multi-detecteurs

Trajectoires generees par 5 familles n'utilisant ni la dette ni la marge MCS (certaines partagent l'hypothese generale qu'une erosion de R et B reduit une capacite latente). Calibration : 150 trajectoires ; validation : 300 (graines disjointes). Seuils calibres par la meme regle vers un FPR cible commun : 10%. Parametres des detecteurs pre-enregistres dans le code.

| detecteur | sensibilite | FPR observe | precision | delai median (pas) |
|---|---|---|---|---|
| mcs_fuite_additive | 1.00 | 0.11 | 0.92 | 16.0 |
| mcs_sans_debordement | 1.00 | 0.09 | 0.93 | 15.0 |
| cusum | 0.15 | 0.14 | 0.57 | 14.0 |
| mcs_complet | 1.00 | 0.05 | 0.96 | 11.0 |
| mcs_sans_dette | 0.86 | 0.08 | 0.93 | 5.0 |
| moyenne_mobile | 0.61 | 0.14 | 0.85 | 4.0 |
| ewma | 0.64 | 0.10 | 0.89 | 4.0 |
| seuil_L | 0.38 | 0.08 | 0.85 | 2.0 |
| pente_L | 0.34 | 0.08 | 0.85 | 2.0 |

**Critere principal.** gain median APPARIE de delai d'alerte du MCS complet sur la baseline la plus defavorable (detection manquee = avance nulle), avec la meme regle de calibration et un FPR cible commun (10%).
Gains apparies par baseline : `seuil_L` +11.0, `moyenne_mobile` +8.0, `ewma` +8.0, `pente_L` +11.0, `cusum` +11.0.
Baseline la plus defavorable : `moyenne_mobile`. **Gain median apparie : +8.0 pas** (sensibilite MCS 1.00, FPR observe 0.05).
Distribution appariee : victoire 100.0%, egalite 0.0%, defaite 0.0%; IC95 bootstrap de la mediane [+6.0; +10.0] pas.

## Ventilation par famille (MCS complet)

| famille | sensibilite | delai median | n evenements |
|---|---|---|---|
| ramp_to_break | 1.00 | 23.0 | 51 |
| regime_switch | 1.00 | 4.0 | 59 |
| silent_erosion | 1.00 | 13.0 | 57 |

Resultats publies tels quels, echecs compris. Un gain nul ou negatif est une information, pas un accident a masquer. Les FPR observes en validation peuvent depasser la cible : les seuils sont calibres sur un jeu fini (ecart de generalisation documente, non corrige a posteriori).