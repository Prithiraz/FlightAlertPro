from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel

from config import config, validate_env_vars
from secrets import secrets_manager
from duffel_service import duffel_service
from aerodatabox_service import aerodatabox_service
from serpapi_service import serpapi_service
from amadeus_service import amadeus_service
from skyscanner_service import skyscanner_provider
from currency_service import currency_service
from prediction_service import prediction_service
from notifications import notification_service
from payments import payments_service
from worker import AlertWorker

# Import new routes
from metadata import router as metadata_router, airports_router, airlines_router, history_router
from search import router as search_router
from currency import router as currency_router
from alerts import router as alerts_router
from systemcheck import router as systemcheck_router
from user_service import router as user_router
from trip_service import router as trip_router
from delay_service import router as delay_router
from operational_ledger import router as operational_router
import telemetry_store
from weather_service import (
    calculate_adsb_aerodynamics,
    calculate_dispatch_time,
    calculate_optimal_dispatch,
    calculate_ready_time_window,
    DEFAULT_TAXI_TIME_MIN,
    DEFAULT_DRIVE_TIME_MIN,
    DEFAULT_WAIT_COST_PER_MIN,
    DEFAULT_LATE_COST_PER_MIN,
    DEFAULT_READY_TIME_CONFIDENCE,
)
from physics_engine import (
    predict_touchdown,
    predict_on_block,
    predict_passenger_ready,
    calculate_dispatch_window,
)
from datetime import timedelta

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

app = FastAPI(title="FlightAlertPro API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include new routers
app.include_router(metadata_router)
app.include_router(airports_router)
app.include_router(airlines_router)
app.include_router(history_router)
app.include_router(search_router)
app.include_router(currency_router)
app.include_router(alerts_router)
app.include_router(systemcheck_router)
app.include_router(user_router)
app.include_router(trip_router)
app.include_router(delay_router)
app.include_router(operational_router)

class SimpleSearchRequest(BaseModel):
    from_iata: str
    to_iata: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int = 1
    cabin_class: str = "economy"
    currency: str = "USD"

class AlertRequest(BaseModel):
    user_email: str
    from_iata: str
    to_iata: str
    max_price: float
    departure_date: Optional[str] = None
    channels: List[str] = ["email"]
    phone: Optional[str] = None


class TelemetryAircraft(BaseModel):
    hex_id: str
    flight_number: Optional[str] = ""
    lon: float
    lat: float
    altitude: float
    ground_speed: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    # Optional ground-transport dispatch parameters (minutes). When omitted the
    # operator-wide defaults are applied.
    taxi_time_min: Optional[float] = None
    drive_time_min: Optional[float] = None
    # Optional ground-handling context surfaced to the mobile driver view.
    passenger_name: Optional[str] = None
    fbo: Optional[str] = None
    airport_code: Optional[str] = None
    # Drives the passenger-ready model (deplane time scales with cabin size).
    aircraft_category: Optional[str] = None


class TelemetryIngestRequest(BaseModel):
    aircraft: List[TelemetryAircraft]

@app.on_event("startup")
async def startup_event():
    logger.info("FlightAlertPro API Starting...")
    print(secrets_manager.get_report())
    missing = validate_env_vars()
    if missing:
        logger.critical(
            "CRITICAL: %d required environment variable(s) are missing: %s. "
            "Affected features will be disabled.",
            len(missing),
            ", ".join(missing),
        )
    if not config.CRON_SECRET:
        logger.warning("CRON_SECRET is not configured — /api/cron/run-worker endpoint will be disabled")
    logger.info("API Ready")

@app.get("/")
async def root():
    return {
        "service": "FlightAlertPro API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": config.ENVIRONMENT
    }

@app.get("/api/health")
async def api_health_check():
    """Primary health-check endpoint for Render / Vercel uptime monitors."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": config.ENVIRONMENT
    }

@app.get("/health/integrations")
async def integrations_health():
    from ycloud_whatsapp import ycloud_whatsapp_service

    integrations = {
        "duffel": {"enabled": duffel_service.enabled, "status": "ok" if duffel_service.enabled else "disabled"},
        "rapidapi": {"enabled": config.RAPIDAPI_KEY is not None, "status": "ok" if config.RAPIDAPI_KEY else "disabled"},
        "flightapi": {"enabled": config.FLIGHTAPI_KEY is not None, "status": "ok" if config.FLIGHTAPI_KEY else "disabled"},
        "serpapi": {"enabled": serpapi_service.enabled, "status": "ok" if serpapi_service.enabled else "disabled"},
        "openai": {"enabled": config.OPENAI_API_KEY is not None, "status": "ok" if config.OPENAI_API_KEY else "disabled"},
        "stripe": {"enabled": payments_service.enabled, "status": "ok" if payments_service.enabled else "disabled"},
        "ycloud": {"enabled": ycloud_whatsapp_service.enabled, "status": "ok" if ycloud_whatsapp_service.enabled else "disabled"},
        "gmail": {"enabled": config.GMAIL_USER is not None, "status": "ok" if config.GMAIL_USER else "disabled"},
        "telegram": {"enabled": config.TELEGRAM_BOT_TOKEN is not None, "status": "ok" if config.TELEGRAM_BOT_TOKEN else "disabled"}
    }

    all_ok = all(i["status"] == "ok" or i["status"] == "disabled" for i in integrations.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(content=integrations, status_code=status_code)

@app.post("/api/cron/run-worker")
async def run_worker(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    cron_secret = config.CRON_SECRET
    if not cron_secret:
        raise HTTPException(status_code=500, detail="CRON_SECRET not configured")
    if authorization != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        worker = AlertWorker()
        worker.check_alerts()
        return {"status": "ok", "message": "Worker run completed"}
    except Exception as e:
        logger.error(f"Worker run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Worker run failed: {str(e)}")

@app.post("/api/search/simple")
async def search_flights_simple(request: SimpleSearchRequest):
    logger.info(f"Flight search: {request.from_iata} -> {request.to_iata}")

    all_offers = skyscanner_provider.search_flights(
        request.from_iata,
        request.to_iata,
        request.departure_date,
        request.return_date,
        request.passengers,
        request.passengers,
        0,
        request.currency,
        request.cabin_class,
    )
    all_offers = sorted(all_offers, key=lambda x: x.get('price', 999999))

    return {
        "results": all_offers,
        "count": len(all_offers),
        "route": f"{request.from_iata} -> {request.to_iata}",
        "providers": ["skyscanner"] if all_offers else []
    }

@app.post("/api/predict")
async def predict_price(from_iata: str, to_iata: str, current_price: float,
                       departure_date: str, historical_prices: List[float] = []):
    route = f"{from_iata}_{to_iata}"

    prediction = prediction_service.predict(
        route=route,
        current_price=current_price,
        historical_prices=historical_prices or [current_price],
        departure_date=departure_date
    )

    return prediction

@app.post("/api/currency/convert")
async def convert_currency(amount: float, from_currency: str, to_currency: str):
    converted = currency_service.convert(amount, from_currency, to_currency)

    return {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "original_amount": amount,
        "converted_amount": round(converted, 2)
    }

@app.post("/api/alerts")
async def create_alert(alert: AlertRequest):
    logger.info(f"Creating alert for {alert.user_email}: {alert.from_iata} -> {alert.to_iata}")

    return {
        "status": "created",
        "alert_id": f"alert_{datetime.utcnow().timestamp()}",
        "user_email": alert.user_email,
        "route": f"{alert.from_iata} -> {alert.to_iata}",
        "max_price": alert.max_price
    }

@app.post("/api/notifications/send")
async def send_notification(user_email: str, message: str, channels: List[str],
                           phone: Optional[str] = None, telegram_chat_id: Optional[str] = None):
    result = notification_service.send_notification(
        user_email=user_email,
        message=message,
        channels=channels,
        phone=phone,
        telegram_chat_id=telegram_chat_id
    )

    return result


@app.post("/api/ingest_flight_data")
async def ingest_flight_data(request: TelemetryIngestRequest):
    processed: list[dict] = []
    now = datetime.utcnow()

    for aircraft in request.aircraft:
        ground_speed = aircraft.ground_speed if aircraft.ground_speed is not None else aircraft.speed
        if ground_speed is None:
            continue

        heading = aircraft.heading if aircraft.heading is not None else 0.0
        aero = calculate_adsb_aerodynamics(
            altitude_ft=aircraft.altitude,
            ground_speed_kt=ground_speed,
            heading_deg=heading,
        )

        # Operational milestones via the modular probabilistic chain:
        #   telemetry -> touchdown -> on-block -> passenger-ready -> dispatch window
        # Each stage compounds uncertainty; the final stage returns an acceptable
        # dispatch *window* (not an exact minute) by minimising expected cost.
        taxi_time_min = aircraft.taxi_time_min if aircraft.taxi_time_min is not None else DEFAULT_TAXI_TIME_MIN
        drive_time_min = aircraft.drive_time_min if aircraft.drive_time_min is not None else DEFAULT_DRIVE_TIME_MIN
        uncertainty_min = aero.get("confidence_interval_min", 0) or 0

        touchdown = predict_touchdown({
            "now": now,
            "logistics_eta_min": aero["logistics_eta_min"],
            "confidence_interval_min": uncertainty_min,
        })
        on_block = predict_on_block(touchdown, {"taxi_time_min": taxi_time_min})
        ready = predict_passenger_ready(on_block, aircraft.aircraft_category)

        predicted_touchdown = touchdown["touchdown_time"]
        predicted_on_block = on_block["on_block_time"]
        predicted_ready = ready["ready_time"]
        ready_uncertainty = ready["uncertainty_minutes"]

        dispatch_time = calculate_dispatch_time(predicted_touchdown, taxi_time_min, drive_time_min)

        # Probabilistic dispatch. The passenger-ready distribution feeds both the
        # ready-time window and the expected-cost dispatch window.
        window = calculate_ready_time_window(predicted_ready, ready_uncertainty)
        optimal = calculate_optimal_dispatch(
            predicted_ready,
            ready_uncertainty,
            DEFAULT_WAIT_COST_PER_MIN,
            DEFAULT_LATE_COST_PER_MIN,
        )
        dispatch_window = calculate_dispatch_window(
            predicted_ready,
            ready_uncertainty,
            DEFAULT_WAIT_COST_PER_MIN,
            DEFAULT_LATE_COST_PER_MIN,
            drive_time_min,
        )
        # Risk-adjusted leave time = staged presence target minus the drive.
        risk_adjusted_dispatch = (
            optimal["recommended_dispatch_time"] - timedelta(minutes=drive_time_min)
        ).replace(second=0, microsecond=0)

        processed.append({
            "hex_id": aircraft.hex_id,
            "flight_number": aircraft.flight_number,
            "lon": aircraft.lon,
            "lat": aircraft.lat,
            "altitude_ft": aircraft.altitude,
            "predicted_touchdown_time": predicted_touchdown.isoformat() + "Z",
            "predicted_on_block_time": predicted_on_block.isoformat() + "Z",
            "predicted_passenger_ready_time": predicted_ready.isoformat() + "Z",
            "ready_uncertainty_minutes": int(round(ready_uncertainty)),
            "dispatch_time": dispatch_time.isoformat() + "Z",
            "median_ready_time": window["median_ready_time"].isoformat() + "Z",
            "confidence_interval_start": window["confidence_interval_start"].isoformat() + "Z",
            "confidence_interval_end": window["confidence_interval_end"].isoformat() + "Z",
            "dispatch_window_start": dispatch_window["window_start"].isoformat() + "Z",
            "dispatch_window_end": dispatch_window["window_end"].isoformat() + "Z",
            "expected_driver_wait_minutes": dispatch_window["expected_driver_wait_minutes"],
            "recommendation_confidence": dispatch_window["recommendation_confidence"],
            "risk_adjusted_dispatch_time": risk_adjusted_dispatch.isoformat() + "Z",
            "risk_adjusted_presence_time": optimal["recommended_dispatch_time"].isoformat() + "Z",
            "dispatch_buffer_minutes": optimal["buffer_minutes"],
            "critical_fractile": optimal["critical_fractile"],
            "wait_cost_per_min": DEFAULT_WAIT_COST_PER_MIN,
            "late_cost_per_min": DEFAULT_LATE_COST_PER_MIN,
            "taxi_time_min": taxi_time_min,
            "drive_time_min": drive_time_min,
            "passenger_name": aircraft.passenger_name,
            "fbo": aircraft.fbo,
            "airport_code": aircraft.airport_code,
            "aircraft_category": aircraft.aircraft_category,
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
    aircraft, updated_at = telemetry_store.get_snapshot()
    return {
        "aircraft": aircraft,
        "updated_at": updated_at,
        "count": len(aircraft),
    }


class DispatchOptimizeRequest(BaseModel):
    expected_ready_time: str  # ISO-8601 median ready (on-block) time
    uncertainty_minutes: float
    wait_cost_per_min: float = DEFAULT_WAIT_COST_PER_MIN
    late_cost_per_min: float = DEFAULT_LATE_COST_PER_MIN
    drive_time_min: Optional[float] = None
    confidence: float = DEFAULT_READY_TIME_CONFIDENCE


def _iso_z(dt: datetime) -> str:
    """Format a datetime as UTC ISO-8601 with a single trailing 'Z'."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


@app.post("/api/dispatch/optimize")
async def optimize_dispatch(request: DispatchOptimizeRequest):
    """Recompute the risk-adjusted dispatch time for dispatcher-supplied costs."""
    try:
        expected = datetime.fromisoformat(request.expected_ready_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="expected_ready_time must be ISO-8601")

    drive = request.drive_time_min if request.drive_time_min is not None else DEFAULT_DRIVE_TIME_MIN
    optimal = calculate_optimal_dispatch(
        expected,
        request.uncertainty_minutes,
        request.wait_cost_per_min,
        request.late_cost_per_min,
    )
    window = calculate_ready_time_window(expected, request.uncertainty_minutes, request.confidence)
    dispatch_window = calculate_dispatch_window(
        expected,
        request.uncertainty_minutes,
        request.wait_cost_per_min,
        request.late_cost_per_min,
        drive,
    )

    presence = optimal["recommended_dispatch_time"]
    response = {
        "median_ready_time": _iso_z(window["median_ready_time"]),
        "confidence_interval_start": _iso_z(window["confidence_interval_start"]),
        "confidence_interval_end": _iso_z(window["confidence_interval_end"]),
        "dispatch_window_start": _iso_z(dispatch_window["window_start"]),
        "dispatch_window_end": _iso_z(dispatch_window["window_end"]),
        "expected_driver_wait_minutes": dispatch_window["expected_driver_wait_minutes"],
        "recommendation_confidence": dispatch_window["recommendation_confidence"],
        "risk_adjusted_presence_time": _iso_z(presence),
        "dispatch_buffer_minutes": optimal["buffer_minutes"],
        "critical_fractile": optimal["critical_fractile"],
        "z_score": optimal["z_score"],
        "wait_cost_per_min": optimal["wait_cost_per_min"],
        "late_cost_per_min": optimal["late_cost_per_min"],
    }
    if request.drive_time_min is not None:
        leave = (presence - timedelta(minutes=request.drive_time_min)).replace(second=0, microsecond=0)
        response["risk_adjusted_dispatch_time"] = _iso_z(leave)
    return response

from pydantic import BaseModel
from stripe_service import stripe_service # Import the correct service
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

# Define the exact JSON package we expect from React
class CheckoutRequest(BaseModel):
    user_email: str
    success_url: str
    cancel_url: str
    plan: str = "pro"

@app.post("/api/payments/checkout")
async def create_checkout(request: CheckoutRequest):
    if not stripe_service.enabled:
        raise HTTPException(status_code=503, detail="Payment service unavailable")

    if request.plan not in {"pro", "elite", "business"}:
        raise HTTPException(status_code=400, detail="Invalid plan")

    session = stripe_service.create_checkout_session(
        request.user_email, request.plan, request.success_url, request.cancel_url
    )

    if not session or "url" not in session:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    return {"checkout_url": session["url"]}

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature")

    event = stripe_service.verify_webhook_signature(payload, sig_header)

    if not event:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get('type')
    data = event.get('data', {}).get('object', {})

    if event_type == 'checkout.session.completed':
        result = stripe_service.handle_checkout_completed(data)
        logger.info(f"Checkout completed: {result}")

    elif event_type == 'invoice.paid':
        result = stripe_service.handle_invoice_paid(data)
        logger.info(f"Invoice paid: {result}")

    return JSONResponse(content={"status": "success"}, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
