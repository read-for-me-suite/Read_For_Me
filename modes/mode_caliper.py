# modes/mode_caliper.py
"""
Mode "Pied à coulisse" pour l'assistant ReadForMe.

Ce module encapsule toute la logique "métier" et l'interface utilisateur pour 
les mesures de distance sans fil :

- Gestion de la voix :
    * Toutes les annonces passent par le `Speaker` central.
- Gestion du matériel :
    * Dialogue avec le récepteur radio via `CaliperDriver`.
- Logique UX (Bouton poussoir) :
    * Appui court   : Annoncer la dernière mesure reçue.
    * Appui long    : Annoncer l'état de connexion radio (SPI/NRF24).
    * Double appui  : Activer ou désactiver la lecture automatique périodique.

Ce mode suit le cycle de vie défini par `core.mode_base.Mode`.
"""

from typing import Optional
from threading import Timer

from core.mode_base import Mode
from core.speaker import Speaker
from hardware.devices.caliper import CaliperDriver, CaliperData


class ModeCaliper(Mode):
    """
    Mode "Pied à coulisse" de l'assistant.

    Rôle
    ----
    Fournit une interface vocale pour le pied à coulisse numérique. Il traduit
    les paquets radio reçus en annonces audibles et gère les interactions
    utilisateur via le bouton du sélecteur rotatif.
    """

    def __init__(self, speaker: Speaker):
        """
        Initialise le mode Pied à coulisse.

        Paramètres
        ----------
        speaker : Speaker
            Instance du gestionnaire vocal central pour les annonces.
        """
        super().__init__(name="Pied à coulisse")
        self.speaker = speaker

        # Initialisation du driver (Radio NRF24 + Décodage)
        self._driver = CaliperDriver(
            on_status=self._on_status_from_driver,
            on_new_measure=self._on_new_measure
        )

        # État interne du mode
        self._last_data: Optional[CaliperData] = None
        self._auto_read_enabled: bool = False
        self._auto_read_timer: Optional[Timer] = None
        self._auto_read_interval: float = 4.0  # Délai de lecture auto en secondes

    # ---------- Callbacks venant du driver ----------

    def _on_status_from_driver(self, text: str) -> None:
        """
        Callback appelé par le driver pour signaler un changement d'état.
        Ex: "Pied à coulisse prêt", "Erreur SPI", etc.
        """
        self.speaker.speak(text)

    def _on_new_measure(self, data: CaliperData) -> None:
        """
        Callback appelé à chaque réception de mesure radio.
        Met à jour la mémoire du mode sans déclencher de parole immédiate.
        """
        self._last_data = data

    # ---------- Cycle de vie du Mode (Hooks) ----------

    def on_enter(self) -> None:
        """
        Hook appelé lors de la sélection du mode.
        - Désactive la lecture automatique par sécurité.
        - Démarre le thread de lecture radio.
        """
        self._auto_read_enabled = False
        self._driver.start()

    def on_exit(self) -> None:
        """
        Hook appelé quand on change de mode.
        - Arrête les annonces automatiques.
        - Coupe proprement le driver radio.
        """
        self._auto_read_enabled = False
        if self._auto_read_timer:
            self._auto_read_timer.cancel()
        self._driver.stop()

    # ---------- Actions utilisateur (Bouton) ----------

    def on_short_press(self) -> None:
        """
        Appui court : Annonce vocalement la dernière mesure mémorisée.
        
        Gère le formatage du signe et de l'unité (millimètres ou pouces).
        Exemple : "moins 12.45 millimètres"
        """
        if not self._last_data:
            self.speaker.speak("Aucune mesure disponible.")
            return
        
        # Préparation du préfixe de signe
        signe = "moins " if self._last_data.is_negative else ""
        
        # Construction du message vocal
        # On ajoute un 's' à l'unité pour la grammaire (ex: millimètres)
        msg = f"{signe}{self._last_data.value} {self._last_data.unit_name}s"
        
        self.speaker.speak(msg)

    def on_long_press(self) -> None:
        """
        Appui long : Annonce l'état du matériel.
        Utile pour diagnostiquer si le module NRF24 est bien branché au Pi.
        """
        etat = "connecté" if self._driver.is_connected else "non détecté"
        self.speaker.speak(f"Le récepteur radio est {etat}.")

    def on_double_press(self) -> None:
        """
        Double appui : Bascule l'état de la lecture automatique.
        """
        self._auto_read_enabled = not self._auto_read_enabled
        
        if self._auto_read_enabled:
            self.speaker.speak("Lecture automatique activée.")
            self._auto_read_tick()
        else:
            if self._auto_read_timer:
                self._auto_read_timer.cancel()
            self.speaker.speak("Lecture automatique désactivée.")

    # ---------- Logique de lecture automatique ----------

    def _auto_read_tick(self) -> None:
        """
        Boucle périodique pour la lecture automatique.
        Utilise un threading.Timer pour ne pas bloquer l'application.
        """
        if self._auto_read_enabled:
            # On réutilise la logique de l'appui court
            self.on_short_press()
            
            # Planification du prochain tick
            self._auto_read_timer = Timer(self._auto_read_interval, self._auto_read_tick)
            self._auto_read_timer.daemon = True
            self._auto_read_timer.start()
