"""
SOLACE — Emotionally Intelligent AI Companion
Backend: Flask + SQLAlchemy + Gemini / NVIDIA NIM
Fixed for: google-genai SDK compatibility, unified models, and fallback chains
"""

import os, re, hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from langdetect import detect, DetectorFactory
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk

DetectorFactory.seed = 42

# ── App Initialization ────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///solace.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

try:
    sia = SentimentIntensityAnalyzer()
except LookupError:
    nltk.download("vader_lexicon", quiet=True)
    sia = SentimentIntensityAnalyzer()

# ── Database Models ──────────────────────────────────────────────────────────
class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False)
    name       = db.Column(db.String(128))
    region     = db.Column(db.String(64))
    language   = db.Column(db.String(16), default="en")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages   = db.relationship("Message", backref="user", lazy=True, cascade="all,delete")
    memories   = db.relationship("Memory",  backref="user", lazy=True, cascade="all,delete")

class Message(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role      = db.Column(db.String(16), nullable=False)
    content   = db.Column(db.Text, nullable=False)
    emotion   = db.Column(db.String(32))
    sentiment = db.Column(db.Float)
    language  = db.Column(db.String(16))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Memory(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    key        = db.Column(db.String(128), nullable=False)
    value      = db.Column(db.Text, nullable=False)
    category   = db.Column(db.String(64))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ── Regional EQ Context ────────────────────────────────────────────────────────
REGIONAL_CTX = {
    "pk": {
        "culture": "South Asian / Pakistani",
        "values": "family, honour, community, resilience, faith",
        "norms": "respect for elders, collectivist society, strong family bonds",
        "taboos": "sensitive to family shame, societal pressure, and honour",
        "emotions_style": "acknowledge family pressure and societal expectations explicitly; use Urdu/Roman-Urdu warmth when the user writes in it",
    },
    "in": {
        "culture": "South Asian / Indian",
        "values": "family, dharma, community, ambition, tradition",
        "norms": "respect for elders, diverse cultural practices, strong aspirations",
        "taboos": "sensitive to parental expectations and social comparisons",
        "emotions_style": "acknowledge parental expectations and career pressure; be inclusive of diverse Indian cultural backgrounds",
    },
    "ae": {
        "culture": "Gulf Arab / Emirati",
        "values": "hospitality, honour, family, faith, progress",
        "norms": "respect for hierarchy and elders, strong Islamic values",
        "taboos": "sensitive to family honour and public/private duality",
        "emotions_style": "acknowledge divine will, family honour, and social duty sensitively",
    },
    "us": {
        "culture": "North American / Western",
        "values": "individualism, self-reliance, achievement, personal freedom",
        "norms": "direct communication, therapy-positive, rights-focused",
        "taboos": "",
        "emotions_style": "encourage personal agency, boundary-setting, and self-advocacy",
    },
    "gb": {
        "culture": "British",
        "values": "stoicism, politeness, dry humour, privacy, fairness",
        "norms": "understated emotion, value of decorum",
        "taboos": "",
        "emotions_style": "gentle and understated validation with quiet warmth",
    },
    "default": {
        "culture": "Global",
        "values": "respect, empathy, growth, connection",
        "norms": "universal human dignity",
        "taboos": "",
        "emotions_style": "empathetic, non-judgmental, and universally warm",
    },
}

def get_regional_ctx(region):
    return REGIONAL_CTX.get((region or "").lower().strip(), REGIONAL_CTX["default"])

# ── Emotion Analysis ───────────────────────────────────────────────────────────
EMOTION_KEYWORDS = {
    "sadness":    ["sad","cry","tears","upset","grief","loss","depressed","hopeless","heartbreak","mourn","devastated"],
    "anxiety":    ["anxious","worried","stress","scared","fear","panic","nervous","overwhelmed","dread","apprehensive"],
    "anger":      ["angry","furious","rage","hate","frustrated","irritat","mad","resent","bitter","outrage"],
    "joy":        ["happy","joy","excited","grateful","love","wonderful","blessed","thrilled","delighted","elated"],
    "loneliness": ["lonely","alone","isolated","miss","empty","no one","abandoned","left out","invisible"],
    "confusion":  ["confused","lost","unsure","don't know","helpless","directionless","uncertain","stuck"],
    "guilt":      ["guilty","ashamed","embarrassed","regret","blame myself","my fault","sorry"],
}

def analyse_emotion(text):
    scores   = sia.polarity_scores(text)
    compound = scores["compound"]
    lower    = text.lower()
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if any(w in lower for w in keywords):
            return {"emotion": emotion, "sentiment": round(compound, 4)}
    if compound >= 0.05:
        return {"emotion": "positive", "sentiment": round(compound, 4)}
    elif compound <= -0.05:
        return {"emotion": "negative", "sentiment": round(compound, 4)}
    return {"emotion": "neutral", "sentiment": round(compound, 4)}

def detect_language(text):
    try:
        return detect(text)
    except Exception:
        return "en"

# ── Memory Extraction ──────────────────────────────────────────────────────────
MEMORY_PATTERNS = [
    (r"my name is ([A-Za-z\s]+)",                                      "name",             "personal"),
    (r"i(?:'m| am) (\d+) years? old",                                  "age",              "personal"),
    (r"i live in ([A-Za-z\s]+)",                                        "location",         "personal"),
    (r"i work (?:as |at |in )?([A-Za-z]+Stack|(?:\s[A-Za-z]+)?)",       "work",             "personal"),
    (r"i(?:'m| am) (?:a |an )?([A-Za-z ]+?student)",                  "education_status", "personal"),
    (r"i study(?:ing)? ([A-Za-z ]+?)(?:\.|,|\sand|\Z)",               "field_of_study",   "personal"),
    (r"i have (?:a )?([A-Za-z ]+?) (?:problem|issue|struggle|challenge)", "challenge",    "emotional"),
    (r"i feel (?:very |really |so )?([A-Za-z]+)",                      "recurring_feeling","emotional"),
    (r"i love ([A-Za-z]+(?:\s[A-Za-z]+)?)",                           "loves",            "preference"),
    (r"i hate ([A-Za-z]+(?:\s[A-Za-z]+)?)",                           "dislikes",         "preference"),
    (r"i (?:lost|miss) (?:my )?([A-Za-z]+(?:\s[A-Za-z]+)?)",         "loss",             "emotional"),
]

def extract_memories(text, existing_keys):
    new   = []
    lower = text.lower()
    for pattern, key, cat in MEMORY_PATTERNS:
        if key in existing_keys:
            continue
        m = re.search(pattern, lower)
        if m:
            val = m.group(1).strip().title()
            if len(val) > 1:
                new.append({"key": key, "value": val, "category": cat})
                existing_keys.add(key)
    return new

# ── System Prompt Builder ──────────────────────────────────────────────────────
def build_system_prompt(user, memories, region_ctx):
    mem_text = ""
    if memories:
        mem_text = "\n\nKnown facts about this user:\n"
        for m in memories:
            mem_text += f"  • [{m.category}] {m.key}: {m.value}\n"

    return f"""You are Solace — a deeply empathetic, emotionally intelligent AI companion.
Your primary role is genuine emotional support, active listening, and culturally-aware guidance.
You are NOT a therapist, but you are a compassionate, insightful friend who truly cares.

════════════════════════════════
CULTURAL & REGIONAL CONTEXT
════════════════════════════════
Culture       : {region_ctx['culture']}
Core values   : {region_ctx['values']}
Social norms  : {region_ctx.get('norms', 'N/A')}
Emotional tone: {region_ctx['emotions_style']}
{f"Sensitive areas: {region_ctx['taboos']}" if region_ctx.get('taboos') else ''}

════════════════════════════════
USER PROFILE
════════════════════════════════
Name    : {user.name or 'Not shared yet'}
Region  : {user.region or 'Unknown'}
Language: {user.language or 'en'}
{mem_text}

════════════════════════════════
EMOTIONAL INTELLIGENCE FRAMEWORK
════════════════════════════════
1. LISTEN FIRST — always reflect back what you heard before offering perspective.
2. VALIDATE — never dismiss, minimise, or rush past feelings.
3. CULTURAL LENS — honour the user's cultural framework. A Pakistani student saying "my parents are pressuring me" carries different weight than the same words from a Western user — account for that.
4. CONTEXTUAL MEMORY — reference what the user has shared before, naturally and warmly.
5. GENTLE CURIOSITY — ask ONE thoughtful follow-up question when appropriate; never interrogate.
6. LANGUAGE MIRROR — respond in the same language the user writes in (English, Urdu, Roman Urdu, Arabic, Hindi etc.).
7. LARGE TEXT — if the user shares a long message, summarise the key emotional themes you heard before responding.
8. SAFETY — if you detect signs of self-harm or crisis: acknowledge with warmth, do NOT panic, and gently encourage professional support.
9. ARC TRACKING — track emotional trajectory across the conversation. If mood lifts, celebrate it. If worsening, become more attentive.

════════════════════════════════
RESPONSE STYLE
════════════════════════════════
• Warm, grounded, and never clinical.
• Use culturally appropriate metaphors (chai, family, faith for South Asian users).
• Distinguish venting (needs listening) from problem-solving (needs guidance).
• Format: flowing prose, new paragraph per emotional beat. No bullet lists in empathetic responses.
• Length: match the user's energy. Short message → concise reply. Long emotional message → thorough response.
• Never judge. Never lecture. Never compare the user's pain to others'.
• End every response with a gentle open question OR a simple expression of presence ("I'm here with you.")."""

# ── AI API Engine Integration ──────────────────────────────────────────────────

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

def call_gemini(system_prompt, history, user_message, api_key):
    """
    Interacts cleanly with the newer google-genai 2.8.0 SDK.
    Uses Client configuration safely with a structured content fallback pipeline.
    """
    from google import genai as gai
    from google.genai import types as gtypes

    client = gai.Client(api_key=api_key)
    
    # Process history strictly into structural Content objects expected by genai SDK
    contents = []
    for msg in history[-24:]:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            gtypes.Content(
                role=role,
                parts=[gtypes.Part.from_text(text=msg["content"])]
            )
        )
    # Append current input turn
    contents.append(
        gtypes.Content(
            role="user",
            parts=[gtypes.Part.from_text(text=user_message)]
        )
    )

    last_error = None
    for model_name in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=gtypes.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.88,
                    top_p=0.95,
                    max_output_tokens=1800,
                )
            )
            if response.text:
                return response.text
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "404" in err_str or "not found" in err_str or "method" in err_str:
                continue
            raise

    raise last_error

NVIDIA_MODELS = [
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
]

def call_nvidia(system_prompt, history, user_message, api_key):
    """
    Sends explicit chat completions to the standard, up-to-date NVIDIA NIM API gateway.
    """
    from openai import OpenAI

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-24:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    last_error = None
    for model_name in NVIDIA_MODELS:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.88,
                max_tokens=1800,
            )
            return completion.choices[0].message.content
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "404" in err_str or "not found" in err_str or "model" in err_str:
                continue
            raise

    raise last_error

# ── API Endpoint Routing ───────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/session", methods=["POST"])
def create_session():
    data = request.json or {}
    sid  = data.get("session_id") or hashlib.sha256(os.urandom(32)).hexdigest()[:32]
    user = User.query.filter_by(session_id=sid).first()
    if not user:
        user = User(
            session_id=sid,
            name=data.get("name"),
            region=data.get("region", "pk").lower(),
            language=data.get("language", "en"),
        )
        db.session.add(user)
        db.session.commit()
    return jsonify({
        "session_id": sid, "user_id": user.id,
        "name": user.name, "region": user.region,
        "language": user.language,
        "created_at": user.created_at.isoformat(),
    })

@app.route("/api/chat", methods=["POST"])
def chat():
    data       = request.json or {}
    sid        = data.get("session_id")
    user_text  = (data.get("message") or "").strip()
    gemini_key = data.get("gemini_key", "")
    nvidia_key = data.get("nvidia_key", "")
    provider   = data.get("provider", "gemini")

    if not sid or not user_text:
        return jsonify({"error": "session_id and message are required"}), 400

    user = User.query.filter_by(session_id=sid).first()
    if not user:
        return jsonify({"error": "Session not found. Please refresh and try again."}), 404

    lang = detect_language(user_text)
    if lang != user.language:
        user.language = lang

    ea = analyse_emotion(user_text)
    user_msg = Message(
        user_id=user.id, role="user", content=user_text,
        emotion=ea["emotion"], sentiment=ea["sentiment"], language=lang,
    )
    db.session.add(user_msg)
    db.session.flush()
    existing_keys = {m.key for m in Memory.query.filter_by(user_id=user.id).all()}
    new_mems = extract_memories(user_text, existing_keys)
    for nm in new_mems:
        db.session.add(Memory(user_id=user.id, **nm))
    db.session.flush()
    history_rows = (
        Message.query.filter_by(user_id=user.id)
        .order_by(Message.timestamp.desc())
        .limit(30).all()
    )
    history = [{"role": r.role, "content": r.content} for r in reversed(history_rows)]
    memories   = Memory.query.filter_by(user_id=user.id).all()
    region_ctx = get_regional_ctx(user.region)
    sys_prompt = build_system_prompt(user, memories, region_ctx)
    reply = ""
    try:
        if provider == "nvidia" and nvidia_key:
            reply = call_nvidia(sys_prompt, history[:-1], user_text, nvidia_key)
        elif provider == "gemini" and gemini_key:
            reply = call_gemini(sys_prompt, history[:-1], user_text, gemini_key)
        # Fallback cascade logic
        elif gemini_key:
            reply = call_gemini(sys_prompt, history[:-1], user_text, gemini_key)
        elif nvidia_key:
            reply = call_nvidia(sys_prompt, history[:-1], user_text, nvidia_key)
        else:
            reply = "⚠️ No active key configured. Check your credentials inside ⚙️ Settings."
    except Exception as e:
        err = str(e)
        if any(x in err.lower() for x in ["api_key", "api key", "unauthorized", "invalid key"]):
            reply = "⚠️ Invalid API key found. Please re-verify setup under ⚙️ Settings."
        elif "quota" in err.lower() or "429" in err:
            reply = "⚠️ API resource limit hit. Give it a brief pause before trying again."
        else:
            reply = f"⚠️ AI processing failure: {err[:200]}"
    db.session.add(Message(
        user_id=user.id, role="assistant",
        content=reply, language=lang,
    ))
    db.session.commit()
    return jsonify({
        "reply": reply,
        "emotion": ea["emotion"],
        "sentiment": ea["sentiment"],
        "language": lang,
        "memories_extracted": len(new_mems),
    })
@app.route("/api/history", methods=["GET"])
def get_history():
    sid  = request.args.get("session_id")
    user = User.query.filter_by(session_id=sid).first()
    if not user:
        return jsonify({"messages": []})
    msgs = Message.query.filter_by(user_id=user.id).order_by(Message.timestamp).all()
    return jsonify({"messages": [
        {"role": m.role, "content": m.content, "emotion": m.emotion,
         "sentiment": m.sentiment, "timestamp": m.timestamp.isoformat()}
        for m in msgs
    ]})
@app.route("/api/memories", methods=["GET"])
def get_memories():
    sid  = request.args.get("session_id")
    user = User.query.filter_by(session_id=sid).first()
    if not user:
        return jsonify({"memories": []})
    mems = Memory.query.filter_by(user_id=user.id).all()
    return jsonify({"memories": [
        {"key": m.key, "value": m.value, "category": m.category,
         "updated_at": m.updated_at.isoformat()}
        for m in mems
    ]})
@app.route("/api/emotion_stats", methods=["GET"])
def emotion_stats():
    sid  = request.args.get("session_id")
    user = User.query.filter_by(session_id=sid).first()
    if not user:
        return jsonify({})
    msgs   = Message.query.filter_by(user_id=user.id, role="user").all()
    counts = {}
    for m in msgs:
        if m.emotion:
            counts[m.emotion] = counts.get(m.emotion, 0) + 1
    sents = [m.sentiment for m in msgs if m.sentiment is not None]
    avg_s = round(sum(sents) / len(sents), 4) if sents else 0
    return jsonify({"emotion_counts": counts, "average_sentiment": avg_s,
                    "total_messages": len(msgs)})
@app.route("/api/profile", methods=["PATCH"])
def update_profile():
    data = request.json or {}
    user = User.query.filter_by(session_id=data.get("session_id")).first()
    if not user:
        return jsonify({"error": "not found"}), 404
    if "name"   in data: user.name   = data["name"]
    if "region" in data: user.region = data["region"].lower()
    db.session.commit()
    return jsonify({"ok": True})
@app.route("/api/clear_history", methods=["DELETE"])
def clear_history():
    sid  = request.args.get("session_id")
    user = User.query.filter_by(session_id=sid).first()
    if user:
        Message.query.filter_by(user_id=user.id).delete()
        db.session.commit()
    return jsonify({"ok": True})
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "1.1.0", "name": "Solace"})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    print("\n🌙 Solace backend starting on http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)