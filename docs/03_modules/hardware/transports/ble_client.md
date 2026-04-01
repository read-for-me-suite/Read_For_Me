# `hardware.transports.ble_client`

## Rôle

`BleClient` est un transport BLE générique basé sur `bleak`.
Il ne connaît aucun périphérique métier en particulier.

## Responsabilités

- scanner les périphériques BLE à proximité ;
- filtrer par nom ou adresse ;
- ouvrir une connexion ;
- s'abonner à une caractéristique de notification ;
- relayer les paquets bruts ;
- gérer les reconnexions automatiques ;
- publier les statuts de connexion.

## Architecture interne

L'API publique est synchrone, mais l'implémentation utilise :

- un thread dédié ;
- une boucle `asyncio` ;
- `BleakScanner` pour la découverte ;
- `BleakClient` pour la connexion et les notifications.

Cette séparation permet à l'application principale de rester simple.

## Callbacks exposés

- `on_status(event)` : événements de cycle de vie ;
- `on_packet(data)` : données brutes reçues.

Événements typiques :

- `search_start` ;
- `not_found` ;
- `found` ;
- `connecting` ;
- `connected` ;
- `disconnected` ;
- `error` ;
- `connect_error` ;
- `stopped`.

## Utilisation dans le projet

Aujourd'hui, `BleClient` est utilisé par `OwonMultimeterDriver`.
Le driver OWON s'occupe ensuite :

- du décodage des 6 octets ;
- des annonces de changement de fonction ;
- de l'API métier consommée par le mode.

## Intérêt architectural

Ce module est un bon exemple du découplage voulu par le dépôt :

- le transport ne formate pas de mesure ;
- le transport ne parle pas à l'utilisateur ;
- le transport peut être réutilisé pour d'autres appareils BLE.
