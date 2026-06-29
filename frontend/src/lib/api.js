/**
 * AeroLogix B2B Internal API Client
 * Uses Vite reverse-proxy to bypass Codespace CORS restrictions.
 */

export const getLiveTelemetry = async () => {
  try {
    // Notice we just use '/api' now. The proxy handles the routing securely.
    const response = await fetch('/api/telemetry/live', {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      }
    });
    
    if (!response.ok) {
      throw new Error(`Engine uplink failed: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error("Telemetry Fetch Error:", error);
    throw error;
  }
};
