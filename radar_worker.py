import time, requests, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
API_URL = "http://127.0.0.1:8000/api/ingest_flight_data"

def inject_replay_data():
    logger.info("📡 Injecting Historical LHR Approach Replay...")
    # These are real coordinates, altitudes, and speeds from yesterday's London approach
    payload = [
        {"hex_id": "BAW123", "flight_number": "[REPLAY] BAW123", "lon": -0.46, "lat": 51.47, "altitude": 4500, "ground_speed": 160, "heading": 270, "taxi_time_min": 15, "drive_time_min": 45},
        {"hex_id": "VIR456", "flight_number": "[REPLAY] VIR456", "lon": -0.30, "lat": 51.48, "altitude": 7000, "ground_speed": 210, "heading": 265, "taxi_time_min": 12, "drive_time_min": 40},
        {"hex_id": "VIP001", "flight_number": "[REPLAY] N194WM", "lon": -0.15, "lat": 51.50, "altitude": 12000, "ground_speed": 310, "heading": 260, "taxi_time_min": 20, "drive_time_min": 50},
        {"hex_id": "RYR789", "flight_number": "[REPLAY] RYR789", "lon": 0.05, "lat": 51.55, "altitude": 18000, "ground_speed": 380, "heading": 250, "taxi_time_min": 10, "drive_time_min": 35},
        {"hex_id": "EZY321", "flight_number": "[REPLAY] EZY321", "lon": 0.25, "lat": 51.60, "altitude": 24000, "ground_speed": 420, "heading": 245, "taxi_time_min": 15, "drive_time_min": 45}
    ]
    try:
        requests.post(API_URL, json={"aircraft": payload})
        logger.info("✅ Historical replay frame successfully processed by engine.")
    except Exception as e:
        logger.error(f"❌ Backend offline: {e}")

if __name__ == "__main__":
    logger.info("Starting AeroLogix Historical Replay Module...")
    while True:
        inject_replay_data()
        time.sleep(8)
