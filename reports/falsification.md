# Harnais de falsification MCS (§ 9.7)

## F1_degradation_silencieuse - PASS
Prediction : D monte et le MCS alerte alors que la charge seule reste muette
Details : `{'scenario': 'degradation_silencieuse', 'event': 12, 'mcs': 9, 'naive_threshold': None, 'naive_moving_avg': None, 'lead_vs_threshold': inf, 'lead_vs_moving_avg': inf, 'lead_vs_event': 3, 'mcs_early_and_valid': True}`

## F2_choc_absorbe - PASS
Prediction : le detecteur de charge s'affole sur un choc bref ; le MCS revient en zone viable (l'hysteresis filtre le transitoire)
Details : `{'final_zone': 'coherence_viable', 'naive_alerts': True, 'M_final': 0.5906432748538012, 'D_final': 0.0}`

## F3a_avance_sur_baseline - PASS
Prediction : en cas de rupture, l'alerte MCS precede l'alerte de charge (t_MCS <= t_baseline)
Details : `{'scenario': 'montee_vers_rupture', 'event': 25, 'mcs': 21, 'naive_threshold': 171, 'naive_moving_avg': 172, 'lead_vs_threshold': 150, 'lead_vs_moving_avg': 151, 'lead_vs_event': 4, 'mcs_early_and_valid': True}`

## F3b_avance_sur_evenement - PASS
Prediction : l'alerte MCS precede la rupture d'au moins 3 pas (avance minimale pre-enregistree) - une alerte simultanee a la rupture n'est pas un signal avance
Details : `{'scenario': 'montee_vers_rupture', 'event': 25, 'mcs': 21, 'naive_threshold': 171, 'naive_moving_avg': 172, 'lead_vs_threshold': 150, 'lead_vs_moving_avg': 151, 'lead_vs_event': 4, 'mcs_early_and_valid': True, 'min_lead': 3}`

Bilan : 4/4 PASS. Aucun echec sur ce jeu ; en chercher d'autres.