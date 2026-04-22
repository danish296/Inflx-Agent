# Inflx — Social-to-Lead Agentic Workflow

> **Assignment:** ServiceHive / Inflx — ML Intern — *Social-to-Lead Agentic Workflow*
> **Product under test:** *AutoStream* — a fictional SaaS that automates video editing for creators.

A production-shaped conversational agent that (1) classifies user intent, (2) answers
product / pricing / policy questions via **RAG** over a local knowledge base, and (3)
qualifies high-intent users and captures them through a **tool-calling** backend.

Built on **LangGraph** (explicit state machine) + **OpenRouter** (vendor) using
**Claude 3 Haiku** as the default LLM — swappable to GPT-4o-mini, Gemini 1.5 Flash,
or any free OpenRouter model via one env var.

---

## 1. Project Layout

```
.
├── agent.py              # LangGraph graph: classify → agent → tools (loop)
├── rag.py                # BM25 retriever over knowledge_base.json
├── tools.py              # mock_lead_capture (spec-mandated signature)
├── knowledge_base.json   # AutoStream plans, features, policies (RAG corpus)
├── main.py               # Interactive CLI
├── app.py                # Streamlit web UI ("editing-room" aesthetic)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 2. Quick Start

```bash
# 1. Clone & enter
git clone <this-repo> inflx && cd inflx

# 2. Create and activate a venv (Python 3.9+)
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# 3. Install deps
pip install -r requirements.txt

# 4. Configure your LLM key
cp .env.example .env    # (Windows: copy .env.example .env)
# then open .env and set OPENROUTER_API_KEY=...

# 5. Run the agent — pick one

# (a) terminal CLI
python main.py

# (b) web UI (Streamlit)
streamlit run app.py
```

Get a free OpenRouter key at <https://openrouter.ai/keys>. The default model is
`anthropic/claude-3-haiku`; swap `OPENROUTER_MODEL` in `.env` for any allowed
variant (e.g. `google/gemini-flash-1.5`, `openai/gpt-4o-mini`, or a
`:free`-suffixed model).

### Web UI

`app.py` ships a deliberately-designed Streamlit interface — *not* a stock
chatbot template. Design direction:

- **Palette** — deep warm black (`#0b0b0c`) paper, cream (`#f1ebe3`) type,
  a single amber studio-light accent (`#d69b3a`), rust for secondary warmth.
  Film-grain overlay + directional vignette evoke a late-night editing room,
  which is on-brand for a video-editing SaaS.
- **Typography** — **Fraunces** (variable serif, editorial) for the
  wordmark and quiet display copy; **IBM Plex Sans** for body; **IBM Plex
  Mono** for status chips and system labels. No Inter, no Space Grotesk,
  no system-ui fallbacks.
- **Information architecture** — a masthead with a slash-separated
  wordmark, a status bar of monospaced chips (`intent · …`, `lead · …`,
  `thread · …`) that update live after every turn, hand-rolled chat
  bubbles with a thin amber side-rule marking the speaker, and a sidebar
  "system log" exposing the model, graph shape, and KB contents.
- **Motion** — a single purposeful `fade-up` on bubble entrance and a
  slow pulse on the `lead · collecting` chip. No gratuitous animation.

---

## 3. Sample Session

```
you > Hi, tell me about your pricing.
inflx > AutoStream has two plans: Basic at $29/month (10 videos, 720p) and Pro at
        $79/month (unlimited videos, 4K, AI captions, 24/7 support). Want more
        detail on either?

you > That sounds good — I want to try the Pro plan for my YouTube channel.
inflx > Awesome! I just need a couple of details to set that up. What's your
        name and email address?

you > Danish Akhtar, danish@example.com
inflx > Thanks, Danish! Just to confirm — your primary creator platform is
        YouTube, correct?

you > yep
inflx > [tool: mock_lead_capture(name="Danish Akhtar",
                                 email="danish@example.com",
                                 platform="YouTube")]
        # stdout: Lead captured successfully: Danish Akhtar, danish@example.com, YouTube
inflx > You're all set, Danish — our team will reach out shortly to onboard your
        YouTube channel onto the Pro plan.
```

---

## 4. Architecture (≈200 words)

We use **LangGraph** rather than AutoGen because the assignment needs *verifiable*,
deterministic control over *when* a backend tool fires. LangGraph's explicit
`StateGraph` makes the flow auditable: every node, edge, and state transition is
visible and testable — crucial for "the tool must not be triggered prematurely".

**Graph shape:**
`START → classify_intent → agent → (tools → agent)* → END`

1. **`classify_intent`** — a small structured-output LLM call (Pydantic schema)
   labels the latest user message as `casual | inquiry | high_intent`. This makes
   intent detection a first-class, observable step rather than a black-box side
   effect of the main LLM.
2. **`agent`** — the main reasoning node. The LLM is bound to two tools
   (`search_knowledge_base`, `mock_lead_capture`) and instructed via a compact
   system prompt to (a) *always* retrieve before answering factual questions and
   (b) *only* call the lead-capture tool once name, email, and platform are all
   confirmed.
3. **`tools`** — LangGraph's prebuilt `ToolNode` executes whichever tool the LLM
   chose; its output returns to `agent` for a grounded natural-language reply.

**State management.** State is a `TypedDict` with `messages` (reducer:
`add_messages`), `intent`, and a `lead_captured` flag. A `MemorySaver`
checkpointer persists state per `thread_id`, so the agent retains full
conversational memory across the 5–6 turns of the qualification flow without
re-sending redundant context. RAG is handled by a BM25 index (`rank_bm25`) over
`knowledge_base.json` — lightweight, fully offline, and deterministic for a
small corpus.

---

## 5. Capabilities Mapped to Requirements

| Requirement | Implementation |
|---|---|
| Intent identification (casual / inquiry / high-intent) | `classify_intent` node with Pydantic structured output |
| RAG-powered knowledge retrieval | `rag.KnowledgeRetriever` (BM25) + `search_knowledge_base` tool |
| Tool execution for lead capture | `mock_lead_capture(name, email, platform)` tool, bound to LLM, gated by system prompt |
| Prevent premature tool calls | Explicit instruction in system prompt *plus* a 3-field checklist the LLM must satisfy before emitting the tool call |
| Memory across 5–6 turns | LangGraph `MemorySaver` checkpointer keyed by `thread_id` |
| Framework | LangGraph (preferred option in spec) |
| LLM | Claude 3 Haiku via OpenRouter (swappable) |

---

## 6. WhatsApp Deployment (Webhook Integration)

To put this agent in front of real users on WhatsApp we would wire it behind the
**WhatsApp Business Cloud API** (Meta) using webhooks. The flow:

1. **Provision.** Register a WhatsApp Business number in Meta Business Manager,
   create a Meta app, and get a permanent access token + phone number ID.
2. **Expose a webhook.** Wrap `agent.chat(message, thread_id=...)` in a FastAPI
   (or Flask) server and deploy it (Cloud Run, Fly.io, Render, AWS Lambda +
   API Gateway, etc.) with HTTPS. Two endpoints:
   - `GET /webhook` — returns `hub.challenge` for Meta's verification handshake.
   - `POST /webhook` — receives inbound message payloads.
3. **Handle inbound messages.** Parse `entry[].changes[].value.messages[]`,
   extract `from` (the user's WhatsApp ID, e.g. `91XXXXXXXXXX`) and the text
   body. **Use `from` as the LangGraph `thread_id`** — this gives each user
   their own persistent conversation state automatically (the same state
   mechanism we already use in the CLI).
4. **Generate the reply.** Call `chat(text, thread_id=from)`. Because
   `MemorySaver` is per-thread, the user's pricing conversation on Monday
   continues naturally on Tuesday.
5. **Send the response.** `POST` to
   `https://graph.facebook.com/v20.0/<PHONE_NUMBER_ID>/messages` with
   `{ "messaging_product": "whatsapp", "to": from, "text": { "body": reply } }`
   using the access token.
6. **Acknowledge fast.** Return `200 OK` immediately (within 20 s) to Meta; move
   actual LLM work to a background task / queue (Celery, Cloud Tasks, SQS) so
   webhook retries don't cause duplicate lead captures.
7. **Harden.** Verify Meta's `X-Hub-Signature-256` header against the app
   secret, persist `MemorySaver` → Redis/Postgres for horizontal scaling, and
   route `mock_lead_capture` to the real CRM (HubSpot, Salesforce, etc.).

Because the LangGraph app is a pure function of `(thread_id, message)`,
migrating from CLI to WhatsApp is a thin transport layer — no changes to the
core agent are required.

---

## 7. Evaluation Checklist

- [x] **Agent reasoning & intent detection** — dedicated classifier node with
  structured output; intent carried in state and surfaced in the system prompt.
- [x] **Correct use of RAG** — BM25 retrieval, context-grounded answers, no
  hard-coded pricing strings in the LLM prompt.
- [x] **Clean state management** — `TypedDict` + `add_messages` reducer +
  `MemorySaver` checkpointer keyed by `thread_id`.
- [x] **Proper tool-calling logic** — tool binding + explicit "don't fire until
  all three fields" guardrail in the system prompt.
- [x] **Code clarity & structure** — one module per concern (`rag.py`,
  `tools.py`, `agent.py`, `main.py`); fully typed; no dead code.
- [x] **Real-world deployability** — stateless LangGraph app keyed by
  `thread_id` ⇒ trivial to front with a WhatsApp / Telegram / Slack webhook.

---

## 8. License

MIT — built as a take-home assignment for ServiceHive (Inflx).
