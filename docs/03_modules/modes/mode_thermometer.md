# `modes.mode_thermometer`

## Rôle

`ModeThermometre` est l'interface utilisateur du thermomètre ESP32 sur le réseau local.

## Comportement utilisateur

- `on_enter()` : démarre le polling HTTP ;
- `on_exit()` : arrête le driver ;
- appui court : annonce la température ;
- appui long : annonce l'état de connexion.

## Dépendance principale

Le mode s'appuie sur `ThermometerDriver`, qui masque :

- le transport HTTP ;
- le décodage de la valeur ;
- la gestion des statuts réseau.

## Particularité UX

Si aucune mesure n'est encore disponible :

- le mode peut annoncer qu'il attend la première mesure ;
- ou qu'il recherche encore le thermomètre.
