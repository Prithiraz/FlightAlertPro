import logging
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import config
from cache import cache_service
from notifications import notification_service

logger = logging.getLogger(__name__)

# Default number of days ahead to search when an alert has no departure_date
_DEFAULT_ALERT_DAYS_AHEAD = 7

class AlertWorker:
    def __init__(self):
        self.use_redis = config.REDIS_URL is not None

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

    def check_alerts(self):
        lock_key = "check_alerts_lock"

        if not self.acquire_lock(lock_key):
            logger.info("Another worker is checking alerts, skipping")
            return

        try:
            self.process_active_alerts()
        except Exception as e:
            logger.error(f"Error in check_alerts: {str(e)}")
        finally:
            self.release_lock(lock_key)

    # ------------------------------------------------------------------
    # Route-batching + caching entry point
    # ------------------------------------------------------------------

    def process_active_alerts(self):
        """Fetch all active alerts, group them by route/date, apply cache
        logic so that only ONE external API call is made per unique route,
        then notify each user whose max_price threshold is met."""
        import asyncio
        from datetime import timezone
        from supabase import create_client
        from search import search_flights, SearchRequest, FlightSegment, PassengerCount

        logger.info("Starting alert check...")

        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

        result = supabase.table('price_alerts').select('*').eq('active', True).execute()
        alerts = result.data
        logger.info(f"Found {len(alerts)} active alerts")

        if not alerts:
            logger.info("No active alerts — nothing to do")
            return

        # --- Group by (from_iata, to_iata, departure_start_date, departure_end_date) ---
        # For backward-compat, alerts with only departure_date treat it as an exact range.
        groups: dict[tuple, list] = {}
        for alert in alerts:
            start_date = alert.get('departure_start_date') or alert.get('departure_date')
            end_date   = alert.get('departure_end_date')   or alert.get('departure_date')
            if not start_date:
                start_date = (datetime.now(timezone.utc) + timedelta(days=_DEFAULT_ALERT_DAYS_AHEAD)).strftime('%Y-%m-%d')
            if not end_date:
                end_date = start_date
            key = (alert.get('from_iata'), alert.get('to_iata'), start_date, end_date)
            groups.setdefault(key, []).append(alert)

        logger.info(f"Grouped into {len(groups)} unique route/date-range combinations")

        for (from_iata, to_iata, start_date, end_date), group_alerts in groups.items():
            route_label = f"{from_iata}->{to_iata}"
            is_flexible = start_date != end_date
            try:
                currency = group_alerts[0].get('currency', 'USD')

                if not is_flexible:
                    # --- Exact-date path (original logic, with caching) ---
                    departure_date = start_date
                    cached = self._get_cached_price(supabase, from_iata, to_iata, departure_date)

                    if cached is not None:
                        logger.info(f"CACHE HIT: {route_label} {departure_date} (Skipping API call)")
                        lowest_price = cached['lowest_price']
                        best_date = departure_date
                    else:
                        logger.info(f"CACHE MISS: {route_label} {departure_date} (Calling external API)")
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

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            search_result = loop.run_until_complete(search_flights(search_request))
                        finally:
                            loop.close()

                        offers = search_result.get('offers', [])
                        if not offers:
                            logger.info(f"{route_label} {departure_date}: No offers found, skipping group")
                            continue

                        lowest_price = min(offer['price'] for offer in offers)
                        best_date = departure_date

                        self._save_price_cache(
                            supabase, from_iata, to_iata, departure_date,
                            lowest_price, search_result
                        )
                        self._log_price_history(supabase, from_iata, to_iata, lowest_price)

                else:
                    # --- Flexible-date path: check every day in the range ---
                    logger.info(f"FLEXIBLE: {route_label} {start_date}→{end_date} (checking all dates)")
                    lowest_price = None
                    best_date = None

                    current = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt   = datetime.strptime(end_date,   '%Y-%m-%d')

                    while current <= end_dt:
                        dep_str = current.strftime('%Y-%m-%d')

                        # Honour cache per individual date
                        cached = self._get_cached_price(supabase, from_iata, to_iata, dep_str)
                        if cached is not None:
                            day_price = cached['lowest_price']
                            logger.info(f"CACHE HIT: {route_label} {dep_str} → {day_price:.2f}")
                        else:
                            logger.info(f"CACHE MISS: {route_label} {dep_str} (Calling external API)")
                            search_request = SearchRequest(
                                segments=[FlightSegment(
                                    from_iata=from_iata,
                                    to_iata=to_iata,
                                    departure_date=dep_str
                                )],
                                passengers=PassengerCount(adults=1, children=0, infants=0),
                                cabin_class="economy",
                                currency=currency
                            )

                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                search_result = loop.run_until_complete(search_flights(search_request))
                            finally:
                                loop.close()

                            offers = search_result.get('offers', [])
                            if not offers:
                                logger.info(f"{route_label} {dep_str}: No offers found, skipping date")
                                current += timedelta(days=1)
                                continue

                            day_price = min(offer['price'] for offer in offers)
                            self._save_price_cache(
                                supabase, from_iata, to_iata, dep_str,
                                day_price, search_result
                            )
                            self._log_price_history(supabase, from_iata, to_iata, day_price)

                        if lowest_price is None or day_price < lowest_price:
                            lowest_price = day_price
                            best_date = dep_str

                        current += timedelta(days=1)

                    if lowest_price is None:
                        logger.info(f"{route_label} {start_date}→{end_date}: No offers found across range, skipping")
                        continue

                    logger.info(
                        f"FLEXIBLE BEST: {route_label} best date={best_date} price={lowest_price:.2f} {currency}"
                    )

                # 4. Process each user in this route group
                for alert in group_alerts:
                    try:
                        self._process_user_alert(
                            supabase, alert, lowest_price, currency,
                            best_date=best_date if is_flexible else None
                        )
                    except Exception as e:
                        logger.error(
                            f"Error processing alert {alert.get('id')} "
                            f"for {route_label}: {str(e)}"
                        )

            except Exception as e:
                logger.error(f"Error processing route group {route_label} {start_date}→{end_date}: {str(e)}", exc_info=True)

        logger.info("Alert check completed")

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _get_cached_price(self, supabase, from_iata: str, to_iata: str, departure_date: str):
        """Return cached row if it exists and is less than 6 hours old, else None."""
        from datetime import timezone

        try:
            result = (
                supabase.table('flight_price_cache')
                .select('*')
                .eq('origin', from_iata)
                .eq('destination', to_iata)
                .eq('departure_date', departure_date)
                .execute()
            )
            if not result.data:
                return None

            row = result.data[0]
            updated_at_str = row.get('updated_at')
            if not updated_at_str:
                return None

            updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
            age_hours = (datetime.now(timezone.utc) - updated_at).total_seconds() / 3600
            if age_hours < 6:
                return row
            return None

        except Exception as e:
            logger.error(f"Error checking flight_price_cache: {str(e)}")
            return None

    def _save_price_cache(self, supabase, from_iata: str, to_iata: str,
                          departure_date: str, lowest_price: float, api_response: dict):
        """Upsert a price result into the flight_price_cache table."""
        import json
        from datetime import timezone

        try:
            supabase.table('flight_price_cache').upsert({
                'origin': from_iata,
                'destination': to_iata,
                'departure_date': departure_date,
                'lowest_price': lowest_price,
                'api_response_json': api_response,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as e:
            logger.error(f"Error saving to flight_price_cache: {str(e)}")

    def _log_price_history(self, supabase, from_iata: str, to_iata: str, lowest_price: float):
        """Insert a price snapshot into price_history_logs for trend visualisation."""
        from datetime import timezone

        route_group = f"{from_iata}-{to_iata}"
        try:
            supabase.table('price_history_logs').insert({
                'route_group': route_group,
                'lowest_price': lowest_price,
                'recorded_at': datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.info(f"Logged price history for {route_group}: {lowest_price}")
        except Exception as e:
            logger.error(f"Error logging price history for {route_group}: {str(e)}")

    # ------------------------------------------------------------------
    # Per-user notification logic
    # ------------------------------------------------------------------

    def _process_user_alert(self, supabase, alert: dict, lowest_price: float, currency: str,
                            best_date: str | None = None):
        """Compare cached lowest_price against a single user's threshold and
        send a notification if the price is low enough.

        Args:
            best_date: For flexible-date alerts, the specific departure date that
                       produced the lowest price.  None for exact-date alerts.
        """
        from datetime import timezone

        alert_id = alert.get('id')
        from_iata = alert.get('from_iata')
        to_iata = alert.get('to_iata')
        max_price = alert.get('max_price')
        user_email = alert.get('user_email')

        if lowest_price > max_price:
            logger.info(
                f"Checking alert for {from_iata}->{to_iata}... "
                f"Current price {lowest_price:.2f} {currency} is above "
                f"threshold {max_price:.2f} {currency}, skipping"
            )
            return

        # Deduplication — don't re-notify for the same or higher price
        last_triggered_price = alert.get('last_triggered_price')
        if last_triggered_price is not None and lowest_price >= last_triggered_price:
            logger.info(
                f"Checking alert for {from_iata}->{to_iata}... "
                f"Current price {lowest_price:.2f} {currency} not lower than "
                f"last triggered price {last_triggered_price:.2f} {currency}, skipping"
            )
            return

        logger.info(
            f"Checking alert for {from_iata}->{to_iata}... "
            f"Current price {lowest_price:.2f} {currency}... "
            f"Threshold {max_price:.2f} {currency}... Triggering notification"
        )

        channels = alert.get('channels') or alert.get('notification_channels', ['email'])
        phone = alert.get('phone')
        route = f"{from_iata} → {to_iata}"
        old_price = last_triggered_price if last_triggered_price else max_price

        notification_result = notification_service.send_price_alert(
            user_email=user_email,
            route=route,
            old_price=old_price,
            new_price=lowest_price,
            channels=channels,
            phone=phone,
            best_date=best_date
        )

        logger.info(f"Alert {alert_id}: Notification sent - {notification_result}")

        supabase.table('price_alerts').update({
            'triggered_at': datetime.now(timezone.utc).isoformat(),
            'last_triggered_price': lowest_price,
        }).eq('id', alert_id).execute()

        logger.info(f"Alert {alert_id}: Processing completed successfully")

    # ------------------------------------------------------------------
    # Legacy single-alert helper (kept for backward compatibility / tests)
    # ------------------------------------------------------------------

    def _process_alert(self, alert: dict):
        """Process a single price alert by searching for flights and triggering notifications if needed"""
        alert_id = alert.get('id')
        from_iata = alert.get('from_iata')
        to_iata = alert.get('to_iata')
        max_price = alert.get('max_price')
        currency = alert.get('currency', 'USD')
        departure_date = alert.get('departure_date')
        user_email = alert.get('user_email')
        
        logger.info(f"Checking alert for {from_iata}->{to_iata} (id={alert_id}, threshold={max_price} {currency})")

        try:
            # Import search functionality
            import asyncio
            from datetime import timezone
            from search import search_flights, SearchRequest, FlightSegment, PassengerCount

            # Build search request
            if not departure_date:
                # If no specific date, search for next 7 days
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

            # Run the search (need to run async function in sync context)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                search_result = loop.run_until_complete(search_flights(search_request))
            finally:
                loop.close()

            offers = search_result.get('offers', [])

            if not offers:
                logger.info(f"Checking alert for {from_iata}->{to_iata}... No offers found, skipping")
                return

            # Find lowest price (offers list is guaranteed non-empty here)
            lowest_price = min(offer['price'] for offer in offers)
            logger.info(f"Checking alert for {from_iata}->{to_iata}... Current price {lowest_price:.2f} {currency}... Threshold {max_price:.2f} {currency}")

            # Check if price meets threshold
            if lowest_price > max_price:
                logger.info(f"Checking alert for {from_iata}->{to_iata}... Current price {lowest_price:.2f} {currency} is above threshold {max_price:.2f} {currency}, skipping")
                return

            # Check deduplication - avoid sending alert for same or higher price
            last_triggered_price = alert.get('last_triggered_price')
            if last_triggered_price is not None and lowest_price >= last_triggered_price:
                logger.info(f"Checking alert for {from_iata}->{to_iata}... Current price {lowest_price:.2f} {currency} not lower than last triggered price {last_triggered_price:.2f} {currency}, skipping")
                return

            # Price drop detected! Send notification
            logger.info(f"Checking alert for {from_iata}->{to_iata}... Current price {lowest_price:.2f} {currency}... Threshold {max_price:.2f} {currency}... Triggering notification")

            # Get notification channels
            channels = alert.get('channels') or alert.get('notification_channels', ['email'])
            phone = alert.get('phone')

            # Send notification using existing notification service
            route = f"{from_iata} → {to_iata}"
            old_price = last_triggered_price if last_triggered_price else max_price

            notification_result = notification_service.send_price_alert(
                user_email=user_email,
                route=route,
                old_price=old_price,
                new_price=lowest_price,
                channels=channels,
                phone=phone
            )

            logger.info(f"Alert {alert_id}: Notification sent - {notification_result}")
            
            # Update alert in database
            from supabase import create_client
            supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
            
            # Update triggered_at and last_triggered_price
            update_data = {
                'triggered_at': datetime.now(timezone.utc).isoformat(),
                'last_triggered_price': lowest_price
            }
            
            supabase.table('price_alerts').update(update_data).eq('id', alert_id).execute()
            
            logger.info(f"Alert {alert_id}: Processing completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing alert {alert_id}: {str(e)}", exc_info=True)

    def start(self, interval_hours: int = 6):
        """Start the worker as a standalone blocking process."""
        logger.info(f"Starting alert worker (interval: {interval_hours} hours)")

        scheduler = BlockingScheduler()
        scheduler.add_job(
            self.check_alerts,
            trigger=IntervalTrigger(hours=interval_hours),
            id='check_alerts',
            name='Check price alerts',
            replace_existing=True
        )

        logger.info("Worker started")
        scheduler.start()

    def start_background(self, interval_hours: int = 6) -> BackgroundScheduler:
        """Start the worker as a non-blocking background scheduler for use with FastAPI."""
        logger.info(f"Starting background alert worker (interval: {interval_hours} hours)")

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            self.check_alerts,
            trigger=IntervalTrigger(hours=interval_hours),
            id='check_alerts',
            name='Check price alerts',
            replace_existing=True
        )
        scheduler.start()

        logger.info("Background worker started")
        return scheduler

if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()

    worker = AlertWorker()
    worker.start(interval_hours=config.ALERT_CHECK_INTERVAL_HOURS)
