# Ajouter un mode

Cette page décrit la manière recommandée d'ajouter un nouveau mode dans `Read_For_Me`.

## 1. Créer la classe du mode

Créer un fichier dans `modes/`, par exemple `modes/mode_boussole.py`.
Le mode doit hériter de `core.mode_base.Mode`.

Structure minimale :

```python
from core.mode_base import Mode
from core.speaker import Speaker


class ModeBoussole(Mode):
    def __init__(self, speaker: Speaker) -> None:
        super().__init__(name="Boussole")
        self.speaker = speaker

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def on_short_press(self) -> None:
        self.speaker.speak("Action principale du mode boussole.")

    def on_long_press(self) -> None:
        self.speaker.speak("Action secondaire du mode boussole.")
```

## 2. Respecter le contrat du mode

Les méthodes importantes sont :

- `on_enter()` : démarrage ou initialisation du mode ;
- `on_exit()` : nettoyage, arrêt des threads, timers ou drivers ;
- `on_short_press()` : action principale ;
- `on_long_press()` : action secondaire ;
- `on_double_press()` : optionnel ;
- `on_key_pressed()` ou `on_keypad_key()` : optionnel pour les touches clavier.

Bon réflexe : tout ce qui alloue une ressource dans `on_enter()` doit avoir son équivalent de nettoyage dans `on_exit()`.

## 3. Injecter uniquement ce dont le mode a besoin

Aujourd'hui, le `Speaker` est toujours injecté.
Si le mode a besoin d'un driver spécifique, deux stratégies existent :

- le mode instancie son propre driver ;
- `main.py` injecte une configuration ou un objet partagé.

Dans ce dépôt, les modes `multimeter` et `reading_machine` reçoivent déjà des blocs de configuration spécialisés depuis `main.py`.

## 4. Enregistrer le mode

Ajouter l'import dans `core/mode_registry.py`, puis l'entrée dans `MODE_REGISTRY`.

Exemple :

```python
from modes.mode_boussole import ModeBoussole

MODE_REGISTRY = {
    ...
    "compass": ModeBoussole,
}
```

## 5. Activer le mode dans la configuration

Ajouter la clé dans `config/config.toml` sous `[modes].enabled`.

Exemple :

```toml
[modes]
enabled = ["datetime", "dummy", "compass"]
```

L'ordre de cette liste définit l'ordre de rotation du sélecteur.

## 6. Si le mode a besoin du clavier

Les touches globales `2`, `7`, `8`, `9` sont réservées au volume et à la vitesse.
Les autres touches peuvent être interprétées par le mode.

Exemple :

```python
def on_keypad_key(self, key: str) -> None:
    if key == "1":
        self.speaker.speak("Commande 1")
    elif key == "#":
        self.speaker.speak("Commande spéciale")
```

## 7. Si le mode utilise un driver ou un thread

Quelques règles pratiques :

- ne pas parler directement depuis le transport bas niveau ;
- préférer des callbacks de statut et de données ;
- éviter les boucles bloquantes dans les hooks du mode ;
- stopper explicitement timers, players et threads à la sortie.

## 8. Vérification minimale

Avant de considérer le mode terminé, vérifier :

- l'annonce de changement de mode ;
- appui court ;
- appui long ;
- double appui si utilisé ;
- touches clavier si utilisées ;
- comportement quand le matériel est absent ou indisponible.
