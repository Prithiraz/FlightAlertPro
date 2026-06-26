import time
import requests
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://127.0.0.1:8000/api/ingest_flight_data"

def generate_mock_fleet():
    """Generates realistic VIP flights if the live radar is slow."""
    return [
        {
            "hex_id": f"VIP{random.randint(100,999)}",
            "flight_number": f"N{random.randint(1000,9999)}X",
            "lon": -0.4614 + random.uniform(-0.5, 0.5),
            "lat": 51.4700 + random.uniform(-0.5, 0.5),
            "altitude": random.randint(10000, 35000),
            "ground_speed": random.randint(350, 500),
            "heading": random.randint(0, 360),
            "taxi_time_min": 15,
            "drive_time_min": 45
        } for _ in range(random.randint(3, 8))
    ]

def fetch_radar():
    logger.info("📡 Sweeping airspace...")
    try:
        # Try OpenSky with a strict 5-second timeout
        res = requests.get("https://opensky-network.org/api/states/all?lamin=51.0&lomin=-1.0&lamax=52.0&lomax=0.5", timeout=5)
        res.raise_for_status()
        data = res.json()
        states = data.get("states", [])
        
        payload = []
        for s in states[:10]: # Limit to 10 for testing
            if s[8] or not s[5] or not s[9]: continue
            payload.append({
                "hex_id": s[0], "flight_number": s[1].strip() or "UNK",
                "lon": s[5], "lat": s[6], "altitude": (s[7] or 0)*3.28,
                "ground_speed": s[9]*1.94, "heading": s[10] or 0.0,
                "taxi_time_min": 15, "drive_time_min": 45
            })
            
        if not payload:
            raise ValueError("No valid airborne planes found.")
            
    except Exception as e:
        logger.warning(f"Live radar unavailable ({e}). Falling back to simulated VIP fleet.")
        payload = generate_mock_fleet()

    try:
        requests.post(API_URL, json={"aircraft": payload})
        logger.info(f"✅ Injected {len(payload)} flights into AeroLogix.")
    except Exception as e:
        logger.error(f"Failed to reach local backend: {e}")

if __name__ == "__main__":
    while True:
        fetch_radar()
        time.sleep(10)
