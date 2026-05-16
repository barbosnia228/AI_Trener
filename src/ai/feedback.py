import threading
import queue


class FeedbackEngine:
    def __init__(self):
        self._queue: queue.Queue[str] = queue.Queue()
        self._ready = threading.Event()

        # COM must be initialised on the same thread that uses it,
        # so we spin up a dedicated daemon thread.
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

        # Wait up to 5 seconds for TTS to initialise
        self._ready.wait(timeout=5.0)

    # ── Public API ────────────────────────────────────────────────────────────

    def say(self, message: str) -> None:
        pending = list(self._queue.queue)
        if message not in pending:
            self._queue.put(message)

    # ── Private ───────────────────────────────────────────────────────────────

    def _run(self) -> None:
        speaker = self._init_engine()

        if speaker is None:
            # TTS unavailable — fall back to print
            while True:
                msg = self._queue.get()
                print(f"[TTS] {msg}")
                self._queue.task_done()
            return

        while True:
            message = self._queue.get()
            print(f"[FeedbackEngine] Speaking: {message}")
            try:
                speaker(message)
            except Exception as e:
                print(f"[FeedbackEngine] TTS error: {e}")
            finally:
                self._queue.task_done()

    def _init_engine(self):
        """
        Try win32com SAPI first (most reliable on Windows background threads),
        fall back to pyttsx3, then silent.
        Returns a callable: speak_fn(text) -> None, or None on failure.
        """

        # ── Option 1: win32com SAPI (Windows only) ────────────────────────────
        try:
            import pythoncom
            import win32com.client

            # CoInitialize must be called on this thread
            pythoncom.CoInitialize()

            sapi = win32com.client.Dispatch("SAPI.SpVoice")

            # Find best voice: English first, Polish fallback
            voices = sapi.GetVoices()
            chosen_token = None
            chosen_desc  = ""

            english_keywords = ("zira", "david", "hazel", "george", "susan",
                                 "english", "en-us", "en-gb", "en_us", "en_gb")
            polish_keywords  = ("paulina", "polish", "pl-pl", "pl_pl", "zosia")

            for i in range(voices.Count):
                token = voices.Item(i)
                desc  = token.GetDescription().lower()
                if any(k in desc for k in english_keywords):
                    chosen_token = token
                    chosen_desc  = token.GetDescription()
                    print(f"[FeedbackEngine] English voice found: {chosen_desc}")
                    break

            if not chosen_token:
                for i in range(voices.Count):
                    token = voices.Item(i)
                    desc  = token.GetDescription().lower()
                    if any(k in desc for k in polish_keywords):
                        chosen_token = token
                        chosen_desc  = token.GetDescription()
                        print(f"[FeedbackEngine] No English voice — using Polish: {chosen_desc}")
                        break

            if chosen_token:
                sapi.Voice = chosen_token
            else:
                print("[FeedbackEngine] No suitable voice found. Using system default.")

            sapi.Rate   = 1    # -10 (slow) … 10 (fast), 1 ≈ 155 wpm
            sapi.Volume = 100  # 0-100

            print("[FeedbackEngine] TTS ready (win32com SAPI).")

            def speak(text: str) -> None:
                # 0 = synchronous (blocks until done)
                sapi.Speak(text, 0)

            return speak

        except Exception as e:
            print(f"[FeedbackEngine] win32com SAPI unavailable: {e}")

        # ── Option 2: pyttsx3 fallback ────────────────────────────────────────
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")

            polish_voice = None
            for v in voices:
                name = (v.name or "").lower()
                vid  = (v.id  or "").lower()
                if any(k in name or k in vid
                       for k in ("polish", "pl-pl", "pl_pl", "paulina", "zosia")):
                    polish_voice = v.id
                    break

            if polish_voice:
                engine.setProperty("voice", polish_voice)
                print(f"[FeedbackEngine] Polish voice found (pyttsx3): {polish_voice}")
            else:
                print("[FeedbackEngine] No Polish voice found (pyttsx3). Using default.")

            engine.setProperty("rate",   155)
            engine.setProperty("volume", 1.0)
            print("[FeedbackEngine] TTS ready (pyttsx3).")

            def speak(text: str) -> None:
                engine.say(text)
                engine.runAndWait()

            return speak

        except Exception as e:
            print(f"[FeedbackEngine] pyttsx3 unavailable: {e}")
            return None