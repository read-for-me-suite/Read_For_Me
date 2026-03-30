# core/mode_manager.py
"""
core.mode_manager
=================

Orchestrateur central des modes de l'assistant.

Responsabilités
---------------
1. Gérer la liste des modes et le mode courant.
2. Changer de mode quand le sélecteur rotatif tourne (set_index).
3. Router les événements bouton rotatif vers le mode actif
   (handle_short_press, handle_long_press, handle_double_press).
4. Optionnellement gérer un clavier matriciel 4x4 (Keypad4x4) :
   - Les touches "globales" (volume +/-, vitesse +/-) sont
     interceptées ici et traitées directement via le Speaker.
     Elles sont actives dans TOUS les modes, tout le temps.
   - Les autres touches sont transmises au mode actif via
     Mode.on_keypad_key(key). Seuls les modes qui le souhaitent
     surchargent cette méthode (sinon : no-op).

Architecture du clavier
-----------------------
Le Keypad4x4 est démarré UNE SEULE FOIS dans __init__ et tourne
en continu, contrairement à l'ancienne approche où chaque mode
le démarrait/arrêtait dans on_enter/on_exit.

Cela permet aux touches globales d'être disponibles dans n'importe
quel mode, sans aucune gestion spécifique dans les modes eux-mêmes.

Touches globales (non-surchargeables par les modes)
----------------------------------------------------
    KEY_GLOBAL_VOL_UP   = "8"   → volume + VOLUME_STEP
    KEY_GLOBAL_VOL_DOWN = "2"   → volume - VOLUME_STEP
    KEY_GLOBAL_SPEED_UP = "9"   → vitesse × SPEED_FACTOR_UP
    KEY_GLOBAL_SPEED_DOWN = "7" → vitesse × SPEED_FACTOR_DOWN

Un bip de feedback est joué à chaque changement (aigu=+, grave=-).
"""

from __future__ import annotations

from typing import List, Optional, Set

from core.mode_base import Mode
from core.speaker import Speaker


class ModeManager:
    """
    Chef d'orchestre des modes de l'assistant.

    Paramètres
    ----------
    modes :
        Liste ordonnée de modes (index 0 = position 0 du rotatif).
    speaker :
        Speaker central — utilisé pour les annonces et les réglages
        globaux (volume, vitesse, bip).
    keypad :
        Instance de Keypad4x4 (optionnel). Si fourni, le ModeManager
        démarre le clavier et gère les touches globales + la délégation
        vers le mode courant. Si None, le clavier est ignoré.
    volume_step :
        Nombre de points ALSA ajoutés/retirés par pression (0–100).
    speed_factor_up :
        Multiplicateur appliqué à la vitesse pour une augmentation.
    speed_factor_down :
        Multiplicateur appliqué à la vitesse pour une diminution.
    """

    # ── Touches globales (réservées — non transmises aux modes) ──────────
    KEY_GLOBAL_VOL_UP = "8"
    KEY_GLOBAL_VOL_DOWN = "2"
    KEY_GLOBAL_SPEED_UP = "9"
    KEY_GLOBAL_SPEED_DOWN = "7"

    GLOBAL_KEYS = frozenset(
        {
        KEY_GLOBAL_VOL_UP,
        KEY_GLOBAL_VOL_DOWN,
        KEY_GLOBAL_SPEED_UP,
        KEY_GLOBAL_SPEED_DOWN,
        }
    )

    # ── Paramètres des réglages globaux ──────────────────────────────────
    VOLUME_STEP: int = 4
    SPEED_FACTOR_UP: float = 1.25
    SPEED_FACTOR_DOWN: float = 0.80

    def __init__(
        self,
        modes: List[Mode],
        speaker: Speaker,
        keypad=None,          # type: Optional[Keypad4x4]  (import évité pour découplage)
        key_global_vol_up: str = KEY_GLOBAL_VOL_UP,
        key_global_vol_down: str = KEY_GLOBAL_VOL_DOWN,
        key_global_speed_up: str = KEY_GLOBAL_SPEED_UP,
        key_global_speed_down: str = KEY_GLOBAL_SPEED_DOWN,
        volume_step: int = VOLUME_STEP,
        speed_factor_up: float = SPEED_FACTOR_UP,
        speed_factor_down: float = SPEED_FACTOR_DOWN,
    ) -> None:
        """
        Initialise le ModeManager.

        Démarre avec le premier mode (index 0) :
        - annonce vocale du mode,
        - appel de on_enter() sur ce mode.

        Si un keypad est fourni, il est démarré immédiatement et tourne
        en continu pour toute la durée de vie de l'assistant.
        """
        if not modes:
            raise ValueError("[ModeManager] La liste des modes ne peut pas être vide.")

        self._modes: List[Mode] = modes
        self._speaker: Speaker = speaker

        self._key_global_vol_up = key_global_vol_up
        self._key_global_vol_down = key_global_vol_down
        self._key_global_speed_up = key_global_speed_up
        self._key_global_speed_down = key_global_speed_down
        self._global_keys: Set[str] = {
            self._key_global_vol_up,
            self._key_global_vol_down,
            self._key_global_speed_up,
            self._key_global_speed_down,
        }
        self._volume_step = int(volume_step)
        self._speed_factor_up = float(speed_factor_up)
        self._speed_factor_down = float(speed_factor_down)

        self._current_index: int = 0
        self._current_mode: Mode = self._modes[0]

        # ── Keypad (optionnel, géré en continu) ──────────────────────────
        self._keypad = keypad
        if keypad is not None:
            self._setup_keypad(keypad)

        # ── Démarrage : annonce d'abord, puis on_enter ───────────────────
        # L'annonce passe en queue AVANT que on_enter() ne déclenche
        # d'éventuelles annonces propres au mode (ex : scan BLE).
        self._announce_current_mode()
        self._current_mode.on_enter()

    # ─────────────────────────────────────────────────────────────────────
    # Propriétés publiques
    # ─────────────────────────────────────────────────────────────────────

    @property
    def current_index(self) -> int:
        """Index du mode courant (0-based)."""
        return self._current_index

    @property
    def current_mode(self) -> Mode:
        """Instance du mode courant."""
        return self._current_mode

    # ─────────────────────────────────────────────────────────────────────
    # Gestion du clavier (interne)
    # ─────────────────────────────────────────────────────────────────────

    def _setup_keypad(self, keypad) -> None:
        """
        Branche le ModeManager sur le clavier et démarre le scan.

        Le clavier tourne en continu — il n'est jamais arrêté entre
        les changements de mode. Les touches globales sont traitées
        ici, les autres sont déléguées au mode courant.
        """
        keypad.on_key = self._on_keypad_key
        keypad.start()

    def _on_keypad_key(self, key: str) -> None:
        """Callback du driver keypad : route vers handle_key_pressed()."""
        self.handle_key_pressed(key)

    def handle_key_pressed(self, key: str) -> None:
        """
        Point d'entrée unique pour toutes les touches du clavier.

        Traitement
        ----------
        1. Si la touche est "globale" → action immédiate (volume/vitesse)
           + bip de feedback. Ne parvient JAMAIS au mode courant.
        2. Sinon → délégation à self._current_mode.on_keypad_key(key).
           Si le mode ne surcharge pas cette méthode, c'est un no-op.
        """
        if key in self._global_keys:
            self._handle_global_key(key)
        else:
            self._current_mode.on_key_pressed(key)

    def _handle_global_key(self, key: str) -> None:
        """
        Exécute l'action associée à une touche globale.

        Touches prises en charge :
        - KEY_GLOBAL_VOL_UP   ("8") : volume + VOLUME_STEP
        - KEY_GLOBAL_VOL_DOWN ("2") : volume - VOLUME_STEP
        - KEY_GLOBAL_SPEED_UP ("9") : vitesse × SPEED_FACTOR_UP
        - KEY_GLOBAL_SPEED_DOWN ("7") : vitesse × SPEED_FACTOR_DOWN

        Un bip sonore est joué immédiatement pour confirmer chaque action.
        """
        if key == self._key_global_vol_up:
            new_vol = min(100, self._speaker.get_volume() + self._volume_step)
            self._speaker.set_volume_global(new_vol)
            self._speaker.play_notification(blocking=False)

        elif key == self._key_global_vol_down:
            new_vol = max(0, self._speaker.get_volume() - self._volume_step)
            self._speaker.set_volume_global(new_vol)
            self._speaker.play_notification(blocking=False)

        elif key == self._key_global_speed_up:
            new_speed = min(2.0, round(
                self._speaker.get_speed() * self._speed_factor_up, 2
            ))
            self._speaker.set_global_speed(new_speed)
            self._speaker.play_notification(blocking=False)

        elif key == self._key_global_speed_down:
            new_speed = max(0.5, round(
                self._speaker.get_speed() * self._speed_factor_down, 2
            ))
            self._speaker.set_global_speed(new_speed)
            self._speaker.play_notification(blocking=False)

    # ─────────────────────────────────────────────────────────────────────
    # Changement de mode (rotatif)
    # ─────────────────────────────────────────────────────────────────────

    def _announce_current_mode(self) -> None:
        """
        Annonce le nom du mode courant via le Speaker.

        Format : "Mode X : <nom_du_mode>"

        Appelé :
        - au démarrage (index 0),
        - après chaque changement de mode dans set_index().
        """
        message = f"Mode {self._current_index + 1} : {self._current_mode.name}"
        self._speaker.say(message, blocking=False)

    def set_index(self, new_index: int, direction: Optional[str] = None) -> None:
        """
        Change le mode actif.

        Appelé par RotarySelector lorsqu'une rotation stable est détectée.

        Paramètres
        ----------
        new_index :
            Nouvel index (0 ≤ index < len(modes)).
        direction :
            Sens de rotation ("sens horaire" / "sens inverse") — utilisé
            pour les logs. Pas d'effet fonctionnel pour l'instant.

        Comportement
        ------------
        1. Coupe tout audio en cours (stop_all_audio).
        2. on_exit() sur l'ancien mode.
        3. Annonce le nouveau mode (nom mis en queue en premier).
        4. on_enter() sur le nouveau mode.
        """
        if new_index == self._current_index:
            return  # Aucun changement

        if not (0 <= new_index < len(self._modes)):
            return  # Index invalide — ignoré silencieusement

        # 1. Couper tout audio (annonces + lecture longue de l'ancien mode)
        self._speaker.stop_all_audio()

        # 2. Quitter l'ancien mode
        self._current_mode.on_exit()

        # 3. Mettre à jour le mode courant
        self._current_index = new_index
        self._current_mode = self._modes[new_index]

        # 4. Annoncer EN PREMIER : garantit que "Mode X : …" est entendu
        #    avant les annonces propres au mode (ex : scan BLE multimètre).
        self._announce_current_mode()

        # 5. Entrer dans le nouveau mode
        self._current_mode.on_enter()

    # ─────────────────────────────────────────────────────────────────────
    # Événements bouton rotatif
    # ─────────────────────────────────────────────────────────────────────

    def handle_short_press(self) -> None:
        """
        Appui court sur le bouton rotatif.

        Délégué au mode courant via on_short_press().
        """
        self._current_mode.on_short_press()

    def handle_long_press(self) -> None:
        """
        Appui long sur le bouton rotatif.

        Délégué au mode courant via on_long_press().
        """
        self._current_mode.on_long_press()

    def handle_double_press(self) -> None:
        """
        Double appui rapide sur le bouton rotatif.

        Délégué au mode courant via on_double_press().
        """
        self._current_mode.on_double_press()
