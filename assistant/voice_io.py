"""Speech recognition pipeline and text-to-speech output.

Uses pyttsx3 (offline) as primary TTS with gTTS (online) as a higher-quality
fallback. Ambient noise adjustment runs on each listen() call to stay robust
across changing environments.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from typing import Optional

import pyttsx3
import speech_recognition as sr

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_engine: Optional[pyttsx3.Engine] = None


def _get_engine() -> pyttsx3.Engine:
    global _engine
    if _engine is None:
        _engine = pyttsx3.init()
        voices = _engine.getProperty("voices")
        if len(voices) > 1:
            _engine.setProperty("voice", voices[1].id)  # prefer female voice index
        _engine.setProperty("rate", 165)
        _engine.setProperty("volume", 1.0)
    return _engine


def speak(text: str, prefer_gtts: bool = False) -> None:
    """Say *text* aloud; logs to stdout and file simultaneously."""
    logger.info("ARIA: %s", text)
    print(f"\nARIA: {text}")

    if prefer_gtts:
        try:
            from gtts import gTTS
            import playsound
            tts = gTTS(text=text, lang="en", slow=False)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp = f.name
            tts.save(tmp)
            playsound.playsound(tmp)
            os.unlink(tmp)
            return
        except Exception as exc:
            logger.warning("gTTS unavailable (%s) — falling back to pyttsx3", exc)

    with _lock:
        eng = _get_engine()
        eng.say(text)
        eng.runAndWait()


def listen(
    timeout: int = 5,
    phrase_time_limit: int = 10,
) -> Optional[str]:
    """Record from microphone and return transcribed text, or None on failure."""
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.0
    recognizer.energy_threshold = 300

    with sr.Microphone() as source:
        # Brief ambient calibration so background noise doesn't swamp the signal
        recognizer.adjust_for_ambient_noise(source, duration=0.4)
        print("\n[Listening...]", flush=True)
        try:
            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
        except sr.WaitTimeoutError:
            return None

    try:
        text = recognizer.recognize_google(audio)
        print(f"You: {text}", flush=True)
        logger.info("User said: %s", text)
        return text
    except sr.UnknownValueError:
        logger.debug("Speech not understood")
        return None
    except sr.RequestError as exc:
        logger.error("Google STT unavailable: %s", exc)
        speak("Speech recognition is currently unavailable.")
        return None
