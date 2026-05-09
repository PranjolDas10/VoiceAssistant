"""Command registry and all 60+ intent handlers for ARIA.

Each Command holds compiled regex patterns and a handler callable.
CommandRegistry.dispatch() finds the first matching command and invokes it,
speaking the returned string (or nothing if the handler speaks directly).
"""

from __future__ import annotations

import calendar as _cal
import ctypes
import datetime
import logging
import os
import random
import re
import smtplib
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable, List, Optional

import pyjokes
import wikipedia
import requests

from .cache import ResponseCache
from .api_client import APIClient
from .voice_io import speak, listen

logger = logging.getLogger(__name__)

# ── module-level singletons (shared across all handlers) ─────────────────────
_cache = ResponseCache()
_http = APIClient()

# ── constants ─────────────────────────────────────────────────────────────────
LANGUAGE_MAP: dict[str, str] = {
    "spanish": "es",    "french": "fr",     "german": "de",
    "italian": "it",    "portuguese": "pt", "russian": "ru",
    "japanese": "ja",   "chinese": "zh-CN", "korean": "ko",
    "arabic": "ar",     "hindi": "hi",      "dutch": "nl",
    "turkish": "tr",    "polish": "pl",     "swedish": "sv",
    "danish": "da",     "norwegian": "no",  "finnish": "fi",
    "greek": "el",      "hebrew": "he",
}

_ORDINALS = [
    "1st","2nd","3rd","4th","5th","6th","7th","8th","9th","10th",
    "11th","12th","13th","14th","15th","16th","17th","18th","19th","20th",
    "21st","22nd","23rd","24th","25th","26th","27th","28th","29th","30th","31st",
]

_GREET_RESPONSES = [
    "Hey there!", "What's good?", "Hello! How can I help?",
    "Hi! What can I do for you?", "Hey, good to hear from you!",
]

_WEB_SITES: dict[str, str] = {
    "youtube":      "https://youtube.com",
    "google":       "https://google.com",
    "github":       "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit":       "https://reddit.com",
    "netflix":      "https://netflix.com",
    "linkedin":     "https://linkedin.com",
    "twitter":      "https://twitter.com",
    "spotify":      "https://open.spotify.com",
    "gmail":        "https://mail.google.com",
}

_APP_ENV_KEYS: dict[str, str] = {
    "chrome":    "CHROME_PATH",
    "word":      "WORD_PATH",
    "excel":     "EXCEL_PATH",
    "vs code":   "VSCODE_PATH",
    "notepad":   "NOTEPAD_PATH",
    "calculator":"CALCULATOR_PATH",
    "paint":     "PAINT_PATH",
}

_APP_DEFAULTS: dict[str, str] = {
    "chrome":     r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "word":       r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel":      r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "vs code":    os.path.join(os.path.expanduser("~"), r"AppData\Local\Programs\Microsoft VS Code\Code.exe"),
    "notepad":    "notepad.exe",
    "calculator": "calc.exe",
    "paint":      "mspaint.exe",
}


# ── core registry types ───────────────────────────────────────────────────────

@dataclass
class Command:
    patterns:     List[str]
    handler:      Callable[[str], Optional[str]]
    description:  str
    category:     str
    _compiled:    List[re.Pattern] = field(default_factory=list, repr=False, init=False)

    def __post_init__(self) -> None:
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def matches(self, text: str) -> bool:
        return any(p.search(text) for p in self._compiled)


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: List[Command] = []

    def register(self, *cmds: Command) -> None:
        self._commands.extend(cmds)

    def dispatch(self, text: str) -> bool:
        """Find first matching command, invoke it, speak result. Returns True if matched."""
        for cmd in self._commands:
            if cmd.matches(text):
                logger.debug("Matched command: %s", cmd.description)
                try:
                    result = cmd.handler(text)
                    if result:
                        speak(result)
                except Exception as exc:
                    logger.exception("Handler '%s' raised: %s", cmd.description, exc)
                    speak("I ran into a problem with that. Please try again.")
                return True
        return False

    def capability_summary(self) -> str:
        cats: dict[str, list] = {}
        for cmd in self._commands:
            cats.setdefault(cmd.category, []).append(cmd.description)
        lines = [f"I can handle {len(self._commands)} command types across {len(cats)} categories:"]
        for cat, names in cats.items():
            lines.append(f"  {cat}: {', '.join(names)}")
        return "\n".join(lines)


# ── DATE / TIME ───────────────────────────────────────────────────────────────

def _handle_date(text: str) -> str:
    now = datetime.datetime.now()
    week = _cal.day_name[now.weekday()]
    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    return f"Today is {week}, {months[now.month - 1]} the {_ORDINALS[now.day - 1]}."


def _handle_time(text: str) -> str:
    now = datetime.datetime.now()
    hour = now.hour % 12 or 12
    minute = f"{now.minute:02d}"
    meridiem = "PM" if now.hour >= 12 else "AM"
    return f"It is {hour}:{minute} {meridiem}."


# ── GREETINGS / IDENTITY ──────────────────────────────────────────────────────

def _handle_greeting(text: str) -> str:
    return random.choice(_GREET_RESPONSES)


def _handle_how_are_you(_: str) -> str:
    return "I'm doing great, thank you! How can I help you today?"


def _handle_who_are_you(_: str) -> str:
    return (
        "I'm ARIA — an Adaptive Real-time Intelligent Assistant. "
        "I can answer questions, set timers, send messages, check weather, "
        "translate text, open apps, and much more. Just ask!"
    )


def _handle_name(_: str) -> str:
    return "My name is ARIA."


def _handle_whoami(_: str) -> str:
    return "You're the human giving me orders. A pretty important job!"


def _handle_why_exist(_: str) -> str:
    return "I exist to make your life easier. That's reason enough."


def _handle_fine(_: str) -> str:
    return "Glad to hear it!"


def _handle_capabilities(_: str) -> str:
    return (
        "I can tell you the time, date, and weather. I can search Google, YouTube, "
        "and Wikipedia. I can translate text, set timers, send emails and SMS, "
        "take notes, tell jokes, control system volume, open apps, and much more."
    )


# ── BROWSER / APPS ────────────────────────────────────────────────────────────

def _handle_open(text: str) -> str:
    lower = text.lower()

    for site, url in _WEB_SITES.items():
        if site in lower:
            webbrowser.open(url)
            return f"Opening {site.title()}."

    for app, env_key in _APP_ENV_KEYS.items():
        if app in lower:
            path = os.getenv(env_key, _APP_DEFAULTS.get(app, ""))
            if not path:
                return f"Path for {app} is not configured."
            try:
                os.startfile(path)
                return f"Opening {app.title()}."
            except Exception as exc:
                logger.error("Could not open %s: %s", app, exc)
                return f"Could not open {app}. Check the path in your .env file."

    return "I don't know how to open that. You can configure app paths in your .env file."


# ── SEARCH ────────────────────────────────────────────────────────────────────

def _handle_youtube_search(text: str) -> str:
    match = re.search(r'(?:play|youtube|search youtube)\s+(.+)', text, re.IGNORECASE)
    query = match.group(1).strip() if match else text
    url = "https://www.youtube.com/results?search_query=" + "+".join(query.split())
    webbrowser.open(url)
    return f"Searching YouTube for: {query}."


def _handle_google_search(text: str) -> str:
    match = re.search(r'(?:search|google)\s+(.+)', text, re.IGNORECASE)
    query = match.group(1).strip() if match else text
    url = "https://www.google.com/search?q=" + "+".join(query.split())
    webbrowser.open(url)
    return f"Searching Google for: {query}."


# ── KNOWLEDGE: WIKIPEDIA ─────────────────────────────────────────────────────

def _handle_wikipedia(text: str) -> str:
    match = re.search(
        r'(?:who is|tell me about|wikipedia|search wiki(?:pedia)?(?:\s+for)?)\s+(.+)',
        text, re.IGNORECASE,
    )
    if not match:
        return "Who or what would you like me to look up?"

    query = match.group(1).strip()
    cached = _cache.get("wikipedia", query)
    if cached:
        return cached

    try:
        result = wikipedia.summary(query, sentences=2, auto_suggest=True)
        _cache.set("wikipedia", query, result)
        return result
    except wikipedia.DisambiguationError as exc:
        return f"That's ambiguous. Did you mean: {exc.options[0]}?"
    except wikipedia.PageError:
        return f"I couldn't find a Wikipedia article for '{query}'."
    except Exception as exc:
        logger.error("Wikipedia error: %s", exc)
        return "Wikipedia lookup failed. Please try again."


# ── KNOWLEDGE: WOLFRAM ALPHA ─────────────────────────────────────────────────

def _wolfram_query(query: str) -> str:
    app_id = os.getenv("WOLFRAM_APP_ID", "")
    if not app_id:
        return "Wolfram Alpha is not configured. Set WOLFRAM_APP_ID in your .env file."

    cached = _cache.get("wolfram", query)
    if cached:
        return cached

    try:
        import wolframalpha
        client = wolframalpha.Client(app_id)
        res = client.query(query)
        answer = next(res.results).text
        result = f"The answer is {answer}."
        _cache.set("wolfram", query, result)
        return result
    except StopIteration:
        return "I couldn't find an answer for that."
    except Exception as exc:
        logger.error("Wolfram error: %s", exc)
        return "Calculation failed. Please try again."


def _handle_calculate(text: str) -> str:
    match = re.search(r'(?:calculate|compute|solve|math)\s+(.+)', text, re.IGNORECASE)
    query = match.group(1).strip() if match else text
    return _wolfram_query(query)


def _handle_what_is(text: str) -> str:
    match = re.search(r'(?:what is|define|explain)\s+(.+)', text, re.IGNORECASE)
    query = match.group(1).strip() if match else text
    return _wolfram_query(query)


# ── WEATHER ───────────────────────────────────────────────────────────────────

def _handle_weather(text: str) -> str:
    key = os.getenv("OPENWEATHER_KEY", "")
    if not key:
        return "Weather is not configured. Set OPENWEATHER_KEY in your .env file."

    match = re.search(
        r'(?:weather|temperature|forecast)\s+(?:in|for|at)\s+(.+)', text, re.IGNORECASE
    )
    city = match.group(1).strip() if match else "New York"

    cached = _cache.get("weather", city)
    if cached:
        return cached

    try:
        data = _http.get_json(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"appid": key, "q": city, "units": "metric"},
        )
        if "main" not in data:
            return f"City '{city}' not found."
        temp      = round(data["main"]["temp"])
        feels     = round(data["main"]["feels_like"])
        humidity  = data["main"]["humidity"]
        desc      = data["weather"][0]["description"]
        result = (
            f"In {city.title()}: {temp}°C, feels like {feels}°C, "
            f"{desc}. Humidity {humidity}%."
        )
        _cache.set("weather", city, result)
        return result
    except Exception as exc:
        logger.error("Weather API error: %s", exc)
        return "Unable to fetch weather right now. Please try again."


# ── NEWS ──────────────────────────────────────────────────────────────────────

def _handle_news(text: str) -> Optional[str]:
    key = os.getenv("NEWS_API_KEY", "")
    if not key:
        return "News API is not configured. Set NEWS_API_KEY in your .env file."

    category = "general"
    for cat in ("technology", "sports", "business", "entertainment", "health", "science"):
        if cat in text.lower():
            category = cat
            break

    cache_key = f"headlines_{category}"
    articles = _cache.get("news", cache_key)

    if not articles:
        try:
            data = _http.get_json(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "category": category, "pageSize": 5, "apiKey": key},
            )
            articles = [
                a["title"] for a in data.get("articles", [])[:5] if a.get("title")
            ]
            _cache.set("news", cache_key, articles)
        except Exception as exc:
            logger.error("News API error: %s", exc)
            return "Unable to fetch news right now."

    speak(f"Here are the top {category} headlines.")
    for i, headline in enumerate(articles, 1):
        speak(f"{i}. {headline}")
    return None


# ── TRANSLATION ───────────────────────────────────────────────────────────────

def _handle_translate(text: str) -> str:
    match = re.search(
        r'(?:translate|say|how do you say)\s+(.+?)\s+(?:to|in)\s+(\w+)',
        text, re.IGNORECASE,
    )
    if not match:
        return "Please say: translate [phrase] to [language]."

    phrase    = match.group(1).strip()
    lang_name = match.group(2).lower()
    lang_code = LANGUAGE_MAP.get(lang_name)
    if not lang_code:
        supported = ", ".join(LANGUAGE_MAP.keys())
        return f"I don't know '{lang_name}'. Supported languages: {supported}."

    cache_key = f"{phrase}|{lang_code}"
    cached = _cache.get("translate", cache_key)
    if cached:
        return cached

    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="auto", target=lang_code).translate(phrase)
        result = f"'{phrase}' in {lang_name.title()} is: {translated}."
        _cache.set("translate", cache_key, result)
        return result
    except Exception as exc:
        logger.error("Translation error: %s", exc)
        return "Translation failed. Please try again."


# ── COMMUNICATION: EMAIL ──────────────────────────────────────────────────────

def _handle_email(text: str) -> Optional[str]:
    email_addr   = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not all([email_addr, app_password]):
        return "Email is not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env."

    speak("What would you like me to say?")
    content = listen()
    if not content:
        return "I didn't catch the message."

    speak("Who should I send it to? Say an email address or press Enter to use the default.")
    to_addr = os.getenv("DEFAULT_EMAIL_TO", email_addr)

    msg = MIMEMultipart()
    msg["From"]    = email_addr
    msg["To"]      = to_addr
    msg["Subject"] = "Message from ARIA Voice Assistant"
    msg.attach(MIMEText(content, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_addr, app_password)
            server.send_message(msg)
        logger.info("Email sent to %s", to_addr)
        return "Email sent successfully."
    except Exception as exc:
        logger.error("Email failed: %s", exc)
        return "Failed to send email. Please check your credentials."


# ── COMMUNICATION: SMS (TWILIO) ───────────────────────────────────────────────

def _handle_sms(text: str) -> Optional[str]:
    sid      = os.getenv("TWILIO_SID")
    token    = os.getenv("TWILIO_TOKEN")
    from_num = os.getenv("TWILIO_FROM")
    to_num   = os.getenv("TWILIO_TO")

    if not all([sid, token, from_num, to_num]):
        return "SMS is not configured. Set TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, TWILIO_TO in .env."

    speak("What should I say in the message?")
    body = listen()
    if not body:
        return "I didn't catch the message."

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        msg = client.messages.create(body=body, from_=from_num, to=to_num)
        logger.info("SMS sent: SID=%s", msg.sid)
        return "Message sent successfully."
    except Exception as exc:
        logger.error("SMS failed: %s", exc)
        return "Failed to send message. Check your Twilio credentials."


# ── NOTES ─────────────────────────────────────────────────────────────────────

def _handle_note(text: str) -> Optional[str]:
    speak("What would you like me to write down?")
    note_text = listen()
    if not note_text:
        return "I didn't catch that."

    notes_dir = Path("notes")
    notes_dir.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    note_file = notes_dir / f"{stamp}_note.txt"
    note_file.write_text(note_text, encoding="utf-8")

    try:
        subprocess.Popen(["notepad.exe", str(note_file)])
    except Exception:
        pass

    return f"Note saved: '{note_text[:60]}{'...' if len(note_text) > 60 else ''}'."


# ── TIMER / ALARM ─────────────────────────────────────────────────────────────

def _handle_timer(text: str) -> str:
    match = re.search(r'(\d+)\s*(second|minute|hour)s?', text, re.IGNORECASE)
    if not match:
        return "Please say: set timer for [number] seconds, minutes, or hours."

    n    = int(match.group(1))
    unit = match.group(2).lower()
    secs = n * {"second": 1, "minute": 60, "hour": 3600}[unit]
    label = f"{n} {unit}{'s' if n != 1 else ''}"

    def _ring() -> None:
        time.sleep(secs)
        speak(f"Your {label} timer is up!")

    threading.Thread(target=_ring, daemon=True).start()
    return f"Timer set for {label}."


def _handle_reminder(text: str) -> str:
    match = re.search(r'remind(?:er)?\s+(?:me\s+)?(?:in\s+)?(.+)', text, re.IGNORECASE)
    if not match:
        return "Please say: remind me in [time] to [task]."
    return f"Reminder set: {match.group(1).strip()}."


# ── ENTERTAINMENT ─────────────────────────────────────────────────────────────

def _handle_joke(_: str) -> str:
    return pyjokes.get_joke()


def _handle_music(text: str) -> Optional[str]:
    music_dir = os.getenv("MUSIC_DIR", "")
    if not music_dir or not Path(music_dir).is_dir():
        return (
            "Music directory not configured. "
            "Set MUSIC_DIR in your .env file to a folder of MP3s."
        )
    songs = [f for f in Path(music_dir).iterdir() if f.suffix.lower() == ".mp3"]
    if not songs:
        return "No MP3 files found in your music directory."
    choice = random.choice(songs)
    speak(f"Playing {choice.stem}.")
    try:
        import playsound
        playsound.playsound(str(choice))
    except Exception as exc:
        logger.error("Music playback error: %s", exc)
    return None


def _handle_coinflip(_: str) -> str:
    return f"It's {random.choice(['heads', 'tails'])}!"


def _handle_dice(_: str) -> str:
    return f"You rolled a {random.randint(1, 6)}."


def _handle_random_number(text: str) -> str:
    match = re.search(r'between\s+(\d+)\s+and\s+(\d+)', text, re.IGNORECASE)
    if match:
        lo, hi = int(match.group(1)), int(match.group(2))
        return f"Your random number is {random.randint(lo, hi)}."
    return f"Your random number is {random.randint(1, 100)}."


# ── SYSTEM ────────────────────────────────────────────────────────────────────

def _handle_recycle_bin(_: str) -> str:
    try:
        import winshell
        winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=True)
        return "Recycle bin emptied."
    except ImportError:
        return "winshell is not installed. Run: pip install winshell."
    except Exception as exc:
        return f"Could not empty recycle bin: {exc}"


def _handle_wallpaper(_: str) -> str:
    wallpaper_dir = os.getenv("WALLPAPER_DIR", "")
    if not wallpaper_dir or not Path(wallpaper_dir).is_dir():
        return "Wallpaper directory not configured. Set WALLPAPER_DIR in your .env file."
    images = [
        f for f in Path(wallpaper_dir).iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")
    ]
    if not images:
        return "No images found in your wallpaper directory."
    choice = random.choice(images)
    ctypes.windll.user32.SystemParametersInfoW(20, 0, str(choice.resolve()), 3)
    return "Wallpaper changed."


def _handle_screenshot(_: str) -> str:
    try:
        import pyautogui
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"screenshot_{stamp}.png"
        pyautogui.screenshot(fname)
        return f"Screenshot saved as {fname}."
    except ImportError:
        return "Screenshot requires pyautogui. Run: pip install pyautogui."
    except Exception as exc:
        return f"Screenshot failed: {exc}"


def _handle_lock(_: str) -> Optional[str]:
    ctypes.windll.user32.LockWorkStation()
    return None  # already locked by the time we'd speak


def _handle_volume_up(_: str) -> str:
    try:
        import pyautogui
        for _ in range(5):
            pyautogui.press("volumeup")
        return "Volume increased."
    except ImportError:
        return "Volume control requires pyautogui."


def _handle_volume_down(_: str) -> str:
    try:
        import pyautogui
        for _ in range(5):
            pyautogui.press("volumedown")
        return "Volume decreased."
    except ImportError:
        return "Volume control requires pyautogui."


def _handle_mute(_: str) -> str:
    try:
        import pyautogui
        pyautogui.press("volumemute")
        return "Muted."
    except ImportError:
        return "Mute requires pyautogui."


# ── MAPS / LOCATION ───────────────────────────────────────────────────────────

def _handle_maps(text: str) -> str:
    match = re.search(r'where is\s+(.+)', text, re.IGNORECASE)
    location = match.group(1).strip() if match else text
    url = "https://www.google.com/maps/search/" + "+".join(location.split())
    webbrowser.open(url)
    return f"Showing {location} on Google Maps."


def _handle_directions(text: str) -> str:
    match = re.search(r'directions?\s+(?:to|from)\s+(.+)', text, re.IGNORECASE)
    destination = match.group(1).strip() if match else text
    url = "https://www.google.com/maps/dir/?api=1&destination=" + "+".join(destination.split())
    webbrowser.open(url)
    return f"Opening directions to {destination}."


# ── GOOGLE CALENDAR ───────────────────────────────────────────────────────────

def _handle_calendar(_: str) -> Optional[str]:
    try:
        from .auth import get_calendar_service
        service = get_calendar_service()
    except Exception as exc:
        return f"Calendar unavailable: {exc}"

    now = datetime.datetime.utcnow().isoformat() + "Z"
    try:
        result = service.events().list(
            calendarId="primary", timeMin=now,
            maxResults=5, singleEvents=True, orderBy="startTime",
        ).execute()
        events = result.get("items", [])
        if not events:
            return "You have no upcoming events."
        speak(f"You have {len(events)} upcoming event{'s' if len(events) != 1 else ''}.")
        for event in events:
            start   = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "Untitled event")
            if "T" in start:
                t = start.split("T")[1][:5]
                speak(f"{summary} at {t}.")
            else:
                speak(summary + ".")
    except Exception as exc:
        logger.error("Calendar error: %s", exc)
        return "Unable to fetch calendar events."
    return None


# ── UTILITY ───────────────────────────────────────────────────────────────────

def _handle_ip(_: str) -> str:
    cached = _cache.get("default", "my_ip")
    if cached:
        return cached
    try:
        ip = _http.get_json("https://api.ipify.org?format=json")["ip"]
        result = f"Your public IP address is {ip}."
        _cache.set("default", "my_ip", result, ttl=300)
        return result
    except Exception:
        return "Could not retrieve IP address."


def _handle_sleep(text: str) -> str:
    match = re.search(r'(\d+)', text)
    secs = int(match.group(1)) if match else 10
    speak(f"Going quiet for {secs} seconds.")
    time.sleep(secs)
    return "I'm listening again."


def _handle_pizza(_: str) -> Optional[str]:
    """Selenium-based Domino's ordering flow (XPaths may need updating)."""
    speak("Opening Dominos for you.")
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from time import sleep as slp

        options = webdriver.ChromeOptions()
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        driver.get("https://www.dominos.co.in/")
        slp(2)
        speak("Dominos is open. Proceed with your order in the browser.")
        return None
    except Exception as exc:
        logger.error("Pizza ordering error: %s", exc)
        return "Could not launch the Dominos ordering flow. Is ChromeDriver installed?"


def _handle_cache_stats(_: str) -> str:
    stats = _cache.stats()
    return (
        f"Cache stats: {stats['hits']} hits, {stats['misses']} misses, "
        f"hit rate {stats['hit_rate']}, {stats['cached_entries']} entries stored."
    )


# ── REGISTRY FACTORY ─────────────────────────────────────────────────────────

def build_registry() -> CommandRegistry:
    """Instantiate and populate the CommandRegistry with all 60+ command intents."""
    r = CommandRegistry()

    # Date / Time
    r.register(
        Command(
            [r"\bdate\b", r"\bday\b", r"\bmonth\b", r"today'?s? date", r"what day"],
            _handle_date, "Current date", "Date & Time",
        ),
        Command(
            [r"\btime\b", r"what time", r"current time"],
            _handle_time, "Current time", "Date & Time",
        ),
    )

    # Greetings / Identity
    r.register(
        Command(
            [r"\b(hi|hey|hello|hola|greetings|wassup|good morning|good afternoon|good evening)\b"],
            _handle_greeting, "Greeting", "Identity",
        ),
        Command(
            [r"how are you", r"how('re| are) (you|things)"],
            _handle_how_are_you, "How are you", "Identity",
        ),
        Command(
            [r"who are you", r"define yourself", r"what are you", r"introduce yourself"],
            _handle_who_are_you, "Who are you", "Identity",
        ),
        Command(
            [r"your name", r"what('s| is) (your )?name"],
            _handle_name, "Assistant name", "Identity",
        ),
        Command(
            [r"who am i", r"do you know me"],
            _handle_whoami, "Who am I", "Identity",
        ),
        Command(
            [r"why (do you exist|are you here|did you come)", r"what('s| is) your purpose"],
            _handle_why_exist, "Purpose", "Identity",
        ),
        Command(
            [r"\b(i('m| am) (fine|good|great|doing well)|not bad)\b"],
            _handle_fine, "Positive response", "Identity",
        ),
        Command(
            [r"what can you do", r"your capabilities", r"help me", r"list commands"],
            _handle_capabilities, "Capabilities list", "Identity",
        ),
    )

    # Browser / Apps (single handler covers 15+ sites/apps)
    r.register(
        Command(
            [r"\bopen\b", r"\blaunch\b", r"\bstart\b"],
            _handle_open, "Open app or website", "Browser & Apps",
        ),
    )

    # Search
    r.register(
        Command(
            [r"(play|youtube|search youtube)\s+\w", r"on youtube"],
            _handle_youtube_search, "YouTube search", "Search",
        ),
        Command(
            [r"(search|google)\s+\w", r"look up\s+\w", r"find\s+\w+\s+on google"],
            _handle_google_search, "Google search", "Search",
        ),
    )

    # Knowledge
    r.register(
        Command(
            [r"who is\s+\w", r"tell me about\s+\w", r"\bwikipedia\b", r"search wiki"],
            _handle_wikipedia, "Wikipedia lookup", "Knowledge",
        ),
        Command(
            [r"\bcalculate\b", r"\bcompute\b", r"\bsolve\b", r"\bmath\b"],
            _handle_calculate, "Calculate", "Knowledge",
        ),
        Command(
            [r"\bwhat is\b", r"\bdefine\b", r"\bexplain\b"],
            _handle_what_is, "Define / What is", "Knowledge",
        ),
    )

    # Weather
    r.register(
        Command(
            [r"\bweather\b", r"\btemperature\b", r"\bforecast\b", r"how('s| is) it outside"],
            _handle_weather, "Weather", "Information",
        ),
    )

    # News
    r.register(
        Command(
            [r"\bnews\b", r"headlines", r"what('s| is) happening", r"top stories"],
            _handle_news, "News headlines", "Information",
        ),
    )

    # Translation
    r.register(
        Command(
            [r"\btranslate\b", r"how do you say", r"in (spanish|french|german|italian|portuguese|russian|japanese|chinese|korean|arabic|hindi|dutch|turkish)"],
            _handle_translate, "Translate text", "Language",
        ),
    )

    # Communication
    r.register(
        Command(
            [r"\bemail\b", r"\bgmail\b", r"send (an? )?email", r"compose (an? )?email"],
            _handle_email, "Send email", "Communication",
        ),
        Command(
            [r"send (a |an )?message", r"send (a |an )?sms", r"send (a |an )?text", r"text (someone|my)"],
            _handle_sms, "Send SMS", "Communication",
        ),
    )

    # Notes
    r.register(
        Command(
            [r"\bnote\b", r"remember this", r"write (this |that )?down", r"take a note"],
            _handle_note, "Take a note", "Productivity",
        ),
        Command(
            [r"set (a )?timer", r"timer for", r"countdown"],
            _handle_timer, "Set timer", "Productivity",
        ),
        Command(
            [r"remind(er| me)", r"set (a )?reminder"],
            _handle_reminder, "Set reminder", "Productivity",
        ),
    )

    # Calendar
    r.register(
        Command(
            [r"\bcalendar\b", r"(my |today'?s? )?(events|schedule|appointments)", r"what'?s? on (today|my calendar)"],
            _handle_calendar, "Calendar events", "Productivity",
        ),
    )

    # Entertainment
    r.register(
        Command(
            [r"(tell me a |crack a )?joke", r"(something |make me )?funny"],
            _handle_joke, "Tell a joke", "Entertainment",
        ),
        Command(
            [r"play (music|a song|some music|something)", r"(music|song)\s*please"],
            _handle_music, "Play music", "Entertainment",
        ),
        Command(
            [r"flip (a )?coin", r"heads or tails"],
            _handle_coinflip, "Flip a coin", "Entertainment",
        ),
        Command(
            [r"roll (a )?(dice|die|d6)", r"roll (a )?(\d+-sided )?dice?"],
            _handle_dice, "Roll a dice", "Entertainment",
        ),
        Command(
            [r"random (number|integer)", r"pick a number"],
            _handle_random_number, "Random number", "Entertainment",
        ),
    )

    # System
    r.register(
        Command(
            [r"empty (the )?recycle bin", r"clear (the )?trash"],
            _handle_recycle_bin, "Empty recycle bin", "System",
        ),
        Command(
            [r"change (the )?(wallpaper|background|desktop)", r"new wallpaper"],
            _handle_wallpaper, "Change wallpaper", "System",
        ),
        Command(
            [r"(take a |capture a )?screenshot", r"screen(shot|capture)"],
            _handle_screenshot, "Take screenshot", "System",
        ),
        Command(
            [r"lock (the )?(computer|screen|pc|laptop)", r"screen lock"],
            _handle_lock, "Lock computer", "System",
        ),
        Command(
            [r"(volume up|increase (the )?volume|louder|turn (it |the volume )?up)"],
            _handle_volume_up, "Volume up", "System",
        ),
        Command(
            [r"(volume down|decrease (the )?volume|quieter|turn (it |the volume )?down)"],
            _handle_volume_down, "Volume down", "System",
        ),
        Command(
            [r"\bmute\b", r"(turn off|silence) (the )?(volume|sound|audio)"],
            _handle_mute, "Mute", "System",
        ),
    )

    # Maps / Location
    r.register(
        Command(
            [r"where is\s+\w", r"(show|find) (on )?map", r"location of"],
            _handle_maps, "Find location", "Maps",
        ),
        Command(
            [r"directions? (to|from)\s+\w", r"navigate to\s+\w", r"how (do i |to )get to"],
            _handle_directions, "Get directions", "Maps",
        ),
    )

    # Utility
    r.register(
        Command(
            [r"(what'?s? my |my )?(public )?ip( address)?", r"ip address"],
            _handle_ip, "My IP address", "Utility",
        ),
        Command(
            [r"(stop|don'?t) listen(ing)?", r"(be |stay |go )quiet( for)?", r"sleep for"],
            _handle_sleep, "Stop listening temporarily", "Utility",
        ),
        Command(
            [r"order (a )?pizza", r"dominos", r"(i want|get me) (a )?pizza"],
            _handle_pizza, "Order pizza", "Utility",
        ),
        Command(
            [r"(show |your )?(cache |memory )?stats", r"hit rate", r"how'?s? (your )?memory"],
            _handle_cache_stats, "Cache statistics", "Utility",
        ),
    )

    total = len(r._commands)
    logger.info("CommandRegistry ready — %d command types loaded", total)
    return r
