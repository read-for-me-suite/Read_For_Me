# `hardware.transports.wifi_client`

## Rôle

`WifiClient` est un transport HTTP générique basé sur du polling.

## Responsabilités

- interroger périodiquement une URL cible ;
- détecter la disponibilité d'un service distant ;
- signaler les erreurs réseau ou HTTP ;
- transmettre le corps brut d'une réponse valide.

## API exposée

- `start()` ;
- `stop()` ;
- `is_running` ;
- `is_connected` ;
- `on_status(event)` ;
- `on_data(payload)`.

## Utilisation actuelle

Le client est utilisé par `ThermometerDriver` pour lire la température fournie par un ESP32 sur le réseau local.

## Intérêt architectural

Comme `BleClient`, ce module reste volontairement générique.
Il ne sait pas ce qu'est une température.
Il ne sait que :

- joindre une URL ;
- publier un statut ;
- livrer une chaîne brute.
