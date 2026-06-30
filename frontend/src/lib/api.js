export const getLiveTelemetry = async () => {
  try {
    const response = await fetch('/api/telemetry/live', {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    });
    if (!response.ok) throw new Error(`Engine uplink failed: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Telemetry Fetch Error:", error);
    throw error;
  }
};

// Legacy stubs to prevent React from crashing
export const searchAirports = async () => [];
export const getPreferences = async () => ({});
export const updatePreferences = async () => ({});
