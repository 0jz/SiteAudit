"""
metrics.py — Pull behavioral + infrastructure metrics from CloudWatch.
Falls back to realistic mock data if AWS credentials are not configured.
"""

import datetime
import random
from config import (
    AWS_REGION, AWS_ACCESS_KEY, AWS_SECRET_KEY, CLOUDWATCH_NS
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _mock_metrics() -> dict:
    """
    Realistic mock data for demo / local dev when CloudWatch isn't wired up.
    Values intentionally have some problems so Claude has things to diagnose.
    """
    return {
        # Infrastructure (would come from AWS/ApplicationELB or AWS/Lambda)
        "ttfb_p50_ms":       320,
        "ttfb_p95_ms":       2800,   # ← bad, will trigger warning
        "ttfb_p99_ms":       4900,
        "error_rate_4xx_pct": 2.1,
        "error_rate_5xx_pct": 0.4,
        "avg_page_load_ms":  3400,   # ← slow

        # User behavior per section (custom metrics pushed by JS snippet)
        "sections": {
            "above_the_fold": {
                "scroll_depth_pct":  100,  # everyone sees it
                "time_on_section_s": 4.2,
                "bounce_rate_pct":   61,   # ← high — hook problem
                "cta_click_rate_pct": 3.1,
            },
            "features": {
                "scroll_depth_pct":  54,   # ← half bail before features
                "time_on_section_s": 8.7,
                "bounce_rate_pct":   38,
                "cta_click_rate_pct": 1.2,
            },
            "social_proof": {
                "scroll_depth_pct":  31,
                "time_on_section_s": 5.1,
                "bounce_rate_pct":   29,
                "cta_click_rate_pct": 0.8,
            },
            "pricing": {
                "scroll_depth_pct":  18,   # ← very few reach pricing
                "time_on_section_s": 12.3,
                "bounce_rate_pct":   55,   # ← pricing page kills conversions
                "cta_click_rate_pct": 2.4,
            },
            "footer_cta": {
                "scroll_depth_pct":  9,
                "time_on_section_s": 2.1,
                "bounce_rate_pct":   82,
                "cta_click_rate_pct": 0.3,
            },
        },

        "period_days": 7,
        "source": "mock",
    }


def _pull_cloudwatch(metric_name: str, namespace: str,
                     stat: str, period_days: int,
                     dimensions: list | None = None) -> float | None:
    """Pull a single CloudWatch metric average over period_days."""
    try:
        import boto3
        cw = boto3.client(
            "cloudwatch",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY or None,
            aws_secret_access_key=AWS_SECRET_KEY or None,
        )
        end   = datetime.datetime.utcnow()
        start = end - datetime.timedelta(days=period_days)
        resp  = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions or [],
            StartTime=start,
            EndTime=end,
            Period=period_days * 86400,
            Statistics=[stat],
        )
        points = resp.get("Datapoints", [])
        if not points:
            return None
        return points[0].get(stat)
    except Exception as e:
        print(f"[metrics] CloudWatch error for {metric_name}: {e}")
        return None


def pull_metrics(period_days: int = 7) -> dict:
    """
    Main entry point.
    Returns a unified metrics dict regardless of data source.
    """
    if not AWS_ACCESS_KEY:
        print("[metrics] No AWS credentials — using mock data")
        return _mock_metrics()

    print("[metrics] Pulling from CloudWatch...")
    sections = {}
    section_names = [
        "above_the_fold", "features", "social_proof", "pricing", "footer_cta"
    ]

    for section in section_names:
        dims = [{"Name": "Section", "Value": section}]
        sections[section] = {
            "scroll_depth_pct": _pull_cloudwatch(
                "ScrollDepth", CLOUDWATCH_NS, "Average", period_days, dims
            ) or 0,
            "time_on_section_s": _pull_cloudwatch(
                "TimeOnSection", CLOUDWATCH_NS, "Average", period_days, dims
            ) or 0,
            "bounce_rate_pct": _pull_cloudwatch(
                "BounceRate", CLOUDWATCH_NS, "Average", period_days, dims
            ) or 0,
            "cta_click_rate_pct": _pull_cloudwatch(
                "CTAClickRate", CLOUDWATCH_NS, "Average", period_days, dims
            ) or 0,
        }

    return {
        "ttfb_p50_ms": _pull_cloudwatch(
            "TTFB_P50", "AWS/ApplicationELB", "Average", period_days
        ) or 0,
        "ttfb_p95_ms": _pull_cloudwatch(
            "TTFB_P95", "AWS/ApplicationELB", "p95", period_days
        ) or 0,
        "ttfb_p99_ms": _pull_cloudwatch(
            "TTFB_P99", "AWS/ApplicationELB", "p99", period_days
        ) or 0,
        "error_rate_4xx_pct": _pull_cloudwatch(
            "HTTPCode_Target_4XX_Count", "AWS/ApplicationELB", "Sum", period_days
        ) or 0,
        "error_rate_5xx_pct": _pull_cloudwatch(
            "HTTPCode_Target_5XX_Count", "AWS/ApplicationELB", "Sum", period_days
        ) or 0,
        "avg_page_load_ms": _pull_cloudwatch(
            "PageLoadTime", CLOUDWATCH_NS, "Average", period_days
        ) or 0,
        "sections": sections,
        "period_days": period_days,
        "source": "cloudwatch",
    }
