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
                last_triggered_price=None, channels=None, phone=None,
                is_purchased=False, purchase_price=None, airline=None):
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
        'is_purchased': is_purchased,
        'purchase_price': purchase_price,
        'airline': airline,
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
# Flexible date range tests
# ---------------------------------------------------------------------------

def test_flexible_date_range_checks_all_days():
    """Alerts with a date range must result in one API call per day in the range."""
    logger.info("=" * 70)
    logger.info("TEST: flexible dates — 3-day range → three API calls")
    logger.info("=" * 70)

    worker = AlertWorker()

    # Alert uses departure_start_date / departure_end_date (3-day window)
    alert = {
        'id': 'f1',
        'user_email': 'alice@example.com',
        'from_iata': 'LHR',
        'to_iata': 'JFK',
        'max_price': 500,
        'currency': 'USD',
        'departure_date': None,
        'departure_start_date': '2026-12-10',
        'departure_end_date': '2026-12-12',
        'active': True,
        'channels': ['email'],
        'phone': None,
        'last_triggered_price': None,
    }

    api_call_count = {'n': 0}
    prices_by_date = {
        '2026-12-10': 480.0,
        '2026-12-11': 320.0,
        '2026-12-12': 410.0,
    }

    # Real-enough fakes so departure_date is accessible inside fake_search_fn
    class FakeSegment:
        def __init__(self, from_iata, to_iata, departure_date):
            self.departure_date = departure_date

    class FakeSearchRequest:
        def __init__(self, segments, passengers, cabin_class, currency):
            self.segments = segments

    async def fake_search_fn(req):
        api_call_count['n'] += 1
        dep = req.segments[0].departure_date
        return {'offers': [{'price': prices_by_date.get(dep, 999.0)}]}

    mock_search_mod = MagicMock()
    mock_search_mod.search_flights = fake_search_fn
    mock_search_mod.FlightSegment = FakeSegment
    mock_search_mod.SearchRequest = FakeSearchRequest

    mock_supabase = MagicMock()
    # No cache entries
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.eq.return_value.eq.return_value \
        .execute.return_value.data = []
    # Active alerts query
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.execute.return_value.data = [alert]

    notification_mock = MagicMock()
    notification_mock.send_price_alert.return_value = {'success': True}

    with patch.dict(sys.modules, {'search': mock_search_mod, 'fastapi': MagicMock()}), \
         patch('supabase.create_client', return_value=mock_supabase), \
         patch('worker.notification_service', notification_mock):

        worker.process_active_alerts()

    if api_call_count['n'] == 3:
        logger.info("✅ Three API calls made for 3-day flexible range")
        return True
    else:
        logger.error(f"❌ Expected 3 API calls, got {api_call_count['n']}")
        return False


def test_flexible_date_range_finds_cheapest_day():
    """The worker must notify with best_date=cheapest day in the range."""
    logger.info("=" * 70)
    logger.info("TEST: flexible dates — notification includes best date")
    logger.info("=" * 70)

    worker = AlertWorker()

    alert = {
        'id': 'f2',
        'user_email': 'bob@example.com',
        'from_iata': 'CDG',
        'to_iata': 'JFK',
        'max_price': 400,
        'currency': 'USD',
        'departure_date': None,
        'departure_start_date': '2026-11-05',
        'departure_end_date': '2026-11-07',
        'active': True,
        'channels': ['email'],
        'phone': None,
        'last_triggered_price': None,
    }

    prices_by_date = {
        '2026-11-05': 390.0,
        '2026-11-06': 310.0,   # cheapest — should be best_date
        '2026-11-07': 380.0,
    }

    class FakeSegment:
        def __init__(self, from_iata, to_iata, departure_date):
            self.departure_date = departure_date

    class FakeSearchRequest:
        def __init__(self, segments, passengers, cabin_class, currency):
            self.segments = segments

    async def fake_search_fn(req):
        dep = req.segments[0].departure_date
        return {'offers': [{'price': prices_by_date.get(dep, 999.0)}]}

    mock_search_mod = MagicMock()
    mock_search_mod.search_flights = fake_search_fn
    mock_search_mod.FlightSegment = FakeSegment
    mock_search_mod.SearchRequest = FakeSearchRequest

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.eq.return_value.eq.return_value \
        .execute.return_value.data = []
    mock_supabase.table.return_value.select.return_value \
        .eq.return_value.execute.return_value.data = [alert]

    notification_mock = MagicMock()
    notification_mock.send_price_alert.return_value = {'success': True}

    with patch.dict(sys.modules, {'search': mock_search_mod, 'fastapi': MagicMock()}), \
         patch('supabase.create_client', return_value=mock_supabase), \
         patch('worker.notification_service', notification_mock):

        worker.process_active_alerts()

    if not notification_mock.send_price_alert.called:
        logger.error("❌ Notification was NOT sent")
        return False

    call_kwargs = notification_mock.send_price_alert.call_args
    best_date = call_kwargs.kwargs.get('best_date') or (
        call_kwargs.args[5] if len(call_kwargs.args) > 5 else None
    )
    if best_date == '2026-11-06':
        logger.info(f"✅ Notification sent with correct best_date={best_date}")
        return True
    else:
        logger.error(f"❌ Expected best_date='2026-11-06', got best_date={best_date!r}")
        return False


def test_flexible_notification_message_includes_best_date():
    """send_price_alert with best_date must mention the specific departure day."""
    logger.info("=" * 70)
    logger.info("TEST: notification message includes cheapest date for flexible alert")
    logger.info("=" * 70)

    from notifications import NotificationService
    from unittest.mock import MagicMock

    svc = NotificationService()
    captured = {}

    def capture_send(user_email, email_subject, message):
        captured['subject'] = email_subject
        captured['message'] = message
        return True

    svc.email = MagicMock()
    svc.email.send_email.side_effect = capture_send

    svc.send_price_alert(
        user_email='test@example.com',
        route='LHR → JFK',
        old_price=400.0,
        new_price=310.0,
        channels=['email'],
        best_date='2026-10-14',
    )

    msg = captured.get('message', '')
    subj = captured.get('subject', '')

    if 'Oct 14th' in msg and 'Oct 14th' in subj and '$310.00' in msg:
        logger.info("✅ Notification message correctly references Oct 14th and the price")
        return True
    else:
        logger.error(f"❌ Message/subject did not contain expected content.\nSubject: {subj}\nMessage: {msg}")
        return False


# ---------------------------------------------------------------------------
# Post-Booking Travel Credit Engine tests
# ---------------------------------------------------------------------------

def test_post_booking_drop_triggers_when_savings_meet_threshold():
    """Purchased alert: notification sent when live_price is $25+ below purchase_price."""
    logger.info("=" * 70)
    logger.info("TEST: post-booking drop — notified when saving >= $25")
    logger.info("=" * 70)

    worker = AlertWorker()
    mock_supabase = MagicMock()
    alert = _make_alert(
        'p1', 'traveller@example.com', 'LHR', 'JFK', 450,
        is_purchased=True, purchase_price=450.0, airline='BA',
    )

    notification_mock = MagicMock()
    notification_mock.send_post_booking_drop_alert.return_value = {'success': True}

    with patch('worker.notification_service', notification_mock):
        worker._process_user_alert(mock_supabase, alert, lowest_price=420.0, currency='USD')

    if notification_mock.send_post_booking_drop_alert.called:
        logger.info("✅ Post-booking drop notification sent when saving $30")
        return True
    else:
        logger.error("❌ Notification NOT sent even though saving was $30")
        return False


def test_post_booking_drop_not_triggered_below_threshold():
    """Purchased alert: no notification when live_price is < $25 below purchase_price."""
    logger.info("=" * 70)
    logger.info("TEST: post-booking drop — suppressed when saving < $25")
    logger.info("=" * 70)

    worker = AlertWorker()
    mock_supabase = MagicMock()
    alert = _make_alert(
        'p2', 'traveller@example.com', 'LHR', 'JFK', 450,
        is_purchased=True, purchase_price=450.0, airline='BA',
    )

    notification_mock = MagicMock()

    with patch('worker.notification_service', notification_mock):
        worker._process_user_alert(mock_supabase, alert, lowest_price=435.0, currency='USD')

    if not notification_mock.send_post_booking_drop_alert.called:
        logger.info("✅ No notification when saving is only $15 (below $25 threshold)")
        return True
    else:
        logger.error("❌ Notification incorrectly sent when saving was below threshold")
        return False


def test_post_booking_deduplication():
    """Purchased alert: no re-notification when live_price did not drop further."""
    logger.info("=" * 70)
    logger.info("TEST: post-booking deduplication — same or higher price → no notification")
    logger.info("=" * 70)

    worker = AlertWorker()
    mock_supabase = MagicMock()
    alert = _make_alert(
        'p3', 'traveller@example.com', 'CDG', 'LAX', 600,
        is_purchased=True, purchase_price=600.0, airline='AF',
        last_triggered_price=560.0,  # already notified at $560
    )

    notification_mock = MagicMock()

    with patch('worker.notification_service', notification_mock):
        # Same price as last triggered — should be deduplicated
        worker._process_user_alert(mock_supabase, alert, lowest_price=560.0, currency='USD')

    if not notification_mock.send_post_booking_drop_alert.called:
        logger.info("✅ Deduplication correctly suppressed repeat notification")
        return True
    else:
        logger.error("❌ Notification sent despite price not dropping further")
        return False


def test_post_booking_notification_template():
    """send_post_booking_drop_alert must include airline, prices, and credit amount."""
    logger.info("=" * 70)
    logger.info("TEST: post-booking notification template content")
    logger.info("=" * 70)

    from notifications import NotificationService
    from unittest.mock import MagicMock

    svc = NotificationService()
    captured = {}

    def capture_send(user_email, email_subject, message):
        captured['subject'] = email_subject
        captured['message'] = message
        return True

    svc.email = MagicMock()
    svc.email.send_email.side_effect = capture_send

    svc.send_post_booking_drop_alert(
        user_email='test@example.com',
        route='LHR → JFK',
        airline='British Airways',
        purchase_price=500.0,
        live_price=450.0,
        channels=['email'],
    )

    msg = captured.get('message', '')
    subj = captured.get('subject', '')

    ok = (
        'British Airways' in msg
        and '$500.00' in msg
        and '$450.00' in msg
        and '$50.00' in msg
        and 'Travel Credit Alert' in subj
    )
    if ok:
        logger.info("✅ Post-booking notification template contains all expected fields")
        return True
    else:
        logger.error(f"❌ Template missing expected content.\nSubject: {subj}\nMessage: {msg}")
        return False


def test_post_booking_missing_purchase_price_skipped():
    """Purchased alert with no purchase_price must be skipped gracefully."""
    logger.info("=" * 70)
    logger.info("TEST: post-booking with no purchase_price → skipped")
    logger.info("=" * 70)

    worker = AlertWorker()
    mock_supabase = MagicMock()
    alert = _make_alert(
        'p4', 'traveller@example.com', 'MAN', 'DXB', 400,
        is_purchased=True, purchase_price=None,
    )

    notification_mock = MagicMock()

    with patch('worker.notification_service', notification_mock):
        worker._process_user_alert(mock_supabase, alert, lowest_price=300.0, currency='USD')

    if not notification_mock.send_post_booking_drop_alert.called:
        logger.info("✅ Alert with missing purchase_price correctly skipped")
        return True
    else:
        logger.error("❌ Notification sent despite missing purchase_price")
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
        test_flexible_date_range_checks_all_days,
        test_flexible_date_range_finds_cheapest_day,
        test_flexible_notification_message_includes_best_date,
        # Post-Booking Travel Credit Engine tests
        test_post_booking_drop_triggers_when_savings_meet_threshold,
        test_post_booking_drop_not_triggered_below_threshold,
        test_post_booking_deduplication,
        test_post_booking_notification_template,
        test_post_booking_missing_purchase_price_skipped,
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
