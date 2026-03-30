# test_text_reader_device.py
from __future__ import annotations

import os
from datetime import datetime

from hardware.platform.pi_camera import PiCamera
from hardware.devices.text_reader_device import TextReaderDevice


def main() -> None:
    print("=== TEST TEXT READER DEVICE ===")

    basename = f"captures/scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs("captures", exist_ok=True)

    camera = PiCamera()
    device = TextReaderDevice(camera)

    clean_txt_path = device.run_full_pipeline(basename)

    print("✅ Pipeline OK")
    print(" - image:", basename + ".jpg")
    print(" - raw  :", basename + "_raw.txt")
    print(" - clean:", clean_txt_path)


if __name__ == "__main__":
    main()
