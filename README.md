# FinancialOS

> Personal financial operating system — a deterministic Rules Engine for the math, an LLM for the conversation.

[![Status](https://img.shields.io/badge/status-active%20development-blue)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688)]()
[![React](https://img.shields.io/badge/React-18-61dafb)]()
[![License](https://img.shields.io/badge/license-proprietary-red)](LICENSE)

🇹🇷 [Türkçe README](README.tr.md)

FinancialOS is an end-to-end personal finance application: it tracks debts and receivables, manages multiple cash positions and a credit card, enforces user-defined hard rules ("red lines"), and offers a natural-language coaching panel that explains *why* — not just *what*.

The architecture follows one principle: **the Rules Engine decides, the LLM explains.** Calculations stay deterministic and auditable; only the explanation layer is generative.

---

## Why this project exists

Most personal finance apps either show you raw numbers (Mint, YNAB) or hand decision-making to an LLM (which hallucinates math). FinancialOS sits between the two: deterministic Python computes every figure, and an LLM is given the result as ground truth so it can answer questions in plain Turkish without inventing numbers.

The cost: more code. The benefit: every coaching answer is traceable to a row in the database.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend  (React + Vite + Tailwind)                        │
│  Cockpit · Coach · Accounts · Transactions · IncomeDebt     │
│  · RedLines                                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST
┌──────────────────────────▼──────────────────────────────────┐
│  FastAPI  (96 routes, 23 routers)                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Layer 1 — is_question() pre-classifier (Python)      │  │
│  │  Layer 2 — Rules Engine (deterministic decisions)     │  │
│  │  Layer 3 — Action Executor (write side, idempotent)   │  │
│  │  Layer 4 — Fund Tracker (FIFO lot-based investments)  │  │
│  │  Layer 5 — Simulation Engine (what-if projections)    │  │
│  │  Layer 6 — Coach (LLM, read-only, explains decisions) │  │
│  │  Layer 7 — FallbackProvider (multi-LLM orchestration) │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                  ┌────────┴────────┐
                  │  SQLite (SQLAlchemy)  │
                  └─────────────────┘
```

### LLM provider chain

A custom `FallbackProvider` orchestrates four free-tier providers. If one returns an error, an empty response, or hits a rate limit, the next provider is tried automatically:

```
Groq (Llama 3.3 70B) → Cerebras (Qwen-3 235B) → Gemini Flash-Lite → OpenRouter
```

The chain is configured via environment variables; ordering can be changed without code edits. Reordering alone resolved three separate bugs during development (prompt leakage, behavior regression, tool-call inconsistency).

---

## Key engineering decisions

**Deterministic pre-classifier.** The `is_question()` function in `coach.py` decides whether a user message is a question or a statement *before* the LLM ever sees it. This moved a fragile LLM-driven classification into a unit-testable Python function — measurable improvement in answer consistency.

**Date arithmetic in Python, not in the prompt.** LLMs are unreliable at "X days from today" math. The `turkish_date()` and `_day_suffix()` helpers compute "tomorrow / in 3 days / overdue by 2 days" on the backend, then pass the rendered string to the LLM. The LLM never does subtraction.

**Category normalization with explicit override.** When a user says *"260 TL market alışverişi yaptım Enpara nakitten"*, the category dictionary would default to the credit card. A guard clause in `_normalize_transaction_payload` respects an explicit `account_id` if the user named one — user intent beats system defaults.

**Tool-aware history.** The `CoachMemory` table stores both `assistant` rows (with `tool_calls_json`) and `tool` rows (with results). When history is replayed to a new LLM call, a `_to_openai_messages()` adapter rebuilds the OpenAI tool-calling format. Different providers (Groq, Cerebras, Gemini, OpenRouter) get the message shape they expect.

**Card limit warnings, not card limit blocks.** When a transaction would exceed the credit limit, the engine returns a `warning` field instead of rejecting the action. The user is informed but retains agency. This was a deliberate departure from "Rules Engine = hard reject" — the rules engine can also surface metadata for an informed choice.

---

## Tech stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI · SQLAlchemy · Pydantic · SQLite |
| Frontend | React 18 · Vite · Tailwind CSS |
| LLM | Groq · Cerebras · Google Gemini · OpenRouter |
| Tooling | Git · PyCharm · asistan araci · MCP |

---

## Project layout

```
financialos/
├── app/                       # Backend
│   ├── routers/               # 23 routers, 96 routes
│   ├── coach.py               # LLM orchestration, FallbackProvider
│   ├── rules_engine.py        # Deterministic decisions
│   ├── action_executor.py     # Write-side, idempotent
│   ├── fund_tracker.py        # FIFO investment lots
│   ├── simulation_engine.py   # What-if projections
│   └── models.py              # SQLAlchemy models
├── frontend/                  # React app
│   └── src/
│       ├── panels/            # 13 panels
│       └── components/        # 8 components
├── docs/                      # Architecture, dev commands, roadmap
├── scripts/                   # Setup, seed data
└── PROJE.md                  # AI-assisted development notes
```

---

## Screenshots

![Cockpit panel](docs/screenshots/cockpit.png)
![Coach panel — natural-language explanation](docs/screenshots/coach.png)

---

## Running locally

> The repository ships without `.env` and without a populated database. You will need API keys for at least one LLM provider.

```bash
# 1. Backend
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in your API keys
python -m scripts.setup_data      # seed canonical demo data
uvicorn app.main:app --reload --port 8000

# 2. Frontend (in a second terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

### Environment variables

```env
GROQ_API_KEY=...
CEREBRAS_API_KEY=...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
LLM_PROVIDER=fallback
```

Any one of the four providers is enough to run the system; the FallbackProvider skips unconfigured providers automatically.

---

## Status

Active development. Wave-1 stabilization closed 22 bugs systematically; Wave-2 added another 21 fixes covering tool-aware history, deterministic category normalization, and a four-provider LLM chain. Each bug carries a per-bug log of root cause, fix, and verification notes.

This is a personal project — built solo, primarily as a way to think through production-grade architectural decisions, systematic debugging, and the boundary between deterministic systems and generative AI.

---

## License

**Tüm hakları saklıdır — Murat İçgil.** Bu depo görüntülenebilir ancak
kopyalanamaz, değiştirilemez, dağıtılamaz veya kullanılamaz; ayrıntı: [LICENSE](LICENSE).
*(6 May – 7 Ağu 2026 arasında MIT altındaydı; MIT o dönemde edinilen kopyalar için geri alınamaz.)*
