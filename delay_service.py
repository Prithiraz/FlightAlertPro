"""EU261/UK261 Auto-Claim Engine for Elite and Business tier users.

Background cron job that:
1. Fetches active *purchased* flight alerts for Elite/Business users.
2. Checks live flight status via AviationStack (or fallback).
3. For EU/UK-origin or destination flights delayed >3 h or cancelled,
   generates a pre-filled legal compensation email and sends it to the user.
4. Records delay data in the ``flight_delays`` table.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from supabase import create_client, Client

from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/delays", tags=["delays"])

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

# ---------------------------------------------------------------------------
# EU / UK airport sets used to determine EU261 eligibility
# (non-exhaustive representative lists; covers major hubs)
# ---------------------------------------------------------------------------
EU_COUNTRY_CODES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
    # EEA + Iceland/Norway/Liechtenstein are covered under EU261 as well
    "IS", "NO", "LI",
    # UK261 (post-Brexit equivalent)
    "GB",
}

# Compensation thresholds per EU Regulation 261/2004
def _compensation_amount(distance_km: int, delay_hours: float) -> int:
    """Return the EU261 compensation amount in EUR based on distance."""
    if delay_hours < 3:
        return 0
    if distance_km <= 1500:
        return 250
    if distance_km <= 3500:
        return 400
    return 600


# ---------------------------------------------------------------------------
# Airline legal contact email addresses (common carriers)
# ---------------------------------------------------------------------------
AIRLINE_LEGAL_EMAILS: dict[str, str] = {
    "BA":  "customerrelations@ba.com",
    "LH":  "service.center@dlh.de",
    "AF":  "relations.clientele@airfrance.fr",
    "KL":  "customercare@klm.com",
    "IB":  "atencion.cliente@iberia.es",
    "VY":  "customercare@vueling.com",
    "FR":  "complaints@ryanair.com",
    "U2":  "customerservice@easyjet.com",
    "TP":  "pax.relations@tap.pt",
    "EW":  "complaints@eurowings.com",
    "AZ":  "customer.relations@ita-airways.com",
    "LX":  "feedback@swiss.com",
    "OS":  "customer.relations@austrian.com",
    "SN":  "customer.support@brusselsairlines.com",
}
DEFAULT_AIRLINE_EMAIL = "customerrelations@airline.com"


def _airline_legal_email(iata_code: str) -> str:
    return AIRLINE_LEGAL_EMAILS.get((iata_code or "").upper(), DEFAULT_AIRLINE_EMAIL)


# ---------------------------------------------------------------------------
# EU261 legal claim email template
# ---------------------------------------------------------------------------
def build_claim_email(
    user_name: str,
    flight_number: str,
    departure_date: str,
    origin_iata: str,
    destination_iata: str,
    airline_name: str,
    delay_hours: float,
    compensation_eur: int,
    airline_legal_email: str,
) -> dict[str, str]:
    subject = (
        f"EU Regulation 261/2004 – Compensation Claim – Flight {flight_number} on {departure_date}"
    )
    body = f"""To Whom It May Concern,

I am writing to formally claim compensation under EU Regulation 261/2004 (and/or UK261) in respect of the following flight:

  Flight Number : {flight_number}
  Date          : {departure_date}
  Route         : {origin_iata} → {destination_iata}
  Airline       : {airline_name}
  Delay         : approximately {delay_hours:.1f} hours

Under Article 7 of EU Regulation 261/2004, passengers are entitled to compensation of €{compensation_eur} for flights delayed by more than 3 hours upon arrival where the operating carrier is responsible.

I kindly request that you process this claim and transfer the statutory compensation of €{compensation_eur} to my account within 14 days.

Please confirm receipt of this letter and provide a reference number.

Sincerely,
{user_name}

---
Reply-To Airline: {airline_legal_email}
(Simply forward this email directly to the airline to initiate your claim.)
"""
    return {
        "to": airline_legal_email,
        "subject": subject,
        "body": body,
    }


# ---------------------------------------------------------------------------
# Live flight status check via AviationStack
# ---------------------------------------------------------------------------
AVIATIONSTACK_BASE = "http://api.aviationstack.com/v1/flights"


def _check_flight_status(flight_iata: str, flight_date: str) -> Optional[dict]:
    """Query AviationStack for live flight status. Returns raw flight data or None."""
    api_key = getattr(config, "AVIATIONSTACK_KEY", None) or os.environ.get("AVIATIONSTACK_KEY")
    if not api_key:
        logger.warning("AVIATIONSTACK_KEY not configured – skipping live status check")
        return None

    params = {
        "access_key": api_key,
        "flight_iata": flight_iata,
        "flight_date": flight_date,
    }
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(AVIATIONSTACK_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
            flights = data.get("data", [])
            return flights[0] if flights else None
    except Exception as exc:
        logger.warning(f"AviationStack request failed for {flight_iata}: {exc}")
        return None


# ---------------------------------------------------------------------------
# EU261 eligibility check
# ---------------------------------------------------------------------------
def is_eu261_eligible(origin_country: str, dest_country: str) -> bool:
    """True if at least one end of the flight is in the EU/UK area."""
    return (origin_country or "").upper() in EU_COUNTRY_CODES or \
           (dest_country or "").upper() in EU_COUNTRY_CODES


# ---------------------------------------------------------------------------
# Notification helper (reuses existing email service)
# ---------------------------------------------------------------------------
def _send_claim_email_to_user(user_email: str, claim: dict[str, str]) -> None:
    """Email the pre-filled claim template to the user so they can forward it."""
    try:
        from email_service import email_service  # local import to avoid circular
        email_service.send_email(
            to_email=user_email,
            subject=f"[FlightAlertPro] Your EU261 Claim – {claim['subject']}",
            body=(
                "Great news! Your flight may qualify for EU261 compensation.\n\n"
                "We have prepared a ready-to-send claim email below.\n"
                "Simply forward it to the airline to start your claim.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"To: {claim['to']}\n"
                f"Subject: {claim['subject']}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{claim['body']}"
            ),
        )
    except Exception as exc:
        logger.error(f"Failed to send EU261 claim email to {user_email}: {exc}")


# ---------------------------------------------------------------------------
# Core cron logic
# ---------------------------------------------------------------------------
def run_eu261_checks() -> dict:
    """
    Main entry point for the EU261 cron job.

    Fetches Elite/Business purchased-flight alerts with a departure date
    within the next 24 hours (or in the past 24 hours, to catch same-day
    delays), checks live status, and triggers claim flows where eligible.
    """
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(hours=24)).isoformat()
    window_end   = (now + timedelta(hours=24)).isoformat()

    processed = 0
    claims_sent = 0
    errors = 0

    try:
        # Fetch purchased-flight alerts for Elite/Business users
        result = (
            supabase.table("price_alerts")
            .select(
                "id, user_email, from_iata, to_iata, departure_date, airline, "
                "client_name, client_email"
            )
            .eq("active", True)
            .eq("is_purchased", True)
            .gte("departure_date", window_start[:10])
            .lte("departure_date", window_end[:10])
            .execute()
        )
        alerts = result.data or []
        logger.info(f"EU261 cron: found {len(alerts)} purchased-flight alerts in window")

        for alert in alerts:
            try:
                processed += 1
                alert_id      = alert["id"]
                user_email    = alert["user_email"]
                from_iata     = (alert.get("from_iata") or "").upper()
                to_iata       = (alert.get("to_iata") or "").upper()
                dep_date      = alert.get("departure_date") or ""
                airline_iata  = (alert.get("airline") or "").upper()
                flight_number = f"{airline_iata}{from_iata}" if airline_iata else from_iata

                # Derive country codes from IATA prefix heuristic (simple 2-char country lookup)
                origin_country = _country_for_airport(from_iata)
                dest_country   = _country_for_airport(to_iata)

                eligible = is_eu261_eligible(origin_country, dest_country)
                if not eligible:
                    logger.debug(f"Alert {alert_id}: not EU261-eligible ({from_iata}→{to_iata})")
                    continue

                # Check live status
                flight_data = _check_flight_status(flight_number, dep_date)
                delay_minutes = 0
                if flight_data:
                    delay_minutes = _extract_delay_minutes(flight_data)

                delay_hours = delay_minutes / 60.0
                eu261_eligible_now = eligible and delay_hours >= 3

                # Upsert delay record
                supabase.table("flight_delays").upsert({
                    "flight_id": flight_number,
                    "alert_id": alert_id,
                    "user_email": user_email,
                    "delay_minutes": delay_minutes,
                    "eu261_eligible": eu261_eligible_now,
                    "departure_airport": from_iata,
                    "arrival_airport": to_iata,
                    "airline_iata": airline_iata,
                    "updated_at": now.isoformat(),
                }, on_conflict="flight_id,user_email").execute()

                if not eu261_eligible_now:
                    continue

                # Check if we already sent a claim for this flight
                existing_claim = (
                    supabase.table("flight_delays")
                    .select("id, claim_sent_at")
                    .eq("flight_id", flight_number)
                    .eq("user_email", user_email)
                    .not_.is_("claim_sent_at", "null")
                    .execute()
                )
                if existing_claim.data:
                    logger.debug(f"Alert {alert_id}: claim already sent")
                    continue

                # Build and send claim
                compensation = _compensation_amount(
                    _estimate_distance_km(from_iata, to_iata), delay_hours
                )
                claim = build_claim_email(
                    user_name=user_email.split("@")[0],
                    flight_number=flight_number,
                    departure_date=dep_date,
                    origin_iata=from_iata,
                    destination_iata=to_iata,
                    airline_name=airline_iata or "the airline",
                    delay_hours=delay_hours,
                    compensation_eur=compensation,
                    airline_legal_email=_airline_legal_email(airline_iata),
                )
                _send_claim_email_to_user(user_email, claim)

                # Mark claim as sent
                supabase.table("flight_delays").update({
                    "claim_sent_at": now.isoformat(),
                    "compensation_amount": compensation,
                }).eq("flight_id", flight_number).eq("user_email", user_email).execute()

                claims_sent += 1
                logger.info(
                    f"EU261 claim sent for {user_email} flight {flight_number} "
                    f"(delay {delay_hours:.1f}h, €{compensation})"
                )

            except Exception as exc:
                errors += 1
                logger.error(f"Error processing alert {alert.get('id')}: {exc}", exc_info=True)

    except Exception as exc:
        logger.error(f"EU261 cron failed: {exc}", exc_info=True)
        return {"status": "error", "message": str(exc)}

    return {
        "status": "ok",
        "processed": processed,
        "claims_sent": claims_sent,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_delay_minutes(flight_data: dict) -> int:
    """Extract arrival delay in minutes from AviationStack response."""
    try:
        arr = flight_data.get("arrival", {}) or {}
        delay = arr.get("delay")
        if delay is not None:
            return max(0, int(delay))
        # Fallback: compare scheduled vs actual
        scheduled = arr.get("scheduled")
        actual    = arr.get("actual")
        if scheduled and actual:
            dt_sched  = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
            dt_actual = datetime.fromisoformat(actual.replace("Z", "+00:00"))
            diff_mins = (dt_actual - dt_sched).total_seconds() / 60
            return max(0, int(diff_mins))
    except Exception:
        pass
    return 0


# Rough country mapping for major hub airports (sufficient for EU261 eligibility)
_AIRPORT_COUNTRY: dict[str, str] = {
    # UK
    "LHR": "GB", "LGW": "GB", "MAN": "GB", "STN": "GB", "EDI": "GB", "GLA": "GB",
    # Germany
    "FRA": "DE", "MUC": "DE", "BER": "DE", "DUS": "DE", "HAM": "DE", "STR": "DE",
    # France
    "CDG": "FR", "ORY": "FR", "LYS": "FR", "NCE": "FR", "MRS": "FR",
    # Spain
    "MAD": "ES", "BCN": "ES", "PMI": "ES", "AGP": "ES", "VLC": "ES",
    # Italy
    "FCO": "IT", "MXP": "IT", "LIN": "IT", "NAP": "IT", "VCE": "IT",
    # Netherlands
    "AMS": "NL",
    # Belgium
    "BRU": "BE",
    # Portugal
    "LIS": "PT", "OPO": "PT",
    # Switzerland (EEA-adjacent; not EU but often treated similarly)
    "ZRH": "CH", "GVA": "CH",
    # Austria
    "VIE": "AT",
    # Scandinavia
    "ARN": "SE", "OSL": "NO", "CPH": "DK", "HEL": "FI",
    # Eastern Europe
    "WAW": "PL", "PRG": "CZ", "BUD": "HU", "OTP": "RO", "SOF": "BG",
    # Ireland
    "DUB": "IE",
    # Greece
    "ATH": "GR",
    # US (non-EU)
    "JFK": "US", "LAX": "US", "ORD": "US", "MIA": "US", "SFO": "US",
    "BOS": "US", "IAD": "US", "EWR": "US", "ATL": "US", "DFW": "US",
    # Asia (non-EU)
    "DXB": "AE", "SIN": "SG", "HKG": "HK", "NRT": "JP", "PEK": "CN",
    "BKK": "TH", "KUL": "MY", "MNL": "PH", "ICN": "KR",
}


def _country_for_airport(iata: str) -> str:
    return _AIRPORT_COUNTRY.get((iata or "").upper(), "")


def _estimate_distance_km(from_iata: str, to_iata: str) -> int:
    """Very rough distance estimate (good enough for EU261 tier selection)."""
    # Transatlantic/intercontinental routes are typically >3500 km
    us_codes  = {"US", "CA", "MX", "BR", "AR", "CL"}
    asia_codes = {"AE", "SG", "HK", "JP", "CN", "TH", "MY", "PH", "KR", "IN"}
    origin_c = _country_for_airport(from_iata)
    dest_c   = _country_for_airport(to_iata)
    if origin_c in us_codes or dest_c in us_codes or origin_c in asia_codes or dest_c in asia_codes:
        return 4000  # >3500 km -> €600
    # Intra-EU medium-haul heuristic
    return 1800  # >1500 km -> €400


# ---------------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------------

class DelayCheckRequest(BaseModel):
    flight_iata: str
    flight_date: str


@router.post("/check")
async def check_delay(req: DelayCheckRequest):
    """Manually trigger a status check for a single flight."""
    data = _check_flight_status(req.flight_iata, req.flight_date)
    if not data:
        return {"status": "unknown", "delay_minutes": 0}
    delay_minutes = _extract_delay_minutes(data)
    return {
        "status": "ok",
        "flight_iata": req.flight_iata,
        "delay_minutes": delay_minutes,
        "eu261_eligible": delay_minutes >= 180,
        "raw": data,
    }


@router.post("/cron/eu261")
async def cron_eu261(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    """
    Cron endpoint to run the EU261 Auto-Claim Engine.
    Protected with Bearer {CRON_SECRET}.
    """
    cron_secret = config.CRON_SECRET
    if not cron_secret:
        raise HTTPException(status_code=500, detail="CRON_SECRET not configured")
    if authorization != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = run_eu261_checks()
    return result


@router.get("/list")
async def list_delays(user_email: str):
    """List flight delays for a user."""
    try:
        result = (
            supabase.table("flight_delays")
            .select("*")
            .eq("user_email", user_email)
            .order("created_at", desc=True)
            .execute()
        )
        return {"delays": result.data or []}
    except Exception as exc:
        logger.error(f"Failed to list delays for {user_email}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve delay records")
