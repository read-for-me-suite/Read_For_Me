"""
hardware.devices.esp32_thermometer
==================================

Driver pour le thermomètre connecté ESP32.

Vue d'ensemble
==============
Ce module fournit :
1. `ThermometerData` : structure de donnée propre (valeur float).
2. `ThermometerDriver` : pilote haut niveau utilisant `WifiClient`.

Il est conçu pour être utilisé par `ModeThermometre`.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Dict
import time

from hardware.transports.wifi_client import WifiClient

# URL par défaut (mDNS)
DEFAULT_URL = "http://thermo.local/api"

@dataclass
class ThermometerData:
    """
    Représente une mesure de température.
    """
    value: float
    unit: str = "Celsius"
    timestamp: float = 0.0

    @classmethod
    def from_raw(cls, raw_str: str) -> "ThermometerData":
        """Décode la chaîne brute '22.5'."""
        try:
            val = float(raw_str)
            return cls(value=val, timestamp=time.time())
        except ValueError:
            raise ValueError(f"Format invalide : {raw_str}")


class ThermometerDriver:
    """
    Driver haut niveau pour le thermomètre WiFi.
    
    Responsabilités :
    - Piloter le transport WiFi.
    - Décoder les données brutes.
    - Fournir des messages de statut en français pour le Speaker.
    """

    def __init__(
        self,
        *,
        target_url: str = DEFAULT_URL,
        on_status: Optional[Callable[[str], None]] = None,
        on_new_measure: Optional[Callable[[ThermometerData], None]] = None,
    ) -> None:
        
        self._on_status = on_status
        self._on_new_measure = on_new_measure
        
        self._last_data: Optional[ThermometerData] = None

        # Transport WiFi
        self._wifi = WifiClient(
            target_url=target_url,
            on_status=self._handle_wifi_status,
            on_data=self._handle_wifi_data,
            poll_interval=2.0
        )

    # ----------- API Publique -----------

    def start(self) -> None:
        """Démarre la surveillance."""
        self._wifi.start()

    def stop(self) -> None:
        """Arrête la surveillance."""
        self._wifi.stop()

    @property
    def is_connected(self) -> bool:
        """Indique si le capteur est joignable."""
        return self._wifi.is_connected

    def get_last_measure(self) -> Dict[str, Optional[float]]:
        """
        Retourne la dernière mesure sous forme de dict simple.
        Format compatible pour une consommation facile par le Mode.
        """
        if self._last_data is None:
            return {"value": None}
        
        return {"value": self._last_data.value}

    # ----------- Callbacks Internes -----------

    def _handle_wifi_status(self, event: str) -> None:
        """Traduit les événements techniques en phrases françaises."""
        if not self._on_status:
            return

        text: Optional[str] = None

        if event == "connecting":
            text = "Recherche du thermomètre en cours."
        elif event == "connected":
            text = "Thermomètre connecté. Prêt."
        elif event == "disconnected":
            text = "Connexion perdue avec le thermomètre."
        elif event == "http_error":
            text = "Erreur de communication avec le capteur."

        if text:
            self._on_status(text)

    def _handle_wifi_data(self, raw_data: str) -> None:
        """Décode la donnée reçue."""
        try:
            decoded = ThermometerData.from_raw(raw_data)
            self._last_data = decoded
            
            if self._on_new_measure:
                self._on_new_measure(decoded)
        except Exception as e:
            print(f"[THERMO] Erreur décodage : {e}")
