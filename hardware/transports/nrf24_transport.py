# hardware/transports/nrf24_transport.py
"""
hardware.transports.nrf24_transport
===================================

Ce module définit la classe `Nrf24Transport`, responsable de la communication
bas niveau avec le module radio NRF24L01+.

Vue d'ensemble
--------------

Le transport NRF24 agit comme une couche d'abstraction au-dessus du bus SPI :
- Il initialise le matériel radio (CE, CSN, Canal, Débit).
- Il gère la réception des données en arrière-plan via un **thread dédié**.
- Il propage les paquets bruts reçus vers les drivers de périphériques 
  (ex. : pied à coulisse) via un système de callback.

Objectifs du design
-------------------

- **Robustesse** : Utilise des blocs try/except pour éviter le crash de l'application
  si la librairie `pyrf24` est absente ou si le module radio est débranché.
- **Réactivité** : Le thread `Nrf24Worker` écoute en permanence le bus SPI sans 
  bloquer la boucle principale du `ModeManager`.
- **Découplage** : Le transport ne connaît pas le contenu des messages ; il se 
  contente de livrer des octets bruts (`bytes`).

Câblage type (Raspberry Pi 5)
-----------------------------
VCC -> 3.3V | GND -> GND | CE -> GPIO 25 | CSN -> GPIO 8 (CE0)
SCK -> GPIO 11 | MOSI -> GPIO 10 | MISO -> GPIO 9
"""

import threading
import time
import logging
from typing import Optional, Callable, Tuple

# Tentative d'importation sécurisée pour ne pas bloquer le projet 
# si les dépendances NRF24 ne sont pas encore installées sur le système.
try:
    from pyrf24 import RF24, RF24_PA_LOW, RF24_250KBPS
except ImportError:
    RF24 = None


class Nrf24Transport:
    """
    Gère la couche basse radio NRF24L01+ sur bus SPI.

    Rôle
    ----
    Cette classe encapsule la librairie `pyrf24` pour fournir une interface
    de lecture simplifiée et threadée. Elle est conçue pour être utilisée
    par un driver de périphérique (comme le Pied à coulisse).
    """

    def __init__(self, ce_pin: int = 25, csn_pin: int = 0, channel: int = 120, address: bytes = b"00001"):
        """
        Initialise les paramètres du transport radio.

        Paramètres
        ----------
        ce_pin : int
            Broche GPIO pour le signal Chip Enable (défaut : 25).
        csn_pin : int
            Broche pour le signal Chip Select Not (0 pour SPI0 CE0 / GPIO 8).
        channel : int
            Canal radio utilisé (0 à 125). Le pied à coulisse MHK utilise le 120.
        address : bytes
            Adresse unique du tuyau de lecture (pipe), format 5 octets.
        """
        self._ce_pin = ce_pin
        self._csn_pin = csn_pin
        self._channel = channel
        self._address = address
        
        self._radio: Optional[RF24] = None
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._on_packet_callback: Optional[Callable[[bytes], None]] = None

    def start(self, on_packet_callback: Callable[[bytes], None]) -> Tuple[bool, str]:
        """
        Initialise le module radio et démarre le thread d'écoute.

        Paramètres
        ----------
        on_packet_callback : Callable
            Fonction appelée à chaque réception d'un nouveau paquet radio.
            Prend un argument de type `bytes`.

        Returns
        -------
        (bool, str)
            Un tuple contenant le succès (True/False) et un message de statut.
        """
        if RF24 is None:
            return False, "Librairie pyrf24 non installée."
        
        try:
            # 1) Instanciation du module radio sur le bus SPI
            self._radio = RF24(self._ce_pin, self._csn_pin)
            
            # 2) Initialisation physique du module
            if not self._radio.begin():
                return False, "Module NRF24 non détecté physiquement."
            
            # 3) Configuration des paramètres radio MHK (fixes pour ce projet)
            self._radio.setChannel(self._channel)
            self._radio.setDataRate(RF24_250KBPS)  # Bas débit pour une meilleure portée
            self._radio.setPALevel(RF24_PA_LOW)     # Évite les interférences à courte portée
            self._radio.enableDynamicPayloads()    # Autorise les messages de taille variable
            
            # 4) Ouverture du canal de réception
            self._radio.openReadingPipe(1, self._address)
            self._radio.startListening()
            
            # 5) Lancement du thread de surveillance
            self._on_packet_callback = on_packet_callback
            self._running = True
            self._thread = threading.Thread(
                target=self._read_loop, 
                name="Nrf24Worker", 
                daemon=True
            )
            self._thread.start()
            
            return True, "OK"

        except Exception as e:
            return False, f"Erreur d'initialisation SPI : {str(e)}"

    def stop(self) -> None:
        """
        Arrête proprement l'écoute radio et le thread associé.
        """
        self._running = False
        
        if self._thread:
            # On attend la fin du thread (timeout de sécurité)
            self._thread.join(timeout=1.0)
            
        if self._radio:
            self._radio.stopListening()
            # Note : On ne ferme pas explicitement la radio pour permettre
            # un redémarrage rapide sans réinstanciation SPI.

    def _read_loop(self) -> None:
        """
        Boucle principale de réception (exécutée dans un thread dédié).

        Fonctionnement
        --------------
        - Vérifie si des données sont disponibles dans le buffer du NRF24.
        - Si oui, lit la taille dynamique du paquet et récupère les octets.
        - Transmet les octets bruts au driver via le callback enregistré.
        - Observe une pause de 10ms pour ne pas saturer le CPU du Raspberry Pi.
        """
        while self._running:
            if self._radio and self._radio.available():
                # Récupération de la trame
                size = self._radio.getDynamicPayloadSize()
                payload = self._radio.read(size)
                
                # Transmission au driver si un callback est défini
                if self._on_packet_callback:
                    try:
                        self._on_packet_callback(payload)
                    except Exception as e:
                        print(f"[NRF24-Transport] Erreur dans le callback : {e}")
            
            # Petite pause pour libérer du temps processeur
            time.sleep(0.01)
