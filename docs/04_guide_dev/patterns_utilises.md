# Patterns utilisés

Le projet n'emploie pas un framework d'architecture lourd, mais plusieurs patterns reviennent de manière cohérente.

## 1. Strategy légère via les modes

Chaque mode implémente le même contrat `Mode`.
Le `ModeManager` peut donc changer le comportement de l'application sans connaître les détails internes de chaque fonctionnalité.

Ce pattern apporte :

- un cycle de vie uniforme ;
- un point d'entrée unique pour les événements ;
- une extension simple par ajout de classe.

## 2. Registry

`core/mode_registry.py` joue le rôle de registre de plugins simple.
Les modes disponibles sont déclarés une fois, puis instanciés dynamiquement selon la configuration.

Bénéfices :

- moins de logique conditionnelle dans `main.py` ;
- ordre des modes piloté par la configuration ;
- ajout de nouveaux modes plus propre.

## 3. Facade / service central audio

`Speaker` sert de façade unique pour la sortie audio :

- annonces courtes ;
- lecture longue ;
- notifications sonores ;
- contrôle du volume ;
- contrôle de la vitesse.

Le reste du dépôt n'a pas à connaître les détails de Piper, `mplayer` ou `amixer`.

## 4. Découplage transport / device / mode

Ce pattern est central dans la couche hardware :

- le transport reçoit des données ;
- le device les décode ;
- le mode décide quoi en faire.

Il évite d'enfouir de la logique utilisateur dans des couches techniques.

## 5. Callback-based design

Les transports et drivers utilisent largement des callbacks :

- `on_status` ;
- `on_packet` ;
- `on_data` ;
- `on_new_measure`.

Cela permet :

- de rester réactif ;
- de limiter le couplage ;
- de conserver une API simple malgré la présence de threads.

## 6. Thread worker dédié

Le projet isole les opérations lentes dans des workers dédiés.
Ce n'est pas un pattern objet au sens strict, mais c'est un choix architectural majeur.

Il est visible dans :

- `SpeakerQueue` ;
- `BleClientThread` ;
- `WifiClientThread` ;
- `Nrf24Worker` ;
- `ReadingMachinePipeline`.

## 7. Configuration centralisée

Le couple `config.toml` + `config_loader.py` sert de source unique de vérité pour les réglages.
Le pattern ici est proche d'un objet de configuration validé, mais matérialisé sous forme de dictionnaire fusionné.

## 8. Anti-patterns évités volontairement

Le code essaie d'éviter :

- une dépendance directe des modes au GPIO brut ;
- un `main.py` rempli de logique métier ;
- des drivers qui parlent eux-mêmes ;
- des singletons implicites multiples pour l'audio ou la configuration.
