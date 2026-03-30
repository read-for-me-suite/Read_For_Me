# hardware/platform/rotary_selector.py
"""
hardware.platform.rotary_selector
=================================

Driver bas niveau pour le **sélecteur rotatif + bouton poussoir**.

Objectif
--------
Ce module encapsule la logique "physique" du rotateur :

- lecture des signaux **quadrature** (canaux A/B) pour la rotation,
- calcul du **sens** du geste ("sens horaire" / "sens inverse"),
- agrégation de plusieurs impulsions en un seul **geste stable**,
- protection contre les **rebonds** et gestes trop rapides,
- gestion des **appuis sur le bouton** :
    - appui court,
    - appui long,
    - double-clic (double appui court rapide).

Important : ce driver est **agnostique** de la logique métier.

- Il **ne connaît pas** les modes, ni le speaker, ni le multimètre.
- Il expose simplement des **callbacks** que le reste du système branche :
    - `on_position_changed(index, direction)`
    - `on_short_press()`
    - `on_long_press()`
    - `on_double_press()`

L’objectif est d’avoir un composant réutilisable, proprement isolé, qui
s’occupe uniquement de transformer des signaux GPIO bruts en événements
haut niveau exploitables par l’assistant.
"""

import time
from threading import Timer
from typing import Callable, Optional

from gpiozero import Button


class RotarySelector:
    """
    Driver pour un encodeur rotatif incrémental avec bouton poussoir intégré.

    Rôle
    ----
    - Maintient une **position logique de mode** : `0 .. positions_count-1`.
    - Détecte le **sens de rotation** et produit des gestes stables.
    - Gère les appuis :
        * court,
        * long,
        * double appui rapide (double-clic).

    Stratégie UX
    ------------
    - Plusieurs impulsions rapprochées dans le **même sens** sont agrégées
      en **un seul geste** :
        => un seul changement de position / mode.
    - Les allers-retours très rapides (bruit, gestes hésitants) sont
      filtrés via :
        * un délai minimum entre deux changements de mode
          (`min_step_interval`),
        * un délai de **stabilisation de geste** (`gesture_settle_delay`).
    - Une **zone morte** autour des appuis bouton (`rotate_button_deadzone`)
      évite que des rebonds mécaniques du bouton soient interprétés comme
      des rotations.
    - La gestion du **double-clic** repose sur une petite fenêtre de temps
      (`double_click_window`) : si deux appuis courts se succèdent dans ce
      délai, on considère qu’il s’agit d’un double appui.

    Paramètres
    ----------
    pin_a : int
        Broche GPIO du canal A de l’encodeur.
    pin_b : int
        Broche GPIO du canal B de l’encodeur.
    pin_sw : int
        Broche GPIO du bouton poussoir.
    positions_count : int
        Nombre total de positions logiques (nombre de modes disponibles).
    long_press_threshold : float
        Durée (en secondes) à partir de laquelle un appui est considéré comme
        "long" plutôt que "court".
    gesture_settle_delay : float
        Temps sans nouvelle impulsion avant de considérer qu’un geste de
        rotation est terminé et de changer effectivement de position.
    rotate_button_deadzone : float
        Intervalle de temps (en secondes) autour d’un événement bouton
        pendant lequel on ignore les impulsions de rotation (anti-parasites).
    min_step_interval : float
        Délai minimum (en secondes) entre deux changements de position
        consécutifs (limite les changements trop rapides).
    double_click_window : float
        Temps maximum (en secondes) entre deux appuis courts consécutifs pour
        être interprétés comme un **double appui**.
    """

    def __init__(
        self,
        pin_a: int = 17,
        pin_b: int = 27,
        pin_sw: int = 22,
        positions_count: int = 4,
        long_press_threshold: float = 1.0,
        gesture_settle_delay: float = 0.20,   # temps sans impulsion pour valider un geste
        rotate_button_deadzone: float = 0.15, # zone morte autour des appuis bouton
        min_step_interval: float = 0.30,      # temps mini entre deux changements de mode
        double_click_window: float = 0.4,     # temps max entre deux clics pour un double-clic
        button_bounce_time: float = 0.05,
    ) -> None:
        self.positions_count = positions_count

        # Position de mode vue par le reste du système (0..positions_count-1)
        self.position: int = 0

        # Geste de rotation en cours (sens mémorisé jusqu’à stabilisation)
        self._pending_direction: Optional[str] = None
        self.last_direction: Optional[str] = None

        # Compteur de gestes pour debug / logs
        self._gesture_count: int = 0

        # Gestion du bouton poussoir (mesure de la durée d’appui)
        self._press_start_time: Optional[float] = None
        self._long_press_threshold = long_press_threshold

        # Callbacks externes (branchés par ModeManager / application)
        self.on_position_changed: Optional[Callable[[int, str], None]] = None
        self.on_short_press: Optional[Callable[[], None]] = None
        self.on_long_press: Optional[Callable[[], None]] = None
        self.on_double_press: Optional[Callable[[], None]] = None

        # Délai de stabilisation du geste de rotation
        self._gesture_settle_delay = gesture_settle_delay
        self._gesture_timer: Optional[Timer] = None

        # Zone morte entre rotation et bouton (pour filtrer les parasites)
        self._last_button_event_time: float = 0.0
        self._rotate_button_deadzone = rotate_button_deadzone

        # Intervalle minimal entre deux changements de mode
        self._min_step_interval = min_step_interval
        self._last_step_time: float = 0.0

        # Configuration des broches (encodeur rotatif) via gpiozero
        self.channel_a = Button(pin_a)
        self.channel_b = Button(pin_b)

        # Bouton poussoir (pull-up + anti-rebond soft)
        self.button = Button(pin_sw, pull_up=True, bounce_time=button_bounce_time)

        # Wiring des événements GPIO vers les callbacks internes
        self.channel_a.when_pressed = self._on_channel_a_edge
        self.button.when_pressed = self._on_button_pressed
        self.button.when_released = self._on_button_released

        # Gestion du double-clic (timestamps + timer de validation)
        self._double_click_window = double_click_window
        self._last_short_release_time: float = 0.0
        self._click_timer: Optional[Timer] = None

    # =========================
    #   Gestion de la rotation
    # =========================

    def _on_channel_a_edge(self) -> None:
        """
        Callback interne appelée sur un front du canal A.

        Fonctionnement
        --------------
        - Vérifie d’abord si l’on n’est pas trop proche d’un événement bouton
          (appui / relâchement) : si oui, on ignore le tick.
        - Lit l’état de `channel_b` pour déterminer le **sens** du mouvement :
            * `channel_b` actif -> "sens inverse"
            * sinon -> "sens horaire"
        - Mémorise ce sens comme direction du **geste en cours**.
        - Lance ou reprogramme un `Timer` de stabilisation ; si aucune nouvelle
          impulsion n’arrive avant `gesture_settle_delay`, `_validate_gesture()`
          sera appelée pour appliquer le changement de position.
        """
        now = time.time()

        # Protection : si on vient juste d’appuyer / relâcher le bouton,
        # on ignore ce tick (impulsions parasites).
        dt_button = now - self._last_button_event_time
        if dt_button < self._rotate_button_deadzone:
            print(f"[ROTARY] tick ignoré (proche bouton, dt={dt_button:.3f}s)")
            return

        # Déterminer le sens en lisant channel B
        if self.channel_b.is_pressed:
            direction = "sens inverse"
        else:
            direction = "sens horaire"

        # Nouveau geste ou mise à jour du geste en cours
        self._pending_direction = direction
        self.last_direction = direction

        print(f"[ROTARY] impulsion, direction courante du geste = {direction}")

        # (Re)planifier le Timer de stabilisation du geste
        self._schedule_gesture_timer()

    def _schedule_gesture_timer(self) -> None:
        """
        Programme (ou reprogramme) le Timer qui validera un geste stabilisé.

        Chaque nouvelle impulsion de rotation :
        - annule le timer précédent,
        - en recrée un nouveau,
        - repousse donc le moment où `_validate_gesture()` sera appelée.

        Résultat : plusieurs impulsions **rapprochées** sont agrégées en
        un seul geste logique.
        """
        if self._gesture_timer is not None and self._gesture_timer.is_alive():
            self._gesture_timer.cancel()

        self._gesture_timer = Timer(
            self._gesture_settle_delay, self._validate_gesture
        )
        self._gesture_timer.daemon = True
        self._gesture_timer.start()

    def _validate_gesture(self) -> None:
        """
        Valide un geste de rotation après `gesture_settle_delay` sans impulsion.

        - Applique **au plus un** changement de position dans le sens mémorisé.
        - Respecte un intervalle minimum entre deux changements de mode pour
          éviter les mouvements trop rapides.
        - Notifie ensuite le callback `on_position_changed`, si défini.
        """
        if self._pending_direction is None:
            # Aucun geste en cours -> rien à faire
            return

        now = time.time()

        # Protection : ne pas changer de mode trop souvent
        dt_step = now - self._last_step_time
        if dt_step < self._min_step_interval:
            print(
                f"[ROTARY] geste ignoré (trop rapproché, dt_step={dt_step:.3f}s)"
            )
            self._pending_direction = None
            return

        # Appliquer UN pas dans le bon sens
        if self._pending_direction == "sens horaire":
            self.position = (self.position + 1) % self.positions_count
        else:
            self.position = (self.position - 1) % self.positions_count

        self._gesture_count += 1
        self._last_step_time = now

        print(
            f"[ROTARY] geste STABLE={self._gesture_count}, direction={self._pending_direction}, "
            f"nouvelle position={self.position}"
        )

        # Notifier l’extérieur (ModeManager, via callback)
        if self.on_position_changed:
            self.on_position_changed(self.position, self._pending_direction)

        # Geste terminé
        self._pending_direction = None

    # =========================
    #   Gestion du bouton
    # =========================

    def _fire_single_short_press(self) -> None:
        """
        Confirme qu’un appui est un **simple clic** (et non un double-clic).

        Cette méthode est appelée par un Timer si aucun second appui
        n’est détecté dans la fenêtre `double_click_window`.

        Elle déclenche alors `on_short_press()` si défini.
        """
        # On remet à zéro le timestamp pour éviter toute réutilisation
        self._last_short_release_time = 0.0
        if self.on_short_press:
            print("[BUTTON] short press confirmed")
            self.on_short_press()

    def _on_button_pressed(self) -> None:
        """
        Callback interne lors de l’appui sur le bouton.

        - Mémorise l’instant de l’appui pour calculer la durée à la
          relâche (distinction court / long).
        - Met à jour `_last_button_event_time` pour la zone morte
          rotation <-> bouton.
        """
        self._press_start_time = time.time()
        self._last_button_event_time = self._press_start_time
        print("[BUTTON] pressed")

    def _on_button_released(self) -> None:
        """
        Callback interne lors du relâchement du bouton.

        Calcule la durée d’appui et décide :
        - si `duration >= long_press_threshold` -> **appui long**
        - sinon :
            * si un clic précédent récent existe dans `double_click_window`
              -> **double appui**
            * sinon -> **candidat appui court**, validé plus tard par timer
              (le temps de vérifier l’absence de second clic).
        """
        now = time.time()
        self._last_button_event_time = now

        if self._press_start_time is None:
            print("[BUTTON] released sans start_time (ignored)")
            return

        duration = now - self._press_start_time
        self._press_start_time = None

        print(f"[BUTTON] released, duration={duration:.3f}s")

        if duration < self._long_press_threshold:
            # CANDIDAT à un appui court -> peut devenir double-clic
            if (
                self._last_short_release_time > 0.0
                and (now - self._last_short_release_time) <= self._double_click_window
            ):
                # Deuxième clic dans la fenêtre -> double-clic
                print("[BUTTON] double press detected")
                self._last_short_release_time = 0.0

                # Annuler le timer du simple clic précédent
                if self._click_timer is not None and self._click_timer.is_alive():
                    self._click_timer.cancel()
                    self._click_timer = None

                if self.on_double_press:
                    self.on_double_press()
            else:
                # Premier clic : on arme un timer qui validera un simple clic
                print("[BUTTON] short press candidate (waiting for double click)")
                self._last_short_release_time = now

                if self._click_timer is not None and self._click_timer.is_alive():
                    self._click_timer.cancel()

                self._click_timer = Timer(
                    self._double_click_window, self._fire_single_short_press
                )
                self._click_timer.daemon = True
                self._click_timer.start()

        else:
            # Appui long : on annule tout ce qui concerne le double-clic
            print("[BUTTON] long press detected")
            self._last_short_release_time = 0.0
            if self._click_timer is not None and self._click_timer.is_alive():
                self._click_timer.cancel()
                self._click_timer = None

            if self.on_long_press:
                self.on_long_press()
