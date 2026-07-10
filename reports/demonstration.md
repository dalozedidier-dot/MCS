# Dossier de démonstration

## Irréversibilité (trace)
Sous une rampe de charge aller-retour strictement symétrique, la marge ne
revient pas par le même chemin : à charge identique, M est plus basse au
retour (écart au point de départ : -3.511), la dette
résiduelle vaut 1.012 et la capacité nominale est usée à
Θ = 0.665. Aire de la boucle : 6.497.
Le témoin sans mémoire (ρ = 0, Θ figé) écrase la boucle
(aire 0.0379) : l'irréversibilité vient de la dette et
de l'usure, pas de la rampe.

## Garde d'emballement (α*)
La pente de la carte de dette, MESURÉE en simulant deux dettes initiales
voisines à travers le simulateur complet, suit la frontière analytique
α*(ρ) avec un accord de 100.0% hors bande numérique de ±5 %.
La valeur propre effective ρ + Θ₀RBα/D_crit gouverne exactement
l'amplification des perturbations en régime de débordement.

## Statut épistémique
Ces deux résultats sont des démonstrations de **cohérence interne** :
le code réalise les propriétés annoncées par les équations. Ils ne
disent rien de la validité empirique du modèle, qui relève du protocole
gelé (§9.2) et du harnais de falsification (§9.7).
