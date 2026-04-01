# `hardware.devices.esp32_thermometer`

## Rôle

Ce module fournit le driver haut niveau du thermomètre ESP32.

## Structures

### `ThermometerData`

Dataclass simple contenant :

- la valeur ;
- l'unité ;
- un timestamp.

### `ThermometerDriver`

Le driver :

- s'appuie sur `WifiClient` ;
- décode les données reçues ;
- mémorise la dernière mesure ;
- traduit les événements techniques en messages français.

## API fournie au mode

- `start()` ;
- `stop()` ;
- `is_connected` ;
- `get_last_measure()`.

## Particularité

Le protocole applicatif est minimal : la réponse HTTP est attendue sous forme de chaîne directement convertible en `float`.
Le module reste donc simple, mais dépend fortement de la stabilité de l'API exposée côté ESP32.
