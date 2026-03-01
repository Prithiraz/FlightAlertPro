from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from config import config
from secrets import secrets_manager
from duffel_service import duffel_service
from aerodatabox_service import aerodatabox_service
from airscraper_service import airscraper_service
from currency_service import currency_service
from prediction_service import prediction_service
from notifications import notification_service
from stripe_service import stripe_service

# Import new routes
from metadata import router as metadata_router
from search import router as search_router
from currency import router as currency_router
from alerts import router as alerts_router
from systemcheck import router as systemcheck_router
from webhooks import router as webhooks_router
from me import router as me_router
from billing import router as billing_router

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
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include new routers
app.include_router(metadata_router)
app.include_router(search_router)
app.include_router(currency_router)
app.include_router(alerts_router)
app.include_router(systemcheck_router)
app.include_router(webhooks_router)
app.include_router(me_router)
app.include_router(billing_router)

class SimpleSearchRequest(BaseModel):
    from_iata: str
    to_iata: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int = 1
    cabin_class: str = "economy"

@app.on_event("startup")
async def startup_event():
    logger.info("FlightAlertPro API Starting...")
    print(secrets_manager.get_report())
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

@app.get("/health/integrations")
async def integrations_health():
    from payments import payments_service
    from ycloud_whatsapp import ycloud_whatsapp_service
    from circuit_breaker import circuit_breaker

    integrations = {
        "duffel": {"enabled": duffel_service.enabled, "status": "ok" if duffel_service.enabled else "disabled"},
        "rapidapi": {"enabled": config.RAPIDAPI_KEY is not None, "status": "ok" if config.RAPIDAPI_KEY else "disabled"},
        "flightapi": {"enabled": config.FLIGHTAPI_KEY is not None, "status": "ok" if config.FLIGHTAPI_KEY else "disabled"},
        "openai": {"enabled": config.OPENAI_API_KEY is not None, "status": "ok" if config.OPENAI_API_KEY else "disabled"},
        "stripe": {"enabled": payments_service.enabled, "status": "ok" if payments_service.enabled else "disabled"},
        "ycloud": {"enabled": ycloud_whatsapp_service.enabled, "status": "ok" if ycloud_whatsapp_service.enabled else "disabled"},
        "gmail": {"enabled": config.GMAIL_USER is not None, "status": "ok" if config.GMAIL_USER else "disabled"},
        "telegram": {"enabled": config.TELEGRAM_BOT_TOKEN is not None, "status": "ok" if config.TELEGRAM_BOT_TOKEN else "disabled"},
    }

    # Annotate circuit-breaker status for each provider
    for provider in ("duffel", "rapidapi"):
        available = circuit_breaker.is_available(provider)
        if not available:
            integrations[provider]["circuit_breaker"] = "open"
            integrations[provider]["status"] = "circuit_open"
        else:
            integrations[provider]["circuit_breaker"] = "closed"

    all_ok = all(i["status"] in ("ok", "disabled") for i in integrations.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(content=integrations, status_code=status_code)

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
    if not stripe_service.enabled:
        raise HTTPException(status_code=503, detail="Payment service unavailable")

    if plan not in {"pro", "elite", "business"}:
        raise HTTPException(status_code=400, detail="Invalid plan. Must be one of: pro, elite, business")

    session = stripe_service.create_checkout_session(user_email, plan, success_url, cancel_url)

    if not session:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    return session

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
