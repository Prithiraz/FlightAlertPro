import asyncio
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import config
from cache import cache_service
from notifications import notification_service

logger = logging.getLogger(__name__)

# Maximum number of alerts processed concurrently (asyncio semaphore)
_MAX_CONCURRENT = 10
# Cooldown: do not re-notify for the same alert within this many seconds (6 hours)
_NOTIFICATION_COOLDOWN_SECONDS = 6 * 3600
# Dedupe tolerance: skip notification if price changed by less than 1%
_PRICE_TOLERANCE = 0.01
# Per-provider in-memory rate limit: max calls per minute
_PROVIDER_RATE_LIMITS = {
    "rapidapi": config.RAPIDAPI_RATE_LIMIT,
    "duffel": config.DUFFEL_RATE_LIMIT,
}


def _jitter_sleep(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    """Return sleep duration using full-jitter exponential backoff."""
    delay = min(cap, base * (2 ** attempt))
    return random.uniform(0, delay)


class AlertWorker:
    def __init__(self):
        self.scheduler = BlockingScheduler()
        self.use_redis = config.REDIS_URL is not None
        # Per-provider call timestamps for simple rate limiting
        self._provider_calls: dict[str, list[float]] = {}

    def acquire_lock(self, lock_key: str, timeout: int = 300) -> bool:
        if self.use_redis:
            return self._acquire_redis_lock(lock_key, timeout)
        else:
            return self._acquire_db_lock(lock_key, timeout)

    def _acquire_redis_lock(self, lock_key: str, timeout: int) -> bool:
        lock_value = cache_service.get(lock_key)
        if lock_value:
            logger.info(f"Lock {lock_key} already held")
            return False

        cache_service.set(lock_key, str(time.time()), ttl=timeout)
        return True

    def _acquire_db_lock(self, lock_key: str, timeout: int) -> bool:
        try:
            from supabase import create_client
            supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

            result = supabase.table('system_locks').select('*').eq('lock_key', lock_key).execute()

            if result.data:
                lock_time = result.data[0].get('locked_at')
                if lock_time:
                    locked_timestamp = datetime.fromisoformat(lock_time.replace('Z', '+00:00')).timestamp()
                    if time.time() - locked_timestamp < timeout:
                        logger.info(f"DB lock {lock_key} already held")
                        return False

            supabase.table('system_locks').upsert({
                'lock_key': lock_key,
                'locked_at': datetime.utcnow().isoformat()
            }).execute()

            return True

        except Exception as e:
            logger.error(f"Error acquiring DB lock: {str(e)}")
            return False

    def release_lock(self, lock_key: str):
        if self.use_redis:
            cache_service.delete(lock_key)
        else:
            try:
                from supabase import create_client
                supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
                supabase.table('system_locks').delete().eq('lock_key', lock_key).execute()
            except Exception as e:
                logger.error(f"Error releasing DB lock: {str(e)}")

    # ------------------------------------------------------------------
    # Provider-level rate limiting (simple token-bucket in memory)
    # ------------------------------------------------------------------

    def _provider_allow(self, provider: str) -> bool:
        """Return True if the provider has capacity; enforces per-minute cap."""
        limit = _PROVIDER_RATE_LIMITS.get(provider)
        if limit is None:
            return True
        now = time.time()
        calls = self._provider_calls.setdefault(provider, [])
        # Keep only timestamps within the last 60 s
        calls[:] = [t for t in calls if now - t < 60]
        if len(calls) >= limit:
            logger.warning("Provider %s rate-limited (%d/%d calls/min)", provider, len(calls), limit)
            return False
        calls.append(now)
        return True

    # ------------------------------------------------------------------
    # Async check_alerts / _process_alert
    # ------------------------------------------------------------------

    def check_alerts(self):
        """Synchronous entry point: run the async check in a fresh event loop."""
        lock_key = "check_alerts_lock"

        if not self.acquire_lock(lock_key):
            logger.info("Another worker is checking alerts, skipping")
            return

        try:
            asyncio.run(self._check_alerts_async())
        except Exception as e:
            logger.error(f"Error in check_alerts: {str(e)}")
        finally:
            self.release_lock(lock_key)

    async def _check_alerts_async(self):
        logger.info("Starting alert check...")

        from supabase import create_client
        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

        result = supabase.table('price_alerts').select('*').eq('active', True).execute()
        alerts = result.data or []
        logger.info(f"Found {len(alerts)} active alerts")

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        async def bounded(alert):
            async with semaphore:
                try:
                    await self._process_alert_async(alert)
                except Exception as exc:
                    logger.error("Error processing alert %s: %s", alert.get('id'), exc, exc_info=True)

        await asyncio.gather(*[bounded(a) for a in alerts])
        logger.info("Alert check completed")

    async def _process_alert_async(self, alert: dict):
        """Process a single price alert (async version)."""
        alert_id = alert.get('id')
        from_iata = alert.get('from_iata')
        to_iata = alert.get('to_iata')
        max_price = alert.get('max_price')
        currency = alert.get('currency', 'USD')
        departure_date = alert.get('departure_date')
        user_email = alert.get('user_email')

        logger.info(f"Processing alert {alert_id}: {from_iata} -> {to_iata}, max_price: {max_price} {currency}")

        try:
            from search import search_flights, SearchRequest, FlightSegment, PassengerCount

            if not departure_date:
                departure_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

            search_request = SearchRequest(
                segments=[FlightSegment(
                    from_iata=from_iata,
                    to_iata=to_iata,
                    departure_date=departure_date
                )],
                passengers=PassengerCount(adults=1, children=0, infants=0),
                cabin_class="economy",
                currency=currency
            )

            # Apply per-provider rate limiting before hitting the search layer.
            # Use whichever provider is configured; fall back to "rapidapi".
            search_provider = "duffel" if config.DUFFEL_API_KEY else "rapidapi"
            if not self._provider_allow(search_provider):
                logger.warning("Alert %s: skipped – provider %s rate-limited", alert_id, search_provider)
                return

            # Search with jittered exponential backoff on transient failures
            search_result = None
            for attempt in range(3):
                try:
                    search_result = await search_flights(search_request)
                    break
                except Exception as exc:
                    if attempt == 2:
                        raise
                    delay = _jitter_sleep(attempt)
                    logger.warning(
                        "Search failed for alert %s (attempt %d/3), retrying in %.1fs: %s",
                        alert_id, attempt + 1, delay, exc
                    )
                    await asyncio.sleep(delay)
            offers = search_result.get('offers', [])
            provider = (offers[0].get('provider') if offers else None) or 'unknown'

            # --- Save price history (even when above threshold) ---
            if offers:
                lowest_price = min(offer['price'] for offer in offers)
                logger.info(f"Alert {alert_id}: Lowest price found: {lowest_price} {currency}")
                await self._save_price_history(alert_id, lowest_price, currency, provider)
            else:
                logger.info(f"No offers found for alert {alert_id}")
                return

            # Check if price meets threshold
            if lowest_price > max_price:
                logger.info(f"Alert {alert_id}: Price {lowest_price} exceeds threshold {max_price}, skipping")
                return

            # --- Dedupe: tolerance + persistent cooldown ---
            last_triggered_price = alert.get('last_triggered_price')
            last_triggered_at_raw = alert.get('last_triggered_at')

            if last_triggered_price is not None:
                # 1% tolerance: if new price is within 1% of last triggered price, skip.
                # Guard against zero/near-zero last_triggered_price to avoid division issues.
                if last_triggered_price > 0 and abs(lowest_price - last_triggered_price) / last_triggered_price <= _PRICE_TOLERANCE:
                    logger.info(
                        f"Alert {alert_id}: Price {lowest_price} within tolerance of last "
                        f"triggered price {last_triggered_price}, skipping"
                    )
                    return
                # Must be strictly lower (beyond tolerance) to trigger
                if lowest_price >= last_triggered_price:
                    logger.info(
                        f"Alert {alert_id}: Price {lowest_price} not lower than last triggered "
                        f"price {last_triggered_price}, skipping"
                    )
                    return

            # Persistent cooldown via last_triggered_at in DB
            if last_triggered_at_raw:
                try:
                    last_triggered_at = datetime.fromisoformat(
                        last_triggered_at_raw.replace('Z', '+00:00')
                    )
                    cooldown_expires = last_triggered_at + timedelta(seconds=_NOTIFICATION_COOLDOWN_SECONDS)
                    if datetime.now(timezone.utc) < cooldown_expires:
                        logger.info(f"Alert {alert_id}: Within cooldown window, skipping notification")
                        return
                except Exception:
                    pass

            # --- Idempotency check via notification_log ---
            channels = alert.get('channels') or alert.get('notification_channels', ['email'])
            now_bucket = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')
            rounded = round(lowest_price)

            if config.DRY_RUN:
                logger.info(
                    "[DRY_RUN] Alert %s: would send notification to %s (price %.2f %s)",
                    alert_id, user_email, lowest_price, currency
                )
                return

            # Check/insert dedupe key to avoid duplicate sends
            from supabase import create_client
            supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            for channel in channels:
                dedupe_key = f"{alert_id}:{channel}:{rounded}:{now_bucket}"
                try:
                    existing = (
                        supabase.table('notification_log')
                        .select('id')
                        .eq('dedupe_key', dedupe_key)
                        .execute()
                    )
                    if existing.data:
                        logger.info(f"Alert {alert_id}: Duplicate notification skipped (key={dedupe_key})")
                        return
                except Exception:
                    pass  # table may not exist yet – proceed

            # --- Send notification ---
            logger.info(f"Alert {alert_id}: Price drop detected! {lowest_price} <= {max_price}")
            route = f"{from_iata} → {to_iata}"
            old_price = last_triggered_price if last_triggered_price else max_price

            notification_result = notification_service.send_price_alert(
                user_email=user_email,
                route=route,
                old_price=old_price,
                new_price=lowest_price,
                channels=channels,
                phone=alert.get('phone')
            )
            logger.info(f"Alert {alert_id}: Notification sent - {notification_result}")

            # --- Log to notification_log ---
            now_iso = datetime.now(timezone.utc).isoformat()
            for channel in channels:
                dedupe_key = f"{alert_id}:{channel}:{rounded}:{now_bucket}"
                try:
                    supabase.table('notification_log').insert({
                        'alert_id': alert_id,
                        'channel': channel,
                        'status': 'sent',
                        'message_content': f"Price drop: {route} at {lowest_price} {currency}",
                        'dedupe_key': dedupe_key,
                        'sent_at': now_iso,
                    }).execute()
                except Exception as exc:
                    logger.warning("Could not write notification_log: %s", exc)

            # --- Update alert: triggered_at, last_triggered_price, last_triggered_at ---
            update_data = {
                'triggered_at': now_iso,
                'last_triggered_price': lowest_price,
                'last_triggered_at': now_iso,
            }
            supabase.table('price_alerts').update(update_data).eq('id', alert_id).execute()

            logger.info(f"Alert {alert_id}: Processing completed successfully")

        except Exception as e:
            logger.error(f"Error processing alert {alert_id}: {str(e)}", exc_info=True)

    async def _save_price_history(self, alert_id: str, lowest_price: float, currency: str, provider: str):
        """Persist a price data point for this alert check."""
        try:
            from supabase import create_client
            supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            supabase.table('price_history').insert({
                'alert_id': alert_id,
                'lowest_price': lowest_price,
                'currency': currency,
                'provider': provider,
                'checked_at': datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as exc:
            logger.warning("Could not save price history for alert %s: %s", alert_id, exc)

    def start(self, interval_minutes: int = 5):
        logger.info(f"Starting alert worker (interval: {interval_minutes} minutes)")

        self.scheduler.add_job(
            self.check_alerts,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='check_alerts',
            name='Check price alerts',
            replace_existing=True
        )

        logger.info("Worker started")
        self.scheduler.start()

if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()

    worker = AlertWorker()
    worker.start(interval_minutes=5)
