"""Streamlit web UI for the Inflx / AutoStream agent.

Design language:
    "Late-night editing room" — deep warm black, cream type, a single amber
    studio-light accent. Fraunces serif for display, IBM Plex Sans for body,
    IBM Plex Mono for status chips and labels. No purple gradients, no Inter.
"""
from __future__ import annotations

import html
import json
import uuid
from pathlib import Path

import streamlit as st

from agent import chat_with_state

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Inflx · AutoStream",
    page_icon="◐",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# CSS — typography, palette, bubbles, grain
# ---------------------------------------------------------------------------
CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root {
  --ink: #f1ebe3;
  --ink-dim: #a9a097;
  --ink-faint: #6b635a;
  --paper: #0b0b0c;
  --paper-2: #141214;
  --paper-3: #1c1a1c;
  --line: #2a2629;
  --amber: #d69b3a;
  --amber-soft: #e8b85a;
  --rust: #a94f2a;
  --sage: #8ca68a;
  --ok: #6aa46a;
}

html, body, [class*="css"], .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
  background: var(--paper) !important;
  color: var(--ink) !important;
  font-family: 'IBM Plex Sans', system-ui, sans-serif !important;
}

/* Subtle film-grain overlay */
.stApp::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: 0.045;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/><feColorMatrix values='0 0 0 0 0.95  0 0 0 0 0.92  0 0 0 0 0.88  0 0 0 0.6 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
}

/* Warm vignette */
.stApp::after {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background:
    radial-gradient(900px 600px at 85% -10%, rgba(214,155,58,0.10), transparent 60%),
    radial-gradient(700px 500px at 10% 110%, rgba(169,79,42,0.08), transparent 60%);
}

.main .block-container {
  padding-top: 1.2rem;
  padding-bottom: 6rem;
  max-width: 880px;
  position: relative;
  z-index: 1;
}

/* ===== Masthead ===== */
.masthead {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 0 0 1.2rem 0;
  border-bottom: 1px solid var(--line);
  margin-bottom: 1.6rem;
}
.wordmark {
  font-family: 'Fraunces', serif;
  font-weight: 500;
  font-style: italic;
  font-size: 2.1rem;
  letter-spacing: -0.01em;
  line-height: 1;
  color: var(--ink);
}
.wordmark .slash {
  color: var(--amber);
  font-style: normal;
  font-weight: 300;
  margin: 0 0.35rem;
}
.wordmark .product {
  font-style: normal;
  font-weight: 400;
  color: var(--ink-dim);
}
.kicker {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faint);
  text-align: right;
}
.kicker .amber { color: var(--amber); }

.subhead {
  font-family: 'Fraunces', serif;
  font-weight: 300;
  font-size: 1.25rem;
  color: var(--ink-dim);
  line-height: 1.45;
  max-width: 56ch;
  margin-bottom: 2rem;
  font-style: italic;
}
.subhead em {
  color: var(--ink);
  font-style: normal;
  font-weight: 500;
  border-bottom: 1px solid var(--amber);
  padding-bottom: 1px;
}

/* ===== Status chips (above conversation) ===== */
.statusbar {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 1.4rem;
  flex-wrap: wrap;
}
.chip {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.4rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: 2px;
  color: var(--ink-dim);
  background: var(--paper-2);
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}
.chip .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--ink-faint);
  box-shadow: 0 0 0 3px rgba(255,255,255,0.02);
}
.chip.intent-casual .dot { background: var(--sage); }
.chip.intent-inquiry .dot { background: var(--amber); }
.chip.intent-high_intent .dot { background: var(--rust); }
.chip.lead-idle .dot { background: var(--ink-faint); }
.chip.lead-collecting .dot { background: var(--amber-soft); animation: pulse 1.6s ease-in-out infinite; }
.chip.lead-captured {
  border-color: var(--ok);
  color: var(--ok);
}
.chip.lead-captured .dot { background: var(--ok); }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* ===== Chat bubbles (custom HTML, NOT st.chat_message) ===== */
.turn {
  margin: 0 0 1.4rem 0;
  display: flex;
  flex-direction: column;
  animation: fade-up 0.35s ease both;
}
.turn.user { align-items: flex-end; }
.turn.assistant { align-items: flex-start; }
.turn .who {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-bottom: 0.4rem;
}
.turn.user .who { color: var(--amber); }
.bubble {
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.98rem;
  line-height: 1.62;
  padding: 0.95rem 1.15rem;
  border-radius: 2px;
  max-width: 82%;
  color: var(--ink);
  position: relative;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.turn.assistant .bubble {
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-left: 2px solid var(--amber);
}
.turn.user .bubble {
  background: transparent;
  border: 1px solid var(--line);
  border-right: 2px solid var(--amber);
  color: var(--ink);
}
.turn.system .bubble {
  background: transparent;
  border: 1px dashed var(--line);
  color: var(--ink-dim);
  font-style: italic;
  font-size: 0.88rem;
  font-family: 'IBM Plex Mono', monospace;
  letter-spacing: 0.02em;
}
@keyframes fade-up {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ===== Chat input — single clean border, no double-ring ===== */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] > div,
section[data-testid="stBottom"] {
  background: var(--paper) !important;
  border-top: 1px solid var(--line) !important;
  box-shadow: none !important;
}

/* Outer wrapper — NO border (kills the double-border look). */
[data-testid="stChatInput"],
[data-testid="stChatInputContainer"] {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}

/* Inner base-input box — this is the ONLY visible bordered element. */
[data-testid="stChatInput"] div[data-baseweb="base-input"],
div[data-baseweb="base-input"] {
  background: var(--paper-2) !important;
  border: 1px solid var(--line) !important;
  border-radius: 2px !important;
  box-shadow: none !important;
  outline: none !important;
  transition: border-color 0.2s ease;
}
[data-testid="stChatInput"] div[data-baseweb="base-input"]:focus-within,
div[data-baseweb="base-input"]:focus-within {
  border-color: var(--amber) !important;
  box-shadow: 0 0 0 1px rgba(214,155,58,0.25) !important;
}

/* Textarea itself — no border, transparent so the wrapper border is the only line. */
[data-testid="stChatInput"] textarea,
[data-testid="stChatInputTextArea"],
[data-testid="stChatInput"] input,
div[data-baseweb="base-input"] textarea,
div[data-baseweb="base-input"] input {
  background: transparent !important;
  color: var(--ink) !important;
  caret-color: var(--amber) !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
  font-size: 0.98rem !important;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  -webkit-text-fill-color: var(--ink) !important;
}
[data-testid="stChatInput"] textarea::placeholder,
[data-testid="stChatInputTextArea"]::placeholder,
div[data-baseweb="base-input"] textarea::placeholder,
div[data-baseweb="base-input"] input::placeholder {
  color: var(--ink-faint) !important;
  opacity: 1 !important;
}

/* Send button (the little right-side arrow Streamlit renders). */
[data-testid="stChatInputSubmitButton"],
button[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInput"] button {
  background: transparent !important;
  color: var(--amber) !important;
  border: none !important;
  border-left: 1px solid var(--line) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
[data-testid="stChatInputSubmitButton"] svg,
[data-testid="stChatInput"] button svg {
  fill: var(--amber) !important;
  color: var(--amber) !important;
}
[data-testid="stChatInputSubmitButton"]:hover {
  background: rgba(214,155,58,0.08) !important;
}

/* ===== Sidebar ===== */
[data-testid="stSidebar"] {
  background: var(--paper-2) !important;
  border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] * { color: var(--ink-dim); }
.side-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 1.4rem 0 0.5rem 0;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--line);
}
.side-val {
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.92rem;
  color: var(--ink);
  margin-bottom: 0.25rem;
}
.side-val.mono { font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem; }
.side-note {
  font-family: 'Fraunces', serif;
  font-style: italic;
  font-size: 0.88rem;
  color: var(--ink-dim);
  line-height: 1.5;
  margin-top: 0.4rem;
}
.kb-item {
  border-left: 1px solid var(--line);
  padding: 0.35rem 0 0.35rem 0.7rem;
  margin-bottom: 0.5rem;
}
.kb-item .topic {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--amber);
  margin-bottom: 0.2rem;
}
.kb-item .text {
  font-size: 0.82rem;
  color: var(--ink-dim);
  line-height: 1.45;
}

/* Streamlit button polish */
.stButton > button {
  background: transparent;
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: 2px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  padding: 0.55rem 1rem;
  transition: all 0.15s ease;
}
.stButton > button:hover {
  border-color: var(--amber);
  color: var(--amber);
}

footer, #MainMenu,
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }

/* Nuke remaining light-theme bleed-throughs */
iframe, .stApp > div:first-child {
  background: var(--paper) !important;
}
[data-testid="stAppViewBlockContainer"] { background: transparent !important; }

.footnote {
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faint);
  display: flex;
  justify-content: space-between;
}
.footnote .amber { color: var(--amber); }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session bootstrap
# ---------------------------------------------------------------------------
def _init_state() -> None:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "ui_messages" not in st.session_state:
        st.session_state.ui_messages = []
    if "intent" not in st.session_state:
        st.session_state.intent = "—"
    if "lead_captured" not in st.session_state:
        st.session_state.lead_captured = False
    if "pending_user_msg" not in st.session_state:
        st.session_state.pending_user_msg = None


def _reset_session() -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.ui_messages = []
    st.session_state.intent = "—"
    st.session_state.lead_captured = False
    st.session_state.pending_user_msg = None


_init_state()


# ---------------------------------------------------------------------------
# Masthead
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="masthead">
      <div class="wordmark">
        inflx<span class="slash">/</span><span class="product">autostream</span>
      </div>
      <div class="kicker">
        social → lead · <span class="amber">agentic workflow</span>
      </div>
    </div>
    <div class="subhead">
      An agent built for <em>conversion</em>, not small talk —
      it reads intent, retrieves only what it must, and
      captures the lead the instant the signal is real.
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Status chips
# ---------------------------------------------------------------------------
def _render_statusbar() -> None:
    intent = st.session_state.intent
    if st.session_state.lead_captured:
        lead_state, lead_label = "captured", "lead · captured"
    elif intent == "high_intent":
        lead_state, lead_label = "collecting", "lead · collecting"
    else:
        lead_state, lead_label = "idle", "lead · idle"

    intent_label = (
        {"casual": "intent · casual",
         "inquiry": "intent · inquiry",
         "high_intent": "intent · high"}
        .get(intent, "intent · —")
    )
    intent_cls = f"intent-{intent}" if intent in ("casual", "inquiry", "high_intent") else ""

    st.markdown(
        f"""
        <div class="statusbar">
          <span class="chip {intent_cls}"><span class="dot"></span>{intent_label}</span>
          <span class="chip lead-{lead_state}"><span class="dot"></span>{lead_label}</span>
          <span class="chip"><span class="dot"></span>thread · {st.session_state.thread_id[:8]}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


_render_statusbar()


# ---------------------------------------------------------------------------
# Conversation (custom bubbles, no st.chat_message)
# ---------------------------------------------------------------------------
def _render_turn(role: str, content: str) -> None:
    cls = {"user": "user", "assistant": "assistant", "system": "system"}.get(role, "assistant")
    who = {"user": "you", "assistant": "inflx", "system": "system"}[role]
    st.markdown(
        f"""
        <div class="turn {cls}">
          <div class="who">{who}</div>
          <div class="bubble">{html.escape(content)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if not st.session_state.ui_messages:
    _render_turn(
        "assistant",
        "Hey — I'm the AutoStream assistant. Ask about our plans, or tell me "
        "what you're trying to build and I'll point you at the right tier.",
    )

for m in st.session_state.ui_messages:
    _render_turn(m["role"], m["content"])


# ---------------------------------------------------------------------------
# Sidebar — system panel + KB peek
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="font-family:'Fraunces',serif;font-size:1.4rem;
                    font-style:italic;font-weight:500;color:var(--ink);
                    border-bottom:1px solid var(--line);padding-bottom:0.8rem;">
          system log
        </div>
        """,
        unsafe_allow_html=True,
    )

    import os as _os
    model = _os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")

    st.markdown('<div class="side-label">vendor</div>', unsafe_allow_html=True)
    st.markdown('<div class="side-val">OpenRouter</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-label">model</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="side-val mono">{html.escape(model)}</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-label">framework</div>', unsafe_allow_html=True)
    st.markdown('<div class="side-val">LangGraph · StateGraph</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-label">graph</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="side-val mono" style="font-size:0.76rem;line-height:1.6;">'
        'classify_intent<br>&nbsp;&nbsp;→ agent<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;⇄ tools (rag · lead)'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-label">knowledge base</div>', unsafe_allow_html=True)
    kb_path = Path("knowledge_base.json")
    if kb_path.exists():
        kb = json.loads(kb_path.read_text(encoding="utf-8"))
        for c in kb.get("chunks", []):
            st.markdown(
                f"""
                <div class="kb-item">
                  <div class="topic">{html.escape(c['topic'])}</div>
                  <div class="text">{html.escape(c['text'][:140])}{'…' if len(c['text'])>140 else ''}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height:1rem;"></div>', unsafe_allow_html=True)
    if st.button("reset session", use_container_width=True):
        _reset_session()
        st.rerun()


# ---------------------------------------------------------------------------
# Input → agent invocation (two-phase render so the user's message
# appears IMMEDIATELY, before the LLM round-trip)
# ---------------------------------------------------------------------------

# Phase 2: if there's a pending user message from the previous render, show a
# typing indicator and call the agent now. The user bubble is already on
# screen because it was appended and rendered BEFORE we trigger this phase.
if st.session_state.pending_user_msg:
    pending = st.session_state.pending_user_msg
    st.session_state.pending_user_msg = None

    # Inline "typing" bubble so the UI doesn't feel frozen.
    st.markdown(
        """
        <div class="turn assistant">
          <div class="who">inflx</div>
          <div class="bubble" style="color:var(--ink-dim);font-style:italic;">
            <span class="typing-dots"><span></span><span></span><span></span></span>
          </div>
        </div>
        <style>
          .typing-dots { display:inline-flex; gap:4px; align-items:center; }
          .typing-dots span {
            width: 5px; height: 5px; border-radius: 50%;
            background: var(--amber);
            animation: typ 1.2s infinite ease-in-out;
          }
          .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
          .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
          @keyframes typ {
            0%, 80%, 100% { opacity: 0.2; transform: translateY(0); }
            40% { opacity: 1; transform: translateY(-2px); }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        result = chat_with_state(pending, thread_id=st.session_state.thread_id)
        st.session_state.intent = result["intent"]
        prev_captured = st.session_state.lead_captured
        st.session_state.lead_captured = result["lead_captured"]
        st.session_state.ui_messages.append(
            {"role": "assistant", "content": result["reply"]}
        )
        if result["lead_captured"] and not prev_captured:
            st.session_state.ui_messages.append(
                {
                    "role": "system",
                    "content": "[tool · mock_lead_capture executed — lead recorded]",
                }
            )
    except Exception as exc:
        st.session_state.ui_messages.append(
            {"role": "system", "content": f"[error] {exc}"}
        )
    st.rerun()

# Phase 1: capture new input, append it to history, and rerun so the user's
# own bubble paints BEFORE the (potentially slow) LLM call starts.
user_input = st.chat_input("ask about plans, or tell me what you're building…")
if user_input:
    st.session_state.ui_messages.append({"role": "user", "content": user_input})
    st.session_state.pending_user_msg = user_input
    st.rerun()


# ---------------------------------------------------------------------------
# Footnote
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="footnote">
      <span>built for servicehive · inflx</span>
      <span class="amber">langgraph × openrouter</span>
    </div>
    """,
    unsafe_allow_html=True,
)
