from __future__ import annotations

import os
import pathlib
import threading
import time
import traceback
from typing import Optional, Dict, Any

from core.mode_base import Mode
from core.speaker import Speaker, PlaybackHandle
from hardware.platform.pi_camera import PiCamera, CameraConfig
from hardware.devices.text_reader_device import TextReaderDevice, OCRConfig


class ModeReadingMachine(Mode):
    """
    Mode "Machine à lire" : capture caméra -> OCR -> synthèse -> lecture.

    Ce mode ne pilote pas directement le keypad matériel : il reçoit les
    touches non-globales via ModeManager.on_key_pressed().
    """

    KEY_CAPTURE = "1"
    KEY_CANCEL = "3"
    KEY_BACKWARD = "4"
    KEY_PLAY_PAUSE = "5"
    KEY_FORWARD = "6"
    KEY_REPLAY = "*"

    def __init__(
        self,
        speaker: Speaker,
        *,
        reading_config: Optional[Dict[str, Any]] = None,
        ocr_config: Optional[Dict[str, Any]] = None,
        camera_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name="Machine à lire")
        self.speaker = speaker

        reading_cfg = reading_config or {}
        ocr_cfg = ocr_config or {}
        cam_cfg = camera_config or {}

        self._work_dir = str(reading_cfg.get("work_dir", "/tmp/readforme"))
        self._basename_name = str(reading_cfg.get("basename", "scan"))
        os.makedirs(self._work_dir, exist_ok=True)
        self._basename = os.path.join(self._work_dir, self._basename_name)

        self._key_capture = str(reading_cfg.get("key_capture", self.KEY_CAPTURE))
        self._key_cancel = str(reading_cfg.get("key_cancel", self.KEY_CANCEL))
        self._key_backward = str(reading_cfg.get("key_backward", self.KEY_BACKWARD))
        self._key_play_pause = str(reading_cfg.get("key_play_pause", self.KEY_PLAY_PAUSE))
        self._key_forward = str(reading_cfg.get("key_forward", self.KEY_FORWARD))
        self._key_replay = str(reading_cfg.get("key_replay", self.KEY_REPLAY))

        self._seek_step_sec = int(reading_cfg.get("seek_step_sec", 10))
        self._ocr_feedback_delay_sec = float(reading_cfg.get("ocr_feedback_delay_sec", 0.5))
        self._camera_retry_interval_sec = float(reading_cfg.get("camera_retry_interval_sec", 15.0))
        self._camera_capture_retry_attempts = int(reading_cfg.get("camera_capture_retry_attempts", 2))
        self._camera_capture_retry_delay_sec = float(reading_cfg.get("camera_capture_retry_delay_sec", 1.5))
        self._pipeline_join_timeout_sec = float(reading_cfg.get("pipeline_join_timeout_sec", 4.0))
        self._monitor_announce_every_retry = bool(reading_cfg.get("camera_announce_every_retry", True))

        project_root = pathlib.Path(__file__).parent.parent

        self._sound_capture_shutter = self._resolve_path(
            project_root,
            str(reading_cfg.get("sound_capture_shutter", "sounds/camera-shutter.wav")),
        )
        self._sound_pipeline_start = self._resolve_path(
            project_root,
            str(reading_cfg.get("sound_pipeline_start", "sounds/rm_pipeline_start.wav")),
        )
        self._sound_cancel = self._resolve_path(
            project_root,
            str(reading_cfg.get("sound_cancel", "sounds/rm_cancel.wav")),
        )
        self._sound_error = self._resolve_path(
            project_root,
            str(reading_cfg.get("sound_error", "sounds/rm_error.wav")),
        )
        self._sound_camera_missing = self._resolve_path(
            project_root,
            str(reading_cfg.get("sound_camera_missing", "sounds/rm_camera_missing.wav")),
        )
        self._sound_camera_ready = self._resolve_path(
            project_root,
            str(reading_cfg.get("sound_camera_ready", "sounds/rm_camera_ready.wav")),
        )
        self._sound_camera_busy = self._resolve_path(
            project_root,
            str(reading_cfg.get("sound_camera_busy", "sounds/rm_camera_busy.wav")),
        )

        self._msg_pipeline_start = str(
            reading_cfg.get("prompt_pipeline_start", "Analyse du document en cours.")
        )
        self._msg_cancel = str(reading_cfg.get("prompt_cancel", "Lecture annulée."))
        self._msg_error = str(
            reading_cfg.get("prompt_error", "Une erreur est survenue pendant la lecture.")
        )
        self._msg_camera_missing = str(
            reading_cfg.get(
                "prompt_camera_missing",
                "Pi Camera non détectée. Nouvelle tentative dans 15 secondes.",
            )
        )
        self._msg_camera_ready = str(
            reading_cfg.get(
                "prompt_camera_ready",
                "Pi Camera détectée. Vous pouvez prendre des photos.",
            )
        )
        self._msg_camera_busy = str(
            reading_cfg.get(
                "prompt_camera_busy",
                "La Pi Camera est occupée par un autre processus.",
            )
        )

        self._audio_prompts = {
            "pipeline_start": self._sound_pipeline_start,
            "cancel": self._sound_cancel,
            "error": self._sound_error,
            "camera_missing": self._sound_camera_missing,
            "camera_ready": self._sound_camera_ready,
            "camera_busy": self._sound_camera_busy,
            "capture_shutter": self._sound_capture_shutter,
        }

        camera_obj_cfg = CameraConfig(
            rotation=int(cam_cfg.get("rotation", 180)),
            timeout_ms=int(cam_cfg.get("timeout_ms", 500)),
            width=int(cam_cfg.get("width", 0)) or None,
            height=int(cam_cfg.get("height", 0)) or None,
            command_timeout_sec=float(cam_cfg.get("command_timeout_sec", 10.0)),
        )

        self._device = TextReaderDevice(
            camera=PiCamera(camera_obj_cfg),
            ocr=OCRConfig(
                lang=str(ocr_cfg.get("lang", "fra")),
                psm=int(ocr_cfg.get("psm", 3)),
                oem=int(ocr_cfg.get("oem", 1)),
                preprocess_enabled=bool(ocr_cfg.get("preprocess_enabled", True)),
                autocontrast_cutoff=int(ocr_cfg.get("autocontrast_cutoff", 2)),
                sharpen_factor=float(ocr_cfg.get("sharpen_factor", 1.4)),
                threshold=int(ocr_cfg.get("threshold", 160)),
                timeout_sec=float(ocr_cfg.get("timeout_sec", 20.0)),
            ),
        )

        self._wav_path = f"{self._basename}.wav"
        self._txt_path = f"{self._basename}.txt"

        self._handle: Optional[PlaybackHandle] = None
        self._paused: bool = False

        self._job_lock = threading.Lock()
        self._busy: bool = False
        self._cancel_event = threading.Event()
        self._pipeline_thread: Optional[threading.Thread] = None

        self._camera_state_lock = threading.Lock()
        self._camera_available = False
        self._camera_monitor_stop = threading.Event()
        self._camera_monitor_thread: Optional[threading.Thread] = None

    @staticmethod
    def _resolve_path(project_root: pathlib.Path, configured_path: str) -> pathlib.Path:
        p = pathlib.Path(configured_path)
        if p.is_absolute():
            return p
        return project_root / p

    def on_enter(self) -> None:
        self._cancel_event.clear()
        available = self._is_camera_available()
        self._set_camera_available(available)
        if not available:
            self._start_camera_monitor()

    def on_exit(self) -> None:
        self._cancel_event.set()
        self._stop_playback()
        self._stop_camera_monitor()
        self._join_pipeline_thread()
        self._paused = False

    def on_short_press(self) -> None:
        pass

    def on_long_press(self) -> None:
        pass

    def on_keypad_key(self, key: str) -> None:
        dispatch = {
            self._key_capture: self._start_capture_pipeline,
            self._key_play_pause: self._toggle_pause,
            self._key_forward: lambda: self._seek(+self._seek_step_sec),
            self._key_backward: lambda: self._seek(-self._seek_step_sec),
            self._key_cancel: self._cancel,
            self._key_replay: self._replay,
        }
        action = dispatch.get(key)
        if action is not None:
            action()

    def _start_capture_pipeline(self) -> None:
        with self._job_lock:
            if self._busy:
                self._play_prompt("error")
                return

            if not self._is_camera_available():
                self._set_camera_available(False)
                self._start_camera_monitor()
                self._play_prompt("camera_missing")
                return

            self._busy = True
            self._cancel_event.clear()

        self.speaker.stop_all_audio()
        self._play_prompt("capture_shutter")

        t = threading.Thread(
            target=self._run_pipeline,
            name="ReadingMachinePipeline",
            daemon=False,
        )
        self._pipeline_thread = t
        t.start()

    def _run_pipeline(self) -> None:
        try:
            if self._cancel_event.is_set():
                return

            self._play_prompt("pipeline_start")
            if self._cancel_event.wait(self._ocr_feedback_delay_sec):
                return

            clean_txt_path = self._run_capture_ocr_with_retry()
            if clean_txt_path is None or self._cancel_event.is_set():
                return

            with open(clean_txt_path, "r", encoding="utf-8") as f:
                text = f.read().strip()

            if not text:
                self._play_prompt("error")
                return

            self.speaker.synthesize_to_file(text, self._wav_path)

            if self._cancel_event.is_set():
                return

            if not os.path.exists(self._wav_path):
                self._play_prompt("error")
                return

            self._start_playback(self._wav_path)

        except Exception as exc:
            print(f"[READING_MACHINE] Erreur pipeline: {exc}")
            traceback.print_exc()
            if self._is_camera_busy_error(exc):
                self._announce_camera_busy_debug()
                self._play_prompt("camera_busy")
            else:
                self._play_prompt("error")

            if not self._is_camera_available():
                self._set_camera_available(False)
                self._start_camera_monitor()

        finally:
            with self._job_lock:
                self._busy = False

    def _run_capture_ocr_with_retry(self) -> Optional[str]:
        attempts = max(1, self._camera_capture_retry_attempts)
        last_exc: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            if self._cancel_event.is_set():
                return None

            try:
                return self._device.run_full_pipeline(self._basename)
            except Exception as exc:
                last_exc = exc

                if attempt < attempts:
                    print(
                        f"[READING_MACHINE] Retry capture/OCR {attempt}/{attempts} "
                        f"dans {self._camera_capture_retry_delay_sec}s"
                    )
                    if self._cancel_event.wait(self._camera_capture_retry_delay_sec):
                        return None

        if last_exc is not None:
            raise last_exc
        return None

    @staticmethod
    def _is_camera_busy_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        patterns = (
            "resource busy",
            "device or resource busy",
            "pipeline handler in use",
            "camera in use",
            "failed to acquire camera",
            "v4l2",
        )
        return any(p in msg for p in patterns)

    def _announce_camera_busy_debug(self) -> None:
        processes = PiCamera.detect_blocking_processes()
        if processes:
            print("[READING_MACHINE] Processus potentiellement bloquants caméra:")
            for proc in processes:
                print(f"[READING_MACHINE]   - {proc}")

    def _set_camera_available(self, available: bool) -> None:
        with self._camera_state_lock:
            self._camera_available = available

    def _is_camera_available_cached(self) -> bool:
        with self._camera_state_lock:
            return self._camera_available

    def _is_camera_available(self) -> bool:
        available, _diag = PiCamera.probe()
        return bool(available)

    def _start_camera_monitor(self) -> None:
        if self._camera_monitor_thread is not None and self._camera_monitor_thread.is_alive():
            return

        self._camera_monitor_stop.clear()
        self._camera_monitor_thread = threading.Thread(
            target=self._camera_monitor_loop,
            name="ReadingMachineCameraMonitor",
            daemon=False,
        )
        self._camera_monitor_thread.start()

    def _stop_camera_monitor(self) -> None:
        self._camera_monitor_stop.set()
        if self._camera_monitor_thread is not None and self._camera_monitor_thread.is_alive():
            self._camera_monitor_thread.join(timeout=self._camera_retry_interval_sec + 1.0)
        self._camera_monitor_thread = None

    def _camera_monitor_loop(self) -> None:
        missing_announced = False
        while not self._camera_monitor_stop.is_set():
            available = self._is_camera_available()

            if available:
                self._set_camera_available(True)
                if missing_announced:
                    self._play_prompt("camera_ready")
                return

            self._set_camera_available(False)
            if self._monitor_announce_every_retry or not missing_announced:
                self._play_prompt("camera_missing")
                missing_announced = True

            if self._camera_monitor_stop.wait(self._camera_retry_interval_sec):
                return

    def _join_pipeline_thread(self) -> None:
        if self._pipeline_thread is None:
            return
        if self._pipeline_thread.is_alive():
            self._pipeline_thread.join(timeout=self._pipeline_join_timeout_sec)
            if self._pipeline_thread.is_alive():
                print("[READING_MACHINE] Pipeline toujours actif après timeout de join.")
        self._pipeline_thread = None

    def _cancel(self) -> None:
        self._cancel_event.set()
        self._stop_playback()
        self._play_prompt("cancel")

    def _replay(self) -> None:
        if not os.path.exists(self._wav_path):
            self._play_prompt("error")
            return
        self._start_playback(self._wav_path)

    def _start_playback(self, wav_path: str) -> None:
        self._stop_playback()
        self._paused = False
        self._handle = self.speaker.play(wav_path)

    def _stop_playback(self) -> None:
        if self._handle is not None:
            try:
                self._handle.stop()
            except Exception:
                pass
        self._handle = None
        self._paused = False

    def _toggle_pause(self) -> None:
        if self._handle is None:
            return

        if not self._paused:
            self._handle.pause()
            self._paused = True
        else:
            self._handle.resume()
            self._paused = False

    def _seek(self, seconds: int) -> None:
        if self._handle is not None:
            self._handle.seek(seconds)

    def _play_prompt(self, name: str) -> None:
        path = self._audio_prompts.get(name)
        if path is None:
            return

        if not path.exists():
            print(f"[READING_MACHINE] Son introuvable: {path}")
            return

        try:
            self.speaker.play_sound(str(path), blocking=False)
        except Exception as exc:
            print(f"[READING_MACHINE] Échec lecture son {path}: {exc}")
