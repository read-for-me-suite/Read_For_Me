# hardware/devices/owon_multimeter.py
"""
Driver pour le multimètre OWON 16.

Vue d'ensemble
==============

Ce module fournit deux briques :

1. `OwonMultimeterData`
   ---------------------
   - Représente **une trame de 6 octets** envoyée par le multimètre OWON 16.
   - Décode la structure binaire (bits décimale / overflow / fonction / flags / valeur / signe).
   - Présente les informations dans un objet Python lisible :
       * `value`           : valeur numérique en float (avec signe et décimale appliqués),
       * `unit_name`       : nom de la fonction, ex. `"MILLI VOLT DC"`,
       * flags booléens    : `overflow`, `auto_ranging`, `data_hold_mode`, `relative_mode`, `low_battery`,
       * `raw_data`        : la trame brute (6 octets) pour debug / log.

2. `OwonMultimeterDriver`
   -----------------------
   - Driver **haut niveau** pour le multimètre OWON basé sur le transport générique `BleClient`.
   - Responsabilités :
       * gérer la recherche / connexion BLE (`start()`, `stop()`, `is_connected`),
       * décoder les trames brutes en `OwonMultimeterData`,
       * mémoriser la **dernière mesure** (`get_last_measure()`),
       * annoncer intelligemment les **changements de mode de mesure** (fonction du multimètre)
         via un callback `on_status(text)` (par ex. le `Speaker`).
   - Il ne fait **aucune synthèse vocale directement** : il envoie du texte vers le Mode,
     qui lui-même appelle le `Speaker`.

Couche & responsabilités
------------------------
- Ce module connaît :
    * le protocole binaire OWON (layout des 6 octets),
    * les codes de fonction (`OWON_FUNCTION`),
    * la logique d’annonce des changements de mode (hystérésis).
- Il ne connaît PAS :
    * le sélecteur rotatif (géré ailleurs),
    * l’architecture globale des modes,
    * la façon dont le texte sera lu (voix, langue, etc.).
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from hardware.transports.ble_client import BleClient
import time


# ===========================
#   Décodage des trames OWON
# ===========================

#: Dictionnaire de mapping "nom symbolique" -> code 13 bits "function_selector"
#:
#: Ces valeurs proviennent de la documentation / reverse-engineering du
#: multimètre OWON 16. Le champ "fonction" est encodé sur 13 bits dans les
#: deux premiers octets de chaque trame.
#:
#: Remarque importante sur les milliampères
#: ----------------------------------------
#: Dans la doc d'origine, les codes **AC/DC pour les milliampères** sont
#: inversés par rapport à ce que le multimètre envoie réellement.
#: Après tests sur le matériel, nous avons corrigé le mapping :
#:
#:   - 7699  -> "MILLI_AMPERE_DC"
#:   - 7707  -> "MILLI_AMPERE_AC"
#:
#: Cela garantit que les annonces vocales et `unit_name` sont cohérents avec
#: ce qui est affiché sur l'écran du multimètre (évite de dire "AC" quand
#: l'écran est en "DC" et inversement).
OWON_FUNCTION: Dict[str, int] = {
    "MILLI_VOLT_DC": 7683,
    "MILLI_VOLT_AC": 7691,
    "VOLT_DC": 7684,
    "VOLT_AC": 7692,
    "DIODE_TEST": 7764,
    "MICRO_AMPERE_DC": 7698,
    # Attention : ces deux-là sont volontairement "swappés"
    "MILLI_AMPERE_AC": 7707,
    "MICRO_AMPERE_AC": 7706,
    "MILLI_AMPERE_DC": 7699,
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

#: Mapping "code fonction OWON" -> phrase FR annoncée
#:
#: Utilisé par `OwonMultimeterDriver` pour annoncer les changements de mode
#: (ex : "Mode voltmètre courant continu."). Ces libellés sont pensés pour
#: être prononcés directement par la synthèse vocale.
OWON_MODE_LABEL_FR: Dict[int, str] = {
    OWON_FUNCTION["MILLI_VOLT_DC"]: "millivoltmètre courant continu",
    OWON_FUNCTION["MILLI_VOLT_AC"]: "millivoltmètre courant alternatif",
    OWON_FUNCTION["VOLT_DC"]: "voltmètre courant continu",
    OWON_FUNCTION["VOLT_AC"]: "voltmètre courant alternatif",
    OWON_FUNCTION["DIODE_TEST"]: "test de diode",
    OWON_FUNCTION["MICRO_AMPERE_DC"]: "microampèremètre courant continu",
    OWON_FUNCTION["MILLI_AMPERE_AC"]: "milliampèremètre courant alternatif",
    OWON_FUNCTION["MICRO_AMPERE_AC"]: "microampèremètre courant alternatif",
    OWON_FUNCTION["MILLI_AMPERE_DC"]: "milliampèremètre courant continu",
    OWON_FUNCTION["AMPERE_DC"]: "ampèremètre courant continu",
    OWON_FUNCTION["AMPERE_AC"]: "ampèremètre courant alternatif",
    OWON_FUNCTION["OHM_NORMAL"]: "ohmmètre",
    OWON_FUNCTION["CONTINUITY_TEST"]: "test de continuité",
    OWON_FUNCTION["KILO_OHM"]: "kilo ohmmètre",
    OWON_FUNCTION["MEGA_OHM"]: "méga ohmmètre",
    OWON_FUNCTION["NANO_FARAD"]: "mesure de capacité en nanofarad",
    OWON_FUNCTION["MICRO_FARAD"]: "mesure de capacité en microfarad",
    OWON_FUNCTION["MILLI_FARAD"]: "mesure de capacité en millifarad",
    OWON_FUNCTION["FARAD"]: "mesure de capacité en farad",
    OWON_FUNCTION["HERTZ"]: "fréquencemètre",
    OWON_FUNCTION["PERCENTAGE"]: "mesure de pourcentage",
    OWON_FUNCTION["CELSIUS"]: "thermomètre en degrés Celsius",
    OWON_FUNCTION["FAHRENHEIT"]: "thermomètre en degrés Fahrenheit",
    OWON_FUNCTION["NEAR_FIELD"]: "détection de champ électrique",
}


@dataclass
class OwonMultimeterData:
    """
    Représente une trame décodée du multimètre OWON 16 (6 octets).

    Structure binaire (vue "fabricant")
    -----------------------------------
    Les 6 octets sont organisés comme suit (Little Endian) :

        Field_name          start_bit   length_bit
        -----------------------------------------
        decimal_places          0           2
        overflow                2           1
        function_selector       3          13
        data_hold_mode         16           1
        relative_mode          17           1
        auto_ranging           18           1
        low_battery            19           1
        not_used_1             20           4
        not_used_2             24           8
        value                  32          15
        sign                   47           1

    Interprétation
    --------------
    - `decimal_places` : position de la décimale (0, 1, 2 ou 3).
    - `overflow`       : dépassement de gamme (0 = OK, 1 = overflow).
    - `function_selector` (ici `unit`) :
        code 13 bits mappé via `OWON_FUNCTION` vers un nom symbolique.
    - `data_hold_mode` : flag HOLD (gel d’affichage).
    - `relative_mode`  : mode relatif (REL).
    - `auto_ranging`   : autorange actif ou non.
    - `low_battery`    : batterie faible.
    - `value`          : valeur brute signée (15 bits + signe), mise à l’échelle.
    - `sign`           : 0 = positif, 1 = négatif.

    Attributs principaux exposés
    ----------------------------
    raw_data : List[int]
        Trame brute reçue (6 octets).
    decimal_places : int
        Nombre de décimales à appliquer à la valeur.
    overflow : int
        Flag overflow (0 ou 1).
    unit : int
        Code numérique de la fonction (13 bits).
    unit_name : str
        Nom lisible de la fonction (ex: "MILLI VOLT DC", "OHM NORMAL", ...).
    data_hold_mode : int
        Flag HOLD (0 ou 1).
    relative_mode : int
        Flag REL (0 ou 1).
    auto_ranging : int
        Flag AutoRange (0 ou 1).
    low_battery : int
        Flag batterie faible (0 ou 1).
    value : float
        Valeur numérique finale (signe et décimale appliqués).
    sign : int
        Flag de signe (0 = positif, 1 = négatif).
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
        """
        Construit une instance à partir d'une trame brute (6 octets).

        Paramètres
        ----------
        raw_data : List[int]
            Liste de 6 octets (0–255) reçus depuis le multimètre.

        Returns
        -------
        OwonMultimeterData
            Instance décodée, prête à être utilisée (value, flags, etc.).

        Raises
        ------
        ValueError
            Si la longueur de `raw_data` n'est pas égale à 6.
        """
        if len(raw_data) != 6:
            raise ValueError(f"Expected 6 bytes of data, got {len(raw_data)}")

        # Regroupement des champs :
        # - unit_and_decimal : bits 0..15 (2 premiers octets)
        # - flags            : bits 16..23 (3e octet)
        # - value_and_sign   : bits 32..47 (2 derniers octets)
        unit_and_decimal = (raw_data[1] << 8) | raw_data[0]
        flags = raw_data[2]
        value_and_sign = (raw_data[5] << 8) | raw_data[4]

        # Extraction des sous-champs de unit_and_decimal
        decimal_places = unit_and_decimal & 0b11            # bits 0–1
        overflow = (unit_and_decimal >> 2) & 0b1            # bit 2
        unit = unit_and_decimal >> 3                        # bits 3–15 (13 bits)

        unit_name = cls._get_unit_from_value(unit)

        # Extraction des flags (1 bit chacun)
        data_hold_mode = flags & 0b1                        # bit 0
        relative_mode = (flags >> 1) & 0b1                  # bit 1
        auto_ranging = (flags >> 2) & 0b1                   # bit 2
        low_battery = (flags >> 3) & 0b1                    # bit 3

        # Extraction de la valeur brute + signe
        raw_value = value_and_sign & 0b11111111111111       # 15 bits de valeur
        sign = (value_and_sign >> 15) & 0b1                 # bit 15

        if sign:
            raw_value = -raw_value

        # Application de la décimale
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
        """
        Retourne le nom symbolique (en majuscules avec espaces) associé à un code 13 bits.

        Paramètres
        ----------
        code : int
            Valeur entière du champ `function_selector` (13 bits).

        Returns
        -------
        str
            Nom de la fonction, par ex. `"MILLI VOLT DC"`, `"OHM NORMAL"`.
            Retourne `"UNKNOWN"` si le code n'est pas répertorié dans
            `OWON_FUNCTION`.
        """
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

    Rôle
    ----
    - Utiliser `BleClient` comme **transport BLE générique**.
    - Décoder les trames brutes reçues via BLE en objets `OwonMultimeterData`.
    - Mémoriser la dernière mesure décodée (`_last_data`).
    - Annoncer les **changements de mode de mesure** (tension, courant, ohms, ...)
      via une logique d’hystérésis (temps minimum de stabilité).
    - Exposer une API simple pour les Modes :
        * `start()` / `stop()` pour lancer/arrêter la surveillance BLE.
        * `is_connected` pour vérifier l’état de connexion.
        * `get_last_measure()` pour récupérer la dernière mesure sous forme de dict.

    Couche d’abstraction
    --------------------
    - Ce driver ne fait pas de synthèse vocale.
      Il pousse simplement des **messages texte** dans le callback `on_status`.
    - Le Mode (ex: `ModeMultimetre`) se charge ensuite de passer ces messages
      au `Speaker` central.
    """

    def __init__(
        self,
        *,
        on_status: Optional[Callable[[str], None]] = None,
        on_new_measure: Optional[Callable[[OwonMultimeterData], None]] = None,
        retry_delay: float = 15.0,
    ) -> None:
        """
        Initialise le driver OWON.

        Paramètres
        ----------
        on_status : Optional[Callable[[str], None]]
            Callback pour annoncer des messages utilisateur (via Speaker).
            Exemple de messages :
                - "Multimètre connecté. Vous pouvez effectuer vos mesures."
                - "Mode voltmètre courant continu."
                - "Multimètre non trouvé. Assurez-vous qu'il est allumé..."
        on_new_measure : Optional[Callable[[OwonMultimeterData], None]]
            Callback appelé à chaque **nouvelle trame décodée**.
            Permet au Mode d’enregistrer directement la dernière mesure brute.
        retry_delay : float
            Délai (en secondes) entre deux tentatives lorsqu’aucun multimètre
            n’est trouvé lors du scan BLE.
        """
        self._on_status = on_status
        self._on_new_measure = on_new_measure
        self._retry_delay = retry_delay

        # Dernière mesure décodée (None tant qu'aucune trame n'a été reçue)
        self._last_data: Optional[OwonMultimeterData] = None

        # Gestion des changements de fonction (mode de mesure OWON)
        self._last_unit_code: Optional[int] = None
        self._last_announced_unit_code: Optional[int] = None
        self._last_unit_change_time: float = 0.0
        # Délai avant d'annoncer un mode (pour éviter d'annoncer tous les modes traversés)
        self._mode_announce_delay: float = 0.7  # en secondes, à ajuster au besoin

        # Transport BLE générique
        # - name_filter : "BDM" = nom publicitaire du multimètre OWON 16
        # - characteristic_uuid : UUID utilisée par OWON pour les mesures
        self._ble = BleClient(
            name_filter="BDM",
            characteristic_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
            on_status=self._handle_ble_status,
            on_packet=self._handle_ble_packet,
            retry_delay=self._retry_delay,
        )

    # ----------- API publique -----------

    def start(self) -> None:
        """
        Démarre la recherche / connexion au multimètre OWON.

        Effets
        ------
        - Lance le `BleClient` dans un thread séparé.
        - Le driver se met à l’écoute des trames et des événements d’état.
        """
        self._ble.start()

    def stop(self) -> None:
        """
        Arrête la surveillance du multimètre.

        Effets
        ------
        - Demande l’arrêt du `BleClient` (stop de la boucle de monitoring).
        - À terme, la connexion BLE est fermée et l’état repasse à "stopped".
        """
        self._ble.stop()

    @property
    def is_connected(self) -> bool:
        """
        Indique si le multimètre est actuellement connecté au niveau BLE.

        Returns
        -------
        bool
            `True` si `BleClient` est connecté au périphérique OWON,
            `False` sinon.
        """
        return self._ble.is_connected

    def get_last_measure(self) -> Dict[str, Optional[object]]:
        """
        Retourne la dernière mesure sous forme de dict simple, prêt à consommer.

        Ce format est volontairement **générique** pour être facile à utiliser
        côté Modes / IHM / logs, sans exposer directement l’objet `OwonMultimeterData`.

        Clés du dictionnaire
        --------------------
        - "value"         : float ou None
        - "unit_name"     : str ou None (ex: "MILLI VOLT DC", "OHM NORMAL")
        - "overflow"      : bool ou None
        - "auto_ranging"  : bool ou None
        - "data_hold_mode": bool ou None
        - "relative_mode" : bool ou None

        Returns
        -------
        dict
            Dictionnaire avec les champs ci-dessus. Si aucune mesure n’a
            encore été reçue, toutes les valeurs sont à None.
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

        Paramètres
        ----------
        event : str
            Événement émis par `BleClient` (search_start, found, connected, ...).

        Comportement
        ------------
        - Traduit l’événement en texte en français.
        - Envoie ce texte dans le callback `on_status`, si défini.
        - Certains événements sont silencieux (ex: "stopped") pour ne pas
          polluer l’UX.
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
            text = "Multimètre détecté."
        elif event == "connecting":
            text = "Connexion en cours."
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
            text = None  # on reste silencieux

        if text:
            try:
                self._on_status(text)
            except Exception as e:
                print(f"[OWON] Erreur dans on_status callback : {e}")

    def _announce_mode_change(self, unit_code: int) -> None:
        """
        Annonce un changement de mode du multimètre (fonction de mesure).

        Paramètres
        ----------
        unit_code : int
            Code 13 bits de la fonction OWON (champ `unit` de `OwonMultimeterData`).

        Comportement
        ------------
        - Cherche un libellé français dans `OWON_MODE_LABEL_FR`.
        - Si trouvé, émet "Mode <libellé>." via le callback `on_status`.
        - Si le code n’est pas connu / mappé, reste silencieux.
        """
        if not self._on_status:
            return

        label = OWON_MODE_LABEL_FR.get(unit_code)
        if not label:
            # Mode inconnu ou non mappé → on n'annonce rien
            return

        try:
            self._on_status(f"Mode {label}.")
        except Exception as e:
            print(f"[OWON] Erreur lors de l'annonce de changement de mode : {e}")

    def _handle_ble_packet(self, data: bytes) -> None:
        """
        Reçoit les données brutes depuis BleClient et les décode.

        Logique appliquée
        -----------------
        1. Conversion `bytes` -> `List[int]` -> `OwonMultimeterData.from_raw(...)`.
        2. Mise à jour de `self._last_data`.
        3. Gestion des **changements de mode** (fonction de mesure OWON) :
            - Si `decoded.unit` est différent de `self._last_unit_code` :
                * on enregistre le nouveau code,
                * on mémorise l’instant du changement (`_last_unit_change_time`).
            - Périodiquement, on vérifie :
                * que le code courant est différent du dernier annoncé,
                * que le mode est resté stable au moins `_mode_announce_delay`
                  secondes.
            - Si ces conditions sont remplies, on appelle `_announce_mode_change(...)`.
              Cela évite que l’utilisateur entende tous les modes "traversés"
              pendant qu’il tourne la molette rapidement.
        4. Propagation de la mesure au callback `on_new_measure`, si défini.

        Paramètres
        ----------
        data : bytes
            Trame brute reçue sur la caractéristique BLE.
        """
        try:
            raw_list = list(data)
            decoded = OwonMultimeterData.from_raw(raw_list)
            self._last_data = decoded

            now = time.time()

            # 1) Détection de changement de code fonction (unit)
            if self._last_unit_code is None or decoded.unit != self._last_unit_code:
                # Nouveau mode de mesure détecté -> on mémorise l'instant du changement
                self._last_unit_code = decoded.unit
                self._last_unit_change_time = now

            # 2) Vérifier si le mode courant est resté suffisamment stable
            #    pour être annoncé (sinon on considère que l'utilisateur
            #    est encore en train de tourner la molette).
            if (
                self._last_unit_code is not None
                and self._last_unit_code != self._last_announced_unit_code
                and now - self._last_unit_change_time >= self._mode_announce_delay
            ):
                # Le mode courant est stable depuis au moins _mode_announce_delay
                self._last_announced_unit_code = self._last_unit_code
                self._announce_mode_change(self._last_unit_code)

            # 3) Propager la mesure brute au callback de niveau supérieur (Mode)
            if self._on_new_measure:
                self._on_new_measure(decoded)

        except Exception as e:
            print(f"[OWON] Erreur de décodage trame : {e}")
