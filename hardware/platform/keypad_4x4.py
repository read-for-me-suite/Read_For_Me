# hardware/platform/keypad_4x4.py
"""
Driver clavier matriciel 4x4 (GPIO) pour Raspberry Pi.

Responsabilité
--------------
- Scanner un clavier 4x4 câblé en matrice (4 lignes / 4 colonnes)
- Déclencher un callback quand une touche est pressée
- Fournir start/stop pour activer ce périphérique uniquement dans certains modes

Choix d'API (propre pour l'archi)
---------------------------------
- Keypad4x4.start()  : démarre un thread de scan (non-bloquant)
- Keypad4x4.stop()   : stoppe le thread proprement
- Keypad4x4.on_key   : callback optionnel appelé quand une touche est détectée
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Callable, Optional, List

from gpiozero import OutputDevice, Button


@dataclass(frozen=True)
class KeypadPins:
    # 4 lignes (outputs)
    row1: int
    row2: int
    row3: int
    row4: int
    # 4 colonnes (inputs)
    col1: int
    col2: int
    col3: int
    col4: int


class Keypad4x4:
    """
    Driver de scan clavier 4x4.

    - Scan cyclique des lignes (row) -> lecture colonnes (col)
    - Anti-rebond logiciel simple
    - Détection "press" (pas maintien)
    """

    DEFAULT_LAYOUT: List[List[str]] = [
        ["1", "2", "3", "A"],
        ["4", "5", "6", "B"],
        ["7", "8", "9", "C"],
        ["*", "0", "#", "D"],
    ]

    def __init__(
        self,
        pins: KeypadPins,
        *,
        layout: Optional[List[List[str]]] = None,
        scan_interval: float = 0.02,   # 20ms
        debounce_time: float = 0.20,   # 200ms entre deux triggers
    ) -> None:
        self._pins = pins
        self._layout = layout or self.DEFAULT_LAYOUT
        self._scan_interval = scan_interval
        self._debounce_time = debounce_time

        # Callback externe
        self.on_key: Optional[Callable[[str], None]] = None

        # GPIO init
        self._rows = [
            OutputDevice(pins.row1),
            OutputDevice(pins.row2),
            OutputDevice(pins.row3),
            OutputDevice(pins.row4),
        ]

        # Colonnes en entrée pull-down (comme ton ancien code)
        self._cols = [
            Button(pins.col1, pull_up=False),
            Button(pins.col2, pull_up=False),
            Button(pins.col3, pull_up=False),
            Button(pins.col4, pull_up=False),
        ]

        # Thread scan
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # anti-rebond / anti-spam
        self._last_key: Optional[str] = None
        self._last_key_time: float = 0.0

    def start(self) -> None:
        """Démarre le scan clavier dans un thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, name="Keypad4x4", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stoppe le scan clavier."""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        # Option : mettre les lignes à OFF pour éviter des courants parasites
        for r in self._rows:
            r.off()

    def _scan_loop(self) -> None:
        """Boucle de scan (thread)."""
        while self._running:
            key = self._scan_once()
            if key is not None:
                self._emit_key(key)
            time.sleep(self._scan_interval)

    def _scan_once(self) -> Optional[str]:
        """Active une ligne à la fois et lit les colonnes."""
        for row_idx, row in enumerate(self._rows):
            row.on()
            # Petite pause pour stabiliser (très courte)
            time.sleep(0.001)

            for col_idx, col in enumerate(self._cols):
                if col.is_active:
                    row.off()
                    return self._layout[row_idx][col_idx]

            row.off()
        return None

    def _emit_key(self, key: str) -> None:
        """Applique un anti-rebond puis déclenche le callback."""
        now = time.time()

        # Debounce : même touche dans une courte fenêtre -> ignore
        if self._last_key == key and (now - self._last_key_time) < self._debounce_time:
            return

        self._last_key = key
        self._last_key_time = now

        if self.on_key:
            try:
                self.on_key(key)
            except Exception as e:
                print(f"[KEYPAD] erreur callback on_key: {e}")
