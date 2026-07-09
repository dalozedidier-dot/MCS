# Harnais de falsification MCS (§ 9.7)

## F1_degradation_silencieuse - PASS
Prediction : D monte et le MCS alerte alors que la charge seule reste muette
Details : `{'scenario': 'degradation_silencieuse', 'event': 12, 'mcs': 9, 'naive_threshold': None, 'naive_moving_avg': None, 'lead_vs_threshold': inf, 'lead_vs_moving_avg': inf, 'mcs_early_and_valid': True}`

## F2_choc_absorbe - PASS
Prediction : le detecteur de charge s'affole sur un choc bref ; le MCS revient en zone viable (l'hysteresis filtre le transitoire)
Details : `{'final_zone': 'coherence_viable', 'naive_alerts': True, 'M_final': 0.5906432748538012, 'D_final': 0.0}`

## F3_avance_de_signal - PASS
Prediction : en cas de rupture, l'alerte MCS precede l'alerte de charge
Details : `{'scenario': 'montee_vers_rupture', 'event': 11, 'mcs': 11, 'naive_threshold': 43, 'naive_moving_avg': 45, 'lead_vs_threshold': 32, 'lead_vs_moving_avg': 34, 'mcs_early_and_valid': False}`

Bilan : 3/3 PASS. Aucun echec sur ce jeu ; en chercher d'autres.