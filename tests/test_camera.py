"""
Test simple du driver PiCamera.

- Vérifie que la caméra est détectée
- Capture une image test dans le dossier ./captures
"""

import os
from datetime import datetime

from hardware.platform.pi_camera import PiCamera, CameraConfig


def main() -> None:
    print("=== TEST CAMERA ===")

    if not PiCamera.is_available():
        print("❌ Aucune caméra détectée par rpicam/libcamera.")
        return

    print("✅ Caméra détectée")

    cam = PiCamera(
        CameraConfig(
            rotation=180,
            timeout_ms=800,  
        )
    )

    os.makedirs("captures", exist_ok=True)
    filename = datetime.now().strftime("captures/test_%Y%m%d_%H%M%S.jpg")

    try:
        path = cam.capture(filename)
        print(f"📸 Image capturée avec succès : {path}")
    except Exception as e:
        print(f"❌ Erreur capture : {e}")


if __name__ == "__main__":
    main()
