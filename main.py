from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel
import asyncio

from config import config
from metadata import router as metadata_router, airports_router, airlines_router
from systemcheck import router as systemcheck_router
from user_service import router as user_router
from trip_service import router as trip_router
from delay_service import router as delay_router
from operational_ledger import router as operational_router

import telemetry_store
from weather_service import calculate_adsb_aerodynamics, calculate_dispatch_time, DEFAULT_TAXI_TIME_MIN, DEFAULT_DRIVE_TIME_MIN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AeroLogix Dispatch API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metadata_router)
app.include_router(airports_router)
app.include_router(airlines_router)
app.include_router(systemcheck_router)
app.include_router(user_router)
app.include_router(trip_router)
app.include_router(delay_router)
app.include_router(operational_router)

class TelemetryAircraft(BaseModel):
    hex_id: str
    flight_number: Optional[str] = ""
    lon: float
    lat: float
    altitude: float
    ground_speed: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    taxi_time_min: Optional[float] = None
    drive_time_min: Optional[float] = None
    passenger_name: Optional[str] = None
    fbo: Optional[str] = None

class TelemetryIngestRequest(BaseModel):
    aircraft: List[TelemetryAircraft]

# ---------------------------------------------------------
# THE NEW INTERNAL RADAR LOOP (SAVES RAM)
# ---------------------------------------------------------
async def internal_historical_radar():
    logger.info("📡 Internal Radar Loop Started...")
    payload = [
        {"hex_id": "BAW123", "flight_number": "[REPLAY] BAW123", "lon": -0.46, "lat": 51.47, "altitude": 4500, "ground_speed": 160, "heading": 270, "taxi_time_min": 15, "drive_time_min": 45},
        {"hex_id": "VIR456", "flight_number": "[REPLAY] VIR456", "lon": -0.30, "lat": 51.48, "altitude": 7000, "ground_speed": 210, "heading": 265, "taxi_time_min": 12, "drive_time_min": 40},
        {"hex_id": "VIP001", "flight_number": "[REPLAY] N194WM", "lon": -0.15, "lat": 51.50, "altitude": 12000, "ground_speed": 310, "heading": 260, "taxi_time_min": 20, "drive_time_min": 50},
        {"hex_id": "RYR789", "flight_number": "[REPLAY] RYR789", "lon": 0.05, "lat": 51.55, "altitude": 18000, "ground_speed": 380, "heading": 250, "taxi_time_min": 10, "drive_time_min": 35},
        {"hex_id": "EZY321", "flight_number": "[REPLAY] EZY321", "lon": 0.25, "lat": 51.60, "altitude": 24000, "ground_speed": 420, "heading": 245, "taxi_time_min": 15, "drive_time_min": 45}
    ]
    while True:
        try:
            req = TelemetryIngestRequest(aircraft=payload)
            await ingest_flight_data(req)
            logger.info("✅ Internal Replay Frame Processed.")
        except Exception as e:
            logger.error(f"Internal Radar Error: {e}")
        await asyncio.sleep(8)

@app.on_event("startup")
async def startup_event():
    logger.info("AeroLogix Engine Starting...")
    # Spawn the radar silently in the background
    asyncio.create_task(internal_historical_radar())

@app.post("/api/ingest_flight_data")
async def ingest_flight_data(request: TelemetryIngestRequest):
    processed: list[dict] = []
    now = datetime.utcnow()
    for aircraft in request.aircraft:
        ground_speed = aircraft.ground_speed if aircraft.ground_speed is not None else aircraft.speed
        if ground_speed is None: continue
        heading = aircraft.heading if aircraft.heading is not None else 0.0
        
        aero = calculate_adsb_aerodynamics(altitude_ft=aircraft.altitude, ground_speed_kt=ground_speed, heading_deg=heading)
        taxi_time_min = aircraft.taxi_time_min if aircraft.taxi_time_min is not None else DEFAULT_TAXI_TIME_MIN
        drive_time_min = aircraft.drive_time_min if aircraft.drive_time_min is not None else DEFAULT_DRIVE_TIME_MIN
        eta_min = aero.get("logistics_eta_min", 0)

        predicted_touchdown = (now + timedelta(minutes=eta_min)).replace(second=0, microsecond=0)
        predicted_on_block = predicted_touchdown + timedelta(minutes=taxi_time_min)
        dispatch_time = calculate_dispatch_time(predicted_touchdown, taxi_time_min, drive_time_min)

        processed.append({
            "hex_id": aircraft.hex_id, "flight_number": aircraft.flight_number, "lon": aircraft.lon, "lat": aircraft.lat,
            "altitude_ft": aircraft.altitude, "predicted_touchdown_time": predicted_touchdown.isoformat() + "Z",
            "predicted_on_block_time": predicted_on_block.isoformat() + "Z", "dispatch_time": dispatch_time.isoformat() + "Z",
            "taxi_time_min": taxi_time_min, "drive_time_min": drive_time_min, "passenger_name": aircraft.passenger_name,
            "fbo": aircraft.fbo, **aero,
        })
    updated_at = datetime.utcnow().isoformat()
    telemetry_store.set_snapshot(processed, updated_at)
    return {"status": "ok", "processed": len(processed), "updated_at": updated_at}

@app.get("/api/telemetry/live")
async def get_live_telemetry():
    aircraft, updated_at = telemetry_store.get_snapshot()
    return {"aircraft": aircraft, "updated_at": updated_at, "count": len(aircraft)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
