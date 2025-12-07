# hardware/devices/owon_multimeter.py
"""
Driver pour le multimètre OWON 16.

- Utilise BleClient (transport BLE générique) pour la communication.
- Décode les trames de 6 octets spécifiques au protocole OWON.
- Expose une API simple pour les modes :
    * start() / stop()
    * is_connected
    * get_last_measure()

Ce module ne fait pas de synthèse vocale directement.
Les messages vocaux sont gérés dans le Mode via un callback on_status(text).
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from hardware.transports.ble_client import BleClient


# ===========================
#   Décodage des trames OWON
# ===========================

OWON_FUNCTION = {
    "MILLI_VOLT_DC": 7683,
    "MILLI_VOLT_AC": 7691,
    "VOLT_DC": 7684,
    "VOLT_AC": 7692,
    "DIODE_TEST": 7764,
    "MICRO_AMPERE_DC": 7698,
    "MILLI_AMPERE_AC": 7699,
    "MICRO_AMPERE_AC": 7706,
    "MILLI_AMPERE_DC": 7707,
    "AMPERE_DC": 7700,
    "AMPERE_AC": 7708,
    "OHM_NORMAL": 7716,
    "CONTINUITY_TEST": 7772,
    "KILO_OHM": 7717,
    "MEGA_OHM": 7718,
    "NANO_FARAD": 7721,
    "MICRO_FARAD": 7722,
    "MILLI_FARAD": 7723,
    "FARAD": 7724,
    "HERTZ": 7732,
    "PERCENTAGE": 7740,
    "CELSIUS": 7748,
    "FAHRENHEIT": 7756,
    "NEAR_FIELD": 7788,
}


@dataclass
class OwonMultimeterData:
    """
    Représente une trame décodée du multimètre OWON 16 (6 octets).
    """

    raw_data: List[int]
    decimal_places: int
    overflow: int
    unit: int
    unit_name: str
    data_hold_mode: int
    relative_mode: int
    auto_ranging: int
    low_battery: int
    value: float
    sign: int

    @classmethod
    def from_raw(cls, raw_data: List[int]) -> "OwonMultimeterData":
        if len(raw_data) != 6:
            raise ValueError(f"Expected 6 bytes of data, got {len(raw_data)}")

        unit_and_decimal = (raw_data[1] << 8) | raw_data[0]
        flags = raw_data[2]
        value_and_sign = (raw_data[5] << 8) | raw_data[4]

        decimal_places = unit_and_decimal & 0b11
        overflow = (unit_and_decimal >> 2) & 0b1
        unit = unit_and_decimal >> 3  # 13 bits

        unit_name = cls._get_unit_from_value(unit)

        data_hold_mode = flags & 0b1
        relative_mode = (flags >> 1) & 0b1
        auto_ranging = (flags >> 2) & 0b1
        low_battery = (flags >> 3) & 0b1

        raw_value = value_and_sign & 0b11111111111111
        sign = (value_and_sign >> 15) & 0b1

        if sign:
            raw_value = -raw_value

        scale_factor = 10 ** decimal_places
        value = raw_value / scale_factor

        return cls(
            raw_data=list(raw_data),
            decimal_places=decimal_places,
            overflow=overflow,
            unit=unit,
            unit_name=unit_name,
            data_hold_mode=data_hold_mode,
            relative_mode=relative_mode,
            auto_ranging=auto_ranging,
            low_battery=low_battery,
            value=value,
            sign=sign,
        )

    @staticmethod
    def _get_unit_from_value(code: int) -> str:
        for key, val in OWON_FUNCTION.items():
            if val == code:
                return key.replace("_", " ")
        return "UNKNOWN"


# ===========================
#    Driver multimètre OWON
# ===========================


class OwonMultimeterDriver:
    """
    Driver haut niveau pour le multimètre OWON 16.

    - Utilise BleClient comme transport BLE.
    - Convertit les événements génériques du BLE en messages spécifiques multimètre.
    - Fournit une méthode get_last_measure() pour les Modes.
    """

    def __init__(
        self,
        *,
        on_status: Optional[Callable[[str], None]] = None,
        on_new_measure: Optional[Callable[[OwonMultimeterData], None]] = None,
        retry_delay: float = 15.0,
    ) -> None:
        """
        Paramètres
        ----------
        on_status : Callable[[str], None]
            Callback pour annoncer des messages utilisateur (via Speaker).
        on_new_measure : Callable[[OwonMultimeterData], None]
            Callback appelé à chaque nouvelle mesure décodée.
        retry_delay : float
            Délai entre deux tentatives lorsque le multimètre n'est pas trouvé.
        """
        self._on_status = on_status
        self._on_new_measure = on_new_measure
        self._retry_delay = retry_delay

        # Dernière mesure décodée
        self._last_data: Optional[OwonMultimeterData] = None

        # Transport BLE générique
        self._ble = BleClient(
            name_filter="BDM",
            characteristic_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
            on_status=self._handle_ble_status,
            on_packet=self._handle_ble_packet,
            retry_delay=self._retry_delay,
        )

    # ----------- API publique -----------

    def start(self) -> None:
        """Démarre la recherche / connexion au multimètre OWON."""
        self._ble.start()

    def stop(self) -> None:
        """Arrête la surveillance du multimètre."""
        self._ble.stop()

    @property
    def is_connected(self) -> bool:
        return self._ble.is_connected

    def get_last_measure(self) -> Dict[str, Optional[object]]:
        """
        Retourne la dernière mesure sous forme de dict simple.

        Clés :
            - value : float ou None
            - unit_name : str ou None
            - overflow : bool ou None
            - auto_ranging : bool ou None
            - data_hold_mode : bool ou None
            - relative_mode : bool ou None
        """
        if self._last_data is None:
            return {
                "value": None,
                "unit_name": None,
                "overflow": None,
                "auto_ranging": None,
                "data_hold_mode": None,
                "relative_mode": None,
            }

        d = self._last_data
        return {
            "value": d.value,
            "unit_name": d.unit_name,
            "overflow": bool(d.overflow),
            "auto_ranging": bool(d.auto_ranging),
            "data_hold_mode": bool(d.data_hold_mode),
            "relative_mode": bool(d.relative_mode),
        }

    # ----------- Callbacks internes -----------

    def _handle_ble_status(self, event: str) -> None:
        """
        Mappe les événements génériques BLE en phrases spécifiques au multimètre OWON.
        """
        if not self._on_status:
            return

        text: Optional[str] = None

        if event == "search_start":
            text = "Recherche du multimètre en cours."
        elif event == "not_found":
            text = (
                f"Multimètre non trouvé. Assurez-vous qu'il est allumé "
                f"et que le Bluetooth est activé. Nouvelle tentative dans "
                f"{int(self._retry_delay)} secondes."
            )
        elif event == "found":
            text = "Multimètre détecté. Connexion en cours."
        elif event == "connecting":
            #text = "Connexion au multimètre en cours."
            text = None
        elif event == "connected":
            text = "Multimètre connecté. Vous pouvez effectuer vos mesures."
        elif event == "disconnected":
            text = "Connexion perdue avec le multimètre."
        elif event in ("error", "connect_error"):
            text = (
                "Erreur de communication avec le multimètre. "
                "Nouvelle tentative de connexion."
            )
        elif event == "stopped":
            text = None

        if text:
            try:
                self._on_status(text)
            except Exception as e:
                print(f"[OWON] Erreur dans on_status callback : {e}")

    def _handle_ble_packet(self, data: bytes) -> None:
        """
        Reçoit les données brutes depuis BleClient et les décode.
        """
        try:
            raw_list = list(data)
            decoded = OwonMultimeterData.from_raw(raw_list)
            self._last_data = decoded

            if self._on_new_measure:
                self._on_new_measure(decoded)

        except Exception as e:
            print(f"[OWON] Erreur de décodage trame : {e}")
