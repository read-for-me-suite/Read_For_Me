# hardware/platform/pi_camera.py
"""
hardware.platform.pi_camera
===========================

Driver bas niveau pour la caméra Raspberry Pi (libcamera / rpicam).

Responsabilité
--------------
- Capturer une image via `rpicam-still` (Bookworm) ou `libcamera-still` (legacy)
- Ne contient AUCUNE logique métier (pas d'OCR, pas de TTS, pas de mode)

API
---
- PiCamera.capture(output_path) -> str
    Capture une photo et l'écrit dans output_path.

Notes
-----
- Utilise `subprocess.run` (plus fiable que os.system).
- Lève des exceptions explicites en cas d'erreur.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class CameraConfig:
    """
    Configuration de capture.

    rotation :
        Rotation appliquée par l'outil de capture (0/90/180/270)
    timeout_ms :
        Délai avant capture (ms). Permet auto-exposure stable.
    width / height :
        Optionnels. Si None, l'outil choisit par défaut.
    """
    rotation: int = 180
    timeout_ms: int = 500
    width: Optional[int] = None
    height: Optional[int] = None
    command_timeout_sec: float = 10.0


class PiCamera:
    """
    Caméra Raspberry Pi via rpicam-still (recommandé) ou libcamera-still (legacy).
    """

    def __init__(self, config: CameraConfig | None = None) -> None:
        self._config = config or CameraConfig()
        self._cmd_capture = self._detect_capture_cmd()
        self._cmd_list = self._detect_list_cmd()

    @staticmethod
    def _detect_capture_cmd() -> str:
        """
        Détecte la commande de capture disponible.
        Priorité à rpicam-still (Bookworm), fallback libcamera-still.
        """
        if shutil.which("rpicam-still"):
            return "rpicam-still"
        if shutil.which("libcamera-still"):
            return "libcamera-still"
        raise RuntimeError("Aucune commande caméra trouvée (rpicam-still/libcamera-still).")

    @staticmethod
    def _detect_list_cmd() -> str:
        """
        Détecte la commande de listing des caméras disponible.
        """
        if shutil.which("rpicam-hello"):
            return "rpicam-hello"
        if shutil.which("libcamera-hello"):
            return "libcamera-hello"
        raise RuntimeError("Aucune commande de listing caméra trouvée (rpicam-hello/libcamera-hello).")

    @staticmethod
    def probe() -> tuple[bool, str]:
        """
        Vérifie si une caméra est détectée et retourne (available, diagnostic).
        """
        list_cmd = shutil.which("rpicam-hello") or shutil.which("libcamera-hello")
        if not list_cmd:
            return False, "Commande de listing caméra introuvable."

        try:
            r = subprocess.run(
                [os.path.basename(list_cmd), "--list-cameras"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
            if r.returncode != 0:
                return False, f"list-cameras en erreur ({r.returncode})."
            if "No cameras available" in out:
                return False, "Aucune caméra détectée."
            if "Available cameras" in out:
                return True, "Caméra détectée."
            return False, "Caméra non détectée."
        except Exception as exc:
            return False, f"Erreur de détection caméra: {exc}"

    @staticmethod
    def is_available() -> bool:
        """
        Vérifie si l'outil libcamera/rpicam voit au moins une caméra.
        """
        available, _ = PiCamera.probe()
        return available

    @staticmethod
    def detect_blocking_processes() -> List[str]:
        """
        Retourne best-effort la liste des processus utilisant /dev/video*.
        """
        pids: set[str] = set()
        devices = ["/dev/video0", "/dev/video1", "/dev/media0"]

        if shutil.which("fuser"):
            for dev in devices:
                r = subprocess.run(["fuser", dev], capture_output=True, text=True, check=False)
                content = ((r.stdout or "") + " " + (r.stderr or "")).replace(":", " ")
                for token in content.split():
                    if token.isdigit():
                        pids.add(token)

        if shutil.which("lsof"):
            for dev in devices:
                r = subprocess.run(["lsof", "-t", dev], capture_output=True, text=True, check=False)
                for line in (r.stdout or "").splitlines():
                    pid = line.strip()
                    if pid.isdigit():
                        pids.add(pid)

        result: List[str] = []
        for pid in sorted(pids):
            r = subprocess.run(
                ["ps", "-p", pid, "-o", "pid=,comm=,args="],
                capture_output=True,
                text=True,
                check=False,
            )
            line = (r.stdout or "").strip()
            if line:
                result.append(line)
        return result

    def capture(self, output_path: str) -> str:
        """
        Capture une image et l'écrit dans `output_path`.

        Returns
        -------
        str
            output_path

        Raises
        ------
        RuntimeError
            si l'outil de capture échoue
        FileNotFoundError
            si le fichier n'est pas créé
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        cmd = [
            self._cmd_capture,
            "--rotation",
            str(self._config.rotation),
            "-t",
            str(self._config.timeout_ms),
            "-o",
            output_path,
        ]

        if self._config.width is not None:
            cmd += ["--width", str(self._config.width)]
        if self._config.height is not None:
            cmd += ["--height", str(self._config.height)]

        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=max(1.0, float(self._config.command_timeout_sec)),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"{self._cmd_capture} timeout après {self._config.command_timeout_sec}s"
            ) from exc

        if r.returncode != 0:
            err = (r.stderr or "").strip()
            raise RuntimeError(f"{self._cmd_capture} failed ({r.returncode}): {err}")

        if not os.path.exists(output_path):
            raise FileNotFoundError(output_path)

        return output_path
