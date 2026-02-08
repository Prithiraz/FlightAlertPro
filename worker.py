import logging
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.config import config
from backend.services.cache import cache_service

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

            result = supabase.table('price_alerts').select('*').eq('is_active', True).execute()

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
        logger.info(f"Processing alert {alert.get('id')}: {alert.get('from_iata')} -> {alert.get('to_iata')}")

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
    from backend.utils.logging_config import setup_logging
    setup_logging()

    worker = AlertWorker()
    worker.start(interval_minutes=5)
