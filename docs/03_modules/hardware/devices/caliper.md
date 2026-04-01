# `hardware.devices.caliper`

## Rôle

Ce module fournit le driver haut niveau du pied à coulisse numérique sans fil.

## Structures

### `CaliperData`

Dataclass représentant :

- la valeur ;
- l'unité (`millimètre` ou `pouce`) ;
- le signe.

### `CaliperDriver`

Le driver :

- démarre `Nrf24Transport` ;
- décode la trame radio reçue ;
- mémorise la dernière mesure ;
- expose un état de connexion logique ;
- publie les erreurs de démarrage ou les nouvelles mesures.

## Décodage

Le format radio actuel encode au minimum :

- un `float` sur 4 octets ;
- un bit d'unité ;
- un bit de signe.

Le driver encapsule ce décodage pour que le mode n'ait qu'une donnée lisible à consommer.
