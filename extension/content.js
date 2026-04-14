/**
 * FlightAlertPro — Content Script
 *
 * Responsibilities:
 *  - Use a MutationObserver to detect when Google Flights results have loaded.
 *  - Inject a "Track this route" floating widget into the page.
 *  - Parse Origin, Destination, and Date from the current Google Flights URL.
 *  - On "Track Now" click, send the parsed data to background.js and update the UI.
 */

(function () {
  "use strict";

  // Default max price sent to the backend when the user clicks "Track Now".
  // This is an intentionally permissive sentinel value — users can adjust their
  // threshold inside the FlightAlertPro dashboard after the alert is created.
  const DEFAULT_MAX_PRICE = 9999;

  // Safety timeout (ms): inject the widget even if we never detect a flight
  // card, so users on new or A/B-tested Google Flights layouts still see it.
  const WIDGET_INJECTION_TIMEOUT_MS = 8000;

  // Prevent the widget from being injected more than once.
  if (document.getElementById("fap-widget")) return;

  /* ─────────────────────────────────────────────
   * 1.  URL PARSING
   * ───────────────────────────────────────────── */

  /**
   * Google Flights URL example (one-way):
   *   https://www.google.com/travel/flights/search?tfs=...
   *
   * The route information is embedded in the `tfs` query parameter as a
   * serialised protobuf, which is not easily decoded client-side.  However,
   * Google also exposes readable parameters for simple searches:
   *   ?q=Flights+from+JFK+to+LAX
   * and the page title / h1 typically contains the route text.
   *
   * We fall back to scraping the page's visible text when the URL alone is
   * insufficient.
   */
  function parseRouteFromUrl() {
    const url = new URL(window.location.href);
    const params = url.searchParams;

    // Extract departure date from page regardless of which route-parsing attempt succeeds.
    // Google renders dates in aria-labels like "Departure, Sunday, December 1, 2024".
    const dateEl = document.querySelector('[aria-label*="Departure"]');
    const date = dateEl ? dateEl.getAttribute("aria-label") : null;

    // Attempt 1 — explicit "q" param (rarely present but easy to parse)
    const qParam = params.get("q") || "";
    const qMatch = qParam.match(/from\s+([A-Z]{3})\s+to\s+([A-Z]{3})/i);
    if (qMatch) {
      return { origin: qMatch[1].toUpperCase(), destination: qMatch[2].toUpperCase(), date };
    }

    // Attempt 2 — scrape IATA codes from the page heading / breadcrumbs.
    // Google Flights renders text like "New York · London" or "JFK → LHR".
    const headingEl =
      document.querySelector('h1[class*="gws-flights"]') ||
      document.querySelector('[data-test-id="title"]') ||
      document.querySelector("h1");

    if (headingEl) {
      const text = headingEl.textContent || "";
      // Match two sequences of 3 uppercase letters separated by a non-letter
      const iataMatch = text.match(/\b([A-Z]{3})\b[^A-Z]+\b([A-Z]{3})\b/);
      if (iataMatch) {
        return { origin: iataMatch[1], destination: iataMatch[2], date };
      }
    }

    // Attempt 3 — look for airport codes in the search-box inputs.
    const inputs = document.querySelectorAll('input[aria-label]');
    let origin = null;
    let destination = null;
    inputs.forEach((input) => {
      const label = (input.getAttribute("aria-label") || "").toLowerCase();
      const val = (input.value || "").trim();
      if (!origin && (label.includes("where from") || label.includes("origin"))) {
        origin = val;
      }
      if (!destination && (label.includes("where to") || label.includes("destination"))) {
        destination = val;
      }
    });

    return {
      origin: origin || "???",
      destination: destination || "???",
      date,
    };
  }

  /* ─────────────────────────────────────────────
   * 2.  WIDGET CREATION
   * ───────────────────────────────────────────── */

  /**
   * Safely build a DOM element with an id and optional text content.
   * Never uses innerHTML to avoid XSS risks with user-supplied route data.
   */
  function el(tag, id, text) {
    const node = document.createElement(tag);
    if (id) node.id = id;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function createWidget(route) {
    const widget = el("div", "fap-widget");
    widget.setAttribute("role", "complementary");
    widget.setAttribute("aria-label", "FlightAlertPro price tracker");

    const inner = el("div", "fap-widget-inner");

    // Header row
    const header = el("div", "fap-widget-header");
    header.appendChild(el("span", "fap-widget-logo", "✈"));
    header.appendChild(el("span", "fap-widget-brand", "FlightAlertPro"));
    inner.appendChild(header);

    // Body text — route label is set via textContent, never innerHTML
    const hasRoute = route.origin !== "???" && route.destination !== "???";
    const bodyText = el("p", "fap-widget-text", "Track ");
    const strong = document.createElement("strong");
    strong.textContent = hasRoute
      ? `${route.origin} \u2192 ${route.destination}`
      : "this route";
    bodyText.appendChild(strong);
    const suffix = document.createTextNode(" for price drops.");
    bodyText.appendChild(suffix);
    inner.appendChild(bodyText);

    // Track Now button
    const btn = el("button", "fap-track-btn", "Track Now");
    btn.type = "button";
    inner.appendChild(btn);

    // Status paragraph
    const statusP = el("p", "fap-widget-status", "");
    statusP.setAttribute("aria-live", "polite");
    inner.appendChild(statusP);

    widget.appendChild(inner);
    return widget;
  }

  /* ─────────────────────────────────────────────
   * 3.  WIDGET INJECTION & BEHAVIOUR
   * ───────────────────────────────────────────── */

  function injectWidget() {
    // Guard: skip if widget already present.
    if (document.getElementById("fap-widget")) return;

    const route = parseRouteFromUrl();
    const widget = createWidget(route);
    document.body.appendChild(widget);

    const trackBtn = widget.querySelector("#fap-track-btn");
    const statusEl = widget.querySelector("#fap-widget-status");

    trackBtn.addEventListener("click", async () => {
      trackBtn.disabled = true;
      trackBtn.textContent = "Sending…";
      statusEl.textContent = "";

      chrome.runtime.sendMessage(
        {
          action: "CREATE_ALERT",
          payload: {
            from_iata: route.origin,
            to_iata: route.destination,
            departure_date: route.date,
            max_price: DEFAULT_MAX_PRICE,
            notification_channels: ["email"],
          },
        },
        (response) => {
          if (chrome.runtime.lastError) {
            trackBtn.disabled = false;
            trackBtn.textContent = "Track Now";
            statusEl.textContent =
              "Extension error: " + chrome.runtime.lastError.message;
            statusEl.classList.add("fap-error");
            return;
          }

          if (response && response.success) {
            trackBtn.textContent = "Tracking Active ✓";
            trackBtn.classList.add("fap-active");
            statusEl.textContent = "Alert saved! We'll email you if the price drops.";
            statusEl.classList.remove("fap-error");
          } else {
            trackBtn.disabled = false;
            trackBtn.textContent = "Track Now";
            statusEl.textContent =
              response && response.error ? response.error : "Failed to create alert.";
            statusEl.classList.add("fap-error");
          }
        }
      );
    });
  }

  /* ─────────────────────────────────────────────
   * 4.  MUTATION OBSERVER
   *     Wait for Google Flights results to render.
   * ───────────────────────────────────────────── */

  function isFlightsResultsVisible() {
    // Google Flights uses various container selectors across its A/B tests.
    // We look for any of the known result-list containers.
    return !!(
      document.querySelector('[data-test-id="main-flight-results-container"]') ||
      document.querySelector('ul[class*="gws-flights-results"]') ||
      document.querySelector('[jsname="IWWDBc"]') ||
      document.querySelector('[jsname="t2C7Cc"]') ||
      // Fallback: any list item that looks like a flight card
      document.querySelector('li[class*="pIav2d"]')
    );
  }

  function startObserver() {
    // If results are already painted (e.g. soft navigation / cached page), inject immediately.
    if (isFlightsResultsVisible()) {
      injectWidget();
      return;
    }

    const observer = new MutationObserver((_mutations, obs) => {
      if (isFlightsResultsVisible()) {
        obs.disconnect();
        injectWidget();
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Safety timeout: inject the widget even if we never detect a flight card,
    // so users on new Google Flights layouts still see the button.
    setTimeout(() => {
      observer.disconnect();
      injectWidget();
    }, WIDGET_INJECTION_TIMEOUT_MS);
  }

  // Kick everything off once the DOM is ready.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserver);
  } else {
    startObserver();
  }
})();
