# `hardware.platform.rotary_selector`

## Rôle

`RotarySelector` transforme les signaux GPIO d'un encodeur rotatif et de son bouton en événements haut niveau utilisables par l'application.

## Ce que le module gère

- lecture des canaux A/B ;
- détermination du sens de rotation ;
- agrégation d'impulsions en un geste stable ;
- anti-rebond autour du bouton ;
- détection d'appui court ;
- détection d'appui long ;
- détection de double appui.

## API exposée

Le driver n'expose pas une logique métier.
Il expose des callbacks à brancher :

- `on_position_changed(index, direction)` ;
- `on_short_press()` ;
- `on_long_press()` ;
- `on_double_press()`.

## Logique de rotation

Le choix important ici est la stabilisation de geste.
Une rotation rapide produit plusieurs impulsions électriques, mais le dépôt ne veut pas changer de mode à chaque micro-impulsion.

Le driver :

- mémorise la direction courante ;
- relance un timer à chaque impulsion ;
- ne valide le changement qu'après un délai sans nouvelle impulsion.

Résultat : un geste physique correspond à un changement logique unique.

## Logique du bouton

Le bouton distingue :

- court ;
- long ;
- double clic.

Le double clic est implémenté avec une fenêtre de temps et un timer qui retarde la validation du simple clic.
Ce comportement est nécessaire pour ne pas déclencher un appui court avant de savoir s'il s'agit en fait d'un double appui.

## Paramètres importants

Les réglages principaux viennent de `config.toml` :

- `long_press_threshold` ;
- `gesture_settle_delay` ;
- `rotate_button_deadzone` ;
- `min_step_interval` ;
- `double_click_window` ;
- `button_bounce_time`.

## Limites connues

Le driver ne gère pas lui-même un nettoyage explicite des objets GPIO.
Dans l'état actuel du projet, il est pensé pour vivre toute la durée de l'application.
