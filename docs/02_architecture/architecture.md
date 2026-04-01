# Architecture du système

Cette page donne une vue d'ensemble fidèle au dépôt actuel.
Elle doit permettre de comprendre comment les événements circulent et où se situe chaque responsabilité.

## 1. Assemblage global

Le point d'entrée est `main.py`.
Il réalise les opérations suivantes dans cet ordre :

1. charge et valide la configuration ;
2. instancie le `Speaker` ;
3. instancie le clavier matriciel ;
4. construit dynamiquement la liste des modes activés ;
5. crée le `ModeManager` ;
6. crée le `RotarySelector` ;
7. branche les callbacks du sélecteur vers le `ModeManager` ;
8. laisse vivre l'application avec `signal.pause()`.

Cette séquence d'initialisation est importante parce qu'elle garantit :

- que la voix est disponible avant toute annonce ;
- que le clavier global est actif pour tous les modes ;
- que le premier mode est annoncé puis activé immédiatement.

## 2. Découpage du dépôt

```text
Read_For_Me/
├── config/
│   ├── config.toml
│   └── config_loader.py
├── core/
│   ├── mode_base.py
│   ├── mode_manager.py
│   ├── mode_registry.py
│   └── speaker.py
├── hardware/
│   ├── devices/
│   ├── platform/
│   └── transports/
├── modes/
├── sounds/
├── tests/
└── main.py
```

Le découpage suit une logique en quatre étages :

- `platform` : matériel directement connecté à la Pi ;
- `transports` : couche d'accès à un média de communication ;
- `devices` : décodage ou pilotage d'un périphérique concret ;
- `modes` : comportement utilisateur final.

## 3. Flux d'événements principaux

### 3.1 Changement de mode

Le flux nominal est :

1. le `RotarySelector` détecte une rotation stable ;
2. il appelle `on_position_changed(index, direction)` ;
3. `ModeManager.set_index()` coupe l'audio en cours ;
4. `ModeManager` appelle `on_exit()` sur l'ancien mode ;
5. `ModeManager` annonce le nouveau mode ;
6. `ModeManager` appelle `on_enter()` sur le nouveau mode.

Le fait de couper l'audio avant la bascule est central : un ancien mode ne continue pas à parler alors que l'utilisateur vient d'en sélectionner un autre.

### 3.2 Événements bouton du sélecteur

Le bouton intégré au sélecteur produit trois callbacks haut niveau :

- `handle_short_press()` ;
- `handle_long_press()` ;
- `handle_double_press()`.

Le `ModeManager` ne les interprète pas lui-même.
Il les délègue au mode actif via l'interface commune définie dans `Mode`.

### 3.3 Événements clavier

Le `Keypad4x4` tourne en continu dans un thread dédié.
À chaque touche détectée :

1. le driver appelle `ModeManager.handle_key_pressed(key)` ;
2. si la touche est globale, `ModeManager` agit directement sur `Speaker` ;
3. sinon, la touche est transmise au mode actif.

Ce design évite d'avoir à démarrer ou arrêter le clavier à chaque changement de mode.

### 3.4 Données issues des périphériques

Chaque périphérique suit sensiblement le même schéma :

- le transport reçoit des paquets bruts ou des réponses réseau ;
- le driver de périphérique les traduit en données métier ;
- le mode mémorise ou reformate ces données ;
- le `Speaker` effectue l'annonce au bon moment.

Exemples :

- BLE -> `BleClient` -> `OwonMultimeterDriver` -> `ModeMultimetre` ;
- HTTP -> `WifiClient` -> `ThermometerDriver` -> `ModeThermometre` ;
- NRF24 -> `Nrf24Transport` -> `CaliperDriver` -> `ModeCaliper`.

## 4. Cas particulier : la machine à lire

La machine à lire est le flux le plus riche du dépôt.
Elle assemble plusieurs briques successives :

1. `ModeReadingMachine` reçoit une touche clavier ;
2. il lance un thread de pipeline ;
3. `TextReaderDevice` capture une image ;
4. `TextReaderDevice` exécute l'OCR ;
5. `TextReaderDevice` nettoie le texte ;
6. `Speaker.synthesize_to_file()` génère un WAV ;
7. `Speaker.play()` lance la lecture longue via `mplayer` en mode slave.

Ce mode gère aussi :

- l'annulation ;
- pause / reprise ;
- avance / retour ;
- replay ;
- surveillance de disponibilité de la caméra.

## 5. Gestion de la configuration

La configuration centrale est stockée dans `config/config.toml`.
Le module `config/config_loader.py` :

- fournit les valeurs par défaut ;
- fusionne les surcharges du fichier TOML ;
- valide les bornes, formats et listes ;
- expose des helpers pour le reste de l'application.

La configuration pilote notamment :

- le choix de la voix Piper ;
- le volume et la vitesse par défaut ;
- les GPIO du rotatif et du clavier ;
- les paramètres BLE ;
- les paramètres OCR ;
- les délais propres à chaque mode.

## 6. Modèle d'extensibilité

L'extensibilité repose sur deux points simples.

### 6.1 Registre des modes

`core/mode_registry.py` associe une clé logique à une classe Python.
`main.py` n'a pas besoin de connaître à l'avance l'ordre final des modes : il lit `modes.enabled` dans la config puis instancie chaque classe correspondante.

### 6.2 Empilement platform -> transport -> device -> mode

Lorsqu'un nouveau matériel arrive, la logique idéale est :

1. créer ou réutiliser un transport ;
2. créer un driver de périphérique ;
3. créer un mode qui consomme ce driver ;
4. l'enregistrer dans le registre.

Cela évite de mélanger :

- les détails protocolaires ;
- le décodage des données ;
- l'expérience utilisateur ;
- l'orchestration globale.

## 7. Threads et opérations non bloquantes

Le dépôt utilise volontairement plusieurs boucles ou threads indépendants :

- thread `SpeakerQueue` pour les annonces ;
- processus `mplayer` séparés pour l'audio ;
- thread `BleClientThread` pour la pile BLE ;
- thread `Keypad4x4` pour le scan clavier ;
- thread `ReadingMachinePipeline` pour la machine à lire ;
- thread `ReadingMachineCameraMonitor` pour la disponibilité caméra ;
- thread `WifiClientThread` pour le polling HTTP ;
- thread `Nrf24Worker` pour la radio.

Le thread principal, lui, reste minimal : il initialise, branche et attend.

## 8. Principes d'architecture à retenir

Le projet cherche avant tout à rester :

- simple à étendre ;
- robuste face au matériel ;
- clair à documenter ;
- testable partiellement même sans tout le matériel branché.

Si un nouveau développement ne respecte plus la séparation `mode` / `device` / `transport`, c'est généralement un bon signal qu'il faut refactorer avant d'aller plus loin.
