"""
Charge et valide la configuration centrale depuis ``config/config.toml``.

Le loader renvoie un dictionnaire unique pour toute l'application avec
valeurs par défaut fusionnées puis validées.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Dict

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError as exc:
        raise ImportError(
            "tomli requis pour Python <3.11.\n"
            "Install: pip install tomli --break-system-packages"
        ) from exc


CONFIG_FILE = Path(__file__).parent / "config.toml"


DEFAULT_CONFIG: Dict[str, Any] = {
    "speaker": {
        "voice_model": "fr_FR-siwis-medium",
        "voice_model_dir": "models/piper",
        "default_volume": 75,
        "default_speed": 1.0,
        "verbose_logging": False,
        "notif_wav": "sounds/notif.wav",
        "volume_step": 4,
        "speed_factor_up": 1.25,
        "speed_factor_down": 0.80,
        "min_volume": 0,
        "max_volume": 100,
        "min_speed": 0.5,
        "max_speed": 2.0,
    },
    "gpio": {"numbering": "BCM"},
    "rotary": {
        "pin_a": 17,
        "pin_b": 27,
        "pin_sw": 22,
        "long_press_threshold": 1.0,
        "gesture_settle_delay": 0.20,
        "rotate_button_deadzone": 0.15,
        "min_step_interval": 0.30,
        "double_click_window": 0.40,
        "button_bounce_time": 0.05,
        "steps_per_detent": 4,
        "edge_guard_interval": 0.001,
        "direction_inverted": False,
    },
    "keypad": {
        "row1": 12,
        "row2": 16,
        "row3": 20,
        "row4": 21,
        "col1": 5,
        "col2": 6,
        "col3": 13,
        "col4": 19,
        "scan_interval": 0.02,
        "debounce_time": 0.25,
        "global_volume_up_key": "8",
        "global_volume_down_key": "2",
        "global_speed_up_key": "9",
        "global_speed_down_key": "7",
    },
    "ble": {
        "name_filter": "BDM",
        "address_filter": "",
        "characteristic_uuid": "0000fff4-0000-1000-8000-00805f9b34fb",
        "scan_timeout": 4.0,
        "retry_delay": 15.0,
        "reconnect_delay": 2.0,
        "listen_poll_interval_sec": 0.5,
    },
    "camera": {
        "rotation": 180,
        "timeout_ms": 500,
        "width": 0,
        "height": 0,
    },
    "ocr": {"lang": "fra", "psm": 3},
    "tts": {"engine": "piper"},
    "reading_machine": {
        "work_dir": "/tmp/readforme",
        "basename": "scan",
        "seek_step_sec": 10,
        "ocr_feedback_delay_sec": 0.5,
        "camera_retry_interval_sec": 15.0,
        "camera_missing_message": "Pi Camera non détectée.",
        "camera_ready_message": "Pi Camera détectée. Vous pouvez prendre des photos.",
        "key_capture": "1",
        "key_cancel": "3",
        "key_backward": "4",
        "key_play_pause": "5",
        "key_forward": "6",
        "key_replay": "*",
    },
    "multimeter": {
        "auto_read_interval_sec": 5.0,
        "mode_announce_delay_sec": 0.7,
    },
    "caliper": {
        "ce_pin": 25,
        "csn_pin": 0,
        "channel": 120,
        "address": "00001",
        "auto_read_interval": 4.0,
    },
    "thermometer": {
        "target_url": "http://thermo.local/api",
        "poll_interval": 2.0,
        "request_timeout": 3.0,
    },
    "modes": {
        "enabled": ["datetime", "dummy", "multimeter", "reading_machine", "caliper", "thermometer"]
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _ensure_range(name: str, value: float, minimum: float, maximum: float) -> None:
    if not (minimum <= value <= maximum):
        raise ValueError(f"{name} doit être entre {minimum} et {maximum} (reçu: {value})")


def _validate_config(config: Dict[str, Any]) -> None:
    speaker = config["speaker"]
    keypad = config["keypad"]
    rotary = config["rotary"]
    ble = config["ble"]
    camera = config["camera"]
    ocr = config["ocr"]
    modes = config["modes"]
    multimeter = config["multimeter"]
    reading_machine = config["reading_machine"]
    caliper = config["caliper"]
    thermometer = config["thermometer"]

    valid_voices = {
        "fr_FR-siwis-low",
        "fr_FR-siwis-medium",
        "fr_FR-upmc-medium",
        "fr_FR-tom-medium",
        "fr_FR-gilles-low",
        "fr_FR-mls-medium",
        "fr_FR-mls_1840-low",
    }
    voice = speaker.get("voice_model", "")
    if voice not in valid_voices:
        raise ValueError(
            f"voice_model invalide : '{voice}'. Choix valides : {', '.join(sorted(valid_voices))}"
        )

    _ensure_range("speaker.default_volume", int(speaker["default_volume"]), 0, 100)
    _ensure_range("speaker.default_speed", float(speaker["default_speed"]), 0.5, 2.0)
    _ensure_range("speaker.volume_step", int(speaker["volume_step"]), 1, 100)
    _ensure_range("speaker.speed_factor_up", float(speaker["speed_factor_up"]), 1.0, 3.0)
    _ensure_range("speaker.speed_factor_down", float(speaker["speed_factor_down"]), 0.1, 1.0)
    if int(speaker["min_volume"]) > int(speaker["max_volume"]):
        raise ValueError("speaker.min_volume doit être <= speaker.max_volume")
    if float(speaker["min_speed"]) > float(speaker["max_speed"]):
        raise ValueError("speaker.min_speed doit être <= speaker.max_speed")

    for name in ("scan_interval", "debounce_time"):
        if float(keypad[name]) <= 0:
            raise ValueError(f"keypad.{name} doit être > 0")
    for pin_name in ("row1", "row2", "row3", "row4", "col1", "col2", "col3", "col4"):
        _ensure_range(f"keypad.{pin_name}", int(keypad[pin_name]), 0, 27)

    for key_name in (
        "global_volume_up_key",
        "global_volume_down_key",
        "global_speed_up_key",
        "global_speed_down_key",
    ):
        key_value = str(keypad[key_name])
        if len(key_value) != 1 or key_value not in "0123456789ABCD*#":
            raise ValueError(f"keypad.{key_name} invalide: '{key_value}'")

    for pin_name in ("pin_a", "pin_b", "pin_sw"):
        _ensure_range(f"rotary.{pin_name}", int(rotary[pin_name]), 0, 27)
    for name in (
        "long_press_threshold",
        "gesture_settle_delay",
        "rotate_button_deadzone",
        "min_step_interval",
        "double_click_window",
        "button_bounce_time",
        "edge_guard_interval",
    ):
        if float(rotary[name]) <= 0:
            raise ValueError(f"rotary.{name} doit être > 0")
    if int(rotary["steps_per_detent"]) <= 0:
        raise ValueError("rotary.steps_per_detent doit être > 0")
    if not isinstance(rotary["direction_inverted"], bool):
        raise ValueError("rotary.direction_inverted doit être bool")

    if not str(ble["characteristic_uuid"]).strip():
        raise ValueError("ble.characteristic_uuid ne peut pas être vide")
    for name in ("scan_timeout", "retry_delay", "reconnect_delay", "listen_poll_interval_sec"):
        if float(ble[name]) <= 0:
            raise ValueError(f"ble.{name} doit être > 0")

    if int(camera["rotation"]) not in (0, 90, 180, 270):
        raise ValueError("camera.rotation doit être 0, 90, 180 ou 270")
    if int(camera["timeout_ms"]) < 0:
        raise ValueError("camera.timeout_ms doit être >= 0")
    if int(camera["width"]) < 0 or int(camera["height"]) < 0:
        raise ValueError("camera.width et camera.height doivent être >= 0")

    if not str(ocr["lang"]).strip():
        raise ValueError("ocr.lang ne peut pas être vide")
    if int(ocr["psm"]) < 0:
        raise ValueError("ocr.psm doit être >= 0")

    if float(reading_machine["seek_step_sec"]) <= 0:
        raise ValueError("reading_machine.seek_step_sec doit être > 0")
    if float(reading_machine["ocr_feedback_delay_sec"]) < 0:
        raise ValueError("reading_machine.ocr_feedback_delay_sec doit être >= 0")
    if float(reading_machine["camera_retry_interval_sec"]) <= 0:
        raise ValueError("reading_machine.camera_retry_interval_sec doit être > 0")
    if not str(reading_machine["camera_missing_message"]).strip():
        raise ValueError("reading_machine.camera_missing_message ne peut pas être vide")
    if not str(reading_machine["camera_ready_message"]).strip():
        raise ValueError("reading_machine.camera_ready_message ne peut pas être vide")

    for key_name in (
        "key_capture",
        "key_cancel",
        "key_backward",
        "key_play_pause",
        "key_forward",
        "key_replay",
    ):
        key_value = str(reading_machine[key_name])
        if len(key_value) != 1 or key_value not in "0123456789ABCD*#":
            raise ValueError(f"reading_machine.{key_name} invalide: '{key_value}'")

    if float(multimeter["auto_read_interval_sec"]) <= 0:
        raise ValueError("multimeter.auto_read_interval_sec doit être > 0")
    if float(multimeter["mode_announce_delay_sec"]) < 0:
        raise ValueError("multimeter.mode_announce_delay_sec doit être >= 0")

    _ensure_range("caliper.ce_pin", int(caliper["ce_pin"]), 0, 27)
    _ensure_range("caliper.csn_pin", int(caliper["csn_pin"]), 0, 1)
    _ensure_range("caliper.channel", int(caliper["channel"]), 0, 125)
    if len(str(caliper["address"])) != 5:
        raise ValueError("caliper.address doit contenir exactement 5 caractères")
    if float(caliper["auto_read_interval"]) <= 0:
        raise ValueError("caliper.auto_read_interval doit être > 0")

    if not str(thermometer["target_url"]).strip():
        raise ValueError("thermometer.target_url ne peut pas être vide")
    if float(thermometer["poll_interval"]) <= 0:
        raise ValueError("thermometer.poll_interval doit être > 0")
    if float(thermometer["request_timeout"]) <= 0:
        raise ValueError("thermometer.request_timeout doit être > 0")

    if not isinstance(modes.get("enabled"), list) or not modes["enabled"]:
        raise ValueError("modes.enabled doit être une liste non vide")
    valid_modes = {"datetime", "dummy", "multimeter", "reading_machine", "caliper", "thermometer"}
    unknown_modes = [m for m in modes["enabled"] if m not in valid_modes]
    if unknown_modes:
        raise ValueError(
            "modes.enabled contient des modes inconnus: "
            + ", ".join(unknown_modes)
        )


def load_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Fichier de config introuvable : {CONFIG_FILE}\n"
            "Vérifie que config/config.toml existe."
        )

    with open(CONFIG_FILE, "rb") as f:
        raw_config = tomllib.load(f)

    merged = _deep_merge(DEFAULT_CONFIG, raw_config)
    _validate_config(merged)
    return merged


def get_app_config() -> Dict[str, Any]:
    return load_config()


def get_speaker_config() -> Dict[str, Any]:
    return load_config()["speaker"]
