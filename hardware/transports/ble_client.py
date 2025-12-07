# hardware/transports/ble_client.py
"""
Client BLE générique.

Responsabilités :
- Scanner un périphérique BLE par nom ou adresse.
- Gérer la connexion, la déconnexion et la reconnexion automatique.
- Exposer des callbacks :
    * on_status(event: str)  -> notification d'état (searching, found, connected...)
    * on_packet(data: bytes) -> données brutes reçues depuis la caractéristique.

Ce module ne connaît PAS la notion de "multimètre" ou de "Appareil X".
Il ne fait que gérer le transport BLE.
"""

import asyncio
import threading
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner, BLEDevice


class BleClient:
    """
    Client BLE générique avec reconnexion automatique.

    Paramètres
    ----------
    name_filter : Optional[str]
        Nom BLE à rechercher (exact, insensible à la casse).
    address_filter : Optional[str]
        Adresse MAC BLE à rechercher (optionnel, prioritaire sur le nom si fourni).
    characteristic_uuid : str
        UUID de la caractéristique sur laquelle on reçoit les notifications.
    on_status : Optional[Callable[[str], None]]
        Callback pour les événements d'état (search_start, not_found, found, connecting, connected, disconnected, error, stopped).
    on_packet : Optional[Callable[[bytes], None]]
        Callback appelé à chaque paquet reçu (bytes).
    scan_timeout : float
        Durée d'une phase de scan BLE (en secondes).
    retry_delay : float
        Délai entre deux tentatives de scan lorsqu'aucun device n'a été trouvé.
    reconnect_delay : float
        Délai avant de retenter une connexion après une erreur.
    """

    def __init__(
        self,
        *,
        name_filter: Optional[str],
        characteristic_uuid: str,
        address_filter: Optional[str] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_packet: Optional[Callable[[bytes], None]] = None,
        scan_timeout: float = 4.0,
        retry_delay: float = 15.0,
        reconnect_delay: float = 2.0,
    ) -> None:
        self._name_filter = name_filter.upper() if name_filter else None
        self._address_filter = address_filter.upper() if address_filter else None
        self._characteristic_uuid = characteristic_uuid

        self._on_status = on_status
        self._on_packet = on_packet

        self._scan_timeout = scan_timeout
        self._retry_delay = retry_delay
        self._reconnect_delay = reconnect_delay

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._client: Optional[BleakClient] = None
        self._connected: bool = False

    # ---------------- Propriétés publiques ----------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ---------------- Démarrage / arrêt ----------------

    def start(self) -> None:
        """
        Démarre la boucle de monitoring dans un thread séparé.

        S'il est déjà en cours d'exécution, ne fait rien.
        """
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_asyncio_loop,
            name="BleClientThread",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """
        Demande l'arrêt de la boucle de monitoring.
        """
        self._running = False

    def _run_asyncio_loop(self) -> None:
        """
        Point d'entrée du thread, lance la boucle asyncio.
        """
        try:
            asyncio.run(self._main_loop())
        except Exception as e:
            print(f"[BLE] Erreur dans la boucle asyncio principale : {e}")
            self._connected = False

    # ---------------- Boucle principale ----------------

    async def _main_loop(self) -> None:
        """
        Boucle principale : recherche du device, connexion, écoute, reconnexion.
        """
        while self._running:
            # À chaque cycle de recherche, on émet "search_start"
            self._emit_status("search_start")

            try:
                device = await self._wait_for_device()

                # Si on a été stoppé pendant la recherche, on sort proprement
                if not self._running or device is None:
                    break

                # On a trouvé un device -> tentative de connexion + écoute
                await self._connect_and_listen(device)

            except Exception as e:
                print(f"[BLE] Erreur dans main_loop : {e}")
                self._connected = False
                if self._running:
                    self._emit_status("error")
                    await asyncio.sleep(self._reconnect_delay)

        # Fin de boucle
        self._emit_status("stopped")
        self._connected = False
        self._client = None

    # ---------------- Découverte ----------------

    async def _wait_for_device(self) -> Optional[BLEDevice]:
        """
        Recherche en boucle un périphérique BLE correspondant aux filtres.

        Retourne un BLEDevice ou None si la boucle est stoppée.
        """
        while self._running:
            print("[BLE][DEBUG] _wait_for_device: début de boucle")

            try:
                print("[BLE][DEBUG] lancement scan BLE...")
                devices = await BleakScanner.discover(timeout=self._scan_timeout)
                print(f"[BLE][DEBUG] scan terminé, {len(devices)} device(s) trouvés")
            except Exception as e:
                print(f"[BLE] Erreur pendant le scan : {e}")
                self._emit_status("error")
                await asyncio.sleep(self._retry_delay)
                continue

            # Si on a reçu un stop() pendant le scan, on sort proprement
            if not self._running:
                print("[BLE][DEBUG] stop demandé après le scan, on sort sans not_found")
                return None

            target: Optional[BLEDevice] = None

            for dev in devices:
                name = (dev.name or "").strip().upper()
                addr = (dev.address or "").strip().upper()
                print(f"[BLE][DEBUG] device vu : name='{name}', addr='{addr}'")

                if self._address_filter and addr == self._address_filter:
                    target = dev
                    break

                if self._name_filter and name == self._name_filter:
                    target = dev
                    break

            if target:
                print(f"[BLE] Périphérique détecté : {target.name} @ {target.address}")
                self._emit_status("found")
                return target

            # Juste avant d'émettre not_found, on re-vérifie qu'on est toujours actif
            if not self._running:
                print("[BLE][DEBUG] stop demandé avant not_found, on sort sans not_found")
                return None

            # Non trouvé pour cette tentative -> on le dit, puis on attend
            print("[BLE][DEBUG] aucun périphérique cible trouvé, émettre not_found")
            self._emit_status("not_found")
            await asyncio.sleep(self._retry_delay)

        print("[BLE][DEBUG] _wait_for_device: sortie de boucle (stop demandé)")
        return None

    # ---------------- Connexion + notifications ----------------

    async def _connect_and_listen(self, device: BLEDevice) -> None:
        """
        Établit la connexion BLE et écoute les notifications jusqu'à déconnexion ou arrêt.
        """
        try:
            self._emit_status("connecting")
            async with BleakClient(device) as client:
                self._client = client
                self._connected = True
                self._emit_status("connected")

                await client.start_notify(
                    self._characteristic_uuid,
                    self._handle_notification,
                )

                while self._running and client.is_connected:
                    await asyncio.sleep(0.5)

                if self._running:
                    self._emit_status("disconnected")

        except Exception as e:
            print(f"[BLE] Erreur connexion/écoute : {e}")
            if self._running:
                self._emit_status("connect_error")
                await asyncio.sleep(self._reconnect_delay)
        finally:
            self._connected = False
            self._client = None

    # ---------------- Gestion des notifications ----------------

    def _handle_notification(self, handle: int, data: bytearray) -> None:
        """
        Callback interne appelée à chaque trame reçue sur la caractéristique BLE.
        Transmet les données brutes au callback on_packet.
        """
        if self._on_packet:
            try:
                self._on_packet(bytes(data))
            except Exception as e:
                print(f"[BLE] Erreur dans on_packet callback : {e}")

    # ---------------- Utilitaires ----------------

    def _emit_status(self, event: str) -> None:
        """
        Émet un événement de statut :
        - search_start
        - not_found
        - found
        - connecting
        - connected
        - disconnected
        - error
        - connect_error
        - stopped
        """
        print(f"[BLE][STATUS] {event}")
        if self._on_status:
            try:
                self._on_status(event)
            except Exception as e:
                print(f"[BLE] Erreur dans on_status callback : {e}")
