# modes/mode_dummy.py
"""
Mode de démonstration / test.

Ce mode n’a aucune logique métier réelle : il sert uniquement
à valider les interactions entre :

- le sélecteur rotatif (rotations, appui court, long, double),
- le ModeManager,
- la synthèse vocale (Speaker).

Il est utile comme "mode de développement" pour vérifier que
l’enchaînement complet hardware -> callbacks -> mode -> TTS
fonctionne correctement.

Ce mode peut servir de modèle minimal pour créer rapidement
un nouveau mode.
"""

from core.mode_base import Mode


class ModeDummy(Mode):
    """
    Mode "test" basique.

    Comportement :
    - on_enter       -> ne fait rien
    - on_short_press -> annonce un message simple
    - on_long_press  -> annonce un message spécifique à l’appui long
    - on_double_press -> confirme le détecteur de double-clic

    Ce mode n’effectue aucune action matérielle.
    """

    def __init__(self, speaker):
        """
        Parameters
        ----------
        speaker : Speaker
            Synthèse vocale centrale, utilisée pour les annonces.
        """
        super().__init__("Mode test")
        self.speaker = speaker

    def on_enter(self):
        """
        Appelé quand on arrive sur ce mode.
        Aucun feedback vocal ici pour ne pas surcharger :
        le ModeManager annonce déjà "Mode X : Mode test".
        """
        pass

    def on_exit(self):
        """
        Appelé lorsqu’on quitte ce mode.
        Rien à nettoyer.
        """
        pass

    def on_short_press(self):
        """Annonce une confirmation d’appui court."""
        self.speaker.speak("Appui court dans le mode test.")

    def on_long_press(self):
        """Annonce une confirmation d’appui long."""
        self.speaker.speak("Appui long dans le mode test.")

    def on_double_press(self):
        """Annonce un double appui détecté."""
        self.speaker.speak("Double appui dans le mode test.")
