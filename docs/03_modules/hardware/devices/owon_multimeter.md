# `hardware.devices.owon_multimeter`

## Rôle

Ce module fournit le driver du multimètre OWON ainsi que la structure de décodage de ses trames.

## Deux briques principales

### `OwonMultimeterData`

Cette dataclass représente une trame OWON décodée.
Elle contient notamment :

- la valeur numérique ;
- le code fonction ;
- le nom de l'unité ;
- les drapeaux `overflow`, `hold`, `relative`, `auto_ranging`, `low_battery`.

La méthode clé est `from_raw(raw_data)` qui interprète les 6 octets reçus.

### `OwonMultimeterDriver`

Le driver haut niveau :

- s'appuie sur `BleClient` ;
- mémorise la dernière mesure ;
- traduit les statuts techniques en messages français ;
- annonce les changements de mode de mesure avec hystérésis ;
- expose `start()`, `stop()`, `is_connected` et `get_last_measure()`.

## Décodage OWON

Le protocole du multimètre encode plusieurs informations dans une trame compacte :

- position de la décimale ;
- fonction de mesure ;
- différents flags ;
- valeur ;
- signe.

Le module isole cette complexité pour éviter qu'elle fuite dans les modes.

## Hystérésis sur les changements de mode

Le multimètre peut traverser rapidement plusieurs fonctions quand l'utilisateur tourne sa molette.
Le driver évite donc d'annoncer immédiatement chaque changement détecté.

La stratégie actuelle :

- mémoriser le code fonction courant ;
- attendre qu'il reste stable pendant `mode_announce_delay` ;
- n'annoncer que le mode stabilisé.

Cette logique améliore fortement l'expérience utilisateur.

## API consommée par `ModeMultimetre`

Le mode n'a pas besoin de connaître la trame brute.
Il récupère seulement :

- la dernière mesure simplifiée ;
- l'état de connexion ;
- des messages de statut prêts à être envoyés au `Speaker`.
