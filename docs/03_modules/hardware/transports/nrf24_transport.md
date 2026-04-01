# `hardware.transports.nrf24_transport`

## Rôle

`Nrf24Transport` fournit la couche radio bas niveau pour un module NRF24L01+ connecté au Raspberry Pi.

## Responsabilités

- initialiser le module radio ;
- configurer canal, adresse et débit ;
- lancer un thread d'écoute ;
- récupérer les paquets disponibles ;
- transmettre les octets bruts à un callback.

## API exposée

- `start(on_packet_callback)` ;
- `stop()`.

Le démarrage renvoie un tuple `(success, message)` afin que le driver de niveau supérieur puisse annoncer une erreur proprement.

## Utilisation actuelle

Le transport est utilisé uniquement par `CaliperDriver`.

## Point de conception utile

Le transport ne décode pas la charge utile.
Il se limite à la réception radio.
Le format spécifique du pied à coulisse est traité dans `hardware.devices.caliper`.
