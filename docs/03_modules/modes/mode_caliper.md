# `modes.mode_caliper`

## Rôle

`ModeCaliper` fournit l'interface vocale du pied à coulisse sans fil.

## Comportement utilisateur

- `on_enter()` : démarre le driver radio ;
- `on_exit()` : arrête le driver et les annonces automatiques ;
- appui court : annonce la dernière mesure ;
- appui long : annonce l'état du récepteur radio ;
- double appui : active ou désactive la lecture automatique.

## Lecture automatique

Le mode utilise un `Timer` périodique.
À chaque tick, il réutilise la logique de l'appui court.

## Dépendance principale

Le mode s'appuie sur `CaliperDriver`, qui lui fournit :

- un statut de disponibilité ;
- les nouvelles mesures décodées ;
- un état logique `is_connected`.
