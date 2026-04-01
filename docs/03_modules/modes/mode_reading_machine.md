# `modes.mode_reading_machine`

## Rôle

`ModeReadingMachine` est le mode le plus complet du projet.
Il relie le clavier, la caméra, l'OCR, la synthèse vocale et la lecture audio pilotable.

## Contrôles utilisateur

Dans ce mode, les actions principales passent par le clavier.
Par défaut :

- `1` : capture et lancement du pipeline ;
- `3` : annulation ;
- `4` : retour arrière ;
- `5` : pause / reprise ;
- `6` : avance ;
- `*` : relire.

Les touches globales de volume et vitesse restent gérées par `ModeManager`.

## Dépendances principales

- `Speaker` pour les prompts, la synthèse et la lecture ;
- `PiCamera` pour la capture ;
- `TextReaderDevice` pour le pipeline image -> texte ;
- `PlaybackHandle` pour contrôler la lecture ;
- plusieurs threads et événements pour le pilotage.

## Sous-systèmes internes

Le mode gère plusieurs préoccupations :

- disponibilité de la caméra ;
- pipeline de capture/OCR/synthèse ;
- lecture longue ;
- annulation ;
- monitor caméra avec retry ;
- sons de feedback.

## Cycle de vie

### `on_enter()`

- remet l'état d'annulation à zéro ;
- vérifie la disponibilité de la caméra ;
- lance le monitor caméra si nécessaire.

### `on_exit()`

- annule les opérations en cours ;
- stoppe la lecture ;
- stoppe le monitor caméra ;
- attend la fin du thread de pipeline ;
- remet l'état de pause à zéro.

## Pipeline utilisateur

Lors d'une capture :

1. le mode vérifie qu'il n'est pas déjà occupé ;
2. il vérifie la disponibilité caméra ;
3. il joue un son de déclenchement ;
4. il lance un thread de pipeline ;
5. le pipeline capture l'image puis exécute l'OCR ;
6. le texte propre est synthétisé en WAV ;
7. la lecture démarre.

## Pourquoi ce mode est important

C'est la meilleure démonstration de l'architecture du dépôt :

- orchestration au niveau du mode ;
- découplage de la capture et de l'OCR ;
- voix centralisée dans `Speaker` ;
- contrôle temps réel de la lecture ;
- gestion explicite des erreurs matérielles.
