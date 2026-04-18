"""
simulate_canvas.py
Simulates the SuperPlane canvas flow entirely inside a Daytona sandbox:

  CloudWatch alarm  ──┐
  Daily schedule    ────┼──► sandbox.process.code_run (pipeline) ──► Gemini summary
  Render deploy     ──┘

Run:
    python simulate_canvas.py --trigger alarm
    python simulate_canvas.py --trigger schedule
    python simulate_canvas.py --trigger deploy
    python simulate_canvas.py --trigger all      ← runs all three sequentially
"""

import os
import sys
import argparse
from daytona import Daytona
from google import genai


# ── Config ─────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "key")
TARGET_URL        = os.getenv("TARGET_URL", "https://quiet-cascaron-08f652.netlify.app/")
SITE_NAME         = os.getenv("SITE_NAME", "FlowSync Demo")
# ── The pipeline code that runs INSIDE the sandbox ─────────────────────────
# This is the equivalent of your Lambda function body.
# The sandbox has no access to your local files — everything must be
# self-contained or installed fresh.

PIPELINE_CODE = f"""
import json, random, datetime

# ── Mock CloudWatch metrics (replace with real boto3 calls if AWS creds present)
def pull_metrics():
    return {{
        "site": "{SITE_NAME}",
        "url":  "{TARGET_URL}",
        "run_at": datetime.datetime.utcnow().isoformat(),
        "ttfb_p50_ms":        random.randint(280, 400),
        "ttfb_p95_ms":        random.randint(2200, 3400),
        "avg_page_load_ms":   random.randint(2800, 4200),
        "error_rate_4xx_pct": round(random.uniform(1.0, 3.5), 1),
        "error_rate_5xx_pct": round(random.uniform(0.1, 0.9), 1),
        "sections": {{
            "above_the_fold": {{
                "scroll_depth_pct":   100,
                "bounce_rate_pct":    round(random.uniform(55, 70), 1),
                "time_on_section_s":  round(random.uniform(3.0, 5.5), 1),
                "cta_click_rate_pct": round(random.uniform(2.0, 4.5), 1),
            }},
            "features": {{
                "scroll_depth_pct":   round(random.uniform(45, 60), 1),
                "bounce_rate_pct":    round(random.uniform(30, 45), 1),
                "time_on_section_s":  round(random.uniform(6.0, 10.0), 1),
                "cta_click_rate_pct": round(random.uniform(0.8, 2.0), 1),
            }},
            "social_proof": {{
                "scroll_depth_pct":   round(random.uniform(25, 40), 1),
                "bounce_rate_pct":    round(random.uniform(25, 35), 1),
                "time_on_section_s":  round(random.uniform(4.0, 7.0), 1),
                "cta_click_rate_pct": round(random.uniform(0.5, 1.5), 1),
            }},
            "pricing": {{
                "scroll_depth_pct":   round(random.uniform(12, 22), 1),
                "bounce_rate_pct":    round(random.uniform(48, 62), 1),
                "time_on_section_s":  round(random.uniform(10.0, 15.0), 1),
                "cta_click_rate_pct": round(random.uniform(1.5, 3.5), 1),
            }},
            "footer_cta": {{
                "scroll_depth_pct":   round(random.uniform(5, 12), 1),
                "bounce_rate_pct":    round(random.uniform(75, 90), 1),
                "time_on_section_s":  round(random.uniform(1.5, 3.0), 1),
                "cta_click_rate_pct": round(random.uniform(0.1, 0.5), 1),
            }},
        }}
    }}

metrics = pull_metrics()
print(json.dumps(metrics, indent=2))
"""


# ── Gemini prompt ───────────────────────────────────────────────────────────

def build_gemini_prompt(trigger_name: str, pipeline_output: str) -> str:
    return f"""You are a senior conversion rate optimization and web performance expert.

TRIGGER: {trigger_name}
SITE: {SITE_NAME}
URL: {TARGET_URL}

The following metrics were just collected from the website:

{pipeline_output}

Analyze these metrics and provide:

1. OVERALL HEALTH: One sentence verdict on the site's current state.

2. SECTION SCORES: Score each section 1-10 and explain why in one line.

3. BIGGEST PROBLEM: The single most damaging issue right now with evidence from the numbers.

4. TOP 3 FIXES: Specific, actionable changes ranked by impact. Not generic advice.

5. PERFORMANCE VERDICT: Based on TTFB and load time, what is the user experiencing and what is the one AWS-level fix.

6. QUICK WIN: One thing that could be done today in under 1 hour that would improve metrics.

Be direct and specific. Reference the actual numbers.
"""


# ── Trigger handlers ────────────────────────────────────────────────────────

def on_cloudwatch_alarm(sandbox, gemini_client):
    print("\n" + "="*60)
    print("TRIGGER: CloudWatch Alarm fired (bounce rate spike)")
    print("="*60)
    _run_pipeline(sandbox, gemini_client, trigger_name="CloudWatch Alarm — Bounce Rate Spike")


def on_schedule(sandbox, gemini_client):
    print("\n" + "="*60)
    print("TRIGGER: Daily scheduled audit")
    print("="*60)
    _run_pipeline(sandbox, gemini_client, trigger_name="Daily Scheduled Audit")


def on_render_deploy(sandbox, gemini_client):
    print("\n" + "="*60)
    print("TRIGGER: Render deploy completed")
    print("="*60)
    _run_pipeline(sandbox, gemini_client, trigger_name="Post-Deploy Audit")


def _run_pipeline(sandbox, gemini_client, trigger_name: str):
    # ── Step 1: Run pipeline inside sandbox ───────────────────────────────
    print("\n[ sandbox ] Running metrics pipeline...")
    result = sandbox.process.code_run(PIPELINE_CODE)

    if result.exit_code != 0:
        print(f"[ sandbox ] ERROR (exit {result.exit_code}):")
        print(result.result)
        return

    pipeline_output = result.result
    print("[ sandbox ] Metrics collected:")
    print(pipeline_output[:400] + "..." if len(pipeline_output) > 400 else pipeline_output)

    # ── Step 2: Send to Gemini ────────────────────────────────────────────
    if not GEMINI_API_KEY:
        print("\n[ gemini  ] Skipping — no GEMINI_API_KEY set")
        print("            Set it with: set GEMINI_API_KEY=your_key")
        return

    print("\n[ gemini  ] Analyzing metrics...")
    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=build_gemini_prompt(trigger_name, pipeline_output),
    )

    print("\n[ gemini  ] Analysis complete:")
    print("-" * 60)
    print(response.text)
    print("-" * 60)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Simulate SuperPlane canvas with Daytona")
    parser.add_argument(
        "--trigger",
        choices=["alarm", "schedule", "deploy", "all"],
        default="schedule",
        help="Which trigger to simulate (default: schedule)"
    )
    args = parser.parse_args()

    # Init Daytona — picks up DAYTONA_API_KEY from env automatically
    print("[ daytona ] Initializing...")
    daytona = Daytona()

    # Init Gemini client
    gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

    # Create sandbox
    print("[ daytona ] Creating sandbox...")
    sandbox = daytona.create()
    print(f"[ daytona ] Sandbox ready: {sandbox.id}")

    try:
        if args.trigger == "alarm" or args.trigger == "all":
            on_cloudwatch_alarm(sandbox, gemini_client)

        if args.trigger == "schedule" or args.trigger == "all":
            on_schedule(sandbox, gemini_client)

        if args.trigger == "deploy" or args.trigger == "all":
            on_render_deploy(sandbox, gemini_client)

    finally:
        # Always clean up the sandbox
        print("\n[ daytona ] Cleaning up sandbox...")
        daytona.delete(sandbox)
        print("[ daytona ] Done.")


if __name__ == "__main__":
    main()
