import time
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The URL of your local FastAPI backend
API_URL = "http://127.0.0.1:8000/api/ingest_flight_data"

# Bounding box for London Airspace (approximate LHR approach)
LAMIN = 51.0
LOMIN = -1.0
LAMAX = 52.0
LOMAX = 0.5
OPENSKY_URL = f"https://opensky-network.org/api/states/all?lamin={LAMIN}&lomin={LOMIN}&lamax={LAMAX}&lomax={LOMAX}"

def fetch_live_radar():
    logger.info("📡 Sweeping airspace via OpenSky Network...")
    try:
        response = requests.get(OPENSKY_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        states = data.get("states")
        if not states:
            logger.warning("No aircraft found in airspace.")
            return

        aircraft_payload = []
        for state in states:
            # OpenSky returns an array of values. We only want planes in the air with valid telemetry.
            if state[8] or not state[5] or not state[9]: 
                continue # Skip if grounded, missing altitude, or missing speed

            # Extract and convert data
            hex_id = state[0]
            callsign = state[1].strip() if state[1] else "UNKNOWN"
            lon = state[5]
            lat = state[6]
            # Convert meters to feet for altitude
            altitude_ft = state[7] * 3.28084 if state[7] else 0 
            # Convert m/s to knots for speed
            ground_speed_kt = state[9] * 1.94384 
            heading = state[10] if state[10] else 0.0

            aircraft_payload.append({
                "hex_id": hex_id,
                "flight_number": callsign,
                "lon": lon,
                "lat": lat,
                "altitude": altitude_ft,
                "ground_speed": ground_speed_kt,
                "heading": heading,
                "taxi_time_min": 15, # Default LHR taxi
                "drive_time_min": 45  # Default VIP driver time
            })

        # Inject the live data into the AeroLogix engine
        logger.info(f"🎯 Captured {len(aircraft_payload)} active flights. Injecting into AeroLogix...")
        ingest_res = requests.post(API_URL, json={"aircraft": aircraft_payload})
        
        if ingest_res.status_code == 200:
            logger.info("✅ Engine processed telemetry successfully.")
        else:
            logger.error(f"❌ Injection failed: {ingest_res.status_code}")

    except Exception as e:
        logger.error(f"Radar sweep failed: {e}")

if __name__ == "__main__":
    logger.info("Starting AeroLogix Live Radar Worker...")
    while True:
        fetch_live_radar()
        # Sleep for 15 seconds so we don't spam the free API and get banned
        time.sleep(15)