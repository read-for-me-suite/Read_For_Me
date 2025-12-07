# core/mode_manager.py
from typing import List, Optional

from core.mode_base import Mode
from core.speaker import Speaker


class ModeManager:
    """
    Gère la liste des modes disponibles et le mode actuellement actif.

    - Conserve un index courant
    - Permet de changer de mode (set_index)
    - Propage les appuis bouton au mode courant
    - Annonce vocalement le mode sélectionné
    """

    def __init__(self, modes: List[Mode], speaker: Speaker) -> None:
        if not modes:
            raise ValueError("La liste des modes ne peut pas être vide.")

        self._modes: List[Mode] = modes
        self._speaker: Speaker = speaker

        self._current_index: int = 0
        self._current_mode: Mode = self._modes[self._current_index]

        # On appelle on_enter du premier mode
        self._current_mode.on_enter()
        self._announce_current_mode()

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_mode(self) -> Mode:
        return self._current_mode

    def _announce_current_mode(self) -> None:
        """
        Annonce le nom du mode courant (appelé après un changement de mode).
        """
        message = f"Mode {self._current_index + 1} : {self._current_mode.name}"
        self._speaker.speak(message)

    def set_index(self, new_index: int, direction: Optional[str] = None) -> None:
        """
        Change le mode courant en fonction d'un nouvel index.

        Parameters
        ----------
        new_index : int
            Nouvel index de mode (0 <= index < len(modes))
        direction : Optional[str]
            Sens de rotation du sélecteur (ex: 'sens horaire', 'sens inverse').
            Pour le moment, purement informatif (peut servir pour logs).
        """
        if new_index == self._current_index:
            return  # aucun changement

        if not (0 <= new_index < len(self._modes)):
            # Index invalide, on ignore (sécurité)
            return

        # On annonces en attente
        self._speaker.clear_queue()

        # Quitter l'ancien mode
        self._current_mode.on_exit()

        # Mettre à jour l'index et le mode courant
        self._current_index = new_index
        self._current_mode = self._modes[self._current_index]

        # Hook d'entrée sur le nouveau mode
        self._current_mode.on_enter()

        # Annonce vocale du nouveau mode
        self._announce_current_mode()

    def handle_short_press(self) -> None:
        """
        À appeler lorsqu'un appui court est détecté sur le bouton poussoir.
        """
        self._current_mode.on_short_press()

    def handle_long_press(self) -> None:
        """
        À appeler lorsqu'un appui long est détecté sur le bouton poussoir.
        """
        self._current_mode.on_long_press()
