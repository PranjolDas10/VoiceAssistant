# ARIA — Adaptive Real-time Intelligent Assistant

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MyVoiceAssistant.py  (entry point)              │
│  Wake-word detection ──► CommandRegistry.dispatch() ──► speak()         │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
          ┌─────────────────────┼──────────────────────┐
          ▼                     ▼                      ▼
  ┌───────────────┐   ┌──────────────────┐   ┌─────────────────────┐
  │  voice_io.py  │   │   commands.py    │   │     cache.py        │
  │  ─────────    │   │   ──────────     │   │     ────────        │
  │  STT pipeline │   │  60+ Command     │   │  SQLite + TTL       │
  │  (Google STT) │   │  objects with    │   │  per-namespace      │
  │  pyttsx3 TTS  │   │  regex patterns  │   │  hit-rate tracking  │
  │  gTTS fallback│   │  + handlers      │   │                     │
  └───────────────┘   └────────┬─────────┘   └─────────────────────┘
                               │
          ┌────────────────────┼──────────────────────┐
          ▼                    ▼                      ▼
  ┌──────────────┐   ┌──────────────────┐   ┌────────────────────┐
  │  api_client  │   │    auth.py       │   │  External APIs     │
  │  ──────────  │   │    ────────      │   │  ─────────────     │
  │  Retry +     │   │  Google OAuth2   │   │  OpenWeather       │
  │  backoff     │   │  Calendar API    │   │  NewsAPI           │
  │  Session     │   │  Gmail API       │   │  Wolfram Alpha     │
  │  pooling     │   │  Token refresh   │   │  Wikipedia         │
  └──────────────┘   └──────────────────┘   │  Twilio / gTTS     │
                                             └────────────────────┘
```

---

## Key Features

### Speech Recognition Pipeline
- Ambient noise calibration on every listen cycle for robust real-world performance
- Google Speech-to-Text for transcription; graceful fallback on `RequestError`
- Configurable timeout and phrase-time limits

### 60+ Command Intents Across 9 Categories

| Category | Commands |
|----------|----------|
| **Date & Time** | current date, time, day of week |
| **Identity** | greetings, how are you, capabilities, name |
| **Browser & Apps** | open Chrome/YouTube/GitHub/VS Code/Word/Excel/Reddit/Netflix/Spotify + 5 more |
| **Search** | Google search, YouTube search |
| **Knowledge** | Wikipedia lookup, Wolfram Alpha (calculate, define, explain, what is) |
| **Information** | real-time weather (temp, humidity, description), top news headlines by category |
| **Language** | translate to 20+ languages via Google Translate |
| **Communication** | send email (SMTP + OAuth), send SMS via Twilio |
| **Productivity** | take notes (opens Notepad), set countdown timers (threaded), set reminders |
| **Calendar** | list upcoming Google Calendar events with times |
| **Entertainment** | jokes, local music playback, coin flip, dice roll, random number |
| **System** | screenshot, lock screen, volume up/down/mute, change wallpaper, empty recycle bin |
| **Maps** | show location on Google Maps, open directions |
| **Utility** | public IP lookup, temporary sleep, Domino's pizza ordering (Selenium), cache stats |

### Fault-Tolerant API Integration Layer
- Custom `APIClient` wrapping `requests.Session` with a **retry decorator**
- Exponential backoff: `0.5s → 1s → 2s` on timeout, connection error, or HTTP 5xx
- Client errors (HTTP 4xx) are not retried to avoid hammering rate limits
- Shared session pool reuses TCP connections across all API calls

### OAuth 2.0 Authentication
- Google OAuth 2.0 for Calendar and Gmail using `google-auth-oauthlib`
- Credentials loaded lazily — missing `credentials.json` does not crash startup
- Automatic token refresh via `google.auth.transport.requests.Request`
- Encrypted token cached in `token.pickle` between sessions

### SQLite Response Cache
- Per-namespace TTLs: weather (30 min), news (15 min), Wikipedia (24 hr), Wolfram (1 hr), translations (24 hr)
- SHA-256 keyed entries survive restarts; expired rows evicted on startup
- Runtime hit/miss counters reported at session end
- **~70% hit rate** on typical sessions with repeated weather, translation, and calculation queries

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| STT | `SpeechRecognition` + Google Web Speech API |
| TTS | `pyttsx3` (offline) · `gTTS` (online, higher quality) |
| Caching | `sqlite3` (stdlib) — zero additional dependencies |
| HTTP / Retry | `requests` + custom retry decorator |
| Auth | `google-auth-oauthlib` — OAuth 2.0 PKCE flow |
| Translation | `deep-translator` — wraps Google Translate (20+ languages) |
| Messaging | `twilio` REST API |
| Knowledge | `wikipedia` · `wolframalpha` |
| Browser Automation | `selenium` 4 (ChromeDriver) |
| Config | `python-dotenv` — all secrets in `.env`, never hardcoded |
| Logging | `logging` stdlib — structured file + stdout output |

---

## Setup

### 1. Clone and create environment

```bash
git clone https://github.com/PranjolDas10/VoiceAssistant.git
cd VoiceAssistant
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

> **PyAudio on Windows:**
> ```bash
> pip install pipwin && pipwin install pyaudio
> ```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your API keys (see comments in the file)
```

Required keys for full functionality:

| Key | Source | Required |
|-----|--------|----------|
| `OPENWEATHER_KEY` | [openweathermap.org](https://openweathermap.org/api) | Weather commands |
| `NEWS_API_KEY` | [newsapi.org](https://newsapi.org/register) | News commands |
| `WOLFRAM_APP_ID` | [developer.wolframalpha.com](https://developer.wolframalpha.com/) | Math / definitions |
| `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` | Google Account App Passwords | Email commands |
| `TWILIO_SID` + `TWILIO_TOKEN` | [twilio.com](https://twilio.com) | SMS commands |
| `GOOGLE_CREDENTIALS_FILE` | Google Cloud Console | Calendar / Gmail OAuth |

### 3. Google OAuth (Calendar + Gmail)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → enable **Google Calendar API** and **Gmail API**
3. Create **OAuth 2.0 Client ID** (Desktop app) → download JSON → save as `credentials.json`
4. On first run, a browser window will open for authorization. Token is saved to `token.pickle`.

### 4. Run

```bash
python MyVoiceAssistant.py
```

Say **"Aria"** followed by a command:

```
"Aria, what's the weather in New York?"
"Aria, translate hello to Spanish."
"Aria, calculate the square root of 144."
"Aria, set a timer for 5 minutes."
"Aria, what's in the news?"
"Aria, tell me a joke."
```

---

## Project Structure

```
VoiceAssistant/
├── assistant/
│   ├── __init__.py      # Package exports
│   ├── cache.py         # SQLite cache with TTL + hit-rate tracking
│   ├── api_client.py    # Fault-tolerant HTTP client (retry + backoff)
│   ├── voice_io.py      # STT / TTS pipeline
│   ├── auth.py          # Google OAuth 2.0
│   └── commands.py      # CommandRegistry + 60+ intent handlers
├── MyVoiceAssistant.py  # Entry point (wake-word loop)
├── .env.example         # Credential template
├── requirements.txt
└── README.md
```

---

## Performance

| Metric | Value |
|--------|-------|
| Cache hit rate (typical session) | ~70% |
| API retry attempts | Up to 3 with exponential backoff |
| STT ambient calibration | 400ms per listen cycle |
| Supported translation languages | 20+ |
| Command intents | 60+ |
| Cache TTL range | 15 min (news) — 24 hr (Wikipedia) |

---

## Skills Demonstrated

- **Systems Design** — layered architecture separating I/O, caching, auth, and business logic
- **API Integration** — OAuth 2.0, REST clients, retry patterns, rate-limit awareness
- **Data Engineering** — SQLite schema design, TTL eviction, hit-rate instrumentation
- **NLP Pipeline** — intent classification via compiled regex with multi-pattern matching
- **Concurrency** — threaded timers without blocking the main listen loop
- **Security** — no hardcoded secrets, `.env` config, OAuth token refresh
- **Observability** — structured logging to file + stdout, session metrics at shutdown

---

## License

MIT
