import time, requests, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
API_URL = "http://127.0.0.1:8000/api/ingest_flight_data"

def fetch_real_radar():
    logger.info("📡 Sweeping London airspace for REAL aircraft...")
    try:
        # Strictly pulling live OpenSky data. No fallbacks. No simulations.
        res = requests.get("https://opensky-network.org/api/states/all?lamin=51.0&lomin=-1.0&lamax=52.0&lomax=0.5", timeout=7)
        res.raise_for_status()
        states = res.json().get("states", [])
        
        if not states:
            logger.info("No active flights currently detected in this bounding box.")
            return

        payload = []
        for s in states:
            # Must have valid airborne telemetry
            if s[8] or not s[5] or not s[9]: continue
            payload.append({
                "hex_id": s[0], 
                "flight_number": s[1].strip() if s[1] else "UNKNOWN",
                "lon": s[5], 
                "lat": s[6], 
                "altitude": (s[7] or 0) * 3.28084,  # m to ft
                "ground_speed": s[9] * 1.94384,     # m/s to knots
                "heading": s[10] or 0.0,
                "taxi_time_min": 15, 
                "drive_time_min": 45
            })
            
        if payload:
            payload = payload[:15] # Cap at 15 real planes for dashboard clarity
            requests.post(API_URL, json={"aircraft": payload})
            logger.info(f"✅ Injected {len(payload)} REAL flights into AeroLogix.")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ OpenSky API rejected the connection (Rate Limited/Timeout).")
        logger.info("⏳ Waiting 15 seconds before hitting the API again...")
    except Exception as e:
        logger.error(f"❌ System error: {e}")

if __name__ == "__main__":
    while True:
        fetch_real_radar()
        # Strictly 15 seconds to prevent instant IP bans from OpenSky
        time.sleep(15)
