# `hardware.platform.pi_camera`

## Rôle

`PiCamera` encapsule l'accès à la caméra Raspberry Pi via `rpicam-still` ou `libcamera-still`.

## Ce que le module gère

- détection de la commande de capture disponible ;
- détection de la commande de listing caméra ;
- sonde de disponibilité de la caméra ;
- capture d'une image vers un chemin donné ;
- diagnostic best-effort des processus bloquants.

## `CameraConfig`

La dataclass `CameraConfig` regroupe :

- rotation ;
- délai avant capture ;
- largeur ;
- hauteur ;
- timeout de commande.

## API utile

- `PiCamera.probe()` : dit si une caméra est détectée ;
- `PiCamera.is_available()` : version booléenne simplifiée ;
- `PiCamera.capture(output_path)` : prend une photo ;
- `PiCamera.detect_blocking_processes()` : aide au diagnostic.

## Place dans le projet

Le module ne fait ni OCR ni synthèse vocale.
Il fournit uniquement la capture bas niveau utilisée par la machine à lire.
