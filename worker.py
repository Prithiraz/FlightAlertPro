import logging
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import config
from cache import cache_service
from notifications import notification_service

logger = logging.getLogger(__name__)

class AlertWorker:
    def __init__(self):
        self.scheduler = BlockingScheduler()
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
            logger.info("Starting alert check...")

            from supabase import create_client
            supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

            result = supabase.table('price_alerts').select('*').eq('active', True).execute()

            alerts = result.data
            logger.info(f"Found {len(alerts)} active alerts")

            for alert in alerts:
                try:
                    self._process_alert(alert)
                except Exception as e:
                    logger.error(f"Error processing alert {alert.get('id')}: {str(e)}")

            logger.info("Alert check completed")

        except Exception as e:
            logger.error(f"Error in check_alerts: {str(e)}")

        finally:
            self.release_lock(lock_key)

    def _process_alert(self, alert: dict):
        """Process a single price alert by searching for flights and triggering notifications if needed"""
        alert_id = alert.get('id')
        from_iata = alert.get('from_iata')
        to_iata = alert.get('to_iata')
        max_price = alert.get('max_price')
        currency = alert.get('currency', 'USD')
        departure_date = alert.get('departure_date')
        user_email = alert.get('user_email')
        
        logger.info(f"Processing alert {alert_id}: {from_iata} -> {to_iata}, max_price: {max_price} {currency}")
        
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
                logger.info(f"No offers found for alert {alert_id}")
                return
            
            # Find lowest price (offers list is guaranteed non-empty here)
            lowest_price = min(offer['price'] for offer in offers)
            logger.info(f"Alert {alert_id}: Lowest price found: {lowest_price} {currency}")
            
            # Check if price meets threshold
            if lowest_price > max_price:
                logger.info(f"Alert {alert_id}: Price {lowest_price} exceeds threshold {max_price}, skipping")
                return
            
            # Check deduplication - avoid sending alert for same or higher price
            last_triggered_price = alert.get('last_triggered_price')
            if last_triggered_price is not None and lowest_price >= last_triggered_price:
                logger.info(f"Alert {alert_id}: Price {lowest_price} not lower than last triggered price {last_triggered_price}, skipping")
                return
            
            # Price drop detected! Send notification
            logger.info(f"Alert {alert_id}: Price drop detected! {lowest_price} <= {max_price}")
            
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
