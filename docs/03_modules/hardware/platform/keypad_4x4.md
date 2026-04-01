# `hardware.platform.keypad_4x4`

## Rôle

Ce module gère un clavier matriciel 4x4 branché sur les GPIO du Raspberry Pi.

## Structures principales

### `KeypadPins`

Dataclass immutable décrivant le câblage :

- 4 lignes ;
- 4 colonnes.

### `Keypad4x4`

Driver de scan cyclique qui :

- active chaque ligne à tour de rôle ;
- lit les colonnes ;
- identifie la touche pressée ;
- applique un anti-rebond logiciel ;
- appelle `on_key(key)` si un callback est branché.

## Fonctionnement

Le scan est exécuté dans un thread dédié.
Le driver expose simplement :

- `start()` ;
- `stop()` ;
- la propriété callback `on_key`.

## Place dans l'architecture

Le clavier n'est pas piloté directement par les modes.
Il est démarré une fois dans `main.py`, puis branché au `ModeManager`.

Cela permet :

- des touches globales disponibles partout ;
- un comportement uniforme quel que soit le mode ;
- moins de logique de cycle de vie dans les modes.
