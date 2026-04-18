"""
auditor.py — Send screenshots + metrics to Claude and get a structured audit.
Two Claude calls run for the full picture:
  1. Visual + retention audit  (screenshots + behavioral metrics)
  2. Infrastructure audit       (CloudWatch perf metrics only)
Results are merged into a single audit dict.
"""

import base64
import json
import re
from pathlib import Path
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SITE_NAME


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── Image helpers ──────────────────────────────────────────────────────────

def _encode_image(path: str) -> dict:
    """Return an Anthropic image content block from a file path."""
    data = Path(path).read_bytes()
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.standard_b64encode(data).decode(),
        },
    }


# ── Prompt builders ────────────────────────────────────────────────────────

def _build_visual_prompt(metrics: dict, section_name: str) -> str:
    s = metrics["sections"].get(section_name, {})
    return f"""You are a senior conversion rate optimization expert with 10 years
of experience auditing landing pages and SaaS websites. You have deep expertise
in user psychology, visual hierarchy, and retention patterns.

SECTION: {section_name.replace("_", " ").title()}
SITE: {SITE_NAME}

BEHAVIORAL METRICS (last {metrics['period_days']} days):
- Scroll depth reaching this section: {s.get('scroll_depth_pct', 'n/a')}%
- Average time spent here: {s.get('time_on_section_s', 'n/a')}s
- Bounce rate at this section: {s.get('bounce_rate_pct', 'n/a')}%
- CTA click rate: {s.get('cta_click_rate_pct', 'n/a')}%

You are looking at two screenshots of this section: desktop (first) and mobile (second).

Audit this section like a consultant being paid $10,000 for this report.
Be specific, brutal, and actionable. Reference what you actually see visually.

Respond ONLY in this exact JSON format with no other text:
{{
  "section": "{section_name}",
  "score": <integer 1-10>,
  "problems": [
    "<specific visual or UX problem observed>",
    "<another problem if present>"
  ],
  "evidence": "<which metric + visual observation proves the main problem>",
  "fixes": [
    "<specific concrete fix — not generic advice>",
    "<another fix if needed>"
  ],
  "impact": "<Low|Medium|High>",
  "hook_verdict": "<only for above_the_fold: does it immediately communicate value? brief verdict>"
}}"""


def _build_perf_prompt(metrics: dict) -> str:
    return f"""You are a senior AWS solutions architect and web performance engineer.
You specialize in diagnosing how infrastructure performance directly causes
user drop-off and lost conversions.

SITE: {SITE_NAME}
PERIOD: last {metrics['period_days']} days
DATA SOURCE: {metrics['source']}

CLOUDWATCH METRICS:
- TTFB p50: {metrics['ttfb_p50_ms']}ms
- TTFB p95: {metrics['ttfb_p95_ms']}ms
- TTFB p99: {metrics['ttfb_p99_ms']}ms
- Avg page load: {metrics['avg_page_load_ms']}ms
- 4xx error rate: {metrics['error_rate_4xx_pct']}%
- 5xx error rate: {metrics['error_rate_5xx_pct']}%

Connect infrastructure numbers directly to user experience impact.
Not just "latency is high" but "p95 TTFB of Xms means roughly Y% of users
experience a slow load, causing ~Z% abandonment increase based on industry data."

Respond ONLY in this exact JSON format with no other text:
{{
  "performance_score": <integer 1-10>,
  "metrics": [
    {{
      "name": "<metric name>",
      "value": "<value with unit>",
      "ux_impact": "<what the user actually experiences>",
      "severity": "<Critical|Warning|OK>",
      "fix": "<specific AWS-level action>"
    }}
  ],
  "biggest_win": "<single highest-impact performance fix>",
  "summary": "<2 sentence plain-language summary of performance health>"
}}"""


# ── API calls ──────────────────────────────────────────────────────────────

def _call_claude(content: list) -> dict:
    """Call Claude and parse JSON from response."""
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.content[0].text.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def audit_visual(screenshots: dict, metrics: dict) -> list[dict]:
    """
    Run visual + retention audit for each section.
    Returns list of section audit dicts.
    """
    results = []
    for section_name, paths in screenshots.items():
        print(f"[auditor] Visual audit → {section_name}")
        content = [
            {"type": "text", "text": _build_visual_prompt(metrics, section_name)},
        ]
        # Attach desktop screenshot
        if paths.get("desktop") and Path(paths["desktop"]).exists():
            content.append(_encode_image(paths["desktop"]))
        # Attach mobile screenshot
        if paths.get("mobile") and Path(paths["mobile"]).exists():
            content.append(_encode_image(paths["mobile"]))

        try:
            result = _call_claude(content)
            result["section"] = section_name   # ensure key present
            results.append(result)
        except Exception as e:
            print(f"  [!] Failed for {section_name}: {e}")
            results.append({
                "section": section_name,
                "score": 0,
                "problems": [str(e)],
                "evidence": "Claude call failed",
                "fixes": [],
                "impact": "Unknown",
            })

    return results


def audit_performance(metrics: dict) -> dict:
    """Run infrastructure + performance audit."""
    print("[auditor] Performance audit...")
    content = [{"type": "text", "text": _build_perf_prompt(metrics)}]
    try:
        return _call_claude(content)
    except Exception as e:
        print(f"  [!] Performance audit failed: {e}")
        return {
            "performance_score": 0,
            "metrics": [],
            "biggest_win": "Audit failed",
            "summary": str(e),
        }
