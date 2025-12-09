# core/mode_manager.py
"""
core.mode_manager
=================

Ce module définit la classe `ModeManager`, responsable de la gestion
des **modes actifs** de l’assistant.

Rôle global
-----------

`ModeManager` est le **chef d’orchestre** des modes :

- il connaît la **liste des modes disponibles** (instances de `Mode`),
- il maintient un **index courant** (`_current_index`) et un
  **mode courant** (`_current_mode`),
- il applique les changements de mode lorsqu’on tourne le sélecteur
  rotatif,
- il **propage les événements bouton** (appui court / long / double)
  vers le mode actif,
- il utilise le `Speaker` central pour annoncer le nom du mode.

Ce composant ne connaît pas le matériel en détail (GPIO, BLE, etc.) :
il est piloté par un autre module, typiquement
`hardware.platform.rotary_selector.RotarySelector`, qui appelle :

- `set_index(...)` lors d’un changement de position,
- `handle_short_press()` lors d’un appui court,
- `handle_long_press()` lors d’un appui long,
- `handle_double_press()` lors d’un double appui.

Ainsi, le matériel et la logique de modes sont **découplés**.
"""

from typing import List, Optional

from core.mode_base import Mode
from core.speaker import Speaker


class ModeManager:
    """
    Gère la liste des modes disponibles et le mode actuellement actif.

    Responsabilités principales
    ---------------------------

    - Conserver l'index du mode courant (`_current_index`).
    - Maintenir une référence sur le mode courant (`_current_mode`).
    - Appliquer un changement de mode via `set_index(...)` :
        * appeler `on_exit()` sur l’ancien mode,
        * appeler `on_enter()` sur le nouveau,
        * annoncer vocalement le nouveau mode.
    - Relayer les événements bouton vers le mode actif :
        * `handle_short_press()` -> `current_mode.on_short_press()`,
        * `handle_long_press()`  -> `current_mode.on_long_press()`,
        * `handle_double_press()` -> `current_mode.on_double_press()`.

    Il utilise un `Speaker` partagé pour toutes les annonces globales
    comme "Mode 1 : Date et heure" ou "Mode 3 : Multimètre".
    """

    def __init__(self, modes: List[Mode], speaker: Speaker) -> None:
        """
        Initialise le gestionnaire de modes.

        Parameters
        ----------
        modes :
            Liste **ordonnée** d’instances de `Mode`.  
            Chaque élément correspond à une position possible du
            sélecteur rotatif (index 0, 1, 2, ...).

        speaker :
            Instance unique du `Speaker` central, utilisée pour
            annoncer le nom du mode courant.

        Notes
        -----
        - La liste `modes` ne doit pas être vide : on lève une erreur
          explicite si c’est le cas.
        - Au démarrage, le **premier mode** (index 0) devient le mode
          actif. On appelle immédiatement :
            * `on_enter()` sur ce mode,
            * puis `_announce_current_mode()` pour annoncer
              "Mode 1 : <nom>".
        """
        if not modes:
            raise ValueError("La liste des modes ne peut pas être vide.")

        self._modes: List[Mode] = modes
        self._speaker: Speaker = speaker

        self._current_index: int = 0
        self._current_mode: Mode = self._modes[self._current_index]

        # Hook d'entrée du premier mode au démarrage
        self._current_mode.on_enter()
        self._announce_current_mode()

    @property
    def current_index(self) -> int:
        """
        Index du mode courant dans la liste `modes`.

        Utile pour diagnostic, logs, ou pour une éventuelle IHM future.
        """
        return self._current_index

    @property
    def current_mode(self) -> Mode:
        """
        Retourne l’instance du mode actuellement actif.
        """
        return self._current_mode

    def _announce_current_mode(self) -> None:
        """
        Annonce le nom du mode courant via le `Speaker`.

        Forme choisie : "Mode X : <nom_du_mode>".

        Cette méthode est appelée :
        - au démarrage, pour le premier mode,
        - après chaque changement de mode réussi dans `set_index()`.
        """
        message = f"Mode {self._current_index + 1} : {self._current_mode.name}"
        self._speaker.speak(message)

    def set_index(self, new_index: int, direction: Optional[str] = None) -> None:
        """
        Change le mode courant en fonction d'un nouvel index.

        Cette méthode est typiquement appelée par le driver matériel
        du sélecteur rotatif (`RotarySelector`) lorsqu’un geste stable
        est détecté.

        Parameters
        ----------
        new_index :
            Nouvel index de mode (0 <= index < len(modes)).

        direction :
            Sens de rotation du sélecteur (ex: `"sens horaire"`,
            `"sens inverse"`).  
            Pour l’instant, cet argument est uniquement utilisé pour
            les logs / debug. Il pourra servir plus tard pour adapter
            l’UX si besoin.

        Comportement
        ------------
        - Si `new_index` est identique à l’index courant,
          **aucun changement** n’est appliqué.
        - Si `new_index` est en dehors des bornes, l’appel est ignoré
          (sécurité).
        - Avant de changer de mode, on appelle `speaker.clear_queue()`
          pour vider les annonces TTS en attente (cela évite par
          exemple d’entendre le nom d’un ancien mode alors que
          l’utilisateur vient de tourner la molette).
        - On appelle ensuite :
            1. `on_exit()` sur l’ancien mode,
            2. on met à jour `_current_index` et `_current_mode`,
            3. `on_enter()` sur le nouveau mode,
            4. `_announce_current_mode()` pour annoncer le changement.
        """
        if new_index == self._current_index:
            # Aucun changement de mode nécessaire
            return

        if not (0 <= new_index < len(self._modes)):
            # Index invalide : on ignore silencieusement
            return

        # On coupe les annonces en attente (évite les "queues" TTS
        # d’anciens modes si l’utilisateur tourne rapidement le sélecteur)
        self._speaker.clear_queue()

        # 1) Quitter l'ancien mode
        self._current_mode.on_exit()

        # 2) Mettre à jour l'index et le mode courant
        self._current_index = new_index
        self._current_mode = self._modes[self._current_index]

        # 3) Hook d'entrée sur le nouveau mode
        self._current_mode.on_enter()

        # 4) Annonce vocale du nouveau mode
        self._announce_current_mode()

    def handle_short_press(self) -> None:
        """
        À appeler lorsqu'un **appui court** est détecté sur le bouton poussoir.

        Cette méthode est typiquement appelée depuis `RotarySelector`
        lorsque la durée de l’appui est inférieure au seuil
        `long_press_threshold`.

        Elle délègue simplement au mode actif :
        `current_mode.on_short_press()`.
        """
        self._current_mode.on_short_press()

    def handle_long_press(self) -> None:
        """
        À appeler lorsqu'un **appui long** est détecté sur le bouton poussoir.

        Cette méthode est typiquement appelée depuis `RotarySelector`
        lorsque la durée de l’appui dépasse `long_press_threshold`.

        Elle délègue simplement au mode actif :
        `current_mode.on_long_press()`.
        """
        self._current_mode.on_long_press()

    def handle_double_press(self) -> None:
        """
        À appeler lorsqu'un **double appui court** est détecté sur le bouton.

        Cette méthode est appelée par la logique matérielle si elle
        détecte deux appuis courts rapprochés (double clic).

        Elle délègue simplement au mode actif :
        `current_mode.on_double_press()`.

        Exemple d’usage actuel :
        - dans le `ModeMultimetre`, un double appui active ou désactive
          la **lecture automatique** des mesures toutes les X secondes.
        """
        self._current_mode.on_double_press()
