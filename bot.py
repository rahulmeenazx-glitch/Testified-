"""
✦ TESTIFY BY AARAV — Premium Test Builder Bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Telegram bot for creating premium CBT-style HTML tests
Features: Question parsing, AI prompt studio, test configuration, lifelines, HTML export
"""

import os
import re
import json
import random
from datetime import datetime
from typing import Dict, List, Optional, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL = "@sjvbots"

DEFAULT_SETTINGS = {
    "test_name": "My Test",
    "instructions": "",
    "question_limit": 0,  # 0 = all questions
    "duration": 20,
    "marks_per_question": 4,
    "negative_marking": 0,
    "shuffle_questions": False,
    "shuffle_options": False,
    "resume_enabled": False,
    "language_mode": "auto",  # auto, hindi, english, bilingual
    "lifelines": {
        "fifty_fifty": 1,
        "smart_hint": 1,
        "skip_question": 3,
        "extra_time": 1
    }
}


# ═══════════════════════════════════════════════════════════════
# USER STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

user_data: Dict[int, Dict] = {}


def get_user(uid: int) -> Dict:
    """User data get karta hai, agar nahi hai toh create karta hai."""
    if uid not in user_data:
        user_data[uid] = {
            "step": "menu",
            "questions": [],
            "settings": DEFAULT_SETTINGS.copy(),
            "ai_config": {},
            "draft": ""
        }
    return user_data[uid]


def reset_user(uid: int):
    """User data reset karta hai."""
    if uid in user_data:
        del user_data[uid]


# ═══════════════════════════════════════════════════════════════
# QUESTION PARSER
# ═══════════════════════════════════════════════════════════════

def parse_questions(text: str) -> List[Dict]:
    """
    Raw text se questions parse karta hai.
    Format support:
    Q1. Question?
    A) Option 1
    B) Option 2
    C) Option 3
    D) Option 4
    Ans: B
    Explanation: ...
    """
    questions = []
    
    # Split by question markers
    pattern = r'(?:^|\n)\s*(?:Q?\s*\d+[\.\)\:]|[\d]+[\.\)])\s*'
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    
    for part in parts:
        q = parse_single_question(part)
        if q:
            questions.append(q)
    
    return questions


def parse_single_question(text: str) -> Optional[Dict]:
    """Ek single question block parse karta hai."""
    lines = text.strip().split('\n')
    if not lines:
        return None
    
    question_lines = []
    options = {}
    answer = None
    explanation = None
    
    i = 0
    
    # Extract question text
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^[A-E][\.\)\:]', line, re.IGNORECASE):
            break
        question_lines.append(line)
        i += 1
    
    question_text = ' '.join(question_lines).strip()
    if not question_text:
        return None
    
    # Extract options, answer, explanation
    while i < len(lines):
        line = lines[i].strip()
        
        # Option
        match = re.match(r'^([A-E])[\.\)\:]\s*(.+)', line, re.IGNORECASE)
        if match:
            key = match.group(1).upper()
            options[key] = match.group(2).strip()
            i += 1
            continue
        
        # Answer
        if line.lower().startswith(('ans:', 'answer:', 'correct:', 'uttar:')):
            ans_match = re.search(r'([A-E])', line, re.IGNORECASE)
            if ans_match:
                answer = ans_match.group(1).upper()
            i += 1
            continue
        
        # Explanation
        if line.lower().startswith(('explanation:', 'sol:', 'solution:', 'vyakhya:')):
            explanation = line.split(':', 1)[1].strip() if ':' in line else ""
            i += 1
            # Multi-line explanation
            while i < len(lines) and lines[i].strip() and not re.match(r'^[A-E][\.\)\:]', lines[i], re.IGNORECASE):
                explanation += ' ' + lines[i].strip()
                i += 1
            break
        
        i += 1
    
    if not options:
        return None
    
    return {
        "question": question_text,
        "options": options,
        "answer": answer,
        "explanation": explanation or ""
    }


# ═══════════════════════════════════════════════════════════════
# AI PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════

def build_ai_prompt(config: Dict) -> str:
    """AI prompt generate karta hai based on user config."""
    
    language_map = {
        "hindi": "Hindi",
        "english": "English",
        "bilingual": "Hindi + English (Bilingual)",
        "rajasthani": "Rajasthani"
    }
    
    level_map = {
        "easy": "Easy",
        "moderate": "Moderate",
        "hard": "Hard",
        "very_hard": "Very Hard",
        "extreme": "Extreme",
        "ultra": "Ultra Extreme / Expert",
        "mixed": "Mixed Difficulty"
    }
    
    lang = language_map.get(config.get("language", "hindi"), "Hindi")
    lvl = level_map.get(config.get("level", "moderate"), "Moderate")
    num = config.get("num", 10)
    subject = config.get("subject", "General Knowledge")
    topic = config.get("topic", "General")
    extra = config.get("extra", "")
    
    prompt = f"""Generate {num} high-quality MCQ questions on the following topic.

📚 SUBJECT: {subject}
🎯 TOPIC: {topic}
🌐 LANGUAGE: {lang}
📊 DIFFICULTY LEVEL: {lvl}

FORMAT (strictly follow):
Q1. [Question text]
A) [Option 1]
B) [Option 2]
C) [Option 3]
D) [Option 4]
Ans: [Correct option letter]
Explanation: [Brief explanation in same language]

REQUIREMENTS:
- Each question must have exactly 4 options
- Only ONE correct answer
- Include clear explanation for every question
- Questions should be unique and non-repetitive
{f'- Additional: {extra}' if extra else ''}

Please generate all {num} questions now."""
    
    return prompt


# ═══════════════════════════════════════════════════════════════
# HTML TEST GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_html_test(test_name: str, questions: List[Dict], settings: Dict, instructions: str = "") -> str:
    """Complete HTML test file generate karta hai."""
    
    # Apply shuffle if enabled
    if settings.get("shuffle_questions"):
        random.shuffle(questions)
    if settings.get("shuffle_options"):
        for q in questions:
            opts = list(q["options"].items())
            random.shuffle(opts)
            q["options"] = dict(opts)
    
    # Apply question limit
    limit = settings.get("question_limit", 0)
    if limit > 0:
        questions = questions[:limit]
    
    questions_json = json.dumps(questions, ensure_ascii=False, indent=2)
    settings_json = json.dumps(settings, ensure_ascii=False)
    
    html = f"""<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{test_name} — Testify By Aarav</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',system-ui,sans-serif}}
body{{background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);min-height:100vh;color:#fff;padding:10px}}
.container{{max-width:900px;margin:0 auto}}
.header{{background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:20px;margin-bottom:15px}}
.brand{{color:#ffd700;font-weight:700;font-size:18px}}
.timer{{background:#ff4757;padding:8px 16px;border-radius:8px;display:inline-block;font-weight:600;margin-top:8px}}
.question-box{{background:rgba(255,255,255,0.08);border-radius:16px;padding:20px;margin-bottom:15px}}
.q-text{{font-size:17px;margin-bottom:15px;line-height:1.5}}
.option{{background:rgba(255,255,255,0.05);border:2px solid rgba(255,255,255,0.1);border-radius:10px;padding:12px 15px;margin:8px 0;cursor:pointer;transition:all 0.2s}}
.option:hover{{background:rgba(255,215,0,0.1);border-color:#ffd700}}
.option.selected{{background:rgba(255,215,0,0.2);border-color:#ffd700}}
.option.correct{{background:rgba(46,213,115,0.2);border-color:#2ed573}}
.option.wrong{{background:rgba(255,71,87,0.2);border-color:#ff4757}}
.palette{{display:grid;grid-template-columns:repeat(auto-fill,minmax(40px,1fr));gap:6px;margin:15px 0}}
.pal-btn{{background:rgba(255,255,255,0.1);border:none;color:#fff;padding:10px;border-radius:8px;cursor:pointer;font-weight:600}}
.pal-btn.answered{{background:#2ed573}}
.pal-btn.current{{background:#ffd700;color:#000}}
.pal-btn.bookmarked{{outline:2px solid #ff4757}}
.btn{{background:linear-gradient(135deg,#ffd700,#ff9500);color:#000;border:none;padding:12px 24px;border-radius:10px;font-weight:700;cursor:pointer;margin:5px}}
.btn.secondary{{background:rgba(255,255,255,0.1);color:#fff}}
.lifeline{{background:rgba(255,255,255,0.08);border-radius:10px;padding:10px;margin:5px;display:inline-block;cursor:pointer}}
.result-box{{background:rgba(255,255,255,0.08);border-radius:16px;padding:25px;text-align:center}}
.score{{font-size:48px;color:#ffd700;font-weight:700}}
.explanation{{background:rgba(46,213,115,0.1);border-left:3px solid #2ed573;padding:12px;margin-top:10px;border-radius:6px;font-size:14px}}
@media(max-width:600px){{.q-text{{font-size:15px}}.option{{padding:10px}}}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<div class="brand">✦ TESTIFY BY AARAV</div>
<h2 id="testTitle">{test_name}</h2>
<div class="timer" id="timer">⏱ 00:00</div>
<div style="margin-top:8px;font-size:13px;opacity:0.8">
🎯 {settings.get('marks_per_question',4)} marks/Q | ⏱ {settings.get('duration',20)} min | 📋 <span id="qCount">0</span> Questions
</div>
</div>

<div id="testArea">
<div class="question-box">
<div class="q-text" id="qText"></div>
<div id="optionsArea"></div>
<div id="explanationArea"></div>
</div>

<div style="margin:15px 0">
<strong>📋 Question Palette</strong>
<div class="palette" id="palette"></div>
</div>

<div style="margin:10px 0">
<strong>🛟 Lifelines</strong>
<div id="lifelines"></div>
</div>

<div style="text-align:center;margin:20px 0">
<button class="btn" onclick="prevQ()">← Previous</button>
<button class="btn" onclick="nextQ()">Next →</button>
<button class="btn secondary" onclick="bookmark()">🔖 Bookmark</button>
<button class="btn" onclick="submitTest()" style="background:linear-gradient(135deg,#2ed573,#1e90ff)">✓ Submit Test</button>
</div>
</div>

<div id="resultArea" style="display:none"></div>

<div style="text-align:center;padding:20px;opacity:0.6;font-size:12px">
TESTIFY BY AARAV · EXAM STUDIO<br>
Designed for learners, built for practice.
</div>
</div>

<script>
const questions = {questions_json};
const settings = {settings_json};
let currentQ = 0;
let answers = {{}};
let bookmarks = new Set();
let lifelines = JSON.parse(JSON.stringify(settings.lifelines || {{}}));
let timeLeft = (settings.duration || 20) * 60;
let timerInterval;

document.getElementById('qCount').textContent = questions.length;

function renderQuestion() {{
    const q = questions[currentQ];
    document.getElementById('qText').innerHTML = `<strong>Q${{currentQ+1}}.</strong> ${{q.question}}`;
    const optArea = document.getElementById('optionsArea');
    optArea.innerHTML = '';
    Object.entries(q.options).forEach(([key, val]) => {{
        const div = document.createElement('div');
        div.className = 'option' + (answers[currentQ] === key ? ' selected' : '');
        div.innerHTML = `<strong>${{key}})</strong> ${{val}}`;
        div.onclick = () => selectOption(key);
        optArea.appendChild(div);
    }});
    document.getElementById('explanationArea').innerHTML = '';
    renderPalette();
    renderLifelines();
}}

function selectOption(key) {{
    answers[currentQ] = key;
    renderQuestion();
}}

function renderPalette() {{
    const pal = document.getElementById('palette');
    pal.innerHTML = '';
    questions.forEach((_, i) => {{
        const btn = document.createElement('button');
        btn.className = 'pal-btn';
        if (answers[i] !== undefined) btn.classList.add('answered');
        if (i === currentQ) btn.classList.add('current');
        if (bookmarks.has(i)) btn.classList.add('bookmarked');
        btn.textContent = i + 1;
        btn.onclick = () => {{ currentQ = i; renderQuestion(); }};
        pal.appendChild(btn);
    }});
}}

function renderLifelines() {{
    const area = document.getElementById('lifelines');
    area.innerHTML = '';
    const ll = [
        ['fifty_fifty', '50:50'],
        ['smart_hint', '💡 Hint'],
        ['skip_question', '⏭ Skip'],
        ['extra_time', '+30s']
    ];
    ll.forEach(([key, label]) => {{
        if (lifelines[key] > 0) {{
            const div = document.createElement('div');
            div.className = 'lifeline';
            div.innerHTML = `${{label}} <small>(${{lifelines[key]}})</small>`;
            div.onclick = () => useLifeline(key);
            area.appendChild(div);
        }}
    }});
}}

function useLifeline(key) {{
    if (lifelines[key] <= 0) return;
    lifelines[key]--;
    if (key === 'fifty_fifty') {{
        const correct = questions[currentQ].answer;
        const wrong = Object.keys(questions[currentQ].options).filter(k => k !== correct);
        const toHide = wrong.sort(() => Math.random() - 0.5).slice(0, 2);
        document.querySelectorAll('.option').forEach((el, i) => {{
            const optKey = Object.keys(questions[currentQ].options)[i];
            if (toHide.includes(optKey)) el.style.opacity = '0.3';
        }});
    }} else if (key === 'smart_hint') {{
        alert('💡 Hint: Soch samajh ke answer karein!');
    }} else if (key === 'skip_question') {{
        delete answers[currentQ];
        nextQ();
    }} else if (key === 'extra_time') {{
        timeLeft += 30;
    }}
    renderLifelines();
}}

function bookmark() {{
    if (bookmarks.has(currentQ)) bookmarks.delete(currentQ);
    else bookmarks.add(currentQ);
    renderPalette();
}}

function nextQ() {{ if (currentQ < questions.length - 1) {{ currentQ++; renderQuestion(); }} }}
function prevQ() {{ if (currentQ > 0) {{ currentQ--; renderQuestion(); }} }}

function startTimer() {{
    timerInterval = setInterval(() => {{
        timeLeft--;
        if (timeLeft <= 0) {{ clearInterval(timerInterval); submitTest(); return; }}
        const m = Math.floor(timeLeft / 60);
        const s = timeLeft % 60;
        document.getElementById('timer').textContent = `⏱ ${{String(m).padStart(2,'0')}}:${{String(s).padStart(2,'0')}}`;
    }}, 1000);
}}

function submitTest() {{
    clearInterval(timerInterval);
    let correct = 0, wrong = 0, unattempted = 0;
    questions.forEach((q, i) => {{
        if (answers[i] === undefined) unattempted++;
        else if (answers[i] === q.answer) correct++;
        else wrong++;
    }});
    const marks = settings.marks_per_question || 4;
    const neg = settings.negative_marking || 0;
    const score = (correct * marks) - (wrong * neg);

    let html = `<div class="result-box">
        <h2>📊 Test Result</h2>
        <div class="score">${{score}} / ${{questions.length * marks}}</div>
        <p style="margin:15px 0">✅ Correct: ${{correct}} | ❌ Wrong: ${{wrong}} | ⚪ Unattempted: ${{unattempted}}</p>
        <button class="btn" onclick="showReview()">📖 Review Answers</button>
        <button class="btn secondary" onclick="location.reload()">🔄 Retake</button>
    </div><div id="reviewArea" style="margin-top:20px"></div>`;
    document.getElementById('testArea').style.display = 'none';
    document.getElementById('resultArea').innerHTML = html;
    document.getElementById('resultArea').style.display = 'block';
    window.reviewData = {{ correct, wrong, unattempted }};
}}

function showReview() {{
    const area = document.getElementById('reviewArea');
    area.innerHTML = '';
    questions.forEach((q, i) => {{
        const userAns = answers[i];
        const isCorrect = userAns === q.answer;
        let optHtml = '';
        Object.entries(q.options).forEach(([k, v]) => {{
            let cls = 'option';
            if (k === q.answer) cls += ' correct';
            else if (k === userAns) cls += ' wrong';
            optHtml += `<div class="${{cls}}"><strong>${{k}})</strong> ${{v}}</div>`;
        }});
        area.innerHTML += `<div class="question-box">
            <div class="q-text"><strong>Q${{i+1}}.</strong> ${{q.question}} <span style="float:right">${{isCorrect ? '✅' : (userAns ? '❌' : '⚪')}}</span></div>
            ${{optHtml}}
            ${{q.explanation ? `<div class="explanation">💡 ${{q.explanation}}</div>` : ''}}
        </div>`;
    }});
}}

renderQuestion();
startTimer();
</script>
</body>
</html>"""
    
    return html


# ═══════════════════════════════════════════════════════════════
# BOT HANDLERS
# ═══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler."""
    user = get_user(update.effective_user.id)
    user["step"] = "menu"
    
    keyboard = [
        [InlineKeyboardButton("📝 Paste Questions", callback_data="paste_q")],
        [InlineKeyboardButton("🤖 AI Prompt Studio", callback_data="ai_prompt")],
        [InlineKeyboardButton("⚙️ Test Settings", callback_data="settings")],
        [InlineKeyboardButton("🛟 Lifelines", callback_data="lifelines")],
        [InlineKeyboardButton("🚀 Generate Test", callback_data="generate")],
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL.replace('@','')}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "✦ *TESTIFY BY AARAV* ✦\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 *Premium Test Builder Bot*\n\n"
        "Apne MCQs se premium CBT-style HTML test banayein — seconds mein!\n\n"
        "📝 Questions paste karein\n"
        "🤖 AI se MCQs banwayein\n"
        "⚙️ Test configure karein\n"
        "🚀 Download HTML test\n\n"
        "⏱ Timer | 🎯 Score | 🔖 Bookmark | 💡 Lifelines\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Neeche se option chunein 👇"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


async def paste_questions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paste questions button handler."""
    query = update.callback_query
    await query.answer()
    user = get_user(query.from_user.id)
    user["step"] = "waiting_questions"
    
    text = (
        "📝 *Question Workspace*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Apne formatted questions yahan paste karein.\n\n"
        "*Format:*\n"
        "`Q1. Question text?`\n"
        "`A) Option 1`\n"
        "`B) Option 2`\n"
        "`C) Option 3`\n"
        "`D) Option 4`\n"
        "`Ans: B`\n"
        "`Explanation: ...`\n\n"
        "✓ Hindi supported\n"
        "✓ Column matching\n"
        "✓ Explanation supported\n\n"
        "❌ Cancel karne ke liye /start type karein"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Questions text handler."""
    user = get_user(update.effective_user.id)
    if user["step"] != "waiting_questions":
        return
    
    text = update.message.text
    questions = parse_questions(text)
    
    if not questions:
        await update.message.reply_text(
            "❌ *Koi question detect nahi hua!*\n\n"
            "Format check karein aur dobara paste karein.\n"
            "/start se main menu par jaayein.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    user["questions"] = questions
    user["step"] = "menu"
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Test Configure karein", callback_data="settings")],
        [InlineKeyboardButton("🚀 Test Generate karein", callback_data="generate")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")],
    ]
    
    await update.message.reply_text(
        f"✅ *{len(questions)} questions detect ho gaye!*\n\n"
        f"📊 Questions: {len(questions)}\n"
        f"⏱ Default Duration: {user['settings']['duration']} min\n"
        f"🎯 Marks/Q: {user['settings']['marks_per_question']}\n\n"
        "Aage kya karna chahte hain?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings button handler."""
    query = update.callback_query
    await query.answer()
    user = get_user(query.from_user.id)
    user["step"] = "settings"
    
    s = user["settings"]
    neg_map = {0: "No deduction", -0.25: "−0.25", -0.33: "−0.33", -0.5: "−0.5", -1: "−1"}
    
    text = (
        "⚙️ *Test Configuration*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Test Name: `{s['test_name']}`\n"
        f"⏱ Duration: `{s['duration']} min`\n"
        f"🎯 Marks/Q: `{s['marks_per_question']}`\n"
        f"❌ Negative: `{neg_map.get(s['negative_marking'], 'No')}`\n"
        f"🔀 Shuffle Qs: `{'On' if s['shuffle_questions'] else 'Off'}`\n"
        f"🔀 Shuffle Options: `{'On' if s['shuffle_options'] else 'Off'}`\n"
        f"🌐 Language: `{s['language_mode']}`\n\n"
        "Kya change karna hai?"
    )
    
    keyboard = [
        [InlineKeyboardButton("📛 Test Name", callback_data="set_name")],
        [InlineKeyboardButton("⏱ Duration", callback_data="set_duration")],
        [InlineKeyboardButton("🎯 Marks/Q", callback_data="set_marks")],
        [InlineKeyboardButton("❌ Negative Marking", callback_data="set_negative")],
        [InlineKeyboardButton("🔀 Shuffle Questions", callback_data="toggle_shuffle_q")],
        [InlineKeyboardButton("🔀 Shuffle Options", callback_data="toggle_shuffle_o")],
        [InlineKeyboardButton("🌐 Language Mode", callback_data="set_lang")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")],
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings callback handler."""
    query = update.callback_query
    user = get_user(query.from_user.id)
    data = query.data
    
    if data == "toggle_shuffle_q":
        user["settings"]["shuffle_questions"] = not user["settings"]["shuffle_questions"]
    elif data == "toggle_shuffle_o":
        user["settings"]["shuffle_options"] = not user["settings"]["shuffle_options"]
    elif data == "set_name":
        user["step"] = "set_name"
        await query.edit_message_text("📛 Naya test name type karein:")
        return
    elif data == "set_duration":
        user["step"] = "set_duration"
        await query.edit_message_text("⏱ Duration (minutes) type karein (e.g., 20, 30, 60):")
        return
    elif data == "set_marks":
        user["step"] = "set_marks"
        await query.edit_message_text("🎯 Marks per question type karein (e.g., 1, 4, 5):")
        return
    elif data == "set_negative":
        keyboard = [
            [InlineKeyboardButton("No deduction", callback_data="neg_0")],
            [InlineKeyboardButton("−0.25", callback_data="neg_-0.25")],
            [InlineKeyboardButton("−0.33", callback_data="neg_-0.33")],
            [InlineKeyboardButton("−0.5", callback_data="neg_-0.5")],
            [InlineKeyboardButton("−1", callback_data="neg_-1")],
        ]
        await query.edit_message_text("❌ Negative marking chunein:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    elif data.startswith("neg_"):
        val = float(data.split("_")[1])
        user["settings"]["negative_marking"] = val
    elif data == "set_lang":
        keyboard = [
            [InlineKeyboardButton("Auto-detect", callback_data="lang_auto")],
            [InlineKeyboardButton("Hindi only", callback_data="lang_hindi")],
            [InlineKeyboardButton("English only", callback_data="lang_english")],
            [InlineKeyboardButton("Bilingual (switchable)", callback_data="lang_bilingual")],
        ]
        await query.edit_message_text("🌐 Language mode chunein:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    elif data.startswith("lang_"):
        user["settings"]["language_mode"] = data.split("_")[1]
    
    await query.answer("✅ Updated!")
    user["step"] = "menu"
    await show_menu(query)


async def handle_settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings text input handler."""
    user = get_user(update.effective_user.id)
    text = update.message.text.strip()
    
    if user["step"] == "set_name":
        user["settings"]["test_name"] = text
        user["step"] = "menu"
        await update.message.reply_text(f"✅ Test name set: *{text}*", parse_mode=ParseMode.MARKDOWN)
    elif user["step"] == "set_duration":
        try:
            val = int(text)
            user["settings"]["duration"] = val
            user["step"] = "menu"
            await update.message.reply_text(f"✅ Duration set: *{val} min*", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ Invalid number. Dobara try karein.")
    elif user["step"] == "set_marks":
        try:
            val = int(text)
            user["settings"]["marks_per_question"] = val
            user["step"] = "menu"
            await update.message.reply_text(f"✅ Marks/Q set: *{val}*", parse_mode=ParseMode.MARKDOWN)
        except ValueError:
            await update.message.reply_text("❌ Invalid number. Dobara try karein.")


async def lifelines_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lifelines button handler."""
    query = update.callback_query
    await query.answer()
    user = get_user(query.from_user.id)
    user["step"] = "lifelines"
    
    ll = user["settings"]["lifelines"]
    text = (
        "🛟 *Custom Lifelines*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 50:50 Option Remover: `{ll.get('fifty_fifty', 1)}` uses\n"
        f"💡 Smart Hint: `{ll.get('smart_hint', 1)}` uses\n"
        f"⏭ Skip Question: `{ll.get('skip_question', 3)}` uses\n"
        f"⏱ Extra Time (+30s): `{ll.get('extra_time', 1)}` uses\n\n"
        "Kis lifeline ke uses change karne hain?"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎯 50:50", callback_data="ll_fifty_fifty")],
        [InlineKeyboardButton("💡 Smart Hint", callback_data="ll_smart_hint")],
        [InlineKeyboardButton("⏭ Skip Question", callback_data="ll_skip_question")],
        [InlineKeyboardButton("⏱ Extra Time", callback_data="ll_extra_time")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu")],
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


async def lifeline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lifeline callback handler."""
    query = update.callback_query
    user = get_user(query.from_user.id)
    key = query.data.replace("ll_", "")
    user["step"] = f"set_ll_{key}"
    await query.edit_message_text(f"Kitne uses rakhne hain `{key}` ke liye? (number type karein):", parse_mode=ParseMode.MARKDOWN)


async def handle_lifeline_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lifeline text input handler."""
    user = get_user(update.effective_user.id)
    if not user["step"].startswith("set_ll_"):
        return
    try:
        val = int(update.message.text.strip())
        key = user["step"].replace("set_ll_", "")
        user["settings"]["lifelines"][key] = val
        user["step"] = "menu"
        await update.message.reply_text(f"✅ {key} ke uses set: *{val}*", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")


async def ai_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI prompt button handler."""
    query = update.callback_query
    await query.answer()
    user = get_user(query.from_user.id)
    user["step"] = "ai_lang"
    user["ai_config"] = {}
    
    keyboard = [
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="ail_hindi")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="ail_english")],
        [InlineKeyboardButton("🌐 Bilingual", callback_data="ail_bilingual")],
        [InlineKeyboardButton("🏜 Rajasthani", callback_data="ail_rajasthani")],
    ]
    await query.edit_message_text("🤖 *AI Prompt Studio*\n\n🌐 Language chunein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


async def ai_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI callback handler."""
    query = update.callback_query
    user = get_user(query.from_user.id)
    data = query.data
    
    if data.startswith("ail_"):
        user["ai_config"]["language"] = data.split("_")[1]
        user["step"] = "ai_num"
        await query.edit_message_text("🔢 Kitne questions chahiye? (number type karein):")
    elif data.startswith("ailvl_"):
        user["ai_config"]["level"] = data.split("_")[1]
        user["step"] = "ai_subject"
        await query.edit_message_text("📚 Subject name type karein:")


async def handle_ai_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI text input handler."""
    user = get_user(update.effective_user.id)
    text = update.message.text.strip()
    
    if user["step"] == "ai_num":
        try:
            user["ai_config"]["num"] = int(text)
            user["step"] = "ai_level"
            keyboard = [
                [InlineKeyboardButton("Easy", callback_data="ailvl_easy")],
                [InlineKeyboardButton("Moderate", callback_data="ailvl_moderate")],
                [InlineKeyboardButton("Hard", callback_data="ailvl_hard")],
                [InlineKeyboardButton("Very Hard", callback_data="ailvl_very_hard")],
                [InlineKeyboardButton("Extreme", callback_data="ailvl_extreme")],
                [InlineKeyboardButton("Mixed", callback_data="ailvl_mixed")],
            ]
            await update.message.reply_text("📊 Difficulty level chunein:", reply_markup=InlineKeyboardMarkup(keyboard))
        except ValueError:
            await update.message.reply_text("❌ Invalid number.")
    
    elif user["step"] == "ai_subject":
        user["ai_config"]["subject"] = text
        user["step"] = "ai_topic"
        await update.message.reply_text("🎯 Topic name type karein:")
    
    elif user["step"] == "ai_topic":
        user["ai_config"]["topic"] = text
        user["step"] = "ai_extra"
        await update.message.reply_text("✨ Extra requirements (optional) — ya `skip` type karein:")
    
    elif user["step"] == "ai_extra":
        user["ai_config"]["extra"] = "" if text.lower() == "skip" else text
        prompt = build_ai_prompt(user["ai_config"])
        user["step"] = "menu"
        await update.message.reply_text(
            f"✨ *AI Prompt Generated!*\n\n"
            f"```\n{prompt}\n```\n\n"
            f"📋 Is prompt ko apne AI tool (ChatGPT, Gemini, etc.) mein paste karke questions banwayein.\n"
            f"Phir questions yahan paste karke test generate karein!",
            parse_mode=ParseMode.MARKDOWN
        )


async def generate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate test button handler."""
    query = update.callback_query
    await query.answer()
    user = get_user(query.from_user.id)
    
    if not user["questions"]:
        await query.edit_message_text(
            "❌ *Pehle questions paste karein!*\n\n"
            "/start se main menu par jaayein aur 📝 Paste Questions chunein.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    await query.edit_message_text("⏳ *Test generate ho raha hai...*\n\nPremium HTML file ban rahi hai, please wait.", parse_mode=ParseMode.MARKDOWN)
    
    try:
        html = generate_html_test(
            test_name=user["settings"]["test_name"],
            questions=user["questions"],
            settings=user["settings"],
            instructions=user["settings"]["instructions"]
        )
        
        filename = f"{user['settings']['test_name'].replace(' ', '_')}_testify.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        
        await query.message.reply_document(
            document=open(filename, "rb"),
            caption=(
                f"✅ *Test Ready!*\n\n"
                f"📛 {user['settings']['test_name']}\n"
                f"📋 Questions: {len(user['questions'])}\n"
                f"⏱ Duration: {user['settings']['duration']} min\n"
                f"🎯 Marks/Q: {user['settings']['marks_per_question']}\n\n"
                f"📱 Mobile friendly | Single file | No server required\n\n"
                f"✦ TESTIFY BY AARAV ✦"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        
        os.remove(filename)
        
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")


async def show_menu(query):
    """Menu display karta hai."""
    user = get_user(query.from_user.id)
    q_count = len(user["questions"])
    
    keyboard = [
        [InlineKeyboardButton(f"📝 Paste Questions ({q_count})", callback_data="paste_q")],
        [InlineKeyboardButton("🤖 AI Prompt Studio", callback_data="ai_prompt")],
        [InlineKeyboardButton("⚙️ Test Settings", callback_data="settings")],
        [InlineKeyboardButton("🛟 Lifelines", callback_data="lifelines")],
        [InlineKeyboardButton("🚀 Generate Test", callback_data="generate")],
        [InlineKeyboardButton("📢 Join @sjvbots", url=f"https://t.me/{CHANNEL.replace('@','')}")],
    ]
    
    text = (
        "✦ *TESTIFY BY AARAV* ✦\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Questions: *{q_count}*\n"
        f"📛 Test: `{user['settings']['test_name']}`\n"
        f"⏱ Duration: `{user['settings']['duration']} min`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Kya karna chahte hain?"
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu callback handler."""
    query = update.callback_query
    await query.answer()
    user = get_user(query.from_user.id)
    user["step"] = "menu"
    await show_menu(query)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler."""
    text = (
        "📖 *Testify By Aarav — Help*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*/start* — Main menu\n"
        "*/help* — Yeh help message\n"
        "*/reset* — Sab kuch reset karein\n\n"
        "*Workflow:*\n"
        "1️⃣ Questions paste karein (ya AI se banwayein)\n"
        "2️⃣ Test settings configure karein\n"
        "3️⃣ Generate par click karein\n"
        "4️⃣ HTML file download karein\n\n"
        "*Features:*\n"
        "✓ Timer + Auto-submit\n"
        "✓ Question palette\n"
        "✓ Bookmark\n"
        "✓ Lifelines (50:50, Hint, Skip, Extra Time)\n"
        "✓ Negative marking\n"
        "✓ Detailed solutions\n"
        "✓ Mobile responsive\n\n"
        "📢 Updates: @sjvbots"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset command handler."""
    uid = update.effective_user.id
    reset_user(uid)
    await update.message.reply_text("✅ Sab reset ho gaya! /start se shuru karein.")


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """All text messages handle karta hai."""
    user = get_user(update.effective_user.id)
    step = user["step"]
    
    if step == "waiting_questions":
        await handle_questions(update, context)
    elif step in ["set_name", "set_duration", "set_marks"]:
        await handle_settings_input(update, context)
    elif step.startswith("set_ll_"):
        await handle_lifeline_input(update, context)
    elif step in ["ai_num", "ai_subject", "ai_topic", "ai_extra"]:
        await handle_ai_input(update, context)
    else:
        await update.message.reply_text(
            "👋 Pehle /start karein aur menu se option chunein."
        )


# ═══════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════

def main():
    """Main application runner."""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(paste_questions_handler, pattern="^paste_q$"))
    app.add_handler(CallbackQueryHandler(settings_handler, pattern="^settings$"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^(set_|toggle_|neg_|lang_)"))
    app.add_handler(CallbackQueryHandler(lifelines_handler, pattern="^lifelines$"))
    app.add_handler(CallbackQueryHandler(lifeline_callback, pattern="^ll_"))
    app.add_handler(CallbackQueryHandler(ai_prompt_handler, pattern="^ai_prompt$"))
    app.add_handler(CallbackQueryHandler(ai_callback, pattern="^(ail_|ailvl_)"))
    app.add_handler(CallbackQueryHandler(generate_handler, pattern="^generate$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu$"))
    
    # Text handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_text))
    
    print("🚀 Testify By Aarav Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
