"""
Simple test to verify alert worker logic
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, '/home/runner/work/FlightAlertPro')

import logging
from datetime import datetime
from backend.worker import AlertWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_alert_processing_logic():
    """Test the alert processing logic with a mock alert"""
    
    logger.info("=" * 70)
    logger.info("ALERT WORKER - BASIC LOGIC TEST")
    logger.info("=" * 70)
    
    # Create worker instance
    worker = AlertWorker()
    
    # Mock alert data
    mock_alert = {
        'id': 'test-alert-123',
        'user_email': 'test@example.com',
        'from_iata': 'LHR',
        'to_iata': 'JFK',
        'max_price': 500,
        'currency': 'USD',
        'departure_date': '2025-12-15',
        'active': True,
        'channels': ['email'],
        'phone': None,
        'last_triggered_price': None
    }
    
    logger.info(f"\nTesting with mock alert:")
    logger.info(f"  Route: {mock_alert['from_iata']} → {mock_alert['to_iata']}")
    logger.info(f"  Max Price: ${mock_alert['max_price']}")
    logger.info(f"  User: {mock_alert['user_email']}")
    
    # Test the processing logic (will fail to send notification due to missing API keys, but logic should work)
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

if __name__ == "__main__":
    result = test_alert_processing_logic()
    exit(0 if result else 1)
