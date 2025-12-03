# hardware/rotary_selector.py
import time
from threading import Timer
from typing import Callable, Optional

from gpiozero import Button


class RotarySelector:
    """
    Driver pour le rotateur numérique + bouton poussoir.

    - Ne connaît PAS les modes, ni la synthèse vocale.
    - Gère :
        * une position "mode" (0 .. positions_count-1),
        * le sens des gestes de rotation,
        * les appuis court / long sur le bouton.

    Stratégie UX :
    - Plusieurs impulsions rapprochées dans le MEME sens = 1 seul geste
      => 1 seul changement de mode.
    - Allers-retours très rapides sont absorbés / limités par un délai
      minimum entre deux changements de mode.
    - On ignore les impulsions proches d’un appui sur le bouton.
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
    ) -> None:
        self.positions_count = positions_count

        # Position de mode vue par le reste du système
        self.position: int = 0

        # Geste en cours
        self._pending_direction: Optional[str] = None
        self.last_direction: Optional[str] = None

        # Stats / debug
        self._gesture_count: int = 0

        # Gestion du bouton
        self._press_start_time: Optional[float] = None
        self._long_press_threshold = long_press_threshold

        # Callbacks externes
        self.on_position_changed: Optional[Callable[[int, str], None]] = None
        self.on_short_press: Optional[Callable[[], None]] = None
        self.on_long_press: Optional[Callable[[], None]] = None

        # Gestion de la stabilisation de geste
        self._gesture_settle_delay = gesture_settle_delay
        self._gesture_timer: Optional[Timer] = None

        # Zone morte rotation <-> bouton
        self._last_button_event_time: float = 0.0
        self._rotate_button_deadzone = rotate_button_deadzone

        # Intervalle mini entre deux changements de mode
        self._min_step_interval = min_step_interval
        self._last_step_time: float = 0.0

        # Configuration des broches avec gpiozero
        self.channel_a = Button(pin_a)
        self.channel_b = Button(pin_b)

        # Bouton poussoir
        self.button = Button(pin_sw, pull_up=True, bounce_time=0.05)

        # Wiring des événements
        self.channel_a.when_pressed = self._on_channel_a_edge
        self.button.when_pressed = self._on_button_pressed
        self.button.when_released = self._on_button_released

    # =========================
    #   Gestion de la rotation
    # =========================

    def _on_channel_a_edge(self) -> None:
        """
        Callback interne appelée sur un front du canal A.

        On détecte juste un MOUVEMENT + son SENS, sans changer immédiatement de mode.
        Le changement réel sera appliqué quand le geste sera stabilisé (Timer).
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

        # Si aucun geste en cours, on démarre un nouveau geste
        # Si un geste est déjà en cours, on met simplement à jour la direction
        self._pending_direction = direction
        self.last_direction = direction

        print(f"[ROTARY] impulsion, direction courante du geste = {direction}")

        # (Re)planifier le Timer de stabilisation du geste
        self._schedule_gesture_timer()

    def _schedule_gesture_timer(self) -> None:
        """Programme (ou reprogramme) le Timer qui validera un geste stabilisé."""
        if self._gesture_timer is not None and self._gesture_timer.is_alive():
            self._gesture_timer.cancel()

        self._gesture_timer = Timer(
            self._gesture_settle_delay, self._validate_gesture
        )
        self._gesture_timer.daemon = True
        self._gesture_timer.start()

    def _validate_gesture(self) -> None:
        """
        Appelé après gesture_settle_delay sans nouvelle impulsion.

        À ce moment-là, on considère que le geste est fini, et on applique
        AU PLUS UN changement de mode (en fonction du sens du geste).
        """
        if self._pending_direction is None:
            # Rien à faire
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

        # Notifier l’extérieur (ModeManager)
        if self.on_position_changed:
            self.on_position_changed(self.position, self._pending_direction)

        # Geste terminé
        self._pending_direction = None

    # =========================
    #   Gestion du bouton
    # =========================

    def _on_button_pressed(self) -> None:
        """Mémorise le moment de l'appui."""
        self._press_start_time = time.time()
        self._last_button_event_time = self._press_start_time
        print("[BUTTON] pressed")

    def _on_button_released(self) -> None:
        """Calcule la durée de l'appui et décide court / long."""
        now = time.time()
        self._last_button_event_time = now

        if self._press_start_time is None:
            print("[BUTTON] released sans start_time (ignored)")
            return

        duration = now - self._press_start_time
        self._press_start_time = None

        print(f"[BUTTON] released, duration={duration:.3f}s")

        if duration < self._long_press_threshold:
            if self.on_short_press:
                print("[BUTTON] short press detected")
                self.on_short_press()
        else:
            if self.on_long_press:
                print("[BUTTON] long press detected")
                self.on_long_press()
