#!/usr/bin/env python3
"""
ARIA — Adaptive Real-time Intelligent Assistant
================================================
Entry point. Loads environment, builds the command registry, then runs the
main listen-dispatch loop until the user says "exit", "quit", or "goodbye".

Usage:
    python MyVoiceAssistant.py

Required: copy .env.example → .env and fill in your API keys.
"""

from __future__ import annotations

import logging
import os
import sys
import time

# Load .env before any assistant imports so os.getenv() sees the values
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("aria.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("aria.main")

from assistant.voice_io import speak, listen
from assistant.cache import ResponseCache
from assistant.commands import build_registry

# ── configuration ─────────────────────────────────────────────────────────────

WAKE_WORDS   = {"assistant", "aria", "hey aria", "ok aria", "hey assistant"}
EXIT_PHRASES = {"exit", "quit", "goodbye", "bye", "shut down", "stop"}

# ── helpers ───────────────────────────────────────────────────────────────────

def _has_wake_word(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in WAKE_WORDS)


def _is_exit(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in EXIT_PHRASES)


def _startup_greeting() -> None:
    hour = time.localtime().tm_hour
    if 5 <= hour < 12:
        period = "Good morning"
    elif 12 <= hour < 17:
        period = "Good afternoon"
    else:
        period = "Good evening"
    speak(
        f"{period}! I'm ARIA, your voice assistant. "
        "Say 'Aria' followed by a command to get started."
    )


# ── main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 60)
    logger.info("ARIA Voice Assistant v2.0 starting up")
    logger.info("=" * 60)

    registry     = build_registry()
    session_cache = ResponseCache()

    _startup_greeting()

    consecutive_failures = 0

    while True:
        try:
            text = listen(timeout=5, phrase_time_limit=12)

            if not text:
                consecutive_failures = 0
                continue

            if not _has_wake_word(text):
                continue

            consecutive_failures = 0
            logger.info("Wake word detected — dispatching: %s", text)

            # ── graceful exit ───────────────────────────────────────────────
            if _is_exit(text):
                stats = session_cache.stats()
                speak(
                    f"Goodbye! This session processed {stats['total_requests']} "
                    f"API requests with a {stats['hit_rate']} cache hit rate."
                )
                logger.info("Session ended. Cache stats: %s", stats)
                sys.exit(0)

            # ── dispatch to command registry ────────────────────────────────
            matched = registry.dispatch(text)
            if not matched:
                speak(
                    "I'm not sure how to help with that. "
                    "Try asking about weather, news, time, or say 'what can you do'."
                )

        except KeyboardInterrupt:
            speak("Shutting down. Goodbye!")
            logger.info("Interrupted by user (KeyboardInterrupt)")
            sys.exit(0)

        except Exception as exc:
            consecutive_failures += 1
            logger.exception("Unhandled error in main loop: %s", exc)
            if consecutive_failures >= 5:
                speak("I'm experiencing repeated errors and need to restart. Goodbye.")
                logger.critical("5 consecutive failures — exiting")
                sys.exit(1)


if __name__ == "__main__":
    main()
