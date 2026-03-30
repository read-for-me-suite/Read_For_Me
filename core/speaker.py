# core/speaker.py
"""
core.speaker
============
Sortie audio centrale de l'assistant — deux canaux indépendants :

1. CANAL ANNONCES  (say / speak)
   ─────────────────────────────
   - File d'attente (Queue) pour ordonner les annonces.
   - Chaque annonce = WAV Piper joué par un sous-processus mplayer
     BLOQUANT (non-slave). Le thread queue attend la fin réelle du
     fichier avant de passer au suivant.
   - Interruptible instantanément via stop_all_audio() →
     terminate() sur le sous-processus en cours.

2. CANAL LECTURE LONGUE  (play / PlaybackHandle)
   ──────────────────────────────────────────────
   - mplayer en mode slave (-slave -idle) pour contrôle fin :
     pause, reprise, seek, vitesse.
   - Utilisé exclusivement par ModeReadingMachine.
   - Indépendant de la queue.

VOLUME GLOBAL
   - Contrôlé via amixer (ALSA) → affecte tout (annonces + lecture).
   - set_volume_global() est appelable depuis n'importe quel mode.

ISOLATION DES MODES
   - stop_all_audio() : vide la queue + tue le sous-processus d'annonce
     en cours + envoie stop au player long-form.
   - Appelé par ModeManager avant chaque changement de mode.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
import wave
import shutil
from queue import Queue, Empty
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from piper import PiperVoice
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False

from config.config_loader import get_speaker_config


# ─────────────────────────────────────────────────────────────────────────────
# Handle de lecture longue
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PlaybackHandle:
    """
    Contrôle d'une lecture longue (machine à lire).

    Méthodes disponibles : pause, resume, stop, seek, set_speed.
    """
    _player: "_AudioPlayer"

    def pause(self) -> None:
        self._player.pause()

    def resume(self) -> None:
        self._player.resume()

    def stop(self) -> None:
        self._player.stop()

    def seek(self, seconds: int) -> None:
        self._player.seek(seconds)

    def set_speed(self, speed: float) -> None:
        self._player.set_speed(speed)


# ─────────────────────────────────────────────────────────────────────────────
# Player long-form (mplayer slave)
# ─────────────────────────────────────────────────────────────────────────────

class _AudioPlayer:
    """
    Player mplayer en mode slave (-slave -idle).

    Utilisé UNIQUEMENT pour la lecture longue (machine à lire).
    Permet pause/reprise/seek/vitesse en temps réel.
    Démarré de façon paresseuse au premier appel à play().
    """

    def __init__(self, verbose: bool = False):
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._running = False
        self._verbose = verbose
        self._current_file: Optional[str] = None

    def _start(self) -> None:
        """Démarre mplayer (paresseux — appelé par play())."""
        with self._lock:
            if self._running and self._proc is not None:
                return

            flags = ["-slave", "-idle", "-nolirc"]
            if self._verbose:
                flags += ["-quiet"]
            else:
                flags += ["-really-quiet"]

            self._proc = subprocess.Popen(
                ["mplayer"] + flags,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            self._running = True

    def _send(self, cmd: str) -> None:
        """Envoie une commande à mplayer (thread-safe)."""
        with self._lock:
            if not self._running or self._proc is None or self._proc.stdin is None:
                return
            try:
                self._proc.stdin.write(cmd + "\n")
                self._proc.stdin.flush()
            except Exception:
                self._running = False
                self._proc = None

    def play(self, path: str, speed: Optional[float] = None) -> None:
        """Charge et joue un fichier dans mplayer slave."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Fichier audio introuvable : {path}")

        self._start()
        self._send("stop")
        self._send(f'loadfile "{path}"')

        with self._lock:
            self._current_file = path

        if speed is not None and speed != 1.0:
            time.sleep(0.05)  # Laisser mplayer charger
            self._send(f"speed_set {speed:.2f}")

    def pause(self) -> None:
        """Bascule pause/lecture (commande mplayer 'pause' est un toggle)."""
        self._send("pause")

    def resume(self) -> None:
        """Reprend la lecture (même commande toggle que pause)."""
        self._send("pause")

    def stop(self) -> None:
        """Arrête la lecture (fichier déchargé, mplayer reste en idle)."""
        self._send("stop")
        with self._lock:
            self._current_file = None

    def seek(self, seconds: int) -> None:
        """Seek relatif en secondes (+ = avancer, - = reculer)."""
        if seconds == 0:
            return
        sign = "+" if seconds > 0 else ""
        self._send(f"seek {sign}{seconds} 0")

    def set_speed(self, speed: float) -> None:
        """Change la vitesse de lecture (0.5 – 2.0)."""
        speed = max(0.5, min(speed, 2.0))
        self._send(f"speed_set {speed:.2f}")

    def close(self) -> None:
        """Ferme mplayer proprement."""
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.stdin.write("quit\n")
                    self._proc.stdin.flush()
                    time.sleep(0.1)
                    self._proc.terminate()
                except Exception:
                    pass
            self._proc = None
            self._running = False
            self._current_file = None


# ─────────────────────────────────────────────────────────────────────────────
# Speaker — interface publique
# ─────────────────────────────────────────────────────────────────────────────

class Speaker:
    """
    Synthèse vocale centrale de l'assistant.

    Interface publique
    ------------------
    say(text, blocking=False)      → annonce courte (queue)
    speak(text)                    → alias say() non-bloquant
    play(path) → PlaybackHandle    → lecture longue (machine à lire)
    play_sound(path, blocking)     → son court hors-queue (aplay)
    stop_all_audio()               → coupe tout (changement de mode)
    set_volume_global(percent)     → volume ALSA global
    set_global_speed(speed)        → vitesse globale (0.5 – 2.0)
    close()                        → arrêt propre
    """

    def __init__(self):
        if not PIPER_AVAILABLE:
            raise RuntimeError(
                "[SPEAKER] Piper non installé. "
                "Exécuter : pip install piper-tts"
            )

        self._config = get_speaker_config()
        self._verbose = self._config.get("verbose_logging", False)
        self._min_volume = int(self._config.get("min_volume", 0))
        self._max_volume = int(self._config.get("max_volume", 100))
        self._min_speed = float(self._config.get("min_speed", 0.5))
        self._max_speed = float(self._config.get("max_speed", 2.0))

        # Chargement du modèle TTS
        self._load_piper_model()

        # Player long-form (mplayer slave) — démarré de façon paresseuse
        self._player = _AudioPlayer(verbose=self._verbose)

        # Vitesse globale (appliquée à la fois aux annonces et au player)
        self._global_speed: float = float(self._config.get("default_speed", 1.0))

        # ── Répertoire temporaire pour les WAV générés par Piper ──────────
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="speaker_piper_"))
        self._wav_counter = 0
        self._wav_counter_lock = threading.Lock()

        # ── Queue d'annonces ──────────────────────────────────────────────
        # Contient des chemins WAV (str) ou None (sentinel d'arrêt).
        self._queue: Queue[Optional[str]] = Queue()
        self._queue_running = True

        # Sous-processus mplayer en cours pour l'annonce actuelle.
        # Sauvegardé pour pouvoir le tuer via stop_all_audio().
        self._announcement_proc: Optional[subprocess.Popen] = None
        self._announcement_proc_lock = threading.Lock()

        # Démarrage du thread queue
        self._queue_thread = threading.Thread(
            target=self._process_queue,
            name="SpeakerQueue",
            daemon=True,
        )
        self._queue_thread.start()

        # ── Volume et vitesse courants ────────────────────────────────────
        # Trackés ici pour pouvoir les lire depuis n'importe quel mode
        # sans interroger ALSA (lecture seule, incréments relatifs).
        default_vol = int(self._config.get("default_volume", 75))
        self._current_volume: int = default_vol
        self.set_volume_global(default_vol)

        # ── Sons de notification (feedback utilisateur) ───────────────────
        project_root = Path(__file__).parent.parent
        notif_wav = str(self._config.get("notif_wav", "sounds/notif.wav"))
        self._notif_wav_path = project_root / notif_wav

        if self._verbose:
            print(f"[SPEAKER] Modèle  : {self._config['voice_model']}")
            print(f"[SPEAKER] Vitesse : {self._global_speed}  Volume : {default_vol}%")
            print(f"[SPEAKER] ✅ Init OK")

    # ── Chargement Piper ──────────────────────────────────────────────────

    def _load_piper_model(self) -> None:
        """Charge le modèle Piper depuis le répertoire configuré."""
        model_name = self._config["voice_model"]
        model_dir = Path(self._config.get("voice_model_dir", "models/piper"))

        # Chemin absolu relatif à la racine du projet
        project_root = Path(__file__).parent.parent
        model_dir = project_root / model_dir

        model_path = model_dir / f"{model_name}.onnx"
        config_path = model_dir / f"{model_name}.onnx.json"

        if not model_path.exists():
            raise FileNotFoundError(
                f"[SPEAKER] Modèle Piper introuvable : {model_path}\n"
                f"Télécharger : https://github.com/rhasspy/piper/releases"
            )

        if config_path.exists():
            self._voice = PiperVoice.load(str(model_path), config_path=str(config_path))
        else:
            self._voice = PiperVoice.load(str(model_path))

    # ── Gestion des fichiers WAV temporaires ─────────────────────────────

    def _get_temp_wav_path(self) -> Path:
        """Génère un chemin WAV unique dans le répertoire temporaire."""
        with self._wav_counter_lock:
            self._wav_counter += 1
            return self._tmp_dir / f"tts_{self._wav_counter}.wav"

    def _synthesize_wav(self, text: str) -> Path:
        """Synthétise 'text' via Piper et retourne le chemin du WAV généré."""
        wav_path = self._get_temp_wav_path()
        with wave.open(str(wav_path), "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)
        return wav_path

    def synthesize_to_file(self, text: str, output_path: str) -> None:
        """
        Synthétise 'text' via Piper et écrit le WAV à 'output_path'.

        Méthode publique utilisée par les modules extérieurs (ex: pipeline
        machine à lire) qui veulent utiliser la voix Piper du Speaker sans
        charger un second modèle en mémoire.

        Paramètres
        ----------
        text :
            Texte à synthétiser.
        output_path :
            Chemin absolu du fichier WAV de sortie.
            Le dossier parent doit exister.

        Raises
        ------
        ValueError
            Si le texte est vide.
        """
        text = text.strip()
        if not text:
            raise ValueError("[SPEAKER] synthesize_to_file : texte vide.")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with wave.open(output_path, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)

    # ── Sons de notification ───────────────────────────────────────────────

    def play_notification(self, blocking: bool = False) -> bool:
        """
        Joue le son de notification de volume/vitesse.

        Returns
        -------
        bool
            True si un fichier de notification a été trouvé et tenté,
            False sinon.
        """
        if self._notif_wav_path.exists():
            self.play_sound(str(self._notif_wav_path), blocking=blocking)
            return True
        if self._verbose:
            print("[SPEAKER] Son de notification introuvable (notif.wav).")
        return False

    def beep(self, direction: str = "up") -> None:
        """
        Alias de compatibilité : joue le son de notification.
        """
        _ = direction
        self.play_notification(blocking=False)

    # ── Thread queue d'annonces ───────────────────────────────────────────

    def _play_announcement_blocking(self, wav_path: str) -> None:
        """
        Joue un WAV via mplayer NON-slave (sous-processus bloquant).

        Bloque jusqu'à la fin réelle du fichier ou jusqu'à terminate().
        Enregistre le Popen dans _announcement_proc pour permettre
        une interruption propre via stop_all_audio().
        """
        speed = self._global_speed
        cmd = [
            "mplayer",
            "-really-quiet",
            "-nolirc",
            "-speed", f"{speed:.2f}",
            wav_path,
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        with self._announcement_proc_lock:
            self._announcement_proc = proc

        try:
            proc.wait()   # ← BLOQUE réellement jusqu'à fin de fichier ou kill
        finally:
            with self._announcement_proc_lock:
                # Ne réinitialiser que si c'est encore notre proc
                if self._announcement_proc is proc:
                    self._announcement_proc = None

    def _process_queue(self) -> None:
        """
        Thread dédié au traitement de la queue d'annonces.

        Traite les chemins WAV un par un, de façon bloquante.
        Nettoie chaque WAV après lecture.
        """
        while self._queue_running:
            try:
                wav_path = self._queue.get(timeout=0.5)

                if wav_path is None:
                    # Sentinel d'arrêt
                    self._queue.task_done()
                    break

                try:
                    self._play_announcement_blocking(wav_path)
                except Exception as e:
                    if self._verbose:
                        print(f"[SPEAKER] Erreur lecture annonce : {e}")
                finally:
                    # Nettoyage WAV après lecture (ou interruption)
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
                    self._queue.task_done()

            except Empty:
                continue
            except Exception as e:
                if self._verbose:
                    print(f"[SPEAKER] Erreur thread queue : {e}")

    # ── API publique ──────────────────────────────────────────────────────

    def say(self, text: str, blocking: bool = False) -> None:
        """
        Annonce courte — synthétisée par Piper, lue via la queue.

        Paramètres
        ----------
        text :
            Texte à synthétiser.
        blocking :
            Si True, attend que CETTE annonce (et toutes celles déjà
            en queue avant elle) soit terminée avant de retourner.
            Utiliser pour s'assurer qu'une annonce est entendue avant
            de poursuivre l'initialisation.
        """
        if not text or not text.strip():
            return

        wav_path = self._synthesize_wav(text.strip())
        self._queue.put(str(wav_path))

        if blocking:
            # queue.join() bloque jusqu'à ce que tous les task_done()
            # aient été appelés — c'est-à-dire que tous les WAVs en queue
            # ont été joués (ou sautés).
            self._queue.join()

    def speak(self, text: str) -> None:
        """Alias non-bloquant de say() — compatibilité avec l'ancien code."""
        self.say(text, blocking=False)

    def play(self, path: str) -> PlaybackHandle:
        """
        Lecture longue (machine à lire).

        Coupe les annonces en cours et lance la lecture via mplayer slave.
        Retourne un PlaybackHandle pour contrôle fin.

        Paramètres
        ----------
        path :
            Chemin vers le fichier WAV à lire.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"[SPEAKER] Fichier introuvable : {path}")

        # Couper les annonces en cours (mais PAS supprimer le fichier path,
        # qui est géré par TextReaderDevice)
        self.stop_all_audio()

        # Lancer la lecture longue
        self._player.play(path, speed=self._global_speed)

        return PlaybackHandle(self._player)

    def play_sound(self, path: str, blocking: bool = False) -> None:
        """
        Son court hors-queue (effets sonores : shutter, erreur, etc.).

        Utilise aplay (ALSA, très léger) — aucune interférence avec
        la queue ni le player long-form.
        """
        if not os.path.exists(path):
            if self._verbose:
                print(f"[SPEAKER] Son introuvable : {path}")
            return

        try:
            cmd = None
            ext = Path(path).suffix.lower()

            if ext == ".wav":
                player = shutil.which("aplay") or shutil.which("afplay")
                if player is not None:
                    cmd = [player, path]

            if cmd is None:
                mplayer = shutil.which("mplayer")
                if mplayer is not None:
                    cmd = [mplayer, "-really-quiet", "-nolirc", path]

            if cmd is None:
                return

            if blocking:
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            if self._verbose:
                print(f"[SPEAKER] Erreur play_sound : {e}")

    def stop_all_audio(self) -> None:
        """
        Coupe tout l'audio immédiatement.

        Actions
        -------
        1. Vide la queue (et supprime les WAVs en attente).
        2. Tue le sous-processus d'annonce en cours (terminate).
        3. Arrête le player long-form (mplayer slave → stop).

        Appelé par ModeManager à chaque changement de mode.
        """
        # 1. Vider la queue et supprimer les WAVs en attente
        while not self._queue.empty():
            try:
                wav_path = self._queue.get_nowait()
                if wav_path is not None:
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
                self._queue.task_done()
            except Empty:
                break

        # 2. Interrompre l'annonce en cours de lecture
        with self._announcement_proc_lock:
            proc = self._announcement_proc
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass
                self._announcement_proc = None

        # 3. Arrêter la lecture longue (player slave)
        self._player.stop()

    def set_volume_global(self, percent: int, mixer: Optional[str] = None) -> None:
        """
        Règle le volume ALSA global (0 – 100).

        Affecte toutes les sorties audio (annonces + lecture longue).
        Le mixer est détecté automatiquement si non précisé.
        La valeur est mémorisée dans _current_volume pour permettre
        aux modes de lire le niveau courant via get_volume().
        """
        percent = max(self._min_volume, min(self._max_volume, int(percent)))
        self._current_volume = percent

        if mixer is None:
            mixer = self._detect_alsa_mixer()

        try:
            subprocess.run(
                ["amixer", "-q", "sset", mixer, f"{percent}%"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            if self._verbose:
                print(f"[SPEAKER] Erreur amixer : {e}")

    def get_volume(self) -> int:
        """
        Retourne le volume global courant (0 – 100).

        Valeur mémorisée à chaque appel de set_volume_global().
        Utilisée par les modes pour effectuer des incréments relatifs
        (ex : volume +4, volume -4) sans interroger ALSA.
        """
        return self._current_volume

    def get_speed(self) -> float:
        """
        Retourne la vitesse de lecture globale courante (0.5 – 2.0).

        Valeur mémorisée à chaque appel de set_global_speed().
        Utilisée par les modes pour effectuer des incréments relatifs.
        """
        return self._global_speed

    def _detect_alsa_mixer(self) -> str:
        """Détecte le nom du contrôle ALSA disponible."""
        try:
            result = subprocess.run(
                ["amixer", "scontrols"],
                capture_output=True,
                text=True,
                check=False,
            )
            for mixer in ["Headphone", "PCM", "Master", "Speaker"]:
                if mixer in result.stdout:
                    return mixer
        except Exception:
            pass
        return "Master"

    def set_global_speed(self, speed: float) -> None:
        """
        Règle la vitesse globale (0.5 – 2.0).

        S'applique :
        - Aux prochaines annonces (utilisé au moment du subprocess).
        - Au player long-form immédiatement (commande mplayer).
        """
        self._global_speed = max(self._min_speed, min(self._max_speed, float(speed)))
        # Appliquer immédiatement si le player long-form est actif
        self._player.set_speed(self._global_speed)

    def close(self) -> None:
        """
        Arrêt propre du Speaker.

        Interrompt les lectures en cours, vide la queue, supprime
        les fichiers temporaires.
        """
        # Signaler l'arrêt au thread queue
        self._queue_running = False

        # Couper tout audio en cours
        self.stop_all_audio()

        # Envoyer le sentinel pour faire sortir le thread queue
        self._queue.put(None)
        self._queue_thread.join(timeout=3)

        # Fermer le player long-form
        self._player.close()

        # Supprimer le répertoire temporaire
        try:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        except Exception:
            pass

        if self._verbose:
            print("[SPEAKER] Fermé.")
