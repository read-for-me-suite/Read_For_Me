# main.py
"""
Point d'entrée principal de l'assistant technique ReadForMe.

Responsabilité
--------------
Ce script assemble toutes les briques de haut niveau :

1. Speaker          : synthèse vocale centrale (Piper TTS + mplayer).
2. Keypad4x4        : clavier matriciel — instancié ici, passé au
                      ModeManager qui le gère en continu :
                      - touches globales (2/7/8/9) : volume & vitesse,
                        actives dans TOUS les modes.
                      - autres touches : transmises au mode courant via
                        Mode.on_keypad_key(key).
3. Modes            : instances des différents modes disponibles.
                      Chaque mode reçoit uniquement le Speaker.
                      Les modes qui veulent le clavier surchargent
                      on_keypad_key() — aucune injection nécessaire.
4. ModeManager      : orchestrateur des modes (changement, annonces,
                      clavier global).
5. RotarySelector   : sélecteur rotatif GPIO (navigation entre modes).
6. signal.pause()   : boucle principale bloquante laissant vivre les
                      threads/callbacks GPIO, BLE, TTS.

Architecture globale
--------------------
    GPIO (RotarySelector)
        ↓  on_position_changed / on_*_press
    ModeManager ←── Keypad4x4 (touches globales + délégation)
        ↓  set_index / handle_*_press / on_keypad_key
    Mode actif (ModeDateHeure, ModeMultimetre, ModeReadingMachine…)
        ↓  speaker.say / speaker.play
    Speaker  →  Piper TTS  →  mplayer  →  ALSA

Ajout d'un nouveau mode
-----------------------
1. Créer la classe ModeXxx dans modes/mode_xxx.py.
2. L'importer ici.
3. L'ajouter à la liste `modes` avec Speaker comme seul argument.
4. Si le mode veut le clavier : surcharger on_keypad_key(key).
5. Le ModeManager et le RotarySelector s'adaptent automatiquement.

Ajout d'un périphérique partagé
--------------------------------
Instancier le périphérique ici et le passer à ModeManager ou aux
composants concernés. Ne pas passer de hardware directement aux modes
sauf si indispensable (caméra, capteur propre au mode).
"""

from signal import pause

from config.config_loader import get_app_config
from core.speaker import Speaker
from core.mode_manager import ModeManager
from core.mode_registry import MODE_REGISTRY
from hardware.platform.rotary_selector import RotarySelector
from hardware.platform.keypad_4x4 import Keypad4x4, KeypadPins


def _build_modes(config: dict, speaker: Speaker):
    """Construit dynamiquement les modes dans l'ordre défini par config."""
    enabled = config["modes"]["enabled"]
    modes = []

    for mode_name in enabled:
        mode_cls = MODE_REGISTRY.get(mode_name)
        if mode_cls is None:
            raise ValueError(f"[MAIN] Mode inconnu dans [modes].enabled : '{mode_name}'")

        if mode_name == "multimeter":
            mode = mode_cls(
                speaker,
                auto_read_interval=config["multimeter"]["auto_read_interval_sec"],
                driver_config={
                    "name_filter": config["ble"]["name_filter"],
                    "address_filter": (config["ble"]["address_filter"] or None),
                    "characteristic_uuid": config["ble"]["characteristic_uuid"],
                    "scan_timeout": config["ble"]["scan_timeout"],
                    "retry_delay": config["ble"]["retry_delay"],
                    "reconnect_delay": config["ble"]["reconnect_delay"],
                    "listen_poll_interval_sec": config["ble"]["listen_poll_interval_sec"],
                    "mode_announce_delay": config["multimeter"]["mode_announce_delay_sec"],
                },
            )
        elif mode_name == "reading_machine":
            mode = mode_cls(
                speaker,
                reading_config=config["reading_machine"],
                ocr_config=config["ocr"],
                camera_config=config["camera"],
            )
        elif mode_name == "caliper":
            mode = mode_cls(speaker)
            caliper_cfg = config["caliper"]
            if hasattr(mode, "_auto_read_interval"):
                mode._auto_read_interval = float(caliper_cfg["auto_read_interval"])

            driver = getattr(mode, "_driver", None)
            transport = getattr(driver, "_transport", None)
            if transport is not None:
                transport._ce_pin = int(caliper_cfg["ce_pin"])
                transport._csn_pin = int(caliper_cfg["csn_pin"])
                transport._channel = int(caliper_cfg["channel"])
                transport._address = str(caliper_cfg["address"]).encode("utf-8")
        elif mode_name == "thermometer":
            mode = mode_cls(speaker)
            thermo_cfg = config["thermometer"]
            driver = getattr(mode, "_driver", None)
            wifi = getattr(driver, "_wifi", None)
            if wifi is not None:
                wifi._target_url = str(thermo_cfg["target_url"])
                wifi._poll_interval = float(thermo_cfg["poll_interval"])
                wifi._request_timeout = float(thermo_cfg["request_timeout"])
        else:
            mode = mode_cls(speaker)

        modes.append(mode)

    return modes


def main() -> None:
    """
    Initialise et lance l'assistant.

    Ordre d'initialisation
    ----------------------
    1. Speaker       : premier, car les modes en ont besoin.
    2. Annonce       : "Assistant technique prêt." (bloquant).
    3. Keypad4x4     : hardware partagé, instancié avant les modes.
    4. Modes         : injectés avec Speaker + Keypad si nécessaire.
    5. ModeManager   : orchestre les modes (annonce + lifecycle).
    6. RotarySelector: branchement des callbacks GPIO vers ModeManager.
    7. pause()       : boucle principale (bloque le thread principal).
    """

    config = get_app_config()
    speaker = None
    keypad = None

    try:
        # ── 1. Synthèse vocale centrale ───────────────────────────────────
        speaker = Speaker()

        # ── 2. Annonce de démarrage (bloquant : garantit l'ordre) ────────
        speaker.say("Assistant technique prêt.", blocking=True)

        # ── 3. Clavier matriciel partagé ──────────────────────────────────
        keypad_cfg = config["keypad"]
        keypad = Keypad4x4(
            pins=KeypadPins(
                row1=int(keypad_cfg["row1"]),
                row2=int(keypad_cfg["row2"]),
                row3=int(keypad_cfg["row3"]),
                row4=int(keypad_cfg["row4"]),
                col1=int(keypad_cfg["col1"]),
                col2=int(keypad_cfg["col2"]),
                col3=int(keypad_cfg["col3"]),
                col4=int(keypad_cfg["col4"]),
            ),
            scan_interval=float(keypad_cfg["scan_interval"]),
            debounce_time=float(keypad_cfg["debounce_time"]),
        )

        # ── 4. Modes disponibles ──────────────────────────────────────────
        modes = _build_modes(config=config, speaker=speaker)

        # ── 5. Gestionnaire de modes ──────────────────────────────────────
        mode_manager = ModeManager(
            modes=modes,
            speaker=speaker,
            keypad=keypad,
            key_global_vol_up=str(keypad_cfg["global_volume_up_key"]),
            key_global_vol_down=str(keypad_cfg["global_volume_down_key"]),
            key_global_speed_up=str(keypad_cfg["global_speed_up_key"]),
            key_global_speed_down=str(keypad_cfg["global_speed_down_key"]),
            volume_step=int(config["speaker"]["volume_step"]),
            speed_factor_up=float(config["speaker"]["speed_factor_up"]),
            speed_factor_down=float(config["speaker"]["speed_factor_down"]),
        )

        # ── 6. Sélecteur rotatif (GPIO) ───────────────────────────────────
        rotary_cfg = config["rotary"]
        selector = RotarySelector(
            pin_a=int(rotary_cfg["pin_a"]),
            pin_b=int(rotary_cfg["pin_b"]),
            pin_sw=int(rotary_cfg["pin_sw"]),
            positions_count=len(modes),   # Une position par mode
            long_press_threshold=float(rotary_cfg["long_press_threshold"]),
            gesture_settle_delay=float(rotary_cfg["gesture_settle_delay"]),
            rotate_button_deadzone=float(rotary_cfg["rotate_button_deadzone"]),
            min_step_interval=float(rotary_cfg["min_step_interval"]),
            double_click_window=float(rotary_cfg["double_click_window"]),
            button_bounce_time=float(rotary_cfg["button_bounce_time"]),
        )

        # Branchement des callbacks GPIO → ModeManager
        selector.on_position_changed = lambda index, direction: mode_manager.set_index(
            index, direction
        )
        selector.on_short_press = mode_manager.handle_short_press
        selector.on_long_press = mode_manager.handle_long_press
        selector.on_double_press = mode_manager.handle_double_press

        # ── 7. Boucle principale ──────────────────────────────────────────
        pause()
    finally:
        if keypad is not None:
            try:
                keypad.stop()
            except Exception as e:
                print(f"[MAIN] Erreur arrêt keypad: {e}")
        if speaker is not None:
            try:
                speaker.close()
            except Exception as e:
                print(f"[MAIN] Erreur arrêt speaker: {e}")


if __name__ == "__main__":
    main()
