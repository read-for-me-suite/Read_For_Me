from __future__ import annotations

import os
import time
import wave

from core.speaker import PlaybackHandle
import modes.mode_reading_machine as reading_machine_module


class _FakePlayback:
    def __init__(self) -> None:
        self.paused = False
        self.seek_events: list[int] = []
        self.stopped = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def stop(self) -> None:
        self.stopped = True

    def seek(self, seconds: int) -> None:
        self.seek_events.append(seconds)

    def set_speed(self, speed: float) -> None:
        _ = speed


class FakeSpeaker:
    def __init__(self) -> None:
        self.played_files: list[str] = []
        self.sounds: list[str] = []
        self.playback = _FakePlayback()

    def stop_all_audio(self) -> None:
        return

    def speak(self, text: str) -> None:
        _ = text

    def play_sound(self, path: str, blocking: bool = False) -> None:
        _ = blocking
        self.sounds.append(path)

    def synthesize_to_file(self, text: str, output_path: str) -> None:
        _ = text
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with wave.open(output_path, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(22050)
            f.writeframes(b"\x00\x00" * 2205)

    def play(self, path: str) -> PlaybackHandle:
        self.played_files.append(path)
        return PlaybackHandle(self.playback)


class FakeTextReaderDevice:
    def __init__(self, text_path: str) -> None:
        self._text_path = text_path

    def run_full_pipeline(self, basename: str) -> str:
        _ = basename
        os.makedirs(os.path.dirname(self._text_path) or ".", exist_ok=True)
        with open(self._text_path, "w", encoding="utf-8") as f:
            f.write("Texte de test pour la machine à lire.")
        return self._text_path


class _FakePiCamera:
    def __init__(self, *_args, **_kwargs) -> None:
        return

    @staticmethod
    def is_available() -> bool:
        return True


def _wait_pipeline_done(mode: reading_machine_module.ModeReadingMachine, timeout: float = 5.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        with mode._job_lock:
            if not mode._busy:
                return
        time.sleep(0.05)
    raise TimeoutError("Le pipeline de simulation ne se termine pas.")


def main() -> None:
    print("=== TEST MODE READING MACHINE (SIMULATION) ===")
    reading_machine_module.PiCamera = _FakePiCamera  # type: ignore[assignment]

    fake_speaker = FakeSpeaker()
    mode = reading_machine_module.ModeReadingMachine(fake_speaker)  # type: ignore[arg-type]

    mode._basename = "/tmp/readforme/sim_scan"
    mode._wav_path = f"{mode._basename}.wav"
    mode._txt_path = f"{mode._basename}.txt"
    mode._device = FakeTextReaderDevice(mode._txt_path)  # type: ignore[assignment]

    mode.on_enter()
    mode.on_keypad_key(mode.KEY_CAPTURE)
    _wait_pipeline_done(mode)

    if not os.path.exists(mode._wav_path):
        raise FileNotFoundError(mode._wav_path)
    if not fake_speaker.played_files:
        raise RuntimeError("Aucune lecture déclenchée après KEY_CAPTURE.")

    mode.on_keypad_key(mode.KEY_PLAY_PAUSE)
    mode.on_keypad_key(mode.KEY_PLAY_PAUSE)
    mode.on_keypad_key(mode.KEY_FORWARD)
    mode.on_keypad_key(mode.KEY_BACKWARD)
    mode.on_keypad_key(mode.KEY_REPLAY)
    mode.on_keypad_key(mode.KEY_CANCEL)
    mode.on_exit()

    print("✅ Simulation mode machine à lire OK")
    print(" - WAV généré :", mode._wav_path)
    print(" - lectures   :", len(fake_speaker.played_files))
    print(" - seek events:", fake_speaker.playback.seek_events)


if __name__ == "__main__":
    main()
