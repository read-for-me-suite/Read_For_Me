# /hardware/transports/ble_client.py
"""
hardware.transports.ble_client
==============================

Client BLE générique basé sur **bleak**, utilisé comme couche de transport.

Rôle du module
--------------
Ce module fournit un petit **service BLE réutilisable** qui :

- scanne l’environnement pour trouver un périphérique BLE cible,
- se connecte à ce périphérique,
- s’abonne à une **caractéristique** pour recevoir des notifications,
- gère les **reconnexions automatiques** en cas de perte de connexion
  ou d’erreur,
- expose deux callbacks indépendants de la logique métier :
    * `on_status(event: str)`  :
        - informe l’appelant de l’état du client (recherche, trouvé,
          connecté, déconnecté, erreurs, etc.) ;
    * `on_packet(data: bytes)` :
        - transmet les **trames brutes** reçues sur la caractéristique.

Important
---------
Ce client **ne connaît pas** la notion de "multimètre", "capteur X", etc.

- Il ne fait que gérer le **transport BLE** (scan, connexion, notifications).
- La logique métier (décodage des trames, phrases vocales, etc.)
  est déportée dans des drivers plus haut niveau (ex : `OwonMultimeterDriver`).

Il est donc possible de réutiliser cette classe pour **n’importe quel
périphérique BLE**, à condition de fournir :
- un filtre de nom ou d’adresse,
- l’UUID de la caractéristique à écouter,
- des callbacks adaptés.
"""

import asyncio
import threading
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner, BLEDevice


class BleClient:
    """
    Client BLE générique avec boucle de reconnexion automatique.

    Ce composant tourne dans un **thread dédié** pour ne pas bloquer
    le thread principal de l’application. La logique interne utilise
    `asyncio` (scan / connexion / notifications), mais l’API publique
    (`start()`, `stop()`, propriétés) reste **synchrone** et simple à utiliser.

    Paramètres
    ----------
    name_filter : Optional[str]
        Nom BLE à rechercher (exact, insensible à la casse).
        Exemple : `"BDM"` pour le multimètre OWON 16.
    address_filter : Optional[str]
        Adresse MAC BLE à rechercher (si fournie, elle est prioritaire
        sur `name_filter`).
    characteristic_uuid : str
        UUID de la caractéristique sur laquelle on reçoit les notifications.
        Exemple : `"0000fff4-0000-1000-8000-00805f9b34fb"`.
    on_status : Optional[Callable[[str], None]]
        Callback pour les événements d'état. Les valeurs possibles sont :
        - `"search_start"`  : début d’une phase de recherche.
        - `"not_found"`     : aucun device cible trouvé pour cette tentative.
        - `"found"`         : device cible détecté (avant connexion).
        - `"connecting"`    : tentative de connexion en cours.
        - `"connected"`     : connexion établie.
        - `"disconnected"`  : connexion perdue alors que le client tournait.
        - `"error"`         : erreur générique (scan / boucle principale).
        - `"connect_error"` : erreur lors de la connexion ou de l’écoute.
        - `"stopped"`       : la boucle principale s’est arrêtée (après stop()).
    on_packet : Optional[Callable[[bytes], None]]
        Callback appelé à chaque paquet reçu sur la caractéristique.
        Le paramètre est la trame brute `bytes` (6 octets pour l’OWON, par ex.).
    scan_timeout : float
        Durée (en secondes) d’une phase de scan BLE (`BleakScanner.discover`).
    retry_delay : float
        Délai (en secondes) entre deux tentatives de scan lorsqu'aucun device
        n'a été trouvé.
    reconnect_delay : float
        Délai (en secondes) avant de retenter la connexion après une erreur.
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
        listen_poll_interval_sec: float = 0.5,
    ) -> None:
        # Filtres d’identification de l’appareil cible
        self._name_filter = name_filter.upper() if name_filter else None
        self._address_filter = address_filter.upper() if address_filter else None
        self._characteristic_uuid = characteristic_uuid

        # Callbacks "haut niveau" vers le reste du système
        self._on_status = on_status
        self._on_packet = on_packet

        # Paramètres temporels
        self._scan_timeout = scan_timeout
        self._retry_delay = retry_delay
        self._reconnect_delay = reconnect_delay
        self._listen_poll_interval_sec = listen_poll_interval_sec

        # État interne du client
        self._running: bool = False          # boucle principale active ou non
        self._thread: Optional[threading.Thread] = None
        self._client: Optional[BleakClient] = None
        self._connected: bool = False        # vue simplifiée de l’état de connexion

    # ---------------- Propriétés publiques ----------------

    @property
    def is_running(self) -> bool:
        """
        Indique si la boucle de monitoring BLE est actuellement active.

        Returns
        -------
        bool
            `True` si le thread BLE est démarré (`start()` appelé et non stoppé),
            `False` sinon.
        """
        return self._running

    @property
    def is_connected(self) -> bool:
        """
        Indique si le client est **actuellement connecté** à un périphérique BLE.

        Returns
        -------
        bool
            `True` si une connexion est active et que les notifications
            sont en cours, `False` sinon.
        """
        return self._connected

    # ---------------- Démarrage / arrêt ----------------

    def start(self) -> None:
        """
        Démarre la boucle de monitoring dans un **thread séparé**.

        Comportement
        ------------
        - Si le client est déjà en cours d’exécution (`is_running == True`),
          la méthode ne fait rien (idempotent).
        - Sinon :
            * crée un nouveau thread (`BleClientThread`),
            * lance `_run_asyncio_loop()` dans ce thread,
            * active la reconnexion automatique tant que `stop()` n’est pas appelé.
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
        Demande l'arrêt de la boucle de monitoring BLE.

        Effets
        ------
        - Met `_running` à `False` : la boucle principale (`_main_loop`) va
          se terminer proprement à la prochaine itération.
        - À la fin, un événement `"stopped"` sera émis via `on_status`, et
          `is_connected` passera à `False`.
        """
        self._running = False
        if (
            self._thread is not None
            and self._thread.is_alive()
            and threading.current_thread() is not self._thread
        ):
            self._thread.join(timeout=self._scan_timeout + self._reconnect_delay + 1.0)

    def _run_asyncio_loop(self) -> None:
        """
        Point d'entrée du thread BLE : lance la boucle asyncio.

        Cette méthode encapsule l’appel à `asyncio.run(self._main_loop())`
        et gère les exceptions de haut niveau pour éviter de crasher
        silencieusement le thread.
        """
        try:
            asyncio.run(self._main_loop())
        except Exception as e:
            print(f"[BLE] Erreur dans la boucle asyncio principale : {e}")
            self._connected = False

    # ---------------- Boucle principale ----------------

    async def _main_loop(self) -> None:
        """
        Boucle principale : **recherche**, **connexion**, **écoute**, **reconnexion**.

        Schéma global
        -------------
        Tant que `_running` est `True` :

        1. Émission de l’événement `"search_start"`.
        2. Appel de `_wait_for_device()` :
            - scanne l’environnement BLE,
            - cherche un device correspondant aux filtres name/address.
        3. Si trouvé :
            - appel de `_connect_and_listen(device)` :
                * connexion,
                * start_notify,
                * boucle d’écoute,
                * gestion de la déconnexion.
        4. Si une exception survient :
            - émet `"error"` ou `"connect_error"`,
            - attend `reconnect_delay` secondes avant de retenter.

        À la sortie de la boucle :
        - émet `"stopped"`,
        - réinitialise l’état (`_connected = False`, `_client = None`).
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

        Comportement
        ------------
        - Lance périodiquement `BleakScanner.discover()` avec `scan_timeout`.
        - Pour chaque device découvert :
            * compare le **nom** (`name_filter`) si présent,
            * ou l’**adresse** (`address_filter`) si définie.
        - Si un device cible est trouvé :
            * émet `"found"`,
            * le retourne.
        - Sinon :
            * émet `"not_found"`,
            * attend `retry_delay` secondes,
            * recommence tant que `_running` est `True`.

        Returns
        -------
        Optional[BLEDevice]
            - Un `BLEDevice` si un périphérique correspondant a été trouvé.
            - `None` si `stop()` a été appelé avant la fin de la boucle.
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

        Étapes
        ------
        1. Émet `"connecting"`.
        2. Ouvre un contexte `async with BleakClient(device) as client` :
            - si la connexion réussit :
                * met `_connected = True`,
                * émet `"connected"`,
                * démarre les notifications sur `characteristic_uuid`,
                * boucle tant que :
                    - `_running` est `True` ET
                    - `client.is_connected` est `True`.
            - si `client.is_connected` devient `False` alors que `_running`
              est toujours `True`, émet `"disconnected"`.
        3. En cas d’exception :
            - émet `"connect_error"` si `_running` est toujours `True`,
            - attend `reconnect_delay` secondes avant de rendre la main.
        4. Dans tous les cas (bloc `finally`) :
            - `_connected` est remis à `False`,
            - `_client` est mis à `None`.
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
                    await asyncio.sleep(self._listen_poll_interval_sec)

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

        Paramètres
        ----------
        handle : int
            Identifiant interne de la caractéristique (ignoré ici).
        data : bytearray
            Données brutes reçues. Converties en `bytes` avant d’être
            transmises au callback `on_packet`.

        Remarque
        --------
        - Le décodage de ces données (interprétation métier) est laissé
          au driver applicatif (ex : `OwonMultimeterDriver`).
        """
        if self._on_packet:
            try:
                self._on_packet(bytes(data))
            except Exception as e:
                print(f"[BLE] Erreur dans on_packet callback : {e}")

    # ---------------- Utilitaires ----------------

    def _emit_status(self, event: str) -> None:
        """
        Émet un événement de statut vers le callback `on_status`, si défini.

        Valeurs possibles
        -----------------
        - `"search_start"`
        - `"not_found"`
        - `"found"`
        - `"connecting"`
        - `"connected"`
        - `"disconnected"`
        - `"error"`
        - `"connect_error"`
        - `"stopped"`
        """
        print(f"[BLE][STATUS] {event}")
        if self._on_status:
            try:
                self._on_status(event)
            except Exception as e:
                print(f"[BLE] Erreur dans on_status callback : {e}")
