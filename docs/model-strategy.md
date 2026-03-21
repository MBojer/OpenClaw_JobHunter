# Model Strategy

## The three-model architecture

JobHunter uses three models with strict separation of responsibilities.

---

## Model 1: Free model (OpenRouter)
**Used for:** Orchestration, user interaction, digest delivery
**Sees:** Structured metadata only — never raw content

### What it gets
```
"8 new job matches today:
 #1 score:92 — Senior Backend Dev @ Novo Nordisk | Odense | hybrid | python,fastapi
 #2 score:87 — Software Engineer @ Lunar | Remote | react,typescript
 ..."
```

### What it never gets
- `description_raw` from any job
- Raw CV or cover letter text
- Email content
- Raw LinkedIn profile data

### Why
- 256k context limit is precious — structured data uses ~200 tokens for a 10-job digest
- Free tier has rate limits — one orchestrator call per day is the target
- Privacy — the free model is a cloud service; raw personal data should not leave your machine unless necessary

### Call frequency target
- **1 call per day** for the automatic digest
- **Plus** calls for user-triggered interactions (apply, hide, status, etc.)
- **Never** 1 call per job

---

## Model 2: Qwen2.5:7b (Ollama — local)
**Used for:** All heavy lifting that touches raw content
**Sees:** Everything — this is your hardware

### Tasks
| Task | Script |
|---|---|
| Parse LinkedIn/CV paste into structured JSON | `scripts/onboarding/parse_profile.py` |
| Score each job against profile (0-100) | `scripts/local_llm/score_jobs.py` |
| Extract tags from job descriptions | (part of scoring) |

### Why Qwen2.5:7b
- Fits comfortably in 12GB VRAM (RTX 3060)
- Strong at structured JSON extraction at temperature 0.05-0.1
- Runs offline — no API costs, no rate limits, no privacy concern

### Prompt design
- All prompts request **JSON-only output** — no preamble, no explanation
- Temperature is set low (0.05-0.1) for consistent structured extraction
- Responses are parsed with fallback regex extraction in case of minor formatting issues

---

## Model 3: Together.ai — Llama 3.3 70B Instruct Turbo
**Used for:** CV and cover letter generation only
**Sees:** `profile.json` + single job description

### Why a separate paid model for this
- Quality matters for job applications — a 7B model produces noticeably weaker writing
- The $10 budget is used exclusively for this purpose
- Each call is explicitly user-approved

### Cost management
- Budget tracked in `spend_log` table
- Pre-flight check before every call (`scripts/db/check_budget.py`)
- Warning at $1.00 remaining, refusal at $0.10
- Estimated cost per application: ~$0.01-0.05 depending on job description length

### Budget math
At $0.90/1M tokens (Llama 3.3 70B on Together.ai):
- Typical prompt: ~3,000 tokens
- Typical completion: ~1,500 tokens
- Per application: ~$0.004
- $10 budget ≈ **~2,500 applications** (effectively unlimited for normal use)

---

## Context window budget for the free model

| Content | Tokens (approx) |
|---|---|
| System prompt (orchestrator.md) | ~800 |
| Active skill (e.g. cv-writer SKILL.md) | ~400 |
| 10-job digest | ~200 |
| User message | ~50 |
| Session history (last 50 msgs, compacted) | ~5,000 |
| **Total typical** | **~6,500** |
| **Free model limit** | **256,000** |
| **Safety margin** | **249,500 tokens** |

We are extremely conservative. The limit is not a concern under normal usage.
The compaction threshold is set at 180k as a precaution against long sessions.
