# Academic Writing Coach

A Duolingo-style practice app for writing research papers and technical reports, graded by a
local LLM in LM Studio. It is pitched at writers with an IELTS writing band around 6.5
(B2–C1) in computer science and machine learning: general English is assumed, so the
lessons and feedback focus on genre conventions, claim strength, precision, and concision.

- **Learn**: 14 ordered units in three parts.
  1. Foundations: precise sentences, claim strength and hedging, paragraph structure, flow.
  2. The paper: abstract, introduction and contributions, related work, methods, results,
     figures and captions, discussion and limitations.
  3. The technical report: executive summary, design decisions and trade-offs, revision.

  Each unit has a rule, a weaker and a stronger example, a checklist, and a practice exercise.
  Score 70/100 to unlock the next unit.
- **Today**: one writing challenge a day on a CS, ML, or engineering topic, focused on your
  current unit. Genres rotate through paper sections, reviewer responses, executive summaries,
  design decisions, evaluation reports, incident postmortems, and figure descriptions. The
  question stays on screen while you work through **Plan → Write → Check → Feedback**.

Feedback gives rubric scores, a check of each requirement, corrections that quote your
text, a mini exercise, and a model rewrite. Streaks, XP, and difficulty are tracked locally.

## Setup

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd ~/Documents/Projects/academic-writing-coach
uv sync
```

In LM Studio, load an instruction model and start the server (Developer tab, port 1234).
Then run:

```bash
COACH_LLM_API_KEY=your-key uv run python -m academic_writing_coach
```

Open http://127.0.0.1:8765. Leave out `COACH_LLM_API_KEY` if your server does not require one.

The app uses LM Studio's default model unless you set `COACH_LLM_MODEL`, so switching models
in LM Studio needs no code change. Without a running model the app still opens, with an
offline challenge and built-in exercises, but it cannot grade.

## How the app talks to the model

- Replies use structured JSON output (a JSON schema), which keeps small models on format.
  If a server rejects that, the app falls back to plain prompts automatically.
- An unusable reply is retried once at a lower temperature. An unreachable server is not retried.
- A 3-second health probe, cached for 30 seconds, runs before each model call, so a stopped
  or hung server falls back in seconds instead of waiting for the full timeout.
- Today's challenge is generated in the background at startup, so the first page load does not wait.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `COACH_LLM_URL` | `http://localhost:1234/v1` | OpenAI-compatible base URL |
| `COACH_LLM_MODEL` | server default | Model identifier sent to the server |
| `COACH_LLM_API_KEY` | none | Bearer token, if the server requires one |
| `COACH_LLM_TIMEOUT` | `240` | Seconds to wait for a model reply |
| `COACH_PORT` | `8765` | Port for the web app |
| `COACH_DB` | `data/coach.sqlite3` | SQLite database path |

## Tests

```bash
uv run pytest
```

## Project layout

- `academic_writing_coach/lessons.py`: the Learn units
- `academic_writing_coach/curriculum.py`: scenarios, topics, prompts, and JSON schemas
- `academic_writing_coach/llm.py`: client for the local model
- `academic_writing_coach/service.py`: challenge, grading, Learn, and progress logic
- `academic_writing_coach/store.py`: SQLite storage
- `academic_writing_coach/server.py`: HTTP server and JSON API
- `academic_writing_coach/static/`: single-page front end (no build step)

All data stays on this machine. Nothing is sent to a cloud service.
