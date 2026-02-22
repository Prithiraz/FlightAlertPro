"""System check endpoint for verifying all components"""
from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["systemcheck"])


@router.get("/systemcheck")
async def system_check() -> Dict[str, Any]:
    """
    Run system checks for all major components.
    Returns status of airports, airlines, currency, search, stripe, and alerts.
    """
    checks = {}
    overall_ok = True

    # Check 1: Airports metadata
    try:
        from metadata import AIRPORTS_ALL
        airport_count = len(AIRPORTS_ALL)
        if airport_count > 0:
            checks['airports'] = {
                'status': 'pass',
                'message': f'Found {airport_count} airports',
                'details': f'Metadata loaded successfully'
            }
        else:
            checks['airports'] = {
                'status': 'fail',
                'message': 'No airports found',
                'details': 'Metadata may not be loaded'
            }
            overall_ok = False
    except Exception as e:
        checks['airports'] = {
            'status': 'fail',
            'message': 'Airport check failed',
            'details': str(e)
        }
        overall_ok = False

    # Check 2: Airlines metadata
    try:
        from metadata import AIRLINES
        airline_count = len(AIRLINES)
        if airline_count > 0:
            checks['airlines'] = {
                'status': 'pass',
                'message': f'Found {airline_count} airlines',
                'details': f'Metadata loaded successfully'
            }
        else:
            checks['airlines'] = {
                'status': 'fail',
                'message': 'No airlines found',
                'details': 'Metadata may not be loaded'
            }
            overall_ok = False
    except Exception as e:
        checks['airlines'] = {
            'status': 'fail',
            'message': 'Airline check failed',
            'details': str(e)
        }
        overall_ok = False

    # Check 3: Currency conversion
    try:
        from currency_service import currency_service
        result = currency_service.convert(100, 'USD', 'EUR')
        if result and result != 100:
            checks['currency'] = {
                'status': 'pass',
                'message': 'Currency conversion works',
                'details': f'100 USD = {result:.2f} EUR'
            }
        else:
            checks['currency'] = {
                'status': 'fail',
                'message': 'Currency conversion failed',
                'details': 'No conversion occurred'
            }
            overall_ok = False
    except Exception as e:
        checks['currency'] = {
            'status': 'fail',
            'message': 'Currency check failed',
            'details': str(e)
        }
        overall_ok = False

    # Check 4: Search endpoint (test with sample data)
    try:
        from duffel_service import duffel_service
        from aerodatabox_service import aerodatabox_service
        from airscraper_service import airscraper_service

        enabled_providers = []
        if duffel_service.enabled:
            enabled_providers.append('duffel')
        if aerodatabox_service.enabled:
            enabled_providers.append('aerodatabox')
        if airscraper_service.enabled:
            enabled_providers.append('airscraper')

        if enabled_providers:
            checks['search'] = {
                'status': 'pass',
                'message': f'Search available with {len(enabled_providers)} provider(s)',
                'details': f'Providers: {", ".join(enabled_providers)}'
            }
        else:
            checks['search'] = {
                'status': 'fail',
                'message': 'No search providers configured',
                'details': 'Configure at least one provider (Duffel/RapidAPI)'
            }
            overall_ok = False
    except Exception as e:
        checks['search'] = {
            'status': 'fail',
            'message': 'Search check failed',
            'details': str(e)
        }
        overall_ok = False

    # Check 5: Stripe
    try:
        import stripe
        stripe_key = os.getenv('STRIPE_SECRET_KEY')

        if stripe_key:
            stripe.api_key = stripe_key
            try:
                # Test creating a checkout session (don't actually charge)
                test_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': 'System Check Test',
                            },
                            'unit_amount': 1000,
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url='https://example.com/success',
                    cancel_url='https://example.com/cancel',
                )

                if test_session and test_session.id:
                    checks['stripe'] = {
                        'status': 'pass',
                        'message': 'Stripe configured and working',
                        'details': f'Test session created: {test_session.id[:20]}...'
                    }
                else:
                    checks['stripe'] = {
                        'status': 'fail',
                        'message': 'Stripe session creation failed',
                        'details': 'Could not create test session'
                    }
                    overall_ok = False
            except stripe.error.StripeError as se:
                checks['stripe'] = {
                    'status': 'fail',
                    'message': 'Stripe API error',
                    'details': str(se)
                }
                overall_ok = False
        else:
            checks['stripe'] = {
                'status': 'skipped',
                'message': 'Stripe not configured',
                'details': 'STRIPE_SECRET_KEY not set'
            }
    except Exception as e:
        checks['stripe'] = {
            'status': 'fail',
            'message': 'Stripe check failed',
            'details': str(e)
        }
        overall_ok = False

    # Check 6: Alerts (database check)
    try:
        from config import config
        test_user = os.getenv('SYSTEMCHECK_TEST_USER')

        if config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            if test_user:
                # Attempt to create a test alert
                from supabase import create_client
                supabase = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)

                test_alert = {
                    'user_email': test_user,
                    'from_iata': 'LAX',
                    'to_iata': 'JFK',
                    'max_price': 999.99,
                    'currency': 'USD',
                    'notification_channels': ['email'],
                    'active': True
                }

                result = supabase.table('price_alerts').insert(test_alert).execute()

                if result.data:
                    alert_id = result.data[0].get('id')
                    # Clean up test alert
                    supabase.table('price_alerts').delete().eq('id', alert_id).execute()

                    checks['alerts'] = {
                        'status': 'pass',
                        'message': 'Alert system works',
                        'details': f'Created and deleted test alert'
                    }
                else:
                    checks['alerts'] = {
                        'status': 'fail',
                        'message': 'Alert creation failed',
                        'details': 'Could not insert test alert'
                    }
                    overall_ok = False
            else:
                checks['alerts'] = {
                    'status': 'skipped',
                    'message': 'Alert test skipped',
                    'details': 'Set SYSTEMCHECK_TEST_USER to enable'
                }
        else:
            checks['alerts'] = {
                'status': 'fail',
                'message': 'Database not configured',
                'details': 'Supabase URL or anon key missing'
            }
            overall_ok = False
    except Exception as e:
        checks['alerts'] = {
            'status': 'fail',
            'message': 'Alert check failed',
            'details': str(e)
        }
        overall_ok = False

    return {
        'ok': overall_ok,
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat()
    }
