# main.py
"""
Point d'entrée principal de l'assistant technique.

Ce script assemble toutes les briques de haut niveau :

- Création de la synthèse vocale centrale (`Speaker`)
- Instanciation des différents modes (date/heure, dummy, multimètre, ...)
- Création du `ModeManager` qui orchestre le mode actif
- Configuration du sélecteur rotatif matériel (`RotarySelector`) :
    * rotation  -> changement de mode
    * appui court / long / double -> délégués au mode courant
- Boucle principale bloquante via `signal.pause()` :
    * le programme reste vivant et réagit aux interruptions GPIO.

Architecture globale
--------------------
Matériel (GPIO)  -->  RotarySelector  -->  ModeManager  -->  Mode courant  -->  Speaker
                   (événements bas niveau)   (route les actions)    (logique métier)   (voix)
"""

from signal import pause

from core.speaker import Speaker
from core.mode_manager import ModeManager
from hardware.platform.rotary_selector import RotarySelector

# Imports des modes
from modes.mode_datetime import ModeDateHeure
from modes.mode_dummy import ModeDummy
from modes.mode_multimeter import ModeMultimetre


def main() -> None:
    """
    Initialise et lance l'assistant.

    Étapes
    ------
    1. Créer le `Speaker` (voix centrale).
    2. Instancier tous les modes disponibles (en leur passant la voix).
    3. Créer un `ModeManager` chargé de gérer le mode actif.
    4. Configurer le `RotarySelector` avec :
        - les broches GPIO à utiliser,
        - le nombre de positions (un par mode),
        - les callbacks vers le `ModeManager` pour :
            * changement de position (rotation),
            * appui court,
            * appui long,
            * double appui.
    5. Appeler `pause()` pour bloquer le script tout en laissant
       tourner les callbacks GPIO / threads internes.

    Remarque
    --------
    - L'ajout d'un nouveau mode se fait en trois endroits :
        1) Création de la classe ModeXxx dans `modes/`,
        2) Import ici en haut du fichier,
        3) Ajout de l'instance dans la liste `modes`.
    """
    # 1. Initialiser la synthèse vocale
    speaker = Speaker()
    speaker.speak("Assistant technique prêt.")

    # 2. Créer les modes disponibles
    modes = [
        ModeDateHeure(speaker),
        ModeDummy(speaker),
        ModeMultimetre(speaker),
        # Plus tard :
        # ModeMachineALire(speaker),
        # ModePiedACoulisse(speaker),
        # etc.
    ]

    # 3. Créer le gestionnaire de modes
    mode_manager = ModeManager(modes=modes, speaker=speaker)

    # 4. Configurer le rotateur (GPIO)
    selector = RotarySelector(
        pin_a=17,
        pin_b=27,
        pin_sw=22,
        positions_count=len(modes),  # une position par mode
        long_press_threshold=1.0,    # au-delà de 1s = appui long
    )

    # 5. Connecter les callbacks du rotateur au ModeManager
    selector.on_position_changed = lambda index, direction: mode_manager.set_index(
        index, direction
    )
    selector.on_short_press = mode_manager.handle_short_press
    selector.on_long_press = mode_manager.handle_long_press
    selector.on_double_press = mode_manager.handle_double_press

    # 6. Lancer l'assistant :
    #    `pause()` bloque le thread principal en laissant vivre
    #    les threads/callbacks (GPIO, BLE, TTS).
    pause()


if __name__ == "__main__":
    main()
