/**
 * siteaudit-tracker.js
 * Drop this script on your website to push behavioral metrics
 * to AWS CloudWatch via your backend endpoint.
 *
 * Usage: <script src="/siteaudit-tracker.js"></script>
 *
 * Requires a thin backend endpoint POST /metrics that calls
 * CloudWatch PutMetricData (see tracker-backend.py).
 */

(function () {
  const ENDPOINT = "/metrics";   // your backend endpoint
  const SECTIONS = {
    above_the_fold: { top: 0,    bottom: 700  },
    features:       { top: 700,  bottom: 1400 },
    social_proof:   { top: 1400, bottom: 2100 },
    pricing:        { top: 2100, bottom: 2800 },
    footer_cta:     { top: 2800, bottom: 99999 },
  };

  const state = {};
  Object.keys(SECTIONS).forEach((name) => {
    state[name] = { entered: null, totalMs: 0, ctaClicks: 0, reached: false };
  });

  const bounceTimer = setTimeout(() => pushMetric("BounceRate", 1, "above_the_fold"), 10_000);

  // ── Track scroll depth ──────────────────────────────────────────────────
  function getCurrentSection() {
    const scrollY = window.scrollY + window.innerHeight / 2;
    for (const [name, { top, bottom }] of Object.entries(SECTIONS)) {
      if (scrollY >= top && scrollY < bottom) return name;
    }
    return null;
  }

  let lastSection = null;
  let scrollDepthReached = {};

  window.addEventListener("scroll", () => {
    clearTimeout(bounceTimer);

    const section = getCurrentSection();
    if (!section) return;

    // Mark section as reached
    if (!scrollDepthReached[section]) {
      scrollDepthReached[section] = true;
      pushMetric("ScrollDepth", 1, section);
    }

    // Track time per section
    if (section !== lastSection) {
      const now = Date.now();
      if (lastSection && state[lastSection].entered) {
        state[lastSection].totalMs += now - state[lastSection].entered;
        pushMetric("TimeOnSection", state[lastSection].totalMs / 1000, lastSection);
      }
      state[section].entered = now;
      lastSection = section;
    }
  }, { passive: true });

  // ── Track CTA clicks ────────────────────────────────────────────────────
  document.addEventListener("click", (e) => {
    const el = e.target.closest("a, button, [data-cta]");
    if (!el) return;
    const section = getCurrentSection();
    if (section) pushMetric("CTAClickRate", 1, section);
  });

  // ── Bounce detection ────────────────────────────────────────────────────
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      const section = getCurrentSection() || "above_the_fold";
      pushMetric("BounceRate", 1, section);
    }
  });

  // ── Send metric ─────────────────────────────────────────────────────────
  function pushMetric(name, value, section) {
    const payload = { metric: name, value, section, url: location.pathname };
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, JSON.stringify(payload));
    } else {
      fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(() => {});
    }
  }
})();
