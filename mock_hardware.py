import random
import time
from datetime import datetime

import requests


INGEST_URL = "http://127.0.0.1:8000/api/ingest_flight_data"
LONDON_LAT = 51.5
LONDON_LON = -0.1


def _build_aircraft(index: int) -> dict:
    return {
        "hex_id": f"406{index:03X}",
        "flight_number": f"BA{random.randint(100, 999)}",
        "altitude": round(random.uniform(5000, 39000), 1),
        "speed": round(random.uniform(180, 520), 1),
        "lat": round(LONDON_LAT + random.uniform(-0.25, 0.25), 6),
        "lon": round(LONDON_LON + random.uniform(-0.25, 0.25), 6),
    }


def main() -> None:
    print(f"{datetime.utcnow().isoformat()}Z | mock_hardware started → {INGEST_URL}")
    while True:
        count = random.randint(3, 5)
        payload = {"aircraft": [_build_aircraft(i) for i in range(count)]}
        try:
            response = requests.post(INGEST_URL, json=payload, timeout=10)
            print(
                f"{datetime.utcnow().isoformat()}Z | sent={count} "
                f"status={response.status_code} body={response.text[:160]}"
            )
        except requests.RequestException as exc:
            print(f"{datetime.utcnow().isoformat()}Z | post failed: {exc}")

        time.sleep(2)


if __name__ == "__main__":
    main()
