# `modes.mode_multimeter`

## Rôle

`ModeMultimetre` fournit l'interface utilisateur vocale au-dessus du driver OWON.

## Responsabilités

- démarrer et arrêter le driver du multimètre ;
- mémoriser la dernière mesure ;
- annoncer cette mesure sur demande ;
- indiquer l'état de connexion ;
- gérer une lecture automatique périodique.

## Comportement utilisateur

- `on_enter()` : démarre le driver et revient en mode manuel ;
- `on_exit()` : arrête le driver et coupe la lecture automatique ;
- appui court : annonce la dernière mesure disponible ;
- appui long : annonce l'état de connexion ;
- double appui : active ou désactive la lecture automatique.

## Lecture automatique

Le mode s'appuie sur un `threading.Timer` réarmé à chaque tick.
Cette logique permet :

- de ne pas bloquer le thread principal ;
- de conserver un comportement périodique simple ;
- d'interrompre facilement la lecture auto à la sortie du mode.

## Découplage avec le driver

Le mode ne gère ni BLE ni décodage binaire.
Il délègue ces responsabilités à `OwonMultimeterDriver`.

En pratique, le mode consomme :

- des messages de statut ;
- des objets `OwonMultimeterData` via callback ;
- un dictionnaire simplifié renvoyé par `get_last_measure()`.

## Point UX important

La lecture automatique ne spamme pas si le multimètre est momentanément déconnecté.
Le mode reste activé mais se tait jusqu'à la reconnexion du périphérique.
