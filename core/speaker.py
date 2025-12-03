# core/speaker.py
import pyttsx3


class Speaker:
    """
    Encapsule pyttsx3 pour fournir une interface simple de synthèse vocale.

    - Initialise le moteur une seule fois
    - Essaie de sélectionner une voix française si disponible
    """

    def __init__(self, rate: int = 120):
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        self._set_french_voice()

    def _set_french_voice(self) -> None:
        """
        Tente de sélectionner une voix française.
        Si aucune voix FR n'est trouvée, utilise la voix par défaut.
        """
        for voice in self.engine.getProperty("voices"):
            name = voice.name.lower()
            vid = voice.id.lower()
            if "french" in name or "fr" in vid:
                self.engine.setProperty("voice", voice.id)
                print(f"Voix française activée : {voice.name} ({voice.id})")
                return
        print("Aucune voix française trouvée, utilisation de la voix par défaut.")

    def speak(self, text: str) -> None:
        """
        Prononce un texte de façon synchrone.

        Parameters
        ----------
        text : str
            Le texte à prononcer.
        """
        print(f"[TTS] {text}")
        self.engine.say(text)
        self.engine.runAndWait()
