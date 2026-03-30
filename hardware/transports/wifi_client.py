# /hardware/transports/wifi_client.py
"""
hardware.transports.wifi_client
===============================

Client HTTP générique pour le polling de capteurs sur réseau local.
Architecture inspirée de `ble_client.py`.

Rôle du module
--------------
Ce module fournit un **service de transport HTTP réutilisable** qui :

- Tente de contacter une API HTTP cible (URL) à intervalles réguliers (polling).
- Détecte automatiquement la disponibilité du périphérique (connexion/déconnexion).
- Gère les timeouts et erreurs réseaux de manière transparente.
- Expose deux callbacks indépendants de la logique métier :
    * `on_status(event: str)` : informe de l'état (connecting, connected, error...).
    * `on_data(data: str)`    : transmet le corps de la réponse HTTP brute.

Important
---------
Ce client ne gère **aucun protocole spécifique** au-delà du HTTP standard.
Il ne fait que transporter des chaînes de caractères reçues via HTTP.

Il est réutilisable pour tout capteur exposant une API REST simple,
à condition de fournir l'URL cible.
"""

import threading
import time
import requests
from typing import Callable, Optional


class WifiClient:
    """
    Client de Polling HTTP générique.

    Ce composant tourne dans un **thread dédié** pour ne pas bloquer le thread principal.

    Paramètres
    ----------
    target_url : str
        L'URL complète de l'API à interroger (ex: "http://thermo.local/api").
    on_status : Optional[Callable[[str], None]]
        Callback pour les événements d'état. Valeurs possibles :
        - "connecting"     : tentative de contact avec l'URL (début ou reconnexion).
        - "connected"      : périphérique joint avec succès (HTTP 200).
        - "disconnected"   : perte de liaison (timeout ou erreur réseau).
        - "http_error"     : le périphérique répond mais avec une erreur (404, 500...).
        - "stopped"        : arrêt volontaire du client.
    on_data : Optional[Callable[[str], None]]
        Callback appelé à chaque réponse HTTP valide.
        Le paramètre est le texte brut (str) de la réponse.
    poll_interval : float
        Temps (en secondes) entre deux requêtes HTTP.
    request_timeout : float
        Temps (en secondes) avant de considérer le périphérique comme absent.
    """

    def __init__(
        self,
        *,
        target_url: str,
        on_status: Optional[Callable[[str], None]] = None,
        on_data: Optional[Callable[[str], None]] = None,
        poll_interval: float = 2.0,
        request_timeout: float = 3.0
    ) -> None:
        
        self._target_url = target_url
        self._poll_interval = poll_interval
        self._request_timeout = request_timeout

        # Callbacks vers le driver supérieur
        self._on_status = on_status
        self._on_data = on_data

        # État interne
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._is_connected: bool = False
        
        # Mémoire pour éviter de spammer les statuts identiques
        self._last_emitted_status: Optional[str] = None

    # ---------------- Propriétés publiques ----------------

    @property
    def is_running(self) -> bool:
        """Indique si la boucle de polling est active."""
        return self._running

    @property
    def is_connected(self) -> bool:
        """Indique si la dernière communication HTTP a réussi."""
        return self._is_connected

    # ---------------- Démarrage / arrêt ----------------

    def start(self) -> None:
        """
        Démarre la boucle de polling dans un thread séparé.
        """
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._main_loop,
            name="WifiClientThread",
            daemon=True,
        )
        self._thread.start()
        print(f"WifiClient démarré. Cible: {self._target_url}")
        print(f"WifiClient démarré. Cible: {self._target_url}")

    def stop(self) -> None:
        """
        Arrête la boucle de polling.
        """
        self._running = False
        # Le thread se terminera à la prochaine itération de la boucle

    # ---------------- Boucle principale ----------------

    def _main_loop(self) -> None:
        """
        Boucle principale : Polling HTTP.
        """
        # Au démarrage, on signale qu'on commence à chercher
        self._emit_status("connecting")

        while self._running:
            try:
                self._poll_target()

            except Exception as e:
                print(f"WifiClient: Exception non gérée dans la boucle : {e}")
                print(f"WifiClient: Exception non gérée dans la boucle : {e}")
                self._handle_disconnection()
            
            # Attente avant la prochaine requête (Polling)
            time.sleep(self._poll_interval)

        # Fin de boucle
        self._emit_status("stopped")
        self._is_connected = False
        self._thread = None

    # ---------------- Logique HTTP ----------------

    def _poll_target(self) -> None:
        """
        Effectue une requête unique et gère la réponse.
        """
        try:
            # Envoi de la requête GET
            response = requests.get(self._target_url, timeout=self._request_timeout)

            if response.status_code == 200:
                data = response.text.strip()
                self._handle_connection_success(data)
            else:
                # Le serveur répond, mais avec une erreur (ex: 500 Internal Error)
                print(f"WifiClient: Erreur HTTP {response.status_code}")
                print(f"WifiClient: Erreur HTTP {response.status_code}")
                self._emit_status("http_error")
                # On considère que la liaison est là, mais que le service bugue
                # On ne met pas forcément is_connected à False si on veut garder le lien "vivant"
                
        except requests.exceptions.RequestException:
            # Timeout, DNS error, Connection refused...
            self._handle_disconnection()

    def _handle_connection_success(self, data: str) -> None:
        """Appelé quand une requête réussit."""
        if not self._is_connected:
            self._is_connected = True
            self._emit_status("connected")
        
        # Transmission de la donnée au driver
        if self._on_data:
            self._on_data(data)

    def _handle_disconnection(self) -> None:
        """Appelé quand une requête échoue."""
        if self._is_connected:
            self._is_connected = False
            self._emit_status("disconnected")
        elif self._last_emitted_status != "connecting":
            # Si on n'était pas connecté, on rappelle qu'on cherche
            self._emit_status("connecting")

    # ---------------- Utilitaires ----------------

    def _emit_status(self, event: str) -> None:
        """
        Émet un événement de statut vers le callback `on_status`.
        Filtre les doublons pour ne pas spammer le driver.
        """
        if event == self._last_emitted_status and event != "http_error":
            return

        self._last_emitted_status = event
        
        if self._on_status:
            try:
                self._on_status(event)
            except Exception as e:
                print(f"WifiClient: Erreur callback on_status : {e}")
