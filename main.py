# main.py
from signal import pause

from core.speaker import Speaker
from core.mode_manager import ModeManager
from hardware.rotary_selector import RotarySelector

# Imports des modes 
from modes.mode_datetime import ModeDateHeure
from modes.mode_dummy import ModeDummy

def main() -> None:
    # 1. Initialiser la synthèse vocale
    speaker = Speaker()

    # 2. Créer les modes disponibles
    modes = [
        ModeDateHeure(speaker),
        ModeDummy(speaker),
        #ModeMultimetre(speaker),
        # Plus tard :
        # ModeMachineALire(speaker),
        # ModeMultimetre(speaker),
        # ModePiedACoulisse(speaker),
        # etc.
    ]

    # 3. Créer le gestionnaire de modes
    mode_manager = ModeManager(modes=modes, speaker=speaker)

    # 4. Configurer le rotateur
    selector = RotarySelector(
        pin_a=17,
        pin_b=27,
        pin_sw=22,
        positions_count=len(modes),
        long_press_threshold=1.0,
    )

    # 5. Connecter les callbacks du rotateur au ModeManager
    selector.on_position_changed = lambda index, direction: mode_manager.set_index(
        index, direction
    )
    selector.on_short_press = mode_manager.handle_short_press
    selector.on_long_press = mode_manager.handle_long_press

    # 6. Lancer l'assistant
    speaker.speak("Assistant technique prêt.")
    pause()  # Bloque le programme en attendant les événements GPIO


if __name__ == "__main__":
    main()
