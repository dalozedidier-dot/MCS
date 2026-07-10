# Rapport de robustesse MCS - Phase 1

## Sensibilite (tornado)
Au point de fonctionnement (M = -0.07), 10 % d'erreur par proxy deplace M de 0.429 au total - plus d'une bande de zone entiere : M doit toujours etre rapporte avec IC.

## Monte Carlo (bruit multiplicatif L 10 %, R/B 5 %)
M final q05/q50/q95 = ['-0.857', '-0.542', '-0.317'], taux d'alerte = 100%, pas median de premiere alerte = 3.0, trajectoires divergentes = 0/300.

## Hysteresis
| k | transitions brutes | confirmees | suppression |
|---|---|---|---|
| 1 | 53.1 | 9.9 | 81% |
| 2 | 53.1 | 9.9 | 81% |
| 3 | 53.1 | 2.7 | 95% |
| 5 | 53.1 | 0.4 | 99% |
| 8 | 53.1 | 0.0 | 100% |

k = 3 (defaut) supprime deja 95% des fausses alertes ; le cout est le delai de detection mesure par le pas median de premiere alerte ci-dessus.

## Reseau : condition exacte de petit gain
| couplage | rho(J) | stable (prediction) | noeuds casses |
|---|---|---|---|
| 0.0 | 0.900 | True | 0 |
| 0.05 | 0.920 | True | 0 |
| 0.1 | 0.940 | True | 3 |
| 0.2 | 0.980 | True | 3 |
| 0.3 | 1.020 | False | 3 |
| 0.5 | 1.100 | False | 3 |
| 0.8 | 1.220 | False | 3 |
| 1.2 | 1.380 | False | 3 |

Le verdict spectral (exact) raffine la condition de somme de ligne du noyau, qui n'est qu'une majoration. Nuance importante revelee par le balayage : rho(J) < 1 garantit une dette BORNEE, pas une marge viable - entre les deux seuils (ici couplage 0.1-0.2), la dette converge vers un niveau de repos assez haut pour casser les noeuds. La stabilite de la carte de dette et la viabilite de M sont deux questions distinctes.

## Convergence autour de mu*
mu* = 0.300 au point de fonctionnement. Amplitudes residuelles de D apres transitoire : 0.50x -> 0.0005, 0.80x -> 0.0007, 0.95x -> 0.0008, 1.00x -> 0.0009, 1.05x -> 0.0009, 1.20x -> 0.0011, 1.50x -> 0.0000, 2.00x -> 0.0000.
Changements de signe de la derivee apres transitoire : 0, 0, 0, 0, 0, 0, 0, 0. Aucun cycle n'est detecte dans ce balayage ; la figure mesure une amplitude residuelle de convergence, pas une oscillation entretenue.
