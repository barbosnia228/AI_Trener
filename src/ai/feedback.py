import threading
import queue


class FeedbackEngine:
    """
    Asynchronous text-to-speech engine for training coaching cues.

    Messages are queued and spoken sequentially in a daemon background thread,
    so they never block the video processing loop.
    Duplicate messages already waiting in the queue are silently ignored.
    """

    def __init__(self):
        """
        Initialise the TTS engine and start the worker thread.

        Blocks the calling thread for up to 5 seconds while waiting for TTS
        to become ready (signalled via ``threading.Event``). Continues regardless
        if the timeout expires.
        """
        self._queue: queue.Queue[str] = queue.Queue()
        self._ready = threading.Event()

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

        self._ready.wait(timeout=5.0)

    def say(self, message: str) -> None:
        """
        Add a coaching cue to the TTS playback queue (thread-safe).

        If an identical message is already waiting in the queue, the new one
        is discarded — this prevents the same warning from being repeated
        in rapid succession.

        Parameters
        ----------
        message : str
            Text to be spoken by the TTS engine.
        """
        pending = list(self._queue.queue)
        if message not in pending:
            self._queue.put(message)


    def _run(self) -> None:
        """
        Main loop of the TTS worker thread.

        Initialises the speech engine, then dequeues and speaks messages
        indefinitely. Falls back to printing messages to stdout if no TTS
        engine is available.

        Called exclusively by ``threading.Thread`` — do not invoke directly.
        """
        speaker = self._init_engine()

        if speaker is None:
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
        Attempt to initialise a TTS engine in priority order.

        Tries the following in sequence:
          1. **win32com SAPI** (Windows only) — stable, uses system voices.
             Prefers an English voice (Zira, David, Hazel, …); falls back to a
             Polish voice (Paulina, Zosia, …); uses the system default if neither
             is found.
          2. **pyttsx3** — cross-platform TTS wrapper. Prefers a Polish voice;
             uses the system default if none is found.
          3. **No TTS** — returns ``None``; messages will only appear on stdout.

        Signals readiness via ``self._ready.set()`` after a successful init
        (or after all options are exhausted).

        Returns
        -------
        callable | None
            A ``speak(text: str) -> None`` function ready to call,
            or ``None`` if no TTS engine is available.
        """

        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()

            sapi = win32com.client.Dispatch("SAPI.SpVoice")

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

            sapi.Rate   = 1
            sapi.Volume = 100

            print("[FeedbackEngine] TTS ready (win32com SAPI).")

            def speak(text: str) -> None:
                sapi.Speak(text, 0)

            self._ready.set()
            return speak

        except Exception as e:
            print(f"[FeedbackEngine] win32com SAPI unavailable: {e}")

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

            self._ready.set()
            return speak

        except Exception as e:
            print(f"[FeedbackEngine] pyttsx3 unavailable: {e}")
            self._ready.set()
            return None