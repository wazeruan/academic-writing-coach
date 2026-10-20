# Academic Writing Coach

A Duolingo-style daily practice app for academic English. Each day you get a new
writing challenge (abstract, introduction, methods, reviewer response, and so on),
work through five steps, and submit your text. A local LLM running in LM Studio
generates the challenge and grades your writing against a rubric.

## Daily flow

1. **Understand**: read the situation, task, background facts and key vocabulary.
2. **Plan**: outline the structure, using the hints.
3. **Write**: draft within the target word range. Your text autosaves.
4. **Check**: tick the requirements you met, then submit.
5. **Feedback**: rubric scores, corrections, a model rewrite, and a mini exercise.

Streaks, XP, and difficulty (beginner, intermediate, advanced) are tracked locally.

## Setup

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/). LM Studio is optional;
without it the app serves an offline template challenge and cannot grade.

```bash
cd ~/Documents/academic-writing-coach
uv sync
```

Start the local model:

1. Open LM Studio, download a capable instruction model (7B–14B works; larger is better for grading).
2. Load it, then open the Developer tab and start the server (port 1234).
3. Copy the model identifier shown in LM Studio.

Run the app with that identifier:

```bash
COACH_LLM_MODEL="your-model-identifier" uv run python -m academic_writing_coach
```

Open http://127.0.0.1:8765 in your browser.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `COACH_LLM_URL` | `http://localhost:1234/v1` | OpenAI-compatible base URL |
| `COACH_LLM_MODEL` | `local-model` | Model identifier sent to the server |
| `COACH_LLM_TIMEOUT` | `240` | Seconds to wait for a model reply |
| `COACH_PORT` | `8765` | Port for the web app |
| `COACH_DB` | `data/coach.sqlite3` | SQLite database path |

## Tests

```bash
uv run pytest
```

## Project layout

- `academic_writing_coach/curriculum.py`: scenarios, topics, and prompts
- `academic_writing_coach/llm.py`: client for the local model
- `academic_writing_coach/service.py`: challenge, grading, and progress logic
- `academic_writing_coach/store.py`: SQLite storage
- `academic_writing_coach/server.py`: HTTP server and JSON API
- `academic_writing_coach/static/`: single-page front end (no build step)

All data stays on this machine. Nothing is sent to a cloud service.
