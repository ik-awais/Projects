# 🌙 Solace — Emotionally Intelligent AI Companion

> *A full-stack emotionally intelligent assistant with 3D UI, persistent memory, cultural awareness, and multi-provider AI support.*

---

## ✨ Features

| Feature | Details |
|---|---|
| **3D Visual Environment** | Three.js particle field + morphing orb that reacts to your emotions |
| **Emotional Intelligence** | Real-time emotion detection (VADER NLP + keyword analysis) |
| **Cultural Context** | Region-aware empathy for PK, IN, AE, US, GB and more |
| **Persistent Memory** | SQLite database stores your full chat history and extracted facts |
| **Multi-Provider AI** | Gemini 1.5 Pro (primary) + NVIDIA NIM API (backup) |
| **Language Detection** | Auto-detects Urdu, Hindi, Arabic, English, etc. |
| **Emotional Analytics** | Live mood meter + emotion pattern chart in sidebar |
| **Large Text Support** | Sends full conversation context (up to 30 turns) to AI |

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. NLTK data (first time only)
```python
python3 -c "import nltk; nltk.download('vader_lexicon')"
```

### 3. Start the server
```bash
python3 run.py
```

### 4. Open in browser
```
http://localhost:5000
```

---

## 🔑 API Keys

### Gemini (Recommended)
- Go to https://aistudio.google.com/app/apikey
- Create a free API key
- Enter it in the onboarding screen or Settings

### NVIDIA NIM (Backup)
- Go to https://build.nvidia.com
- Create an account and get your API key
- Supports LLaMA-3.1-405B and many other models

---

## 🏗 Architecture

```
solace/
├── app.py              ← Flask backend (Python)
│   ├── SQLAlchemy models (User, Message, Memory)
│   ├── Emotion analysis (VADER + keyword)
│   ├── Language detection (langdetect)
│   ├── Memory extraction (regex NLP)
│   ├── Gemini 1.5 Pro integration
│   ├── NVIDIA NIM integration
│   └── REST API endpoints
├── static/
│   └── index.html      ← Full frontend (HTML/CSS/JS + Three.js)
│       ├── 3D particle field background
│       ├── Animated 3D orb (emotion-reactive)
│       ├── Chat interface with markdown support
│       ├── Emotion bar charts
│       ├── Memory panel
│       ├── Mood meter
│       └── Settings panel
├── requirements.txt
└── run.py
```

---

## 🌍 Regional Emotional Intelligence

Solace adapts its emotional style based on your region:

| Region | Approach |
|---|---|
| 🇵🇰 Pakistan | Family bonds, societal pressure, faith, honour-aware |
| 🇮🇳 India | Parental expectations, dharma, diverse cultural practices |
| 🇦🇪 Gulf | Islamic values, hospitality, family hierarchy |
| 🇺🇸 USA | Individualism, personal agency, therapy-positive |
| 🇬🇧 UK | Understated warmth, stoicism, gentle validation |

---

## 📡 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/session` | POST | Create or resume a user session |
| `/api/chat` | POST | Send message, get AI reply |
| `/api/history` | GET | Fetch full conversation history |
| `/api/memories` | GET | Get extracted user memories |
| `/api/emotion_stats` | GET | Emotion distribution + avg sentiment |
| `/api/profile` | PATCH | Update name/region |
| `/api/clear_history` | DELETE | Delete all messages |

---

## 🧠 Memory System

Solace automatically extracts and stores:
- **Personal**: name, age, location, work, education
- **Emotional**: recurring feelings, challenges, losses
- **Preferences**: likes, dislikes
- **Events**: significant mentions

These memories are injected into every system prompt so Solace always knows your context.

---

## 🎨 Design System

- **Background**: Deep space `#0a0b14`
- **Accent**: Violet `#826eff` + Purple `#c084fc`
- **Typography**: DM Serif Display (headings) + Inter (body)
- **3D**: Three.js WebGL renderer
- **Animation**: CSS keyframes + Three.js RAF loop
