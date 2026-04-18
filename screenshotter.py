"""
screenshotter.py — Take desktop + mobile screenshots per page section.
Returns a dict of { section_name: { desktop: path, mobile: path } }
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from config import TARGET_URL, SCREENSHOTS_DIR, SECTIONS


DESKTOP_VIEWPORT = {"width": 1280, "height": 800}
MOBILE_VIEWPORT  = {"width": 390,  "height": 844}   # iPhone 14 Pro


def _shot(page, section_name: str, scroll_y: int, suffix: str) -> str:
    """Scroll to position and capture viewport screenshot."""
    page.evaluate(f"window.scrollTo(0, {scroll_y})")
    page.wait_for_timeout(600)   # let lazy-loaded assets settle
    path = str(Path(SCREENSHOTS_DIR) / f"{section_name}_{suffix}.png")
    page.screenshot(path=path, clip={
        "x": 0, "y": 0,
        "width": page.viewport_size["width"],
        "height": page.viewport_size["height"],
    })
    return path


def take_screenshots(url: str = TARGET_URL) -> dict:
    """
    Navigate to url, scroll to each section, capture desktop + mobile.
    Returns:
      {
        "above_the_fold": {"desktop": "screenshots/above_the_fold_desktop.png",
                           "mobile":  "screenshots/above_the_fold_mobile.png"},
        ...
      }
    """
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ── Desktop pass ──────────────────────────────────────────────────
        print(f"[screenshots] Desktop pass → {url}")
        ctx  = browser.new_context(viewport=DESKTOP_VIEWPORT)
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(1000)

        for name, scroll_y in SECTIONS:
            path = _shot(page, name, scroll_y, "desktop")
            results.setdefault(name, {})["desktop"] = path
            print(f"  ✓ {name} desktop")

        ctx.close()

        # ── Mobile pass ───────────────────────────────────────────────────
        print(f"[screenshots] Mobile pass → {url}")
        ctx  = browser.new_context(
            viewport=MOBILE_VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(1000)

        for name, scroll_y in SECTIONS:
            # Mobile scroll positions are larger (viewport is smaller)
            mobile_scroll = int(scroll_y * 0.65)
            path = _shot(page, name, mobile_scroll, "mobile")
            results[name]["mobile"] = path
            print(f"  ✓ {name} mobile")

        ctx.close()
        browser.close()

    print(f"[screenshots] Done — {len(results)} sections captured")
    return results
