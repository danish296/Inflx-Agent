"""AutoStream conversational agent built on LangGraph + OpenRouter.

Graph shape:
    START -> classify_intent -> agent -> (tools? -> agent)* -> END

Nodes:
    classify_intent : explicit intent detector (casual / inquiry / high_intent)
    agent           : LLM with two tools bound (RAG + lead capture)
    tools           : ToolNode executing the chosen tool
"""
from __future__ import annotations

import json
import os
import re
from typing import Annotated, List, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from rag import KnowledgeRetriever
from tools import mock_lead_capture as _capture_lead

load_dotenv()

# ---------------------------------------------------------------------------
# LLM factory (OpenRouter via OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------
def _make_llm(temperature: float = 0.2) -> ChatOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku"),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=api_key,
        temperature=temperature,
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "http://localhost"),
            "X-Title": "Inflx-AutoStream-Agent",
        },
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
_retriever = KnowledgeRetriever()


@tool
def search_knowledge_base(query: str) -> str:
    """Search the AutoStream knowledge base for product, pricing, feature, or policy info.

    Use this for any factual question about AutoStream plans, prices, features,
    refund policy, or support policy. Returns top matching passages.
    """
    chunks = _retriever.retrieve(query, k=3)
    return _retriever.format_context(chunks)


_FAKE_NAMES = {
    "john doe", "jane doe", "test user", "user name", "example name",
    "full name", "first last", "your name", "name here", "sample user",
}
_FAKE_EMAIL_DOMAINS = {
    "example.com", "example.org", "test.com", "email.com", "domain.com",
    "yourdomain.com", "sample.com", "placeholder.com",
}
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate_lead_args(name: str, email: str, platform: str) -> Optional[str]:
    """Return an error string if any arg looks like a placeholder, else None."""
    n = (name or "").strip().lower()
    e = (email or "").strip().lower()
    p = (platform or "").strip().lower()

    if not n or not e or not p:
        return "Missing field(s). Name, email, and platform are all required and must come from the user."
    if len(n) < 2 or " " not in n.strip() and len(n) < 4:
        # allow single-word names >= 4 chars; reject 1-char nonsense
        if len(n) < 2:
            return f"Name '{name}' looks invalid. Ask the user to share their real name."
    if n in _FAKE_NAMES or "example" in n or "placeholder" in n or "dummy" in n:
        return f"Name '{name}' looks like a placeholder. Ask the user for their real name — do not invent one."
    if not _EMAIL_RE.match(e):
        return f"Email '{email}' is not a valid address. Ask the user for their real email."
    domain = e.split("@", 1)[1]
    if domain in _FAKE_EMAIL_DOMAINS or "example" in domain or "placeholder" in domain:
        return f"Email '{email}' uses a placeholder domain. Ask the user for their real email — do not invent one."
    if "example" in p or "placeholder" in p or len(p) < 2:
        return f"Platform '{platform}' looks invalid. Ask the user which creator platform they use (YouTube, Instagram, TikTok, etc.)."
    return None


@tool
def mock_lead_capture(name: str, email: str, platform: str) -> str:
    """Capture a qualified lead in the CRM.

    HARD RULES:
      - Only invoke once NAME, EMAIL, and PLATFORM are all explicitly provided
        by the user in the conversation.
      - NEVER pass placeholder values like 'John Doe', 'john.doe@example.com',
        'test@test.com', 'example.com', or any domain containing 'example'.
      - If any field is missing or uncertain, do NOT call this tool — ask the
        user instead.
      - `platform` is the user's primary creator platform (YouTube, Instagram,
        TikTok, LinkedIn, etc.).
    """
    err = _validate_lead_args(name, email, platform)
    if err:
        # Returning an error string lets the LLM recover (the ToolNode will
        # feed this back as a ToolMessage). This is the core guardrail
        # against premature tool firing.
        return json.dumps({"status": "error", "reason": err})
    result = _capture_lead(name=name, email=email, platform=platform)
    return json.dumps(result)


TOOLS = [search_knowledge_base, mock_lead_capture]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[List, add_messages]
    intent: Optional[str]
    lead_captured: bool


_VALID_INTENTS = ("high_intent", "inquiry", "casual")

_CLASSIFIER_SYSTEM = (
    "Classify the LATEST user message into EXACTLY ONE intent label.\n"
    "Allowed labels (return only the label, nothing else, no punctuation):\n"
    "  casual      - greeting or small talk\n"
    "  inquiry     - asking about AutoStream plans, pricing, features, or policies\n"
    "  high_intent - wants to sign up / try / buy a plan, OR is sharing name, email, or platform\n"
    "Respond with a single word: casual, inquiry, or high_intent."
)


def _parse_intent_label(text: str) -> str:
    """Robust, vendor-agnostic label parser — no structured output needed."""
    t = (text or "").strip().lower()
    # strip common wrappers like quotes, JSON, trailing periods
    t = re.sub(r"[\"'`.\s]", " ", t)
    for label in _VALID_INTENTS:  # check high_intent before inquiry/casual
        if label in t:
            return label
    return "casual"


_AGENT_SYSTEM = """You are Inflx, the AI sales & support assistant for AutoStream \
(automated video editing SaaS for content creators).

Follow these rules strictly:

1. Product, pricing, feature, or policy questions -> ALWAYS call
   `search_knowledge_base` first, then answer from the retrieved passages.
   Never invent prices, features, or policies.

2. High-intent signals (user wants to sign up / try / buy a plan):
   - You must collect THREE fields from the user's own messages:
       NAME, EMAIL, CREATOR PLATFORM (YouTube / Instagram / TikTok / LinkedIn / etc.)
   - When the user first expresses intent to sign up, DO NOT call any tool.
     Reply with a short message asking for the missing fields — nothing else.
   - Only after the user has typed their REAL name, REAL email, and REAL
     platform in this conversation, call `mock_lead_capture(name, email, platform)`
     exactly once, then confirm success in one sentence.

3. ABSOLUTE RULE — never invent user data:
   - Do NOT pass placeholder names like 'John Doe', 'Jane Doe', 'Test User',
     'Full Name', or anything similar.
   - Do NOT pass placeholder emails like 'john.doe@example.com',
     'test@test.com', 'user@domain.com', or anything using 'example.com',
     'test.com', 'placeholder.com', or a made-up domain.
   - Do NOT pre-fill arguments to satisfy a schema. If you don't have the
     value from the user, you are REQUIRED to ask them for it instead of
     calling the tool.
   - If the backend rejects your call (status=error), read the reason,
     apologize briefly, and ask the user for the specific field.

4. Casual greetings -> reply warmly in one short line and invite the user
   to ask about plans or features.

5. Keep responses concise (1-3 sentences). No markdown headings, no emojis,
   no lists unless explicitly asked.

Detected intent for this turn: {intent}
Lead already captured this session: {lead_captured}
"""


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def classify_intent(state: AgentState) -> dict:
    """Lightweight, vendor-agnostic intent classifier on the latest user msg.

    We intentionally avoid `with_structured_output` here because several
    OpenRouter-hosted models (incl. Claude 3 Haiku) emit the label as plain
    text rather than JSON. Parsing a single token is both cheaper and more
    robust than forcing function-calling across every provider.
    """
    last_user = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    if last_user is None:
        return {"intent": "casual"}

    llm = _make_llm(temperature=0)
    response = llm.invoke(
        [
            SystemMessage(content=_CLASSIFIER_SYSTEM),
            HumanMessage(content=last_user.content),
        ]
    )
    return {"intent": _parse_intent_label(getattr(response, "content", ""))}


def agent_node(state: AgentState) -> dict:
    """Main reasoning step. Binds tools and lets the LLM decide next action.

    We do NOT flip `lead_captured` here — only after the tool actually
    executes successfully (see `_post_tools` below). This prevents the
    session from being marked "captured" when the model fires the tool
    with placeholder values (which the tool will reject).
    """
    intent = state.get("intent") or "casual"
    lead_captured = state.get("lead_captured", False)

    llm = _make_llm(temperature=0.3).bind_tools(TOOLS)
    system = SystemMessage(
        content=_AGENT_SYSTEM.format(intent=intent, lead_captured=lead_captured)
    )
    response: AIMessage = llm.invoke([system, *state["messages"]])
    return {"messages": [response]}


def _post_tools(state: AgentState) -> dict:
    """After ToolNode runs, inspect the latest ToolMessage for successful
    lead capture and flip `lead_captured` only then."""
    from langchain_core.messages import ToolMessage

    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage) and msg.name == "mock_lead_capture":
            try:
                payload = json.loads(msg.content)
            except Exception:
                return {}
            if payload.get("status") == "success":
                return {"lead_captured": True}
            return {}
        if not isinstance(msg, ToolMessage):
            break  # only inspect the most recent batch of tool results
    return {}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
def build_app():
    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_intent)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("post_tools", _post_tools)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "agent")
    graph.add_conditional_edges(
        "agent", tools_condition, {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "post_tools")
    graph.add_edge("post_tools", "agent")

    return graph.compile(checkpointer=MemorySaver())


APP = build_app()


def chat(user_message: str, thread_id: str = "default") -> str:
    """Single-turn helper. State persists per `thread_id` via MemorySaver."""
    return chat_with_state(user_message, thread_id=thread_id)["reply"]


def chat_with_state(user_message: str, thread_id: str = "default") -> dict:
    """Richer single-turn helper exposing intent + lead status for UIs."""
    cfg = {"configurable": {"thread_id": thread_id}}
    result = APP.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config=cfg,
    )
    reply = "(no response)"
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            reply = msg.content
            break
    return {
        "reply": reply,
        "intent": result.get("intent", "casual"),
        "lead_captured": bool(result.get("lead_captured", False)),
    }
