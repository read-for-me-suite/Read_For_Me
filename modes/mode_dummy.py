from core.mode_base import Mode

class ModeDummy(Mode):
    def __init__(self, speaker):
        super().__init__("Mode test")
        self.speaker = speaker

    def on_enter(self):
        #self.speaker.speak("Mode test.")
        pass

    def on_exit(self):
        #self.speaker.speak("Sortie du mode test.")
        pass

    def on_short_press(self):
        self.speaker.speak("Appui dans le mode test.")

    def on_long_press(self):
        self.speaker.speak("Appui long dans le mode test.")
