"""
main.py — SiteAudit pipeline entry point.
Run directly:   python main.py
Or via SuperPlane step:  python main.py --url https://yoursite.com
"""

import argparse
import os
import sys
from datetime import datetime

from config import TARGET_URL, SITE_NAME
import metrics as metrics_module
import screenshotter
import auditor
import reporter
import notifier


def run_audit(url: str | None = None, skip_screenshots: bool = False):
    run_ts = datetime.utcnow()
    print(f"\n{'='*60}")
    print(f"  SiteAudit — {SITE_NAME}")
    print(f"  URL    : {url or TARGET_URL}")
    print(f"  Run at : {run_ts.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    # Override URL if passed as argument
    if url:
        os.environ["TARGET_URL"] = url
        import importlib, config
        importlib.reload(config)

    # ── Step 1: Pull metrics ───────────────────────────────────────────────
    print("[ 1/5 ] Pulling metrics from CloudWatch...")
    metrics = metrics_module.pull_metrics(period_days=7)
    print(f"        Source: {metrics['source']}")

    # ── Step 2: Take screenshots ───────────────────────────────────────────
    if skip_screenshots:
        print("[ 2/5 ] Skipping screenshots (--skip-screenshots flag set)")
        # Use any existing screenshots
        screenshots = {
            name: {
                "desktop": f"screenshots/{name}_desktop.png",
                "mobile":  f"screenshots/{name}_mobile.png",
            }
            for name, _ in [
                ("above_the_fold", 0), ("features", 700),
                ("social_proof", 1400), ("pricing", 2100), ("footer_cta", 2800),
            ]
        }
    else:
        print("[ 2/5 ] Taking screenshots...")
        try:
            screenshots = screenshotter.take_screenshots()
        except Exception as e:
            print(f"        Screenshot failed: {e}")
            print("        Continuing without visual analysis...")
            screenshots = {}

    # ── Step 3: Visual + retention audit ──────────────────────────────────
    if screenshots and os.getenv("ANTHROPIC_API_KEY"):
        print("[ 3/5 ] Running visual + retention audit with Claude...")
        visual_audits = auditor.audit_visual(screenshots, metrics)
    else:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("[ 3/5 ] Skipping Claude audit (no ANTHROPIC_API_KEY set)")
        else:
            print("[ 3/5 ] Skipping visual audit (no screenshots)")
        visual_audits = [{
            "section": name,
            "score": 0,
            "problems": ["No API key or screenshots available"],
            "evidence": "Skipped",
            "fixes": ["Set ANTHROPIC_API_KEY to enable Claude analysis"],
            "impact": "Unknown",
        } for name, _ in [
            ("above_the_fold", 0), ("features", 700),
            ("social_proof", 1400), ("pricing", 2100), ("footer_cta", 2800),
        ]]

    # ── Step 4: Performance audit ──────────────────────────────────────────
    if os.getenv("ANTHROPIC_API_KEY"):
        print("[ 4/5 ] Running performance audit with Claude...")
        perf_audit = auditor.audit_performance(metrics)
    else:
        print("[ 4/5 ] Skipping performance audit (no ANTHROPIC_API_KEY)")
        perf_audit = {
            "performance_score": 0,
            "metrics": [],
            "biggest_win": "Set ANTHROPIC_API_KEY to enable",
            "summary": "API key not configured.",
        }

    # ── Step 5: Generate report ────────────────────────────────────────────
    print("[ 5/5 ] Generating report...")
    markdown, snapshot = reporter.generate_report(
        visual_audits, perf_audit, metrics, run_ts=run_ts
    )
    report_path = reporter.save_report(markdown, snapshot)

    # ── Extract top fixes for Slack ────────────────────────────────────────
    top_fixes = []
    for audit in sorted(visual_audits, key=lambda x: x.get("score", 10)):
        fixes = audit.get("fixes", [])
        if fixes:
            top_fixes.append(fixes[0])
        if len(top_fixes) >= 3:
            break
    if perf_audit.get("biggest_win"):
        top_fixes.append(perf_audit["biggest_win"])

    notifier.send_slack(snapshot, report_path, top_fixes)

    # ── Print summary ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  AUDIT COMPLETE")
    print(f"  Overall score : {snapshot['overall_score']}/10")
    print(f"  Visual        : {snapshot['visual_score']}/10")
    print(f"  Performance   : {snapshot['performance_score']}/10")
    print(f"  Report        : {report_path}")
    print(f"{'='*60}\n")

    return report_path, snapshot


def main():
    parser = argparse.ArgumentParser(description="SiteAudit — AI website performance analyzer")
    parser.add_argument("--url",               help="Target URL (overrides config)")
    parser.add_argument("--skip-screenshots",  action="store_true",
                        help="Skip Playwright screenshots (use existing)")
    args = parser.parse_args()

    report_path, snapshot = run_audit(
        url=args.url,
        skip_screenshots=args.skip_screenshots,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
