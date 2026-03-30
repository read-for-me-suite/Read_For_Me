from __future__ import annotations

import os
from datetime import datetime

from core.speaker import Speaker
from hardware.devices.text_reader_device import TextReaderDevice
from hardware.platform.pi_camera import PiCamera


def main() -> None:
    print("=== TEST OCR -> WAV ===")
    basename = f"captures/scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs("captures", exist_ok=True)

    speaker = Speaker()
    try:
        reader = TextReaderDevice(PiCamera())
        clean_txt_path = reader.run_full_pipeline(basename)

        with open(clean_txt_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        if not text:
            raise RuntimeError("Texte OCR vide.")

        wav_path = f"{basename}.wav"
        speaker.synthesize_to_file(text, wav_path)

        if not os.path.exists(wav_path):
            raise FileNotFoundError(wav_path)

        print("✅ Pipeline OCR -> WAV OK")
        print(" - image:", basename + ".jpg")
        print(" - raw  :", basename + "_raw.txt")
        print(" - clean:", clean_txt_path)
        print(" - wav  :", wav_path)
    finally:
        speaker.close()


if __name__ == "__main__":
    main()
