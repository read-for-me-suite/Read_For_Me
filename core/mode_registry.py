# core/mode_registry.py
"""
core.mode_registry
==================

Ce module définit le **registre des modes** disponibles dans l'application.

Pourquoi un registre ?
----------------------
On veut éviter de modifier `main.py` à chaque ajout de mode.

Avec un registre :
- `config/settings.toml` décide quels modes sont actifs et dans quel ordre.
- `main.py` se contente de :
    - lire la config,
    - instancier les modes via ce registre.

Cela rend l'architecture :
- **extensible** (ajouter un mode = 1 import + 1 ligne dans le registre),
- **configurable** (activer/désactiver/re-ordonner via TOML),
- **propre** (pas de if/else ou de liste codée en dur dans main).

Contrat
-------
- Les clés (ex: "datetime") doivent correspondre aux valeurs déclarées
  dans `[modes].enabled` du fichier `config/settings.toml`.
- Chaque valeur du registre est une **classe** dérivée de `Mode`
  (et non une instance).

Exemple
-------
Dans `config/settings.toml` :

[modes]
enabled = ["datetime", "dummy", "multimeter"]

Alors `main.py` instanciera dans cet ordre :
ModeDateHeure, ModeDummy, ModeMultimetre.
"""

from __future__ import annotations

from typing import Dict, Type

from core.mode_base import Mode

from modes.mode_datetime import ModeDateHeure
from modes.mode_dummy import ModeDummy
from modes.mode_multimeter import ModeMultimetre
from modes.mode_reading_machine import ModeReadingMachine
from modes.mode_caliper import ModeCaliper
from modes.mode_thermometer import ModeThermometre


MODE_REGISTRY: Dict[str, Type[Mode]] = {
    "datetime": ModeDateHeure,
    "dummy": ModeDummy,
    "multimeter": ModeMultimetre,
    "reading_machine": ModeReadingMachine,
    "caliper": ModeCaliper,
    "thermometer": ModeThermometre,
}
