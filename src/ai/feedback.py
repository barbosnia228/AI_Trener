import pyttsx3
import threading

class FeedbackEngine:
    def __init__(self):
        self.speaker = pyttsx3.init()
        self.is_speaking = False

    def say(self, message):
        if not self.is_speaking:
            threading.Thread(target=self._speak, args=(message,), daemon=True).start()

    def _speak(self, message):
        self.is_speaking = True
        self.speaker.say(message)
        self.speaker.runAndWait()
        self.is_speaking = False