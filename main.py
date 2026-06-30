from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

# Internal configuration
from config import config
from secrets import secrets_manager

# Import AeroLogix Core Routes
from metadata import router as metadata_router, airports_router, airlines_router
from systemcheck import router as systemcheck_router
from user_service import router as user_router
from trip_service import router as trip_router
from delay_service import router as delay_router
from operational_ledger import router as operational_router

# Telemetry & Physics Engine
import telemetry_store
from weather_service import (
    calculate_adsb_aerodynamics,
    calculate_dispatch_time,
    DEFAULT_TAXI_TIME_MIN,
    DEFAULT_DRIVE_TIME_MIN,
)

# Initialize Sentry for Enterprise Error Tracking
if config.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger = logging.getLogger(__name__)
    logger.info("Sentry initialized")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# App Initialization
# ---------------------------------------------------------
app = FastAPI(title="AeroLogix Dispatch API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Core Routers
app.include_router(metadata_router)
app.include_router(airports_router)
app.include_router(airlines_router)
app.include_router(systemcheck_router)
app.include_router(user_router)
app.include_router(trip_router)
app.include_router(delay_router)
app.include_router(operational_router)

# ---------------------------------------------------------
# Data Models
# ---------------------------------------------------------
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
# Startup & Health Checks
# ---------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("========================================")
    logger.info("AeroLogix Dispatch Engine Starting...")
    logger.info("Initializing Probabilistic Arrival Models")
    logger.info("========================================")
    # Note: Bypassing strict Amadeus/Stripe consumer checks here 
    # to ensure smooth booting for the B2B logistics model.
    logger.info("API Ready for Ingest")

@app.get("/")
async def root():
    return {
        "service": "AeroLogix Dispatch API",
        "version": "2.0.0",
        "status": "operational"
    }

@app.get("/api/health")
async def api_health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": config.ENVIRONMENT
    }

# ---------------------------------------------------------
# Telemetry Ingest & Dispatch Engine
# ---------------------------------------------------------
@app.post("/api/ingest_flight_data")
async def ingest_flight_data(request: TelemetryIngestRequest):
    """
    Ingests raw ADS-B data, runs physics/aerodynamics filtering,
    and calculates operational milestones for ground dispatch.
    """
    processed: list[dict] = []
    now = datetime.utcnow()

    for aircraft in request.aircraft:
        ground_speed = aircraft.ground_speed if aircraft.ground_speed is not None else aircraft.speed
        if ground_speed is None:
            continue

        heading = aircraft.heading if aircraft.heading is not None else 0.0
        
        # Calculate Approach Stability & Aerospace metrics
        aero = calculate_adsb_aerodynamics(
            altitude_ft=aircraft.altitude,
            ground_speed_kt=ground_speed,
            heading_deg=heading,
        )

        # Operational milestones: Predict absolute touchdown & on-block times
        taxi_time_min = aircraft.taxi_time_min if aircraft.taxi_time_min is not None else DEFAULT_TAXI_TIME_MIN
        drive_time_min = aircraft.drive_time_min if aircraft.drive_time_min is not None else DEFAULT_DRIVE_TIME_MIN
        eta_min = aero.get("logistics_eta_min", 0)

        predicted_touchdown = (now + timedelta(minutes=eta_min)).replace(second=0, microsecond=0)
        predicted_on_block = predicted_touchdown + timedelta(minutes=taxi_time_min)
        
        # Generate risk-adjusted dispatch time
        dispatch_time = calculate_dispatch_time(predicted_touchdown, taxi_time_min, drive_time_min)

        processed.append({
            "hex_id": aircraft.hex_id,
            "flight_number": aircraft.flight_number,
            "lon": aircraft.lon,
            "lat": aircraft.lat,
            "altitude_ft": aircraft.altitude,
            "predicted_touchdown_time": predicted_touchdown.isoformat() + "Z",
            "predicted_on_block_time": predicted_on_block.isoformat() + "Z",
            "dispatch_time": dispatch_time.isoformat() + "Z",
            "taxi_time_min": taxi_time_min,
            "drive_time_min": drive_time_min,
            "passenger_name": aircraft.passenger_name,
            "fbo": aircraft.fbo,
            **aero,
        })

    updated_at = datetime.utcnow().isoformat()
    telemetry_store.set_snapshot(processed, updated_at)
    
    return {
        "status": "ok",
        "processed": len(processed),
        "updated_at": updated_at,
    }

@app.get("/api/telemetry/live")
async def get_live_telemetry():
    """
    Serves the latest processed flight snapshots to the React dashboard.
    """
    aircraft, updated_at = telemetry_store.get_snapshot()
    return {
        "aircraft": aircraft,
        "updated_at": updated_at,
        "count": len(aircraft),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)