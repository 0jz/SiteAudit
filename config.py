import os

# ── Anthropic ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ── Target site ───────────────────────────────────────────────────────────
TARGET_URL = os.getenv("TARGET_URL", "https://example.com")
SITE_NAME  = os.getenv("SITE_NAME", "My Website")

# ── AWS CloudWatch ─────────────────────────────────────────────────────────
# Set these to pull real metrics; if absent, mock data is used instead
AWS_REGION        = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY    = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_KEY    = os.getenv("AWS_SECRET_ACCESS_KEY", "")
CLOUDWATCH_NS     = os.getenv("CLOUDWATCH_NAMESPACE", "SiteAudit")   # custom metric namespace

# ── Paths ──────────────────────────────────────────────────────────────────
SCREENSHOTS_DIR = "screenshots"
REPORTS_DIR     = "reports"
HISTORY_DIR     = "history"   # stores previous audit JSON for diffing

# ── Screenshot sections ────────────────────────────────────────────────────
# Each entry: (name, scroll_position_px)
# Playwright scrolls to each position and snaps a viewport screenshot
SECTIONS = [
    ("above_the_fold", 0),
    ("features",       700),
    ("social_proof",   1400),
    ("pricing",        2100),
    ("footer_cta",     2800),
]

# ── Slack ──────────────────────────────────────────────────────────────────
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# ── Scoring thresholds ─────────────────────────────────────────────────────
SCORE_CRITICAL = 4   # below this → Critical in report
SCORE_WARNING  = 6   # below this → Warning
