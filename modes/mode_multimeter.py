# modes/mode_multimetre.py
"""
Mode "Multimètre OWON 16" pour l'assistant.

- Utilise le Speaker central pour toutes les annonces.
- Pilote le driver OWON basé sur le transport BLE générique.
"""

from typing import Optional

from core.mode_base import Mode
from core.speaker import Speaker
from hardware.devices.owon_multimeter import (
    OwonMultimeterDriver,
    OwonMultimeterData,
)


class ModeMultimetre(Mode):
    """
    Mode "Multimètre".

    Comportement UX :

    - on_enter :
        * lance la recherche + connexion BLE en arrière-plan
          (le ModeManager annonce déjà "Mode X : Multimètre").

    - on_exit :
        * arrête proprement le driver OWON.
        * annonce "Arrêt du mode multimètre."

    - on_short_press :
        * annonce la dernière mesure disponible
          (ex: "3.27 VOLT DC").

    - on_long_press :
        * annonce l'état de connexion actuel.
    """

    def __init__(self, speaker: Speaker):
        super().__init__(name="Multimètre")
        self.speaker = speaker

        self._last_data: Optional[OwonMultimeterData] = None

        self._driver = OwonMultimeterDriver(
            on_status=self._on_status_from_driver,
            on_new_measure=self._on_new_measure,
        )

    # ---------- callbacks venant du driver ----------

    def _on_status_from_driver(self, text: str) -> None:
        """Tous les messages d'info du driver passent par la voix centrale."""
        self.speaker.speak(text)

    def _on_new_measure(self, data: OwonMultimeterData) -> None:
        """Mémorise la dernière mesure (sans parler automatiquement)."""
        self._last_data = data

    # ---------- Hooks du Mode ----------

    def on_enter(self) -> None:
        """
        Appelé quand on arrive sur ce mode via le sélecteur rotatif.

        On démarre  le driver.
        """
        self._driver.start()

    def on_exit(self) -> None:
        """Appelé quand on quitte ce mode."""
        self._driver.stop()

    def on_short_press(self) -> None:
        """
        Appui court : annonce la dernière mesure reçue.
        """
        measure = self._driver.get_last_measure()
        value = measure["value"]
        unit_name = measure["unit_name"]

        if value is None or unit_name is None:
            self.speaker.speak("Aucune mesure disponible pour le moment.")
            return

        # TODO plus tard : mapper unit_name -> phrase FR plus naturelle
        message = f"{value} {unit_name}"
        self.speaker.speak(message)

    def on_long_press(self) -> None:
        """
        Appui long : annonce l'état de connexion actuel.
        """
        if self._driver.is_connected:
            self.speaker.speak("Le multimètre est connecté.")
        else:
            # Ici, comme le driver est démarré dès on_enter,
            # si nous ne sommes pas connectés, c'est qu'on est en recherche
            # ou en tentative de connexion.
            self.speaker.speak(
                "Recherche ou connexion au multimètre en cours. "
                "Veuillez patienter ou vérifier qu'il est allumé."
            )
