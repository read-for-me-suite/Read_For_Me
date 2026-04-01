# `config.config_loader`

## Rôle

Ce module charge, fusionne et valide la configuration centrale de l'application.

## Responsabilités

- définir `DEFAULT_CONFIG` ;
- charger `config/config.toml` ;
- fusionner le fichier avec les valeurs par défaut ;
- vérifier les bornes et formats ;
- exposer des helpers comme `get_app_config()` et `get_speaker_config()`.

## Sections de configuration gérées

Le loader connaît aujourd'hui les blocs suivants :

- `speaker` ;
- `gpio` ;
- `rotary` ;
- `keypad` ;
- `ble` ;
- `camera` ;
- `ocr` ;
- `tts` ;
- `reading_machine` ;
- `multimeter` ;
- `caliper` ;
- `thermometer` ;
- `modes`.

## Pourquoi ce module est important

Il apporte trois garanties utiles :

- une valeur par défaut existe même si le TOML ne précise pas tout ;
- une mauvaise configuration est détectée tôt ;
- le reste du code peut travailler sur une structure homogène.

## Points notables de validation

Le loader vérifie notamment :

- les plages de volume et de vitesse ;
- les GPIO ;
- les touches clavier ;
- les temps strictement positifs ;
- les modes activés ;
- les noms de voix Piper autorisés.

## Usage recommandé

Le reste du dépôt ne devrait pas lire directement le TOML.
Il devrait passer par ce module pour garantir une configuration validée.
