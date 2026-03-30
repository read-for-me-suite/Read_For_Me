# hardware/devices/caliper.py
"""
Driver pour le pied à coulisse numérique (version NRF24).

Vue d'ensemble
==============

Ce module assure le lien entre le transport radio brut et la logique métier :

1. `CaliperData` (Dataclass)
   -------------------------
   - Structure les données décodées : valeur, unité (mm/pouce) et signe.

2. `CaliperDriver`
   ----------------
   - Initialise le transport `Nrf24Transport`.
   - Décode la structure binaire `MessageStruct` envoyée par l'ATtiny85.
   - Gère les notifications d'état (prêt/erreur) vers le mode actif.

Protocole Binaire (Caliper_TX_24b_ATtiny85)
-------------------------------------------
La trame reçue via NRF24 comporte au minimum 6 octets (Little Endian) :
- Octets 0 à 3 : float (4 octets) -> Valeur numérique brute.
- Octet 4      : bool (1 octet)  -> Unité (0 = mm, 1 = pouce).
- Octet 5      : bool (1 octet)  -> Signe (0 = plus, 1 = moins).
"""

import struct
from dataclasses import dataclass
from typing import Optional, Callable
from hardware.transports.nrf24_transport import Nrf24Transport


@dataclass
class CaliperData:
    """
    Représente une mesure décodée issue du pied à coulisse.
    
    Attributs
    ---------
    value : float
        Valeur numérique de la mesure (ex: 12.45).
    unit_name : str
        Nom de l'unité ("millimètre" ou "pouce").
    is_negative : bool
        True si la mesure est négative, False sinon.
    """
    value: float
    unit_name: str
    is_negative: bool


class CaliperDriver:
    """
    Driver haut niveau pour le pied à coulisse sans fil.

    Ce driver utilise le transport NRF24 pour recevoir des paquets et les 
    transformer en objets `CaliperData` utilisables par l'assistant vocal.
    """

    def __init__(self, on_status: Callable[[str], None], on_new_measure: Callable[[CaliperData], None]):
        """
        Initialise le driver du pied à coulisse.

        Paramètres
        ----------
        on_status : Callable[[str], None]
            Callback pour signaler l'état du matériel (ex: "Pied à coulisse prêt").
        on_new_measure : Callable[[CaliperData], None]
            Callback appelé automatiquement à chaque nouvelle mesure reçue.
        """
        self._on_status = on_status
        self._on_new_measure = on_new_measure
        
        # Instance du transport SPI/Radio
        self._transport = Nrf24Transport()
        
        # Stockage de la dernière mesure valide
        self._last_data: Optional[CaliperData] = None
        
        # État de connexion logique (basé sur l'initialisation SPI)
        self.is_connected = False

    def start(self) -> None:
        """
        Démarre le transport radio et prépare la réception.

        Cette méthode tente d'initialiser le module NRF24. Le résultat
        est communiqué via le callback `on_status`.
        """
        success, message = self._transport.start(self._handle_raw_packet)
        
        if success:
            self.is_connected = True
            self._on_status("Pied à coulisse prêt.")
        else:
            self.is_connected = False
            # En cas d'erreur (SPI non activé, librairie manquante, etc.)
            self._on_status(f"Erreur pied à coulisse : {message}")

    def stop(self) -> None:
        """
        Arrête proprement le transport et libère les ressources radio.
        """
        self._transport.stop()
        self.is_connected = False

    def _handle_raw_packet(self, data: bytes) -> None:
        """
        Décodeur interne pour les paquets radio entrants.

        Cette méthode implémente le "reverse-unpacking" du format C++
        `MessageStruct` utilisé par l'émetteur.

        Paramètres
        ----------
        data : bytes
            Le paquet brut reçu (octets).
        """
        try:
            # Vérification de la taille minimale (float=4 + unit=1 + sign=1)
            if len(data) >= 6:
                # '<f??' signifie : Little Endian, 1 float, 2 booleens
                val, unit_bit, sign_bit = struct.unpack('<f??', data[:6])
                
                # Traduction des bits en langage métier
                unit = "pouce" if unit_bit else "millimètre"
                
                # Création de l'objet de données formaté
                self._last_data = CaliperData(
                    value=round(val, 2), # Arrondi pour plus de clarté vocale
                    unit_name=unit,
                    is_negative=sign_bit
                )
                
                # Notification du mode actif
                if self._on_new_measure:
                    self._on_new_measure(self._last_data)
                    
        except Exception as e:
            # Erreur silencieuse pour l'utilisateur, mais tracée en console
            print(f"[CALIPER-DRIVER] Erreur lors du décodage de la trame : {e}")

    def get_last_measure(self) -> Optional[CaliperData]:
        """
        Retourne la toute dernière mesure mémorisée.

        Returns
        -------
        CaliperData or None
            La mesure si elle existe, sinon None.
        """
        return self._last_data
