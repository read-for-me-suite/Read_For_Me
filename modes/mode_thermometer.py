"""
modes/mode_thermometer.py
=========================

Mode "Thermomètre WiFi" pour l'assistant.

Rôle :
------
- Interface entre l'utilisateur (boutons, sélecteur) et le Driver Thermomètre.
- Ce mode suppose que la Pi et l'ESP32 sont sur le même réseau WiFi existant.

Comportement UX :
-----------------
- on_enter : Démarrage du driver (recherche du capteur sur le réseau).
- on_exit : Arrêt du driver.
- Appui court : Lit la température ("Il fait 22 virgule 5 degrés").
- Appui long : Annonce l'état ("Le thermomètre est connecté au réseau local").
"""

import time
from typing import Optional

from core.mode_base import Mode
from core.speaker import Speaker
from hardware.devices.esp32_thermometer import ThermometerDriver, ThermometerData

class ModeThermometre(Mode):
    """
    Mode Thermomètre connecté via le réseau local.
    """

    def __init__(self, speaker: Speaker):
        super().__init__(name="Thermomètre")
        self.speaker = speaker
        
        # Stockage de la dernière mesure valide
        self._last_data: Optional[ThermometerData] = None

        # Le driver gère la communication avec l'ESP32 via mDNS (thermo.local)
        self._driver = ThermometerDriver(
            on_status=self._on_status_from_driver,
            on_new_measure=self._on_new_measure
        )

    # ---------- Callbacks Driver ----------

    def _on_status_from_driver(self, text: str) -> None:
        """Relais des messages de statut (ex: 'Thermomètre connecté') vers le Speaker."""
        self.speaker.speak(text)

    def _on_new_measure(self, data: ThermometerData) -> None:
        """
        Appelé à chaque nouvelle mesure reçue (Polling).
        On stocke juste la valeur pour l'instant T.
        """
        self._last_data = data

    def _format_value_for_speech(self, value: float) -> str:
        """Formate 22.5 en '22 virgule 5'."""
        if value is None: return ""
        txt = str(value).replace('.', ',')
        if value < 0:
            return f"moins {txt.replace('-', '')}"
        return txt

    # ---------- Hooks du Mode (Cycle de vie) ----------

    def on_enter(self) -> None:
        """
        Arrivée sur le mode Thermomètre :
        On lance le driver qui va chercher l'ESP32 sur le réseau local.
        """
        print("Entrée dans le mode Thermomètre (Réseau Local)")
        self._last_data = None
        self._driver.start()

    def on_exit(self) -> None:
        """
        Sortie du mode :
        On arrête le driver pour économiser des ressources réseau.
        """
        print("Sortie du mode Thermomètre")
        self._driver.stop()

    # ---------- Gestion Boutons ----------

    def on_short_press(self) -> None:
        """
        Appui court : Annonce la température.
        """
       
        measure = self._driver.get_last_measure()
        val = measure["value"]
        unit = measure.get("unit_name", "degrés") # Valeur par défaut si manquant

        if val is None:
            if self._driver.is_connected:
                self.speaker.speak("Attente de la première mesure...")
            else:
                self.speaker.speak("Le thermomètre n'est pas connecté.")
            return

        val_text = self._format_value_for_speech(val)
        message = f"Il fait {val_text} {unit}."
        self.speaker.speak(message)

    def on_long_press(self) -> None:
        """
        Appui long : Annonce l'état de connexion.
        """
        if self._driver.is_connected:
            self.speaker.speak("Le thermomètre est bien connecté au réseau local.")
        else:
            self.speaker.speak("Recherche du thermomètre en cours. Vérifiez qu'il est sur le même Wi-Fi.")
