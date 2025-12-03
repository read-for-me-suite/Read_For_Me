# modes/mode_datetime.py
from datetime import datetime

from core.mode_base import Mode
from core.speaker import Speaker


class ModeDateHeure(Mode):
    """
    Mode "Date et heure".

    - Appui court : annonce l'heure
    - Appui long : annonce la date du jour
    """

    def __init__(self, speaker: Speaker):
        super().__init__(name="Date et heure")
        self.speaker = speaker

    def on_enter(self) -> None:
        # Optionnel : petit feedback à l'entrée du mode
        # Ici on ne dit rien pour éviter le spam, c'est le ModeManager qui annoncera le nom du mode.
        pass

    def on_exit(self) -> None:
        # Rien de spécial à faire pour ce mode quand on le quitte.
        pass

    def on_short_press(self) -> None:
        """Annonce l'heure système actuelle."""
        maintenant = datetime.now()
        # Les noms de jours/mois dépendent de la locale système (fr_FR conseillé)
        heure_str = maintenant.strftime("%H heures %M")
        message = f"Il est {heure_str}"
        self.speaker.speak(message)

    def on_long_press(self) -> None:
        """Annonce la date du jour."""
        maintenant = datetime.now()

        # Selon la locale système, jour_semaine/mois peuvent être en anglais.
        jour_semaine = maintenant.strftime("%A")
        jour = int(maintenant.strftime("%d"))
        mois = maintenant.strftime("%B")
        annee = maintenant.strftime("%Y")

        message = f"Nous sommes le {jour_semaine} {jour} {mois} {annee}"
        self.speaker.speak(message)
