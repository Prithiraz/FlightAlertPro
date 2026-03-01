"""Lifecycle email module – sends activation and retention emails to users."""
from datetime import datetime, timedelta
from typing import Optional
import logging

from supabase import create_client, Client
from config import config
from email_service import email_service

logger = logging.getLogger(__name__)


def _get_supabase() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------

TEMPLATES = {
    "welcome": {
        "subject": "Welcome to FlightAlertPro ✈️",
        "body": """\
Hi there,

Welcome to FlightAlertPro! You're now set up to never miss a cheap flight again.

Here's how to get started:
1. Go to Search and find your route.
2. Click "Create Alert" and enter your target price.
3. We'll email you the moment fares drop.

Happy travels!
The FlightAlertPro Team
""",
    },
    "nudge_create_alert": {
        "subject": "You searched — now set an alert ✈️",
        "body": """\
Hi there,

We noticed you searched for flights but haven't set a price alert yet.

Setting an alert takes 10 seconds and means you won't have to check back manually — we'll notify you when the price is right.

Log in and create your first alert: {app_url}/search

The FlightAlertPro Team
""",
    },
    "tips_after_alert": {
        "subject": "Tips to get the most out of your FlightAlertPro alert",
        "body": """\
Hi there,

Great — you've set your first price alert! Here are a few tips:

• Set alerts for flexible date windows (±3 days) to catch more deals.
• Enable WhatsApp alerts (Pro plan) for instant push notifications.
• Check Price History to see how fares have moved over time.

Happy hunting!
The FlightAlertPro Team
""",
    },
    "reengagement": {
        "subject": "Missing out on cheap flights? 👀",
        "body": """\
Hi there,

It's been a while since we've seen you on FlightAlertPro.

Prices change every day — your saved alerts may have deals waiting for you right now.

Log back in: {app_url}/dashboard

The FlightAlertPro Team
""",
    },
}


def _format_body(template_key: str, **kwargs) -> str:
    body = TEMPLATES[template_key]["body"]
    app_url = kwargs.get("app_url", "https://flightalertpro.com")
    return body.format(app_url=app_url)


# ---------------------------------------------------------------------------
# Worker functions – called by a daily cron / background job
# ---------------------------------------------------------------------------

def run_lifecycle_emails(dry_run: bool = False) -> dict:
    """
    Main entry-point for the daily lifecycle email job.
    Returns a summary dict with counts per template.
    """
    supabase = _get_supabase()
    now = datetime.utcnow()
    summary = {k: 0 for k in TEMPLATES}

    # -------------------------------------------------------------------
    # 1. Welcome email – sent once after signup (profile created ≤ 1 hour ago,
    #    no welcome_sent flag)
    # -------------------------------------------------------------------
    try:
        cutoff = (now - timedelta(hours=1)).isoformat()
        r = (
            supabase.table("user_profiles")
            .select("user_id, email, lifecycle_welcome_sent, lifecycle_emails_opt_in, created_at")
            .is_("lifecycle_welcome_sent", None)
            .gte("created_at", cutoff)
            .execute()
        )
        for row in (r.data or []):
            if row.get("lifecycle_emails_opt_in") is False:
                continue
            email = row.get("email")
            if not email:
                continue
            if not dry_run:
                sent = email_service.send_email(
                    to=email,
                    subject=TEMPLATES["welcome"]["subject"],
                    body=_format_body("welcome"),
                )
                if sent:
                    supabase.table("user_profiles").update(
                        {"lifecycle_welcome_sent": True}
                    ).eq("user_id", row["user_id"]).execute()
            summary["welcome"] += 1
    except Exception as exc:
        logger.warning("lifecycle welcome email error: %s", exc)

    # -------------------------------------------------------------------
    # 2. Nudge create alert – signed up > 2 hours ago, searched but no alert
    # -------------------------------------------------------------------
    try:
        horizon = (now - timedelta(hours=2)).isoformat()
        r = (
            supabase.table("user_profiles")
            .select("user_id, email, lifecycle_nudge_sent, lifecycle_emails_opt_in, created_at")
            .is_("lifecycle_nudge_sent", None)
            .lte("created_at", horizon)
            .execute()
        )
        for row in (r.data or []):
            if row.get("lifecycle_emails_opt_in") is False:
                continue
            email = row.get("email")
            uid = row.get("user_id")
            if not email or not uid:
                continue
            # Check if they searched but have no active alert
            search_r = (
                supabase.table("usage_events")
                .select("id", count="exact")
                .eq("user_id", uid)
                .eq("type", "search")
                .execute()
            )
            alert_r = (
                supabase.table("price_alerts")
                .select("id", count="exact")
                .eq("user_id", uid)
                .execute()
            )
            if (search_r.count or 0) > 0 and (alert_r.count or 0) == 0:
                if not dry_run:
                    sent = email_service.send_email(
                        to=email,
                        subject=TEMPLATES["nudge_create_alert"]["subject"],
                        body=_format_body("nudge_create_alert"),
                    )
                    if sent:
                        supabase.table("user_profiles").update(
                            {"lifecycle_nudge_sent": True}
                        ).eq("user_id", uid).execute()
                summary["nudge_create_alert"] += 1
    except Exception as exc:
        logger.warning("lifecycle nudge_create_alert error: %s", exc)

    # -------------------------------------------------------------------
    # 3. Tips after first alert – has alert, tips not sent yet
    # -------------------------------------------------------------------
    try:
        r = (
            supabase.table("user_profiles")
            .select("user_id, email, lifecycle_tips_sent, lifecycle_emails_opt_in")
            .is_("lifecycle_tips_sent", None)
            .execute()
        )
        for row in (r.data or []):
            if row.get("lifecycle_emails_opt_in") is False:
                continue
            email = row.get("email")
            uid = row.get("user_id")
            if not email or not uid:
                continue
            alert_r = (
                supabase.table("price_alerts")
                .select("id", count="exact")
                .eq("user_id", uid)
                .execute()
            )
            if (alert_r.count or 0) > 0:
                if not dry_run:
                    sent = email_service.send_email(
                        to=email,
                        subject=TEMPLATES["tips_after_alert"]["subject"],
                        body=_format_body("tips_after_alert"),
                    )
                    if sent:
                        supabase.table("user_profiles").update(
                            {"lifecycle_tips_sent": True}
                        ).eq("user_id", uid).execute()
                summary["tips_after_alert"] += 1
    except Exception as exc:
        logger.warning("lifecycle tips_after_alert error: %s", exc)

    # -------------------------------------------------------------------
    # 4. Re-engagement – inactive ≥ 7 days, re-engage not yet sent
    # -------------------------------------------------------------------
    try:
        inactive_since = (now - timedelta(days=7)).isoformat()
        r = (
            supabase.table("user_profiles")
            .select("user_id, email, lifecycle_reengagement_sent, lifecycle_emails_opt_in")
            .is_("lifecycle_reengagement_sent", None)
            .execute()
        )
        for row in (r.data or []):
            if row.get("lifecycle_emails_opt_in") is False:
                continue
            email = row.get("email")
            uid = row.get("user_id")
            if not email or not uid:
                continue
            # Check last activity
            activity_r = (
                supabase.table("usage_events")
                .select("ts")
                .eq("user_id", uid)
                .order("ts", desc=True)
                .limit(1)
                .execute()
            )
            last_events = activity_r.data or []
            if last_events:
                last_ts_str = last_events[0].get("ts", "")
                if last_ts_str and last_ts_str > inactive_since:
                    continue  # Still active
            if not dry_run:
                sent = email_service.send_email(
                    to=email,
                    subject=TEMPLATES["reengagement"]["subject"],
                    body=_format_body("reengagement"),
                )
                if sent:
                    supabase.table("user_profiles").update(
                        {"lifecycle_reengagement_sent": True}
                    ).eq("user_id", uid).execute()
            summary["reengagement"] += 1
    except Exception as exc:
        logger.warning("lifecycle reengagement error: %s", exc)

    logger.info("Lifecycle email run complete: %s", summary)
    return summary
