# AGENTS.md — SiteAudit

Python CLI pipeline: Playwright screenshots + CloudWatch (or mock) metrics → Claude section/performance audit → Markdown report + Slack digest.

## Commands
- Install: `pip install anthropic playwright requests boto3` then `playwright install chromium`. `pyproject.toml`/`uv.lock` declare only `anthropic` and `daytona`, so `uv sync` alone is not enough.
- Run: `python main.py` (env: `ANTHROPIC_API_KEY`, `TARGET_URL`) · `python main.py --skip-screenshots`
- Tracker backend: `python tracker_backend.py` (Flask, port 8080, needs `flask boto3`)
- Daytona demo: `python simulate_canvas.py --trigger alarm|schedule|deploy|all`
- Test / lint / build: none configured
- Default branch is `master`.

## Where logic lives
- `main.py`: `run_audit()` orchestrates 5 steps; section list is duplicated here (keep in sync with `config.SECTIONS`)
- `config.py`: all env vars, `CLAUDE_MODEL = "claude-sonnet-4-20250514"`, `SECTIONS`, thresholds, dirs (`screenshots/`, `reports/`, `history/`)
- `auditor.py`: prompts (`_build_visual_prompt`, `_build_perf_prompt`) + `_call_claude` (strips ``` fences, `json.loads`)
- `metrics.py`: `pull_metrics()` uses CloudWatch if `AWS_ACCESS_KEY_ID` is set, else `_mock_metrics()`
- `reporter.py`: report Markdown, `history/<site_key>_last.json` for diffs
- `notifier.py`: Slack Block Kit webhook

## Conventions
- Plain modules, no package, run from the repo root (relative output dirs).
- Config is read from `os.getenv` at import time; there is no dotenv.
- Claude must answer in raw JSON; the prompt JSON shape and `reporter.py` field names must match.
- Each Claude call has a try/except fallback dict, so the pipeline never hard-fails on the AI step.

## Do not commit / touch
- Generated output: `screenshots/`, `reports/`, `history/`. There's no `.gitignore` yet, so add one before committing.
- API keys. **`maine.py` contains a hard-coded Daytona API key**: rotate it and read `DAYTONA_API_KEY` from env instead.
- `.idea/` is IDE config that was committed by accident.

## Gotchas
- `--url` only changes the printed header. Modules bind `TARGET_URL` at import, so set the env var instead.
- Without AWS creds, all speed/behaviour numbers are mock values.
- Fixes are only suggested; nothing applies them to the site.
- `superplane.yaml`'s regression check always exits 0.
- `siteaudit-tracker.js` comment says `tracker-backend.py`; the real file is `tracker_backend.py`.

Humans: see README.md
