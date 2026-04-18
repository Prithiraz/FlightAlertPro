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
from airscraper_service import airscraper_service
from serpapi_service import serpapi_service
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

class SimpleSearchRequest(BaseModel):
    from_iata: str
    to_iata: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int = 1
    cabin_class: str = "economy"

class AlertRequest(BaseModel):
    user_email: str
    from_iata: str
    to_iata: str
    max_price: float
    departure_date: Optional[str] = None
    channels: List[str] = ["email"]
    phone: Optional[str] = None

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

    all_offers = []

    duffel_offers = duffel_service.search_flights(
        request.from_iata,
        request.to_iata,
        request.departure_date,
        request.return_date,
        request.passengers,
        request.cabin_class
    )
    all_offers.extend(duffel_offers)
    logger.info(f"Duffel returned {len(duffel_offers)} offers")

    aerodatabox_offers = aerodatabox_service.search_flights(
        request.from_iata,
        request.to_iata,
        request.departure_date,
        request.return_date,
        request.passengers
    )
    all_offers.extend(aerodatabox_offers)
    logger.info(f"AeroDataBox returned {len(aerodatabox_offers)} offers")

    if len(all_offers) == 0:
        logger.info("No results from primary providers, using fallback")
        fallback_offers = airscraper_service.search_flights(
            request.from_iata,
            request.to_iata,
            request.departure_date
        )
        all_offers.extend(fallback_offers)

    all_offers = sorted(all_offers, key=lambda x: x.get('price', 999999))

    return {
        "results": all_offers,
        "count": len(all_offers),
        "route": f"{request.from_iata} -> {request.to_iata}",
        "providers": list(set([o.get('provider') for o in all_offers]))
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

@app.post("/api/payments/checkout")
async def create_checkout(user_email: str, success_url: str, cancel_url: str, plan: str = "pro"):
    if not payments_service.enabled:
        raise HTTPException(status_code=503, detail="Payment service unavailable")

    if plan not in {"pro", "elite", "business"}:
        raise HTTPException(status_code=400, detail="Invalid plan. Must be one of: pro, elite, business")

    session = payments_service.create_checkout_session(user_email, plan, success_url, cancel_url)

    if not session:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    checkout_url = None
    if isinstance(session, dict):
        checkout_url = session.get("checkout_url") or session.get("url")
    else:
        checkout_url = getattr(session, "url", None)

    if not checkout_url:
        raise HTTPException(status_code=500, detail="Checkout URL missing from Stripe session")

    return {"checkout_url": checkout_url}

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature")

    event = payments_service.verify_webhook_signature(payload, sig_header)

    if not event:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get('type')
    data = event.get('data', {}).get('object', {})

    if event_type == 'checkout.session.completed':
        result = payments_service.handle_checkout_completed(data)
        logger.info(f"Checkout completed: {result}")

    elif event_type == 'invoice.paid':
        result = payments_service.handle_invoice_paid(data)
        logger.info(f"Invoice paid: {result}")

    return JSONResponse(content={"status": "success"}, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
