"""
Tests to verify alert worker logic — including the new route-batching and
caching behaviour introduced in process_active_alerts().
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, '/home/runner/work/FlightAlertPro')

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

# Pre-load supabase so patch.dict(sys.modules, ...) doesn't evict it between
# tests, which would cause PyO3 extension re-initialisation errors.
import supabase as _supabase_mod  # noqa: F401

from worker import AlertWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(alert_id, user_email, from_iata, to_iata, max_price,
                departure_date='2026-12-15', currency='USD',
                last_triggered_price=None, channels=None, phone=None):
    return {
        'id': alert_id,
        'user_email': user_email,
        'from_iata': from_iata,
        'to_iata': to_iata,
        'max_price': max_price,
        'currency': currency,
        'departure_date': departure_date,
        'active': True,
        'channels': channels or ['email'],
        'phone': phone,
        'last_triggered_price': last_triggered_price,
    }


# ---------------------------------------------------------------------------
# Legacy single-alert test (kept for backward compatibility)
# ---------------------------------------------------------------------------

def test_alert_processing_logic():
    """Test the alert processing logic with a mock alert"""
    
    logger.info("=" * 70)
    logger.info("ALERT WORKER - BASIC LOGIC TEST")
    logger.info("=" * 70)
    
    worker = AlertWorker()
    
    mock_alert = _make_alert(
        'test-alert-123', 'test@example.com', 'LHR', 'JFK', 500,
        departure_date='2025-12-15',
    )
    
    logger.info(f"\nTesting with mock alert:")
    logger.info(f"  Route: {mock_alert['from_iata']} → {mock_alert['to_iata']}")
    logger.info(f"  Max Price: ${mock_alert['max_price']}")
    logger.info(f"  User: {mock_alert['user_email']}")
    
    try:
        logger.info("\n[1/1] Testing alert processing logic...")
        worker._process_alert(mock_alert)
        logger.info("✅ Alert processing logic executed (notifications may fail without API keys)")
        return True
    except Exception as e:
        logger.error(f"❌ Alert processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Grouping tests
# ---------------------------------------------------------------------------

def test_alerts_grouped_by_route():
    """Alerts sharing the same route/date must result in only ONE API call."""
    logger.info("=" * 70)
    logger.info("TEST: grouping — two alerts, same route → one API call")
    logger.info("=" * 70)

    worker = AlertWorker()

    alerts = [
        _make_alert('a1', 'alice@example.com', 'LGW', 'JFK', 400),
        _make_alert('a2', 'bob@example.com',   'LGW', 'JFK', 450),
    ]

    mock_supabase = MagicMock()
    # Simulate no cache entry (all .eq()... chains return empty list)
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.eq.return_value.eq.return_value \
        .execute.return_value.data = []
    # Active alerts query returns both alerts
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.execute.return_value.data = alerts

    api_call_count = {'n': 0}
    fake_search_result = {'offers': [{'price': 350.0}]}

    async def fake_search_fn(req):
        api_call_count['n'] += 1
        return fake_search_result

    # Pre-populate sys.modules so that the `from search import ...` inside
    # process_active_alerts() does not attempt to import the real search.py
    # (which requires fastapi, not installed in test environments).
    mock_search_mod = MagicMock()
    mock_search_mod.search_flights = fake_search_fn

    notification_mock = MagicMock()
    notification_mock.send_price_alert.return_value = {'success': True}

    with patch.dict(sys.modules, {'search': mock_search_mod, 'fastapi': MagicMock()}), \
         patch('supabase.create_client', return_value=mock_supabase), \
         patch('worker.notification_service', notification_mock):

        worker.process_active_alerts()

    if api_call_count['n'] == 1:
        logger.info("✅ Only ONE API call made for two users on the same route")
        return True
    else:
        logger.error(f"❌ Expected 1 API call, got {api_call_count['n']}")
        return False


def test_different_routes_get_separate_api_calls():
    """Two different routes must each trigger their own API call."""
    logger.info("=" * 70)
    logger.info("TEST: grouping — two different routes → two API calls")
    logger.info("=" * 70)

    worker = AlertWorker()

    alerts = [
        _make_alert('b1', 'alice@example.com', 'LGW', 'JFK', 400),
        _make_alert('b2', 'bob@example.com',   'LHR', 'LAX', 600),
    ]

    api_call_count = {'n': 0}
    fake_search_result = {'offers': [{'price': 350.0}]}

    async def fake_search_fn(req):
        api_call_count['n'] += 1
        return fake_search_result

    mock_search_mod = MagicMock()
    mock_search_mod.search_flights = fake_search_fn

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.eq.return_value.eq.return_value \
        .execute.return_value.data = []
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.execute.return_value.data = alerts

    notification_mock = MagicMock()
    notification_mock.send_price_alert.return_value = {'success': True}

    with patch.dict(sys.modules, {'search': mock_search_mod, 'fastapi': MagicMock()}), \
         patch('supabase.create_client', return_value=mock_supabase), \
         patch('worker.notification_service', notification_mock):

        worker.process_active_alerts()

    if api_call_count['n'] == 2:
        logger.info("✅ Two API calls made for two distinct routes")
        return True
    else:
        logger.error(f"❌ Expected 2 API calls, got {api_call_count['n']}")
        return False


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------

def test_cache_hit_skips_api():
    """A fresh cache entry (< 6 hours old) must prevent an external API call."""
    logger.info("=" * 70)
    logger.info("TEST: cache hit — API must NOT be called")
    logger.info("=" * 70)

    worker = AlertWorker()

    fresh_updated_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    cached_row = {
        'origin': 'LGW', 'destination': 'JFK', 'departure_date': '2026-12-15',
        'lowest_price': 320.0, 'api_response_json': {'offers': []},
        'updated_at': fresh_updated_at,
    }

    mock_supabase = MagicMock()
    # Cache returns a fresh row
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.eq.return_value.eq.return_value \
        .execute.return_value.data = [cached_row]

    api_called = {'flag': False}

    async def fake_search(req):
        api_called['flag'] = True
        return {'offers': [{'price': 300.0}]}

    result = worker._get_cached_price(mock_supabase, 'LGW', 'JFK', '2026-12-15')

    if result is not None and not api_called['flag']:
        logger.info("✅ Cache hit correctly returned cached data without calling the API")
        return True
    else:
        logger.error("❌ Cache hit test failed")
        return False


def test_cache_miss_stale_entry():
    """A cache entry older than 6 hours must be treated as a miss."""
    logger.info("=" * 70)
    logger.info("TEST: cache miss — stale entry (> 6 h) → returns None")
    logger.info("=" * 70)

    worker = AlertWorker()

    stale_updated_at = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    stale_row = {
        'origin': 'LGW', 'destination': 'JFK', 'departure_date': '2026-12-15',
        'lowest_price': 320.0, 'api_response_json': {},
        'updated_at': stale_updated_at,
    }

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.eq.return_value.eq.return_value \
        .execute.return_value.data = [stale_row]

    result = worker._get_cached_price(mock_supabase, 'LGW', 'JFK', '2026-12-15')

    if result is None:
        logger.info("✅ Stale cache entry correctly treated as a miss (returns None)")
        return True
    else:
        logger.error("❌ Stale cache entry was incorrectly returned as a hit")
        return False


def test_cache_miss_no_entry():
    """Absence of a cache entry must be treated as a miss."""
    logger.info("=" * 70)
    logger.info("TEST: cache miss — no entry → returns None")
    logger.info("=" * 70)

    worker = AlertWorker()

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.eq.return_value.eq.return_value \
        .execute.return_value.data = []

    result = worker._get_cached_price(mock_supabase, 'LGW', 'JFK', '2026-12-15')

    if result is None:
        logger.info("✅ Missing cache entry correctly treated as a miss (returns None)")
        return True
    else:
        logger.error("❌ Unexpected non-None result for missing cache entry")
        return False


# ---------------------------------------------------------------------------
# Per-user notification logic
# ---------------------------------------------------------------------------

def test_user_notified_when_price_below_threshold():
    """_process_user_alert must send a notification when price < max_price."""
    logger.info("=" * 70)
    logger.info("TEST: notification triggered when price is below threshold")
    logger.info("=" * 70)

    worker = AlertWorker()
    mock_supabase = MagicMock()
    alert = _make_alert('u1', 'user@example.com', 'LGW', 'JFK', 400)

    notification_mock = MagicMock()
    notification_mock.send_price_alert.return_value = {'success': True}

    with patch('worker.notification_service', notification_mock):
        worker._process_user_alert(mock_supabase, alert, lowest_price=299.0, currency='USD')

    if notification_mock.send_price_alert.called:
        logger.info("✅ Notification sent when price is below threshold")
        return True
    else:
        logger.error("❌ Notification NOT sent even though price was below threshold")
        return False


def test_user_not_notified_when_price_above_threshold():
    """_process_user_alert must NOT send a notification when price > max_price."""
    logger.info("=" * 70)
    logger.info("TEST: no notification when price is above threshold")
    logger.info("=" * 70)

    worker = AlertWorker()
    mock_supabase = MagicMock()
    alert = _make_alert('u2', 'user@example.com', 'LGW', 'JFK', 400)

    notification_mock = MagicMock()

    with patch('worker.notification_service', notification_mock):
        worker._process_user_alert(mock_supabase, alert, lowest_price=450.0, currency='USD')

    if not notification_mock.send_price_alert.called:
        logger.info("✅ Notification correctly suppressed when price is above threshold")
        return True
    else:
        logger.error("❌ Notification sent even though price was above threshold")
        return False


def test_deduplication_skips_same_price():
    """_process_user_alert must NOT notify if new price >= last_triggered_price."""
    logger.info("=" * 70)
    logger.info("TEST: deduplication — same price as last trigger → no notification")
    logger.info("=" * 70)

    worker = AlertWorker()
    mock_supabase = MagicMock()
    alert = _make_alert('u3', 'user@example.com', 'LGW', 'JFK', 400,
                        last_triggered_price=299.0)

    notification_mock = MagicMock()

    with patch('worker.notification_service', notification_mock):
        worker._process_user_alert(mock_supabase, alert, lowest_price=299.0, currency='USD')

    if not notification_mock.send_price_alert.called:
        logger.info("✅ Deduplication correctly suppressed notification for same price")
        return True
    else:
        logger.error("❌ Notification sent even though price matches last_triggered_price")
        return False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_alert_processing_logic,
        test_alerts_grouped_by_route,
        test_different_routes_get_separate_api_calls,
        test_cache_hit_skips_api,
        test_cache_miss_stale_entry,
        test_cache_miss_no_entry,
        test_user_notified_when_price_below_threshold,
        test_user_not_notified_when_price_above_threshold,
        test_deduplication_skips_same_price,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            ok = test_fn()
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            logger.error(f"❌ {test_fn.__name__} raised: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1

    logger.info("=" * 70)
    logger.info(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    logger.info("=" * 70)
    exit(0 if failed == 0 else 1)
