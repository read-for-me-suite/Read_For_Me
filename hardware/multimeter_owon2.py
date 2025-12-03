# hardware/multimeter_owon.py

import asyncio
import threading
from datetime import datetime
from typing import Optional, List, Dict, Callable

from bleak import BleakClient, BleakScanner, BLEDevice

# Table de correspondance code d'unité -> nom lisible
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


class OwonMeasurement:
    """
    Représente une mesure décodée du multimètre OWON 16.

    Trame brute : bloc de 6 octets (little-endian).
    """

    def __init__(self, raw_data: List[int]) -> None:
        if len(raw_data) != 6:
            raise ValueError(f"Expected 6 bytes of data, got {len(raw_data)}")

        self.raw_data = list(raw_data)
        self._decode()

    def _decode(self) -> None:
        """
        Décodage interne de la trame brute en champs de données.

        - Octets 0-1 : décimales + overflow + code d'unité
        - Octet  2   : flags (hold, relatif, autorange, batterie)
        - Octet  3   : réservé
        - Octets 4-5 : valeur + signe
        """
        unit_and_decimal = (self.raw_data[1] << 8) | self.raw_data[0]
        flags = self.raw_data[2]
        value_and_sign = (self.raw_data[5] << 8) | self.raw_data[4]

        # Bits 0-1 : nombre de décimales
        self.decimal_places = unit_and_decimal & 0b11
        # Bit 2 : overflow
        self.overflow = (unit_and_decimal >> 2) & 0b1
        # Bits 3-15 : code d'unité (13 bits)
        self.unit_code = unit_and_decimal >> 3

        self.unit_name = self._unit_name_from_code(self.unit_code)

        # Flags dans l'octet 2
        self.data_hold_mode = flags & 0b1          # bit 0
        self.relative_mode = (flags >> 1) & 0b1    # bit 1
        self.auto_ranging = (flags >> 2) & 0b1     # bit 2
        self.low_battery = (flags >> 3) & 0b1      # bit 3

        # Valeur brute + signe (14 bits + 1 bit signe)
        raw_value = value_and_sign & 0b11111111111111  # 14 bits
        self.sign = (value_and_sign >> 15) & 0b1       # bit 15

        if self.sign:
            raw_value = -raw_value

        scale_factor = pow(10, self.decimal_places)
        self.value = raw_value / scale_factor

    @staticmethod
    def _unit_name_from_code(code: int) -> str:
        """Retourne un nom d'unité lisible à partir du code entier."""
        for key, val in OWON_FUNCTION.items():
            if val == code:
                return key.replace("_", " ")
        return "unknown"

    def __repr__(self) -> str:
        return (
            f"OwonMeasurement("
            f"value={self.value}, unit='{self.unit_name}', "
            f"decimals={self.decimal_places}, overflow={self.overflow}, "
            f"hold={self.data_hold_mode}, relative={self.relative_mode}, "
            f"autorange={self.auto_ranging}, low_batt={self.low_battery}"
            f")"
        )


MODEL_NAME = "BDM"  # Nom BLE du multimètre
CHARACTERISTIC_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"


class OwonBleMultimeter:
    """
    Driver BLE pour le multimètre OWON 16.

    - Thread unique qui tourne en permanence une fois démarré.
    - last_measure contient la dernière mesure décodée.
    - get_measure() retourne une vue simple (value/unit).

    Callbacks optionnels (pour le Mode) :
        - on_status(event: str, info: dict)
          events possibles :
              "search_start"
              "search_retry"   (info["attempt"] = 1, 2, 3, ...)
              "device_found"
              "connected"
              "disconnected"
              "error"
              "stopped"
    """

    def __init__(self) -> None:
        self.last_measure: Optional[OwonMeasurement] = None
        self.last_raw_data: Optional[List[int]] = None

        self.client: Optional[BleakClient] = None
        self.running: bool = False
        self.connected: bool = False
        self._thread: Optional[threading.Thread] = None

        # Callback statuts (injecté par le Mode)
        self.on_status: Optional[Callable[[str, Dict], None]] = None

    # ========= Interface publique =========

    def start(self) -> None:
        """
        Démarre la surveillance BLE dans un thread séparé.

        IMPORTANT : on l'appelle UNE SEULE FOIS (depuis le constructeur du Mode),
        et ensuite le thread tourne en permanence. On ne l'arrête plus quand
        on change de mode : les annonces sont filtrées côté Mode.
        """
        if self._thread is not None and self._thread.is_alive():
            # Déjà en cours
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_async, daemon=True)
        self._thread.start()
        print("[OWON] Monitor BLE démarré (thread unique).")

    def stop(self) -> None:
        """
        Méthode prévue pour un arrêt global (fin de programme).
        Dans ton appli actuelle, on ne l'utilise pas à chaque changement de mode.
        """
        self.running = False
        print("[OWON] Arrêt demandé pour le monitor BLE.")

    def is_connected(self) -> bool:
        """Retourne True si une connexion BLE active est établie."""
        return self.connected

    def get_measure(self) -> Dict[str, Optional[float]]:
        """
        Retourne la dernière mesure décodée sous forme simple.

        {"value": float|None, "unit": str|None}
        """
        if self.last_measure is None:
            return {"value": None, "unit": None}
        return {
            "value": self.last_measure.value,
            "unit": self.last_measure.unit_name,
        }

    # ========= Boucle interne / asyncio =========

    def _run_async(self) -> None:
        """Lance la boucle asyncio dans ce thread."""
        try:
            asyncio.run(self._main_loop())
        except Exception as e:
            print(f"[OWON] Erreur fatale dans _run_async : {e}")

    async def _main_loop(self) -> None:
        """
        Boucle principale BLE avec auto-reconnexion tant que running == True.
        """
        print("[OWON] _main_loop démarrée.")
        while self.running:
            client: Optional[BleakClient] = None

            try:
                device = await self._wait_for_device()
                if not self.running:
                    break

                print(
                    f"[OWON] Périphérique trouvé : {device.name} @ {device.address}"
                )
                self._emit_status(
                    "device_found",
                    {"name": device.name, "address": device.address},
                )

                # Création du client BLE
                client = BleakClient(device)
                self.client = client

                print("[OWON] Tentative de connexion BLE...")
                # Timeout de connexion explicite
                try:
                    await asyncio.wait_for(client.connect(), timeout=8.0)
                except asyncio.TimeoutError:
                    raise RuntimeError("Timeout de connexion au multimètre.")
                except Exception as e:
                    raise RuntimeError(f"Erreur de connexion BLE: {e}")

                if not client.is_connected:
                    raise RuntimeError("Connexion BLE non établie.")

                self.connected = True
                print(
                    "[OWON] Connecté au multimètre, démarrage des notifications."
                )
                self._emit_status(
                    "connected",
                    {"name": device.name, "address": device.address},
                )

                await client.start_notify(
                    CHARACTERISTIC_UUID,
                    self._handle_notification,
                )

                # Tant que running et connecté, on attend
                while self.running and client.is_connected:
                    await asyncio.sleep(1.0)

                print("[OWON] Fin de session BLE.")

                if self.running and not client.is_connected:
                    # Déconnexion "inattendue"
                    self._emit_status(
                        "disconnected",
                        {"reason": "link_lost"},
                    )

            except Exception as e:
                if not self.running:
                    break
                print(f"[OWON] Erreur BLE : {e}")
                self.connected = False
                self.client = None
                self._emit_status("error", {"message": str(e)})
                # Pause avant de retenter une recherche
                await asyncio.sleep(2.0)

            finally:
                # On essaye de se déconnecter proprement
                if client is not None:
                    try:
                        if client.is_connected:
                            await client.disconnect()
                    except Exception as e2:
                        print(f"[OWON] Erreur lors de la déconnexion : {e2}")

                self.connected = False
                self.client = None

        print("[OWON] _main_loop terminée.")
        self.connected = False
        self.client = None
        self._emit_status("stopped", {})

    async def _wait_for_device(self) -> BLEDevice:
        """
        Recherche le multimètre OWON 16 par nom BLE.

        Boucle tant que self.running == True jusqu'à trouver le device.
        """
        print("[OWON] Recherche du multimètre OWON 16 (BDM)...")
        self._emit_status("search_start", {})

        attempt = 0

        while self.running:
            print("[OWON] Scan BLE en cours...")
            devices = await BleakScanner.discover(timeout=4.0)
            print(f"[OWON] Scan terminé, {len(devices)} périphériques trouvés.")

            for dev in devices:
                name = (dev.name or "").strip().upper()
                if name == MODEL_NAME:
                    print(f"[OWON] ✅ OWON détecté : {dev.name} @ {dev.address}")
                    return dev

            attempt += 1
            print("[OWON] Aucun OWON trouvé, nouvelle tentative dans 16s...")
            self._emit_status("search_retry", {"attempt": attempt})

            # Pause avant de recommencer un scan
            await asyncio.sleep(16.0)

        # Sortie si running passe à False pendant la recherche
        raise RuntimeError("Recherche interrompue (running=False).")

    # ========= Callback de notification =========

    def _handle_notification(self, handle: int, data: bytearray) -> None:
        """
        Callback appelée pour chaque trame BLE reçue.
        On décode et on mémorise la mesure.
        """
        try:
            raw = list(data)
            measurement = OwonMeasurement(raw)
            self.last_measure = measurement

            # Debug simple
            now = datetime.now().isoformat()
            print(
                f"[{now}] Mesure OWON : {measurement.value} {measurement.unit_name}"
            )

        except Exception as e:
            print(f"[OWON] Erreur de décodage : {e}")
            self._emit_status("error", {"message": f"decode: {e}"})

    # ========= Helpers internes =========

    def _emit_status(self, event: str, info: Dict) -> None:
        """Appelle le callback de statut si défini."""
        if not self.on_status:
            return
        try:
            self.on_status(event, info)
        except Exception as e:
            # Ne jamais faire planter la couche hardware à cause du callback
            print(f"[OWON] Erreur dans callback on_status : {e}")
