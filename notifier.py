"""
notifier.py — Send a concise Slack digest when the audit finishes.
Skips silently if SLACK_WEBHOOK_URL is not configured.
"""

import json
import requests
from config import SLACK_WEBHOOK_URL, SITE_NAME, TARGET_URL


def _score_emoji(score: float) -> str:
    if score < 4:  return "🔴"
    if score < 6:  return "🟡"
    return "🟢"


def send_slack(snapshot: dict, report_path: str, top_fixes: list[str]):
    """Post audit summary to Slack."""
    if not SLACK_WEBHOOK_URL:
        print("[notifier] No SLACK_WEBHOOK_URL set — skipping Slack notification")
        return

    overall = snapshot.get("overall_score", 0)
    visual  = snapshot.get("visual_score", 0)
    perf    = snapshot.get("performance_score", 0)

    fixes_text = "\n".join(f"• {f}" for f in top_fixes[:3]) if top_fixes else "None found"

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"SiteAudit Complete — {SITE_NAME}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Overall*\n{_score_emoji(overall)} {overall}/10"},
                    {"type": "mrkdwn", "text": f"*Visual & Retention*\n{_score_emoji(visual)} {visual}/10"},
                    {"type": "mrkdwn", "text": f"*Performance*\n{_score_emoji(perf)} {perf}/10"},
                    {"type": "mrkdwn", "text": f"*URL*\n{TARGET_URL}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Top Priority Fixes:*\n{fixes_text}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Report: `{report_path}` · Run: {snapshot.get('run_at', '')[:16]}",
                    }
                ],
            },
        ]
    }

    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            print("[notifier] Slack notification sent")
        else:
            print(f"[notifier] Slack error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[notifier] Slack request failed: {e}")
