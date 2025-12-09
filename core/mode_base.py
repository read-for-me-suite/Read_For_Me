# core/mode_base.py
"""
core.mode_base
==============

Définit la classe abstraite `Mode`, base commune à **tous les modes
fonctionnels** de l'assistant (date/heure, multimètre, mode test, etc.).

Rôle de cette classe
--------------------

Un *mode* représente un "contexte" d’utilisation de l’assistant :
par exemple "Mode Date et heure", "Mode Multimètre", etc.  
À un instant donné, **un seul mode est actif**. Le changement de mode
est piloté par le sélecteur rotatif et orchestré par `ModeManager`.

Cette classe définit le **contrat minimal** qu’un mode doit respecter :

- un **nom** lisible (`name`) pour l’annonce vocale du mode,
- des hooks de cycle de vie :
    - `on_enter()` : appelé quand on arrive sur le mode,
    - `on_exit()` : appelé quand on quitte le mode,
- des callbacks liés au **bouton poussoir** :
    - `on_short_press()` : appui court,
    - `on_long_press()`  : appui long,
    - `on_double_press()` : double appui rapide (optionnel, valeur par défaut : ne fait rien).

Cette classe ne connaît rien :
- ni de la synthèse vocale (`Speaker`),
- ni du matériel (rotary, BLE, etc.),
- ni du `ModeManager` qui l’utilise.

Elle sert uniquement de **base commune**, pour garder une interface
cohérente entre tous les modes.
"""

from abc import ABC, abstractmethod


class Mode(ABC):
    """
    Classe de base abstraite pour tous les modes de l'assistant.

    Chaque mode concret (ex: `ModeDateHeure`, `ModeMultimetre`, etc.)
    doit **hériter** de cette classe et implémenter au minimum :

    - `on_short_press()` : réaction à un appui court sur le bouton,
    - `on_long_press()`  : réaction à un appui long sur le bouton.

    Les hooks `on_enter()` / `on_exit()` et `on_double_press()` sont
    **optionnels** : l’implémentation par défaut ne fait rien. Ils
    peuvent être surchargés si le mode en a besoin (par exemple pour
    démarrer un driver, activer un timer, etc.).
    """

    def __init__(self, name: str):
        """
        Initialise un mode abstrait.

        Parameters
        ----------
        name :
            Nom lisible du mode, utilisé pour les annonces vocales
            (exemples : "Machine à lire", "Multimètre", "Date et heure").
        """
        self.name = name

    def on_enter(self) -> None:
        """
        Hook appelé quand on **arrive** sur ce mode.

        Ce hook est invoqué par le `ModeManager` lorsque le sélecteur
        rotatif pointe sur ce mode et que ce mode devient le mode actif.

        Par défaut, cette méthode ne fait rien. Les sous-classes peuvent
        la surcharger pour, par exemple :

        - démarrer une tâche ou un driver matériel,
        - initialiser un état interne,
        - annoncer un message spécifique au mode, etc.
        """
        pass

    def on_exit(self) -> None:
        """
        Hook appelé quand on **quitte** ce mode.

        Ce hook est invoqué par le `ModeManager` juste avant de basculer
        vers un autre mode (lors d’une rotation stable du sélecteur).

        Par défaut, cette méthode ne fait rien. Les sous-classes peuvent
        la surcharger pour, par exemple :

        - arrêter proprement un driver,
        - libérer des ressources,
        - annuler des timers, etc.
        """
        pass

    @abstractmethod
    def on_short_press(self) -> None:
        """
        Appui **court** sur le bouton poussoir lorsque ce mode est actif.

        Cette méthode **doit** être implémentée par chaque mode concret.

        Exemple d’usage typique :

        - dans un mode "Multimètre" : annoncer la dernière mesure,
        - dans un mode "Date et heure" : lire l’heure actuelle,
        - dans un mode "Lecture" : lire la ligne ou l’élément suivant.
        """
        raise NotImplementedError

    @abstractmethod
    def on_long_press(self) -> None:
        """
        Appui **long** sur le bouton poussoir lorsque ce mode est actif.

        Cette méthode **doit** être implémentée par chaque mode concret.

        Exemple d’usage typique :

        - afficher ou annoncer un état détaillé,
        - activer une fonction secondaire,
        - basculer dans un sous-mode, etc.
        """
        raise NotImplementedError

    def on_double_press(self) -> None:
        """
        **Double appui rapide** sur le bouton poussoir lorsque ce mode est actif.

        Ce hook est **optionnel** : par défaut, il ne fait rien.  
        Il peut être surchargé par un mode qui souhaite proposer un
        comportement spécifique sur double clic.

        Exemple d’usage typique :

        - dans le mode "Multimètre" : activer / désactiver la
          lecture automatique toutes les X secondes,
        - dans un autre mode : activer un mode "favori" ou une fonction
          avancée sans surcharger le simple appui court.
        """
        pass
