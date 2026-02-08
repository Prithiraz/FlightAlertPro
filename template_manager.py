import logging
from typing import Dict, List, Optional
import re

logger = logging.getLogger(__name__)

class TemplateManager:
    def __init__(self):
        self.templates = {}

    def add_template(self, name: str, channel: str, body: str, required_params: List[str]) -> bool:
        if not self._validate_template(body, required_params):
            logger.error(f"Template validation failed for {name}")
            return False

        self.templates[name] = {
            'channel': channel,
            'body': body,
            'required_params': required_params
        }

        logger.info(f"Template added: {name}")
        return True

    def _validate_template(self, body: str, required_params: List[str]) -> bool:
        placeholders = re.findall(r'\{(\w+)\}', body)

        for param in required_params:
            if param not in placeholders:
                logger.error(f"Required param {param} not in template")
                return False

        return True

    def render(self, name: str, params: Dict) -> Optional[str]:
        if name not in self.templates:
            logger.error(f"Template {name} not found")
            return None

        template = self.templates[name]

        for param in template['required_params']:
            if param not in params:
                logger.error(f"Missing required param {param}")
                return None

        try:
            return template['body'].format(**params)
        except Exception as e:
            logger.error(f"Template render error: {str(e)}")
            return None

template_manager = TemplateManager()

template_manager.add_template(
    'price_drop_alert',
    'whatsapp',
    'Price Drop Alert!\n\nRoute: {route}\nOld: £{old_price}\nNew: £{new_price}\nSave: £{savings}\n\nBook now!',
    ['route', 'old_price', 'new_price', 'savings']
)

template_manager.add_template(
    'price_drop_email',
    'email',
    'Flight Price Drop: {route}\n\nGood news! The price for your watched route has dropped.\n\nOld Price: £{old_price}\nNew Price: £{new_price}\nYou Save: £{savings}\n\nBook now before prices increase!',
    ['route', 'old_price', 'new_price', 'savings']
)
