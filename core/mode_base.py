# core/mode_base.py
from abc import ABC, abstractmethod


class Mode(ABC):
    """
    Classe de base abstraite pour tous les modes de l'assistant.

    Chaque mode doit au minimum savoir quoi faire sur :
      - on_short_press() : appui court sur le bouton
      - on_long_press()  : appui long sur le bouton

    Les hooks on_enter / on_exit sont optionnels.
    """

    def __init__(self, name: str):
        # Nom lisible du mode (ex: "Machine à lire", "Multimètre", "Date et heure")
        self.name = name

    def on_enter(self) -> None:
        """
        Appelé quand on ARRIVE sur ce mode (sélecteur tourné vers ce mode).
        Par défaut, ne fait rien.
        """
        pass

    def on_exit(self) -> None:
        """
        Appelé quand on QUITTE ce mode.
        Par défaut, ne fait rien.
        """
        pass

    @abstractmethod
    def on_short_press(self) -> None:
        """
        Appui court sur le bouton poussoir lorsque ce mode est actif.
        """
        raise NotImplementedError

    @abstractmethod
    def on_long_press(self) -> None:
        """
        Appui long sur le bouton poussoir lorsque ce mode est actif.
        """
        raise NotImplementedError
