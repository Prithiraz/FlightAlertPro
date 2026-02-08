import logging
from logging.handlers import RotatingFileHandler
import os
from config import config

def setup_logging():
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                'logs/app.log',
                maxBytes=10*1024*1024,
                backupCount=7
            )
        ]
    )

    os.makedirs('logs', exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at {log_level} level")
