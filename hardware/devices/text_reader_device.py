# hardware/devices/text_reader_device.py
"""
hardware.devices.text_reader_device
====================================

Device "machine à lire" (couche au-dessus du hardware brut).

Responsabilité
--------------
Orchestrer les trois premières étapes de la chaîne de lecture :

    1. Capture caméra       → <basename>.jpg          (via PiCamera)
    2. OCR                  → <basename>_raw.txt       (via pytesseract)
    3. Nettoyage du texte   → <basename>.txt           (logique propre)

Ce module NE gère PAS :
    - La synthèse vocale (TTS) : déléguée au Speaker central via
      Speaker.synthesize_to_file(), ce qui évite de charger le modèle
      Piper une deuxième fois en mémoire.
    - Le keypad / les touches : gérés par le mode (ModeReadingMachine).
    - Le playback / pause / seek : gérés par Speaker/mplayer côté core.
    - La logique de mode (on_enter/on_exit, mapping touches, etc.).

Fichiers produits
-----------------
Pour un basename donné (ex : "/tmp/readforme/scan") :
    - Image brute  : /tmp/readforme/scan.jpg
    - Texte OCR    : /tmp/readforme/scan_raw.txt
    - Texte propre : /tmp/readforme/scan.txt

Le fichier WAV est produit EN DEHORS de ce module, par le mode qui
appelle Speaker.synthesize_to_file() puis Speaker.play().

Pourquoi cette séparation ?
---------------------------
L'ancien code embarquait le TTS (pico2wave, puis Piper) directement ici.
Cela impliquait de charger le modèle Piper une seconde fois, consommant
inutilement de la RAM sur le Raspberry Pi.
Désormais, un seul modèle Piper est chargé (dans Speaker.__init__) et
partagé via Speaker.synthesize_to_file().
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pytesseract as pyt
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from hardware.platform.pi_camera import PiCamera


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OCRConfig:
    """
    Paramètres de la reconnaissance optique de caractères (OCR).

    Attributs
    ---------
    lang :
        Code langue tesseract (ex : "fra" pour le français, "eng" pour
        l'anglais). Doit correspondre à un pack de langues installé.
    psm :
        Page Segmentation Mode tesseract (--psm).
        3 = détection automatique (valeur recommandée pour documents).
        Voir : tesseract --help-psm
    """
    lang: str = "fra"
    psm: int = 6
    oem: int = 1
    preprocess_enabled: bool = True
    autocontrast_cutoff: int = 2
    sharpen_factor: float = 1.2
    threshold: int = 0
    timeout_sec: float = 20.0
    fallback_psm: tuple[int, ...] = (7, 11, 3)
    save_debug_ocr_input: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Device principal
# ─────────────────────────────────────────────────────────────────────────────

class TextReaderDevice:
    """
    Device "machine à lire" — pipeline capture → OCR → texte propre.

    Ce device s'arrête à la production du texte nettoyé.
    La synthèse vocale est gérée par le Speaker central.

    API principale
    --------------
    capture(basename)         → str   chemin de l'image
    ocr_to_text(basename)     → str   chemin du texte OCR brut
    clean_text(basename)      → str   chemin du texte nettoyé
    run_full_pipeline(basename) → str   chemin du texte nettoyé (enchaîne les 3)

    Convention de nommage (basename = "/tmp/readforme/scan") :
        Image brute  : /tmp/readforme/scan.jpg
        Texte OCR    : /tmp/readforme/scan_raw.txt
        Texte propre : /tmp/readforme/scan.txt
    """

    def __init__(
        self,
        camera: PiCamera,
        *,
        ocr: Optional[OCRConfig] = None,
    ) -> None:
        """
        Initialise le device.

        Paramètres
        ----------
        camera :
            Instance de PiCamera configurée (rotation, résolution…).
        ocr :
            Configuration OCR. Si None, utilise les valeurs par défaut
            (lang="fra", psm=3).
        """
        self._camera = camera
        self._ocr = ocr or OCRConfig()

    @staticmethod
    def _score_ocr_text(text: str) -> int:
        """
        Score heuristique de lisibilité OCR.
        """
        stripped = (text or "").strip()
        if not stripped:
            return -10_000

        alpha = sum(ch.isalpha() for ch in stripped)
        digits = sum(ch.isdigit() for ch in stripped)
        spaces = sum(ch.isspace() for ch in stripped)
        weird = sum(not (ch.isalnum() or ch.isspace() or ch in ".,;:!?'-\"()") for ch in stripped)
        return (alpha * 4) + (digits * 2) + spaces - (weird * 3)

    def _preprocess_for_ocr(self, img: Image.Image) -> Image.Image:
        """
        Prétraitement robuste pour améliorer le contraste texte/fond.
        """
        if not self._ocr.preprocess_enabled:
            return img

        gray = img.convert("L")
        auto = ImageOps.autocontrast(gray, cutoff=max(0, int(self._ocr.autocontrast_cutoff)))
        denoised = auto.filter(ImageFilter.MedianFilter(size=3))
        sharp = ImageEnhance.Sharpness(denoised).enhance(max(1.0, float(self._ocr.sharpen_factor)))

        threshold = int(self._ocr.threshold)
        if threshold > 0:
            binarized = sharp.point(lambda px: 255 if px >= threshold else 0, mode="1")
            return binarized.convert("L")
        return sharp

    # ── Helpers chemins ───────────────────────────────────────────────────

    @staticmethod
    def _img_path(basename: str) -> str:
        """Chemin de l'image capturée (<basename>.jpg)."""
        return f"{basename}.jpg"

    @staticmethod
    def _raw_txt_path(basename: str) -> str:
        """Chemin du texte OCR brut (<basename>_raw.txt)."""
        return f"{basename}_raw.txt"

    @staticmethod
    def _clean_txt_path(basename: str) -> str:
        """Chemin du texte nettoyé (<basename>.txt)."""
        return f"{basename}.txt"

    # ── Étape 1 : capture caméra ──────────────────────────────────────────

    def capture(self, basename: str) -> str:
        """
        Capture une photo et écrit <basename>.jpg.

        Paramètres
        ----------
        basename :
            Chemin sans extension (ex : "/tmp/readforme/scan").

        Retourne
        --------
        str
            Chemin complet du fichier image créé.
        """
        img_path = self._img_path(basename)
        os.makedirs(os.path.dirname(img_path) or ".", exist_ok=True)
        return self._camera.capture(img_path)

    # ── Étape 2 : OCR → texte brut ────────────────────────────────────────

    def ocr_to_text(self, basename: str) -> str:
        """
        Effectue l'OCR sur <basename>.jpg et écrit <basename>_raw.txt.

        Utilise pytesseract avec la langue et le PSM configurés.

        Paramètres
        ----------
        basename :
            Chemin sans extension.

        Retourne
        --------
        str
            Chemin du fichier texte brut produit.

        Raises
        ------
        FileNotFoundError
            Si l'image n'existe pas (étape capture non réalisée).
        """
        img_path = self._img_path(basename)
        if not os.path.exists(img_path):
            raise FileNotFoundError(
                f"[TEXT_READER] Image introuvable : {img_path}. "
                "Lancer capture() d'abord."
            )

        available_langs = set(pyt.get_languages(config=""))
        if self._ocr.lang not in available_langs:
            raise RuntimeError(
                f"[TEXT_READER] Langue OCR '{self._ocr.lang}' indisponible. "
                f"Langues installées: {', '.join(sorted(available_langs))}"
            )

        with Image.open(img_path) as img:
            ocr_input = self._preprocess_for_ocr(img)
            if self._ocr.save_debug_ocr_input:
                debug_path = f"{basename}_ocr_input.jpg"
                ocr_input.save(debug_path)

            candidates = [int(self._ocr.psm)] + [int(v) for v in self._ocr.fallback_psm]
            # Supprimer les doublons en conservant l'ordre
            psm_list: list[int] = []
            for psm in candidates:
                if psm not in psm_list:
                    psm_list.append(psm)

            best_text = ""
            best_score = -10_000

            for psm in psm_list:
                config = f"--oem {int(self._ocr.oem)} --psm {psm}"
                current = pyt.image_to_string(
                    ocr_input,
                    lang=self._ocr.lang,
                    config=config,
                    timeout=max(1.0, float(self._ocr.timeout_sec)),
                )
                score = self._score_ocr_text(current)
                if score > best_score:
                    best_score = score
                    best_text = current

                # Texte suffisamment propre, on évite d'ajouter de la latence.
                if score >= 80:
                    break

            text = best_text

        raw_path = self._raw_txt_path(basename)
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(text)

        return raw_path

    # ── Étape 3 : nettoyage texte ─────────────────────────────────────────

    def clean_text(self, basename: str) -> str:
        """
        Nettoie le texte OCR brut et écrit <basename>.txt.

        Stratégie de nettoyage (identique à l'ancien projet) :
        - Les lignes non vides sont concaténées avec des espaces.
        - Une ligne vide introduit un saut de paragraphe (double newline).
        - Les traits d'union de fin de ligne ("- \\n") sont supprimés
          (gestion des mots coupés par l'OCR).

        Paramètres
        ----------
        basename :
            Chemin sans extension.

        Retourne
        --------
        str
            Chemin du fichier texte nettoyé.

        Raises
        ------
        FileNotFoundError
            Si le texte brut n'existe pas (étape ocr_to_text non réalisée).
        RuntimeError
            Si le texte nettoyé est vide (document illisible ou page vide).
        """
        raw_path = self._raw_txt_path(basename)
        if not os.path.exists(raw_path):
            raise FileNotFoundError(
                f"[TEXT_READER] Texte brut introuvable : {raw_path}. "
                "Lancer ocr_to_text() d'abord."
            )

        with open(raw_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        texte = ""
        for line in lines:
            if line.strip():
                texte += line.strip() + " "
            else:
                texte += "\n\n"

        # Suppression des césures de fin de ligne
        texte = texte.replace("-\n", "")
        texte = texte.replace("-\r\n", "")
        texte = texte.strip()

        if not texte:
            raise RuntimeError(
                "[TEXT_READER] Texte vide après nettoyage. "
                "Le document est peut-être vide ou illisible."
            )

        clean_path = self._clean_txt_path(basename)
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(texte)

        return clean_path

    # ── Pipeline complète ─────────────────────────────────────────────────

    def run_full_pipeline(self, basename: str) -> str:
        """
        Exécute la chaîne complète : capture → OCR → nettoyage.

        Équivalent à appeler capture(), ocr_to_text(), clean_text()
        dans l'ordre, avec gestion d'erreurs centralisée.

        Paramètres
        ----------
        basename :
            Chemin sans extension (ex : "/tmp/readforme/scan").

        Retourne
        --------
        str
            Chemin du fichier texte nettoyé (<basename>.txt).
            Le contenu est prêt à être synthétisé via
            Speaker.synthesize_to_file().

        Raises
        ------
        FileNotFoundError
            Si un fichier intermédiaire n'existe pas.
        RuntimeError
            Si le texte résultant est vide.
        """
        self.capture(basename)
        self.ocr_to_text(basename)
        return self.clean_text(basename)
