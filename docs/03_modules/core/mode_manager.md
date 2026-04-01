# `core.mode_manager`

## Rôle

`ModeManager` est l'orchestrateur central de l'application.
Il relie les entrées utilisateur aux modes, sans contenir la logique métier de ces modes.

## Responsabilités principales

- conserver la liste ordonnée des modes ;
- savoir quel mode est actif ;
- annoncer le mode courant via `Speaker` ;
- gérer les changements de mode ;
- router les appuis du bouton rotatif ;
- gérer le clavier matriciel global ;
- appliquer les touches globales de volume et de vitesse.

## Fonctionnement au démarrage

Lors de son initialisation, `ModeManager` :

1. mémorise les modes et le `Speaker` ;
2. démarre le clavier s'il a été fourni ;
3. positionne le premier mode comme mode courant ;
4. annonce ce mode ;
5. appelle `on_enter()` sur ce mode.

L'ordre "annonce puis `on_enter()`" est volontaire : si le mode émet lui-même des messages, l'annonce du nom du mode reste prioritaire.

## Gestion du clavier

Le clavier 4x4 n'est pas géré mode par mode.
Il est branché une fois pour toute dans `ModeManager`.

Deux catégories de touches coexistent :

- touches globales, interceptées par `ModeManager` ;
- touches métier, transmises au mode actif.

Par défaut, les touches globales sont :

- `8` : volume + ;
- `2` : volume - ;
- `9` : vitesse + ;
- `7` : vitesse -.

## Changement de mode

`set_index()` applique la bascule selon la séquence suivante :

1. coupe tout l'audio en cours ;
2. appelle `on_exit()` sur l'ancien mode ;
3. remplace le mode courant ;
4. annonce le nouveau mode ;
5. appelle `on_enter()` sur le nouveau mode.

Cette méthode concentre une règle UX très importante : un changement de mode annule immédiatement l'expérience audio précédente.

## Points forts du design

- le gestionnaire ne connaît pas la logique métier de chaque mode ;
- les touches globales ne polluent pas les modes ;
- le clavier reste actif en permanence ;
- l'ordre des modes est déterminé à l'extérieur par la configuration.
