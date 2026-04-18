"""
reporter.py — Generate markdown audit report + diff vs previous run.
Saves JSON snapshot to history/ for future diffs.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from config import SITE_NAME, TARGET_URL, REPORTS_DIR, HISTORY_DIR, SCORE_CRITICAL, SCORE_WARNING


SEVERITY_EMOJI = {"Critical": "🔴", "Warning": "🟡", "OK": "🟢"}
IMPACT_EMOJI   = {"High": "🔥", "Medium": "⚡", "Low": "💡"}
SCORE_LABELS   = {range(1, 5): "Critical", range(5, 7): "Warning", range(7, 11): "Good"}


def _score_label(score: int) -> str:
    for r, label in SCORE_LABELS.items():
        if score in r:
            return label
    return "Unknown"


def _score_emoji(score: int) -> str:
    if score < SCORE_CRITICAL:  return "🔴"
    if score < SCORE_WARNING:   return "🟡"
    return "🟢"


def _load_previous(site_key: str) -> dict | None:
    path = Path(HISTORY_DIR) / f"{site_key}_last.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def _save_snapshot(site_key: str, data: dict):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = Path(HISTORY_DIR) / f"{site_key}_last.json"
    path.write_text(json.dumps(data, indent=2))


def _score_diff(current: int, previous: int | None) -> str:
    if previous is None:
        return ""
    delta = current - previous
    if delta > 0:  return f" ▲{delta}"
    if delta < 0:  return f" ▼{abs(delta)}"
    return " →0"


def generate_report(
    visual_audits: list[dict],
    perf_audit: dict,
    metrics: dict,
    run_ts: datetime | None = None,
) -> tuple[str, dict]:
    """
    Build the full markdown report.
    Returns (markdown_string, snapshot_dict).
    """
    run_ts    = run_ts or datetime.utcnow()
    site_key  = TARGET_URL.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "_")
    previous  = _load_previous(site_key)

    # Overall visual score = average of section scores
    section_scores = [a.get("score", 0) for a in visual_audits if a.get("score")]
    avg_visual  = round(sum(section_scores) / len(section_scores), 1) if section_scores else 0
    perf_score  = perf_audit.get("performance_score", 0)
    overall     = round((avg_visual + perf_score) / 2, 1)

    prev_overall = previous.get("overall_score") if previous else None

    # ── Snapshot for history ───────────────────────────────────────────────
    snapshot = {
        "run_at": run_ts.isoformat(),
        "url": TARGET_URL,
        "overall_score": overall,
        "visual_score": avg_visual,
        "performance_score": perf_score,
        "sections": {a["section"]: a.get("score", 0) for a in visual_audits},
        "metrics_source": metrics.get("source"),
    }

    # ── Build markdown ─────────────────────────────────────────────────────
    lines = []
    a = lines.append

    a(f"# SiteAudit Report — {SITE_NAME}")
    a(f"**URL:** {TARGET_URL}  ")
    a(f"**Run:** {run_ts.strftime('%Y-%m-%d %H:%M UTC')}  ")
    a(f"**Data source:** {metrics.get('source', 'unknown')} · last {metrics.get('period_days', 7)} days")
    a("")

    # Overall scores
    a("## Overall Scores")
    a("")
    a(f"| Dimension | Score | Status | vs Last |")
    a(f"|-----------|-------|--------|---------|")

    prev_visual = previous.get("visual_score") if previous else None
    prev_perf   = previous.get("performance_score") if previous else None

    a(f"| Visual & Retention | {avg_visual}/10 | {_score_emoji(int(avg_visual))} {_score_label(int(avg_visual))} | {_score_diff(int(avg_visual), int(prev_visual) if prev_visual else None)} |")
    a(f"| Performance        | {perf_score}/10 | {_score_emoji(perf_score)} {_score_label(perf_score)} | {_score_diff(perf_score, prev_perf)} |")
    a(f"| **Overall**        | **{overall}/10** | {_score_emoji(int(overall))} {_score_label(int(overall))} | {_score_diff(int(overall), int(prev_overall) if prev_overall else None)} |")
    a("")

    if previous:
        a(f"> Previous audit: {previous.get('run_at', 'unknown')[:10]}")
        a("")

    # Top priorities
    a("## Top Priority Fixes")
    a("")
    critical_sections = sorted(
        [s for s in visual_audits if s.get("score", 10) < SCORE_WARNING],
        key=lambda x: x.get("score", 10)
    )
    for i, section in enumerate(critical_sections[:3], 1):
        fixes = section.get("fixes", [])
        fix_text = fixes[0] if fixes else "See section details below"
        a(f"{i}. **{section['section'].replace('_', ' ').title()}** ({_score_emoji(section['score'])} {section['score']}/10) — {fix_text}")
    if perf_audit.get("biggest_win"):
        a(f"{len(critical_sections[:3])+1}. **Performance** ({_score_emoji(perf_score)} {perf_score}/10) — {perf_audit['biggest_win']}")
    a("")

    # Section-by-section visual audit
    a("## Visual & Retention Audit — Section by Section")
    a("")
    for audit in visual_audits:
        section_name = audit.get("section", "unknown")
        score        = audit.get("score", 0)
        prev_section = (previous.get("sections") or {}).get(section_name) if previous else None

        a(f"### {section_name.replace('_', ' ').title()}")
        a(f"**Score:** {_score_emoji(score)} {score}/10 {_score_label(score)}{_score_diff(score, prev_section)}")
        a("")

        if audit.get("hook_verdict"):
            a(f"**Hook verdict:** {audit['hook_verdict']}")
            a("")

        if audit.get("evidence"):
            a(f"**Evidence:** {audit['evidence']}")
            a("")

        if audit.get("problems"):
            a("**Problems found:**")
            for p in audit["problems"]:
                a(f"- {p}")
            a("")

        if audit.get("fixes"):
            impact = audit.get("impact", "Medium")
            a(f"**Fixes** {IMPACT_EMOJI.get(impact, '')} ({impact} impact):")
            for f in audit["fixes"]:
                a(f"- {f}")
            a("")

        a("---")
        a("")

    # Performance audit
    a("## Infrastructure & Performance Audit")
    a("")
    a(f"**Score:** {_score_emoji(perf_score)} {perf_score}/10")
    a("")
    a(perf_audit.get("summary", ""))
    a("")

    if perf_audit.get("metrics"):
        a("| Metric | Value | Severity | UX Impact |")
        a("|--------|-------|----------|-----------|")
        for m in perf_audit["metrics"]:
            sev = m.get("severity", "OK")
            a(f"| {m.get('name')} | {m.get('value')} | {SEVERITY_EMOJI.get(sev, '')} {sev} | {m.get('ux_impact', '')} |")
        a("")

        a("**Performance fixes:**")
        for m in perf_audit.get("metrics", []):
            if m.get("fix") and m.get("severity") in ("Critical", "Warning"):
                a(f"- **{m['name']}:** {m['fix']}")
        a("")

    # Raw metrics reference
    a("## Raw Behavioral Metrics")
    a("")
    a("| Section | Scroll depth | Time on section | Bounce rate | CTA clicks |")
    a("|---------|-------------|-----------------|-------------|------------|")
    for section_name, s in metrics.get("sections", {}).items():
        a(f"| {section_name.replace('_', ' ').title()} "
          f"| {s.get('scroll_depth_pct', '-')}% "
          f"| {s.get('time_on_section_s', '-')}s "
          f"| {s.get('bounce_rate_pct', '-')}% "
          f"| {s.get('cta_click_rate_pct', '-')}% |")
    a("")

    a(f"*Report generated by SiteAudit — powered by Claude + SuperPlane*")

    return "\n".join(lines), snapshot


def save_report(markdown: str, snapshot: dict) -> str:
    """Save markdown report and update history snapshot. Returns report path."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    site_key = TARGET_URL.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "_")
    path     = Path(REPORTS_DIR) / f"audit_{site_key}_{ts}.md"
    path.write_text(markdown)
    _save_snapshot(site_key, snapshot)
    print(f"[reporter] Report saved → {path}")
    return str(path)
