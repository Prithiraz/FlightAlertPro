from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
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
from weather_service import get_live_aircraft_performance

# Import new routes
from metadata import router as metadata_router, airports_router, airlines_router, history_router
from search import router as search_router
from currency import router as currency_router
from alerts import router as alerts_router
from systemcheck import router as systemcheck_router
from user_service import router as user_router
from trip_service import router as trip_router
from delay_service import router as delay_router

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

LIVE_FLIGHT_TELEMETRY = {
    "updated_at": None,
    "count": 0,
    "aircraft": [],
}

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


class AircraftTelemetry(BaseModel):
    hex_id: str
    flight_number: str
    altitude: float
    speed: float
    lat: float
    lon: float


class TelemetryIngestRequest(BaseModel):
    aircraft: List[AircraftTelemetry]

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
async def ingest_flight_data(payload: TelemetryIngestRequest):
    enriched_aircraft = []
    for aircraft in payload.aircraft:
        item = aircraft.model_dump()
        performance = get_live_aircraft_performance(
            altitude_ft=aircraft.altitude,
            lat=aircraft.lat,
            lon=aircraft.lon,
        )

        item["density_altitude_ft"] = performance.get("density_altitude_ft") if performance else None
        item["isa_deviation_c"] = performance.get("isa_deviation_c") if performance else None
        item["takeoff_risk_level"] = performance.get("takeoff_risk_level") if performance else None
        item["metar_airport_icao"] = performance.get("icao") if performance else None
        item["received_at"] = datetime.utcnow().isoformat()
        enriched_aircraft.append(item)

    global LIVE_FLIGHT_TELEMETRY
    LIVE_FLIGHT_TELEMETRY = {
        "updated_at": datetime.utcnow().isoformat(),
        "count": len(enriched_aircraft),
        "aircraft": enriched_aircraft,
    }
    return {"status": "ok", "ingested_count": len(enriched_aircraft)}


@app.get("/api/flight_data")
async def get_ingested_flight_data():
    return LIVE_FLIGHT_TELEMETRY

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
