# modes/mode_multimetre.py
"""
Mode "Multimètre OWON 16" pour l'assistant.

Ce module encapsule toute la logique "métier" côté utilisateur pour le multimètre :

- Gestion de la voix :
    * Toutes les annonces passent par le `Speaker` central.
- Gestion du matériel :
    * Dialogue avec le multimètre via `OwonMultimeterDriver`
      (qui lui-même utilise le transport BLE générique `BleClient`).
- Logique UX :
    * Appui court  : lire la dernière mesure.
    * Appui long   : annoncer l'état de connexion du multimètre.
    * Double appui : activer / désactiver une lecture automatique périodique
      (toutes les X secondes).

Le mode ne contient AUCUN code BLE direct et ne gère pas les broches GPIO :
il consomme simplement un driver de plus bas niveau.
"""

from typing import Optional
from threading import Timer

from core.mode_base import Mode
from core.speaker import Speaker
from hardware.devices.owon_multimeter import (
    OwonMultimeterDriver,
    OwonMultimeterData,
)


class ModeMultimetre(Mode):
    """
    Mode "Multimètre" de l'assistant.

    Rôle
    ----
    Ce mode fournit une interface vocale par-dessus le multimètre OWON 16 :
    il traduit les actions utilisateur (appuis sur le bouton, double-clic,
    sélection du mode) en :

    - commandes haut niveau vers `OwonMultimeterDriver` (start/stop),
    - annonces vocales lisibles pour un utilisateur non voyant.

    Comportement UX
    ---------------
    - `on_enter` :
        * démarre la recherche / connexion BLE en arrière-plan via le driver.
        * remet à zéro le mode de lecture automatique (on revient en manuel).
        * l’annonce "Mode X : Multimètre" est gérée par le `ModeManager`.
    - `on_exit` :
        * arrête proprement le driver OWON (scan + connexion BLE).
        * désactive la lecture automatique et annule les timers.
    - `on_short_press` (clic simple) :
        * annonce la dernière mesure disponible (ex : "3.27 VOLT DC").
        * si aucune mesure n’est encore disponible : message d’erreur vocal.
    - `on_long_press` (appui long) :
        * annonce l’état de connexion actuel (connecté / en recherche).
    - `on_double_press` (double clic) :
        * active / désactive un mode de lecture automatique :
          toutes les `self._auto_read_interval` secondes, la dernière
          mesure est annoncée, tant que le multimètre est connecté.

    Détails techniques
    ------------------
    - La conversion "nombre -> texte" est centralisée dans
      `_format_value_for_speech()` afin de gérer proprement :
        * les valeurs négatives ("moins 1.3"),
        * le format numérique passé au TTS.
    - La lecture automatique est pilotée par un `threading.Timer`
      qui se réarme lui-même (`_schedule_auto_read` / `_auto_read_tick`).
    - Quand la connexion BLE est perdue, le mode auto reste activé
      mais ne parle pas tant que le multimètre n'est pas reconnecté.
    """

    def __init__(self, speaker: Speaker):
        """
        Initialise le mode Multimètre.

        Paramètres
        ----------
        speaker : Speaker
            Instance du `Speaker` central utilisée pour toutes les annonces vocales.
        """
        super().__init__(name="Multimètre")
        self.speaker = speaker

        # Dernière mesure brute fournie par le driver
        self._last_data: Optional[OwonMultimeterData] = None

        # Gestion de la lecture automatique
        self._auto_read_enabled: bool = False          # état ON/OFF du mode auto
        self._auto_read_interval: float = 5.0          # période de lecture auto (secondes)
        self._auto_read_timer: Optional[Timer] = None  # Timer courant (si actif)

        # Driver haut niveau du multimètre OWON (BLE + décodage trames)
        self._driver = OwonMultimeterDriver(
            on_status=self._on_status_from_driver,
            on_new_measure=self._on_new_measure,
        )

    # ---------- callbacks venant du driver ----------

    def _on_status_from_driver(self, text: str) -> None:
        """
        Callback appelé par `OwonMultimeterDriver` pour signaler un événement.

        Exemples de messages typiques :
            - "Recherche du multimètre en cours."
            - "Multimètre connecté. Vous pouvez effectuer vos mesures."
            - "Connexion perdue avec le multimètre."

        Stratégie
        ---------
        Tous ces messages passent par la voix centrale (Speaker) afin de garder
        un point d'entrée unique pour la synthèse vocale dans l'application.
        """
        self.speaker.speak(text)

    def _on_new_measure(self, data: OwonMultimeterData) -> None:
        """
        Callback appelé à chaque nouvelle trame de mesure.

        Comportement
        ------------
        - Met simplement à jour `self._last_data`.
        - Ne déclenche PAS de parole automatique (pour éviter de spammer
          l'utilisateur à chaque mise à jour en BLE).
        - La lecture reste pilotée par :
            * un appui manuel (`on_short_press`),
            * ou le mode auto périodique (`_auto_read_tick`).
        """
        self._last_data = data

    def _cancel_auto_read(self) -> None:
        """
        Annule le timer de lecture automatique s'il existe.

        Utilisé :
        - à l'entrée du mode (`on_enter`),
        - à la sortie du mode (`on_exit`),
        - lors de la désactivation explicite du mode auto (`on_double_press`).
        """
        if self._auto_read_timer is not None and self._auto_read_timer.is_alive():
            self._auto_read_timer.cancel()
        self._auto_read_timer = None

    def _schedule_auto_read(self) -> None:
        """
        Planifie un tick de lecture automatique si ce mode est activé.

        Implémentation
        --------------
        - Si `_auto_read_enabled` est False, on ne planifie rien.
        - Sinon, on crée un `threading.Timer` qui appellera `_auto_read_tick`
          au bout de `self._auto_read_interval` secondes.
        - Le timer est toujours recréé (pattern "auto-reschedule").
        """
        if not self._auto_read_enabled:
            return

        self._auto_read_timer = Timer(self._auto_read_interval, self._auto_read_tick)
        self._auto_read_timer.daemon = True
        self._auto_read_timer.start()

    def _auto_read_tick(self) -> None:
        """
        Tick périodique du mode de lecture automatique.

        Étapes
        ------
        1) Vérifie que le mode auto est toujours actif.
        2) Vérifie que le multimètre est connecté :
           - S'il ne l'est pas, on ne dit rien mais on replanifie
             le prochain tick (le mode auto "attend la reconnection").
        3) Récupère la dernière mesure via `get_last_measure()`.
        4) Si une valeur + unité sont disponibles :
           - Formate le nombre pour la voix (`_format_value_for_speech`),
           - Envoie la phrase au `Speaker`.
        5) Replanifie le tick suivant via `_schedule_auto_read()`.
        """
        # Si le mode auto a été désactivé entre-temps, on ne fait rien
        if not self._auto_read_enabled:
            return

        # Ne parler que si le multimètre est réellement connecté
        if not self._driver.is_connected:
            # On ne dit rien, mais on garde le mode auto actif
            # pour qu'il reprenne tout seul après reconnexion.
            self._schedule_auto_read()
            return

        measure = self._driver.get_last_measure()
        value = measure["value"]
        unit_name = measure["unit_name"]

        if value is not None and unit_name is not None:
            speech_value = self._format_value_for_speech(value)
            message = f"{speech_value} {unit_name}"
            self.speaker.speak(message)

        # On re-planifie le prochain tick
        self._schedule_auto_read()

    def _format_value_for_speech(self, value: float) -> str:
        """
        Convertit un float en texte lisible par la synthèse vocale.

        Gestion du signe
        ----------------
        - Valeur négative : retourne "moins X" (ex : -1.3 -> "moins 1.3").
        - Valeur positive ou nulle : retourne la valeur convertie en chaîne.

        Paramètres
        ----------
        value : float
            Valeur numérique provenant du driver.

        Retour
        ------
        str
            Représentation textuelle prête à être insérée dans une phrase.
        """
        if value is None:
            return ""
        if value < 0:
            return f"moins {abs(value)}"
        return str(value)

    # ---------- Hooks du Mode ----------

    def on_enter(self) -> None:
        """
        Hook appelé quand on arrive sur ce mode via le sélecteur rotatif.

        Actions réalisées
        -----------------
        - Désactive la lecture automatique (on revient en mode manuel).
        - Annule tout timer éventuellement encore actif.
        - Démarre le driver OWON :
            * scan BLE en arrière-plan,
            * tentatives de connexion automatiques.

        Remarque
        --------
        Le `ModeManager` se charge déjà d’annoncer "Mode X : Multimètre",
        donc on ne parle pas ici pour éviter les doublons.
        """
        self._auto_read_enabled = False
        self._cancel_auto_read()
        self._driver.start()

    def on_exit(self) -> None:
        """
        Hook appelé quand on quitte ce mode.

        Actions réalisées
        -----------------
        - Désactive le mode de lecture automatique.
        - Annule le timer de lecture automatique.
        - Arrête le driver OWON (arrêt des scans / connexions BLE).
        """
        self._auto_read_enabled = False
        self._cancel_auto_read()
        self._driver.stop()

    def on_short_press(self) -> None:
        """
        Appui court : annonce la dernière mesure reçue.

        Comportement
        ------------
        - Si aucune mesure n'est disponible (pas encore de trame reçue) :
          annonce "Aucune mesure disponible pour le moment.".
        - Sinon :
          * récupère le dictionnaire simplifié via `get_last_measure()`,
          * formate la valeur pour la voix (`_format_value_for_speech`),
          * concatène la valeur + le nom d'unité tel que décodé par le driver
            (ex : "MILLI VOLT DC", "OHM NORMAL", "CELSIUS"...),
          * envoie la phrase au `Speaker`.

        Exemple de rendu
        ----------------
            "moins 1.3 MILLI VOLT DC"
        """
        measure = self._driver.get_last_measure()
        value = measure["value"]
        unit_name = measure["unit_name"]

        if value is None or unit_name is None:
            self.speaker.speak("Aucune mesure disponible pour le moment.")
            return

        speech_value = self._format_value_for_speech(value)
        message = f"{speech_value} {unit_name}"
        self.speaker.speak(message)

    def on_long_press(self) -> None:
        """
        Appui long : annonce l'état de connexion actuel du multimètre.

        Cas gérés
        ---------
        - Si `OwonMultimeterDriver.is_connected` est True :
            -> "Le multimètre est connecté."
        - Sinon :
            -> "Recherche ou connexion au multimètre en cours.
                Veuillez patienter ou vérifier qu'il est allumé."
        """
        if self._driver.is_connected:
            self.speaker.speak("Le multimètre est connecté.")
        else:
            # Le driver est démarré dès on_enter, donc si on n'est pas
            # connecté ici, c'est qu'on est en recherche ou en tentative
            # de connexion.
            self.speaker.speak(
                "Recherche ou connexion au multimètre en cours. "
                "Veuillez patienter ou vérifier qu'il est allumé."
            )

    def on_double_press(self) -> None:
        """
        Double appui : bascule entre lecture automatique et lecture manuelle.

        Comportement
        ------------
        - Si la lecture automatique est désactivée :
            * l'active,
            * annonce "Lecture automatique du multimètre activée.",
            * planifie le premier tick avec `_schedule_auto_read()`.
        - Si la lecture automatique est déjà active :
            * la désactive,
            * annule le timer associé,
            * annonce "Lecture automatique désactivée. Retour au mode manuel.".
        """
        if not self._auto_read_enabled:
            # Activation
            self._auto_read_enabled = True
            self.speaker.speak("Lecture automatique du multimètre activée.")
            self._schedule_auto_read()
        else:
            # Désactivation
            self._auto_read_enabled = False
            self._cancel_auto_read()
            self.speaker.speak("Lecture automatique désactivée. Retour au mode manuel.")
