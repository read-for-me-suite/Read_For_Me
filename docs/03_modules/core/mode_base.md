# `core.mode_base`

## Rôle

`Mode` est l'abstraction commune à tous les modes de l'assistant.
Elle définit le contrat minimal que `ModeManager` sait manipuler.

## Responsabilités

La classe de base impose ou prépare :

- un nom lisible du mode ;
- un hook d'entrée `on_enter()` ;
- un hook de sortie `on_exit()` ;
- une action d'appui court `on_short_press()` ;
- une action d'appui long `on_long_press()` ;
- une action optionnelle de double appui `on_double_press()` ;
- une gestion optionnelle du clavier `on_key_pressed()` / `on_keypad_key()`.

## Pourquoi cette classe est importante

Sans cette abstraction, `ModeManager` devrait connaître la forme exacte de chaque mode.
Grâce à `Mode`, le gestionnaire peut :

- changer de mode de façon uniforme ;
- déléguer les événements sans condition métier ;
- rester indépendant des fonctionnalités concrètes.

## Points de conception

- `on_short_press()` et `on_long_press()` sont abstraites : chaque mode doit les implémenter.
- `on_enter()` et `on_exit()` sont des no-op par défaut, car tous les modes n'ont pas besoin d'initialisation lourde.
- `on_key_pressed()` délègue vers `on_keypad_key()` pour préserver la compatibilité avec l'évolution du projet.

## À retenir pour l'extension

Quand un nouveau mode est créé, le plus important est de respecter ce contrat et de garder les hooks cohérents :

- ce qui démarre dans `on_enter()` doit être nettoyé dans `on_exit()` ;
- l'action principale doit vivre dans `on_short_press()` ;
- l'appui long doit rester lisible et distinct de l'appui court.
