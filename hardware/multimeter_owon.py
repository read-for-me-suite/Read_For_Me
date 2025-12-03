# hardware/multimeter_owon.py
"""
Driver BLE pour le multimètre OWON 16, adapté à l'architecture de l'assistant.

- Contient :
    * OwonMultimeterData : petite classe de décodage des 6 octets
    * OwonMultimeter : driver BLE asynchrone avec reconnexion automatique

- NE fait PAS de synthèse vocale directement.
  Toute "parole" passe par un callback on_info(text) géré par le Mode.
"""

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from bleak import BleakClient, BleakScanner, BLEDevice


# ===========================
#   Décodage des trames 6B
# ===========================

# Mapping des fonctions du multimètre (13 bits)
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

    Attributs principaux :
        - value : valeur numérique (float)
        - unit_name : unité + mode (ex: 'VOLT DC', 'OHM NORMAL', etc.)
        - overflow, auto_ranging, data_hold_mode, relative_mode, low_battery
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
        """Construit une instance à partir d'une liste de 6 octets."""
        if len(raw_data) != 6:
            raise ValueError(f"Expected 6 bytes of data, got {len(raw_data)}")

        # 2 premiers octets : décimales + code fonction
        unit_and_decimal = (raw_data[1] << 8) | raw_data[0]
        # octet 3 : flags
        flags = raw_data[2]
        # octets 5 et 6 : valeur + signe (little endian)
        value_and_sign = (raw_data[5] << 8) | raw_data[4]

        decimal_places = unit_and_decimal & 0b11
        overflow = (unit_and_decimal >> 2) & 0b1
        unit = unit_and_decimal >> 3  # 13 bits

        unit_name = cls._get_unit_from_value(unit)

        data_hold_mode = flags & 0b1
        relative_mode = (flags >> 1) & 0b1
        auto_ranging = (flags >> 2) & 0b1
        low_battery = (flags >> 3) & 0b1

        raw_value = value_and_sign & 0b11111111111111  # 15 bits
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
        """Renvoie un nom d'unité lisible à partir du code entier."""
        for key, val in OWON_FUNCTION.items():
            if val == code:
                return key.replace("_", " ")
        return "UNKNOWN"


# ===========================
#     Driver BLE OWON
# ===========================


class OwonMultimeter:
    """
    Driver BLE pour le multimètre OWON 16.

    - Lancement / arrêt via start() / stop()
    - Recherche automatique de l'appareil par son nom BLE (model_name)
    - Connexion / reconnexion automatique
    - Callbacks :
        * on_info(text: str) : messages d'état
        * on_measure(data: OwonMultimeterData) : nouvelle mesure
    """

    def __init__(
        self,
        model_name: str = "BDM",
        characteristic_uuid: str = "0000fff4-0000-1000-8000-00805f9b34fb",
        on_info: Optional[Callable[[str], None]] = None,
        on_measure: Optional[Callable[[OwonMultimeterData], None]] = None,
        scan_timeout: float = 4.0,
        retry_delay_not_found: float = 3.0,
        reconnect_delay: float = 2.0,
    ) -> None:
        self.model_name = model_name
        self.characteristic_uuid = characteristic_uuid

        self._on_info = on_info
        self._on_measure = on_measure

        self._scan_timeout = scan_timeout
        self._retry_delay_not_found = retry_delay_not_found
        self._reconnect_delay = reconnect_delay

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._client: Optional[BleakClient] = None
        self._connected: bool = False

        self._last_not_found_announce: float = 0.0
        self._last_data: Optional[OwonMultimeterData] = None

    # ---------- Propriétés publiques ----------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ---------- Démarrage / arrêt ----------

    def start(self) -> None:
        """Lance la boucle de monitoring dans un thread séparé."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_asyncio_loop,
            name="OwonMultimeterThread",
            daemon=True,
        )
        self._thread.start()
        self._info("Recherche du multimètre en cours.")

    def stop(self) -> None:
        """Demande l'arrêt de la boucle de monitoring."""
        self._running = False

    def _run_asyncio_loop(self) -> None:
        try:
            asyncio.run(self._main_loop())
        except Exception as e:
            print(f"[OWON] Erreur boucle asyncio : {e}")
            self._connected = False

    # ---------- Boucle principale ----------

    async def _main_loop(self) -> None:
        while self._running:
            try:
                device = await self._wait_for_device()
                if not self._running or device is None:
                    break
                await self._connect_and_listen(device)
            except Exception as e:
                print(f"[OWON] Erreur dans main_loop : {e}")
                self._connected = False
                if self._running:
                    self._info(
                        "Erreur de communication avec le multimètre. "
                        "Nouvelle tentative de connexion."
                    )
                    await asyncio.sleep(self._reconnect_delay)

        self._info("Arrêt du suivi du multimètre.")
        self._connected = False
        self._client = None

    # ---------- Découverte ----------

    async def _wait_for_device(self) -> Optional[BLEDevice]:
        """Recherche en boucle le multimètre par son nom BLE."""
        while self._running:
            devices = await BleakScanner.discover(timeout=self._scan_timeout)
            for dev in devices:
                name = (dev.name or "").strip().upper()
                if name == self.model_name.upper():
                    self._info("Multimètre détecté. Connexion en cours.")
                    print(f"[OWON] Détecté : {dev.name} @ {dev.address}")
                    return dev

            now = time.time()
            if now - self._last_not_found_announce > self._retry_delay_not_found:
                self._info(
                    "Multimètre non trouvé. "
                    "Assurez-vous qu'il est allumé et que le Bluetooth est activé. "
                    "Nouvelle tentative."
                )
                self._last_not_found_announce = now

            await asyncio.sleep(self._retry_delay_not_found)

        return None

    # ---------- Connexion + notifications ----------

    async def _connect_and_listen(self, device: BLEDevice) -> None:
        try:
            self._info("Connexion au multimètre en cours.")
            async with BleakClient(device) as client:
                self._client = client
                self._connected = True
                self._info("Multimètre connecté. Vous pouvez faire vos mesures.")

                await client.start_notify(
                    self.characteristic_uuid,
                    self._handle_notification,
                )

                while self._running and client.is_connected:
                    await asyncio.sleep(0.5)

                if self._running:
                    self._info("Connexion perdue avec le multimètre.")
        except Exception as e:
            print(f"[OWON] Erreur connexion/écoute : {e}")
            if self._running:
                self._info(
                    "Connexion au multimètre échouée. "
                    "Nouvelle tentative dans quelques secondes."
                )
                await asyncio.sleep(self._reconnect_delay)
        finally:
            self._connected = False
            self._client = None

    def _handle_notification(self, handle: int, data: bytearray) -> None:
        """Décodage de chaque trame reçue (6 octets)."""
        try:
            raw_list = list(data)
            decoded = OwonMultimeterData.from_raw(raw_list)

            self._last_data = decoded

            if self._on_measure:
                self._on_measure(decoded)
        except Exception as e:
            print(f"[OWON] Erreur décodage trame : {e}")

    # ---------- Lecture simplifiée ----------

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

    # ---------- Utilitaire ----------

    def _info(self, text: str) -> None:
        """Envoie un message d'info au callback + log console."""
        print(f"[OWON][INFO] {text}")
        if self._on_info:
            try:
                self._on_info(text)
            except Exception as e:
                print(f"[OWON] Erreur on_info callback : {e}")
