# `core.mode_registry`

## Rôle

`mode_registry` centralise la liste des classes de modes disponibles.
Il matérialise le lien entre une clé de configuration et une classe Python concrète.

## Contenu

Le module importe les classes :

- `ModeDateHeure` ;
- `ModeDummy` ;
- `ModeMultimetre` ;
- `ModeReadingMachine` ;
- `ModeCaliper` ;
- `ModeThermometre`.

Puis il expose un dictionnaire `MODE_REGISTRY`.

## Utilisation dans l'application

`main.py` lit `config["modes"]["enabled"]`.
Pour chaque clé, il récupère la classe correspondante dans `MODE_REGISTRY` puis l'instancie.

## Intérêt

Ce registre permet :

- d'éviter une liste codée en dur dans `main.py` ;
- de faire varier l'ordre des modes via la configuration ;
- d'ajouter un mode avec une modification très locale.
