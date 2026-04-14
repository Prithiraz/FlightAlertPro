/**
 * FlightAlertPro — Background Service Worker (Manifest V3)
 *
 * Responsibilities:
 *  - Listen for messages from content.js
 *  - Retrieve the stored auth token from chrome.storage.local
 *  - POST the route data to the FlightAlertPro backend /api/alerts/create
 *  - Return the result back to the content script so it can update the widget UI
 */

const API_BASE_URL = "https://flightalertpro.com";

/**
 * Send a POST request to the backend to create a price alert.
 *
 * @param {object} routeData  Parsed route fields from the content script.
 * @param {string} token      JWT / session token retrieved from storage.
 * @returns {Promise<object>} Response payload from the backend.
 */
async function createAlert(routeData, token) {
  const response = await fetch(`${API_BASE_URL}/api/alerts/create`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(routeData),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Backend returned ${response.status}: ${errorText}`);
  }

  return response.json();
}

/**
 * Main message listener.
 *
 * Expected message shape from content.js:
 * {
 *   action: "CREATE_ALERT",
 *   payload: {
 *     user_email: string,
 *     from_iata: string,
 *     to_iata: string,
 *     departure_date: string | null,
 *     max_price: number,
 *     notification_channels: string[]
 *   }
 * }
 *
 * Sends back:
 * { success: true,  alert_id: string }  — on success
 * { success: false, error: string }     — on failure
 */
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action !== "CREATE_ALERT") return false;

  // Retrieve the stored auth data, then create the alert.
  chrome.storage.local.get(["fap_token", "fap_email"], async (stored) => {
    const token = stored.fap_token;
    const email = stored.fap_email;

    if (!token || !email) {
      sendResponse({
        success: false,
        error: "Not authenticated. Please log in via the FlightAlertPro extension popup.",
      });
      return;
    }

    try {
      const routeData = {
        user_email: email,
        from_iata: message.payload.from_iata,
        to_iata: message.payload.to_iata,
        departure_date: message.payload.departure_date || null,
        max_price: message.payload.max_price || 9999,
        notification_channels: message.payload.notification_channels || ["email"],
      };

      const result = await createAlert(routeData, token);
      sendResponse({ success: true, alert_id: result.alert_id });
    } catch (err) {
      console.error("[FlightAlertPro] createAlert failed:", err);
      sendResponse({ success: false, error: err.message });
    }
  });

  // Return true to indicate that the response will be sent asynchronously.
  return true;
});
