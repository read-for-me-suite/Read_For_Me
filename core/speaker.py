# core/speaker.py
"""
core.speaker
============

Ce module définit la classe `Speaker`, responsable de la **synthèse vocale**
globale de l’assistant.

Objectifs du design
-------------------

Le moteur TTS `pyttsx3` n’est **pas thread-safe** :  
si plusieurs threads appellent `say()` ou `runAndWait()` en même temps,
des deadlocks ou blocages peuvent survenir (cas rencontré lorsqu’un mode,
le driver BLE ou le ModeManager faisaient des appels simultanés).

Pour éviter cela, nous utilisons :

- un **thread dédié** pour TOUTES les opérations pyttsx3 ;
- une **file d’attente thread-safe** (`queue.Queue`) pour les messages ;
- une API simple et non bloquante :
    - `speaker.speak("texte")` : ajoute un message à la file
    - `speaker.clear_queue()` : vide la file, utile lors d’un changement de mode

Ce design garantit :

- aucun appel direct concurrent à pyttsx3  
- une synthèse vocale **fluide et stable**  
- la possibilité d’appeler `speak()` depuis n’importe quel thread  
- un comportement contrôlé même en cas de spam vocal (BLE, mode, erreurs…)

Le module ne gère **que la TTS**.  
La logique métier (quand parler, quoi dire, filtrage, UX) appartient aux modes.
"""

import pyttsx3
import threading
import queue


class Speaker:
    """
    Gestionnaire de synthèse vocale basé sur pyttsx3, avec un worker dédié.

    Fonctionnement général
    ----------------------
    - Au démarrage, un **thread worker** (`_tts_worker`) est lancé.
    - Ce worker initialise pyttsx3 (obligatoirement dans SON thread).
    - Il lit les messages déposés dans `_queue` et les prononce dans l'ordre.
    - `speak(text)` ne bloque jamais : il ne fait qu'empiler une requête.
    - `clear_queue()` permet d'effacer les messages EN ATTENTE
      (sans couper celui déjà en train d'être lu).

    Avantages
    ---------
    - Architecture robuste même en cas d’appels concurrents.
    - Pas de risque de deadlock pyttsx3.
    - Priorité au comportement temps réel : éviter les files d’attente longues.

    Paramètres
    ----------
    rate : int
        Vitesse de lecture pyttsx3 (rotation / minute).  
        Valeur par défaut : 120 (locution lente et claire).
    """

    def __init__(self, rate: int = 120):
        """
        Initialise le speaker et démarre le thread TTS.

        Notes
        -----
        - Le moteur pyttsx3 **n’est pas créé ici** mais dans le thread worker,
          car pyttsx3 impose que toutes ses opérations soient faites dans
          le même thread, moteur inclus.
        """
        self._queue: "queue.Queue[str]" = queue.Queue()

        self._thread = threading.Thread(
            target=self._tts_worker,
            name="SpeakerTTSWorker",
            daemon=True,
        )

        self._engine = None      # sera instancié dans le worker
        self._rate = rate        # vitesse de lecture

        # Lancement immédiat du worker
        self._thread.start()

    # ----------------------------------------------------------------------
    #       INITIALISATION DU MOTEUR
    # ----------------------------------------------------------------------

    def _init_engine(self) -> None:
        """
        Initialise le moteur pyttsx3 **dans le thread worker**.

        - Configure la vitesse de lecture.
        - Sélectionne une voix française si disponible.
        """
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", self._rate)
        self._set_french_voice()

    def _set_french_voice(self) -> None:
        """
        Tente de sélectionner automatiquement une voix française.

        Recherche :
        - nom contenant "french"
        - identifiant contenant "fr"

        Si aucune voix compatible n'est trouvée, garde la voix par défaut.
        """
        for voice in self._engine.getProperty("voices"):
            name = voice.name.lower()
            vid = voice.id.lower()
            if "french" in name or "fr" in vid:
                self._engine.setProperty("voice", voice.id)
                print(f"Voix française activée : {voice.name} ({voice.id})")
                return

        print("Aucune voix française trouvée, utilisation de la voix par défaut.")

    # ----------------------------------------------------------------------
    #       THREAD WORKER TTS
    # ----------------------------------------------------------------------

    def _tts_worker(self) -> None:
        """
        Boucle principale du thread TTS.

        Fonctionnement
        --------------
        - Initialise pyttsx3.
        - Attend les textes dans `_queue`.
        - Les lit un par un.
        - Continue indéfiniment jusqu'à recevoir `None`.

        Ce worker tourne en permanence pendant toute la vie du programme.
        """
        self._init_engine()  # moteur créé dans ce thread

        while True:
            text = self._queue.get()  # attente bloquante

            if text is None:
                # Option éventuelle pour arrêt propre du thread
                break

            print(f"[TTS] {text}")
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                print(f"[TTS] Erreur TTS : {e}")

    # ----------------------------------------------------------------------
    #       API PUBLIQUE
    # ----------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """
        Ajoute un texte à la file d'attente pour synthèse vocale.

        Propriétés
        ----------
        - **thread-safe** : peut être appelé depuis n'importe où
          (BLE, ModeManager, timers…).
        - **non bloquant** : n'attend pas la fin de la lecture.

        Paramètres
        ----------
        text : str
            Message vocal à prononcer.
        """
        self._queue.put(text)

    def clear_queue(self) -> None:
        """
        Vide la file des messages EN ATTENTE.

        Important
        ---------
        - Ne coupe pas la phrase en cours de lecture.
        - Utilisé notamment lors d'un changement de mode, pour que
          l’utilisateur n'entende pas plusieurs annonces obsolètes.

        Cette méthode ne génère aucune erreur si la file est déjà vide.
        """
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
                self._queue.task_done()
        except queue.Empty:
            pass
