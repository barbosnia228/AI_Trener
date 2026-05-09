import threading
import queue


class FeedbackEngine:
    def __init__(self):
        self._queue: queue.Queue[str] = queue.Queue()
        self._ready = threading.Event()  # чекаємо поки worker стартує

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

        # Чекаємо максимум 5 сек поки TTS ініціалізується
        self._ready.wait(timeout=5.0)

    # ── Public API ────────────────────────────────────────────────────────────

    def say(self, message: str) -> None:
        pending = list(self._queue.queue)
        if message not in pending:
            self._queue.put(message)

    # ── Private ───────────────────────────────────────────────────────────────

    def _run(self) -> None:
        engine = self._init_engine()
        self._ready.set()  # сигналізуємо що готові

        if engine is None:
            # TTS недоступний — просто друкуємо
            while True:
                msg = self._queue.get()
                print(f"[TTS] {msg}")
                self._queue.task_done()
            return

        while True:
            message = self._queue.get()
            print(f"[FeedbackEngine] Speaking: {message}")
            try:
                engine.say(message)
                engine.runAndWait()
            except Exception as e:
                print(f"[FeedbackEngine] Błąd TTS: {e}")
            finally:
                self._queue.task_done()

    def _init_engine(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")

            polish_voice = None
            for v in voices:
                name = (v.name or "").lower()
                vid  = (v.id  or "").lower()
                if ("polish" in name or "pl-pl" in vid
                        or "pl_pl" in vid or "paulina" in name or "zosia" in name):
                    polish_voice = v.id
                    break

            if polish_voice:
                engine.setProperty("voice", polish_voice)
                print(f"[FeedbackEngine] Znaleziono głos polski: {polish_voice}")
            else:
                print(
                    "[FeedbackEngine] Nie znaleziono polskiego głosu SAPI5.\n"
                    "  Zainstaluj go: Ustawienia → Czas i język → Mowa → Dodaj głos → Polski.\n"
                    "  Używam domyślnego głosu systemu."
                )

            engine.setProperty("rate",   155)
            engine.setProperty("volume", 1.0)
            print("[FeedbackEngine] TTS gotowy.")
            return engine

        except Exception as e:
            print(f"[FeedbackEngine] TTS unavailable: {e}")
            return None