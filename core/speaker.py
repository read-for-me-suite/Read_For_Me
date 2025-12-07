# core/speaker.py
import pyttsx3
import threading
import queue


class Speaker:
    """
    Encapsule pyttsx3 pour fournir une interface simple de synthèse vocale.

    Nouveau design :
    - Un thread dédié gère TOUTES les interactions avec pyttsx3.
    - speaker.speak(text) est thread-safe et non bloquant : il met juste le texte en file.
    - On évite ainsi les blocages ou deadlocks lorsqu'on appelle speak() depuis
      des threads différents (ex: thread BLE).
    """

    def __init__(self, rate: int = 120):
        # File de messages à prononcer
        self._queue: "queue.Queue[str]" = queue.Queue()

        # Thread TTS dédié
        self._thread = threading.Thread(
            target=self._tts_worker,
            name="SpeakerTTSWorker",
            daemon=True,
        )

        # Initialisation du moteur dans le thread TTS (pas dans le thread principal)
        self._engine = None  # sera créé dans le worker
        self._rate = rate

        # Lancement du worker
        self._thread.start()

    def _init_engine(self) -> None:
        """
        Initialise pyttsx3 dans le thread TTS.
        """
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", self._rate)
        self._set_french_voice()

    def _set_french_voice(self) -> None:
        """
        Tente de sélectionner une voix française.
        Si aucune voix FR n'est trouvée, utilise la voix par défaut.
        """
        for voice in self._engine.getProperty("voices"):
            name = voice.name.lower()
            vid = voice.id.lower()
            if "french" in name or "fr" in vid:
                self._engine.setProperty("voice", voice.id)
                print(f"Voix française activée : {voice.name} ({voice.id})")
                return
        print("Aucune voix française trouvée, utilisation de la voix par défaut.")

    def _tts_worker(self) -> None:
        """
        Boucle principale du thread TTS.

        Récupère les textes dans la file et les passe au moteur pyttsx3.
        """
        # Initialisation du moteur dans CE thread
        self._init_engine()

        while True:
            text = self._queue.get()  # bloque en attente d'un texte
            if text is None:
                # Permettrait un jour de stopper proprement le worker si besoin
                break

            print(f"[TTS] {text}")
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                print(f"[TTS] Erreur TTS : {e}")

    def speak(self, text: str) -> None:
        """
        Demande à prononcer un texte de façon asynchrone.

        - Thread-safe : peut être appelé depuis n'importe quel thread.
        - Non bloquant : le texte est juste mis en file.
        """
        self._queue.put(text)

    def clear_queue(self) -> None:
        """
        Vide les messages EN ATTENTE dans la file (sans couper la phrase
        actuellement en cours de lecture).

        Utile lors d'un changement de mode pour éviter d'avoir une
        rafale d'anciennes annonces de modes.
        """
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
                self._queue.task_done()
        except queue.Empty:
            pass
