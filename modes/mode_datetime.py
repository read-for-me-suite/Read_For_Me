# modes/mode_datetime.py
"""
Mode "Date et heure".

Ce module définit un mode très simple qui exploite l'horloge système
pour annoncer :

- l'heure actuelle (appui court),
- la date du jour (appui long).

Il ne gère aucune logique matérielle directement : il s'appuie sur
le `ModeManager` (pour la sélection du mode) et sur le `Speaker`
(pour la synthèse vocale).
"""

from datetime import datetime

from core.mode_base import Mode
from core.speaker import Speaker


class ModeDateHeure(Mode):
    """
    Mode "Date et heure" de l'assistant.

    Comportement UX
    ---------------
    - À l'entrée du mode (`on_enter`) :
        * rien n'est annoncé ici, le `ModeManager` annonce déjà
          "Mode X : Date et heure".
    - Appui court (`on_short_press`) :
        * annonce l'heure système actuelle (ex : "Il est 14 heures 32").
    - Appui long (`on_long_press`) :
        * annonce la date du jour (ex : "Nous sommes le mardi 5 juin 2025").

    Remarques
    ---------
    - Les libellés de jour et de mois (`%A`, `%B`) dépendent de la locale
      système (ex : `fr_FR` recommandé pour avoir les noms en français).
    """

    def __init__(self, speaker: Speaker):
        """
        Initialise le mode "Date et heure".

        Paramètres
        ----------
        speaker : Speaker
            Instance du `Speaker` central utilisée pour prononcer les messages.
        """
        super().__init__(name="Date et heure")
        self.speaker = speaker

    def on_enter(self) -> None:
        """
        Hook appelé lorsque l'on ARRIVE sur ce mode.

        Ici, on ne fait rien :
        - le `ModeManager` se charge déjà d’annoncer le nom du mode,
        - cela évite d’ajouter du bruit vocal à chaque changement de mode.

        Ce hook existe principalement pour symétrie et pour d'éventuelles
        évolutions (par ex. "rafraîchir" un cache, etc.).
        """
        pass

    def on_exit(self) -> None:
        """
        Hook appelé lorsque l'on QUITTE ce mode.

        Aucun nettoyage spécifique n'est nécessaire pour ce mode, donc
        l'implémentation est vide pour le moment.
        """
        pass

    def on_short_press(self) -> None:
        """
        Appui court : annonce l'heure système actuelle.

        Exemple de rendu vocal :
            "Il est 14 heures 32"

        Implémentation
        --------------
        - Récupère l'heure courante via `datetime.now()`.
        - Formate l'heure avec `strftime("%H heures %M")`.
        - Envoie la phrase complète au `Speaker`.
        """
        maintenant = datetime.now()
        # Les noms de jours/mois dépendent de la locale système (fr_FR conseillé)
        heure_str = maintenant.strftime("%H heures %M")
        message = f"Il est {heure_str}"
        self.speaker.speak(message)

    def on_long_press(self) -> None:
        """
        Appui long : annonce la date du jour.

        Exemple de rendu vocal :
            "Nous sommes le mardi 5 juin 2025"

        Implémentation
        --------------
        - Utilise `datetime.now()` pour récupérer la date actuelle.
        - Décompose :
            * jour de la semaine : `%A`
            * jour du mois       : `%d` (converti en int pour éviter les zéros en tête)
            * mois               : `%B`
            * année              : `%Y`
        - Construit une phrase en français et la passe au `Speaker`.

        Remarque
        --------
        - Selon la configuration locale du système (locale),
          `%A` et `%B` peuvent être en anglais. Pour forcer le français,
          il est recommandé de configurer la locale en `fr_FR` au niveau OS.
        """
        maintenant = datetime.now()

        jour_semaine = maintenant.strftime("%A")
        jour = int(maintenant.strftime("%d"))
        mois = maintenant.strftime("%B")
        annee = maintenant.strftime("%Y")

        message = f"Nous sommes le {jour_semaine} {jour} {mois} {annee}"
        self.speaker.speak(message)
