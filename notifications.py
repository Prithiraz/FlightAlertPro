import logging
from typing import List, Optional
from datetime import datetime
from ycloud_whatsapp import ycloud_whatsapp_service
from email_service import email_service
from telegram_service import telegram_service

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.whatsapp = ycloud_whatsapp_service
        self.email = email_service
        self.telegram = telegram_service

    def send_notification(self, user_email: str, message: str, channels: List[str],
                         subject: Optional[str] = None, phone: Optional[str] = None,
                         telegram_chat_id: Optional[str] = None) -> dict:

        results = {
            "sent": [],
            "failed": [],
            "timestamp": datetime.utcnow().isoformat()
        }

        if "whatsapp" in channels and phone:
            try:
                message_id = self.whatsapp.send_text(phone, message)
                if message_id:
                    results["sent"].append({
                        "channel": "whatsapp",
                        "message_id": message_id,
                        "provider": "ycloud"
                    })
                    logger.info(f"WhatsApp sent to {phone} via YCloud")
                else:
                    results["failed"].append({"channel": "whatsapp", "reason": "Service unavailable"})
            except Exception as e:
                logger.error(f"WhatsApp send failed: {str(e)}")
                results["failed"].append({"channel": "whatsapp", "reason": str(e)})

        if "email" in channels:
            try:
                email_subject = subject or "FlightAlertPro Notification"
                success = self.email.send_email(user_email, email_subject, message)
                if success:
                    results["sent"].append({"channel": "email", "to": user_email})
                    logger.info(f"Email sent to {user_email}")
                else:
                    results["failed"].append({"channel": "email", "reason": "Send failed"})
            except Exception as e:
                logger.error(f"Email send failed: {str(e)}")
                results["failed"].append({"channel": "email", "reason": str(e)})

        if "telegram" in channels and telegram_chat_id:
            try:
                success = self.telegram.send_message(telegram_chat_id, message)
                if success:
                    results["sent"].append({"channel": "telegram", "chat_id": telegram_chat_id})
                    logger.info(f"Telegram sent to {telegram_chat_id}")
                else:
                    results["failed"].append({"channel": "telegram", "reason": "Send failed"})
            except Exception as e:
                logger.error(f"Telegram send failed: {str(e)}")
                results["failed"].append({"channel": "telegram", "reason": str(e)})

        logger.info(f"Notification summary: {len(results['sent'])} sent, {len(results['failed'])} failed")

        return results

    def send_price_alert(self, user_email: str, route: str, old_price: float,
                        new_price: float, channels: List[str], **kwargs) -> dict:
        savings = old_price - new_price
        message = f"""🎉 Price Drop Alert!

Route: {route}
Old Price: ${old_price:.2f}
New Price: ${new_price:.2f}
You Save: ${savings:.2f}

Book now: https://flightalertpro.com/book"""

        subject = f"Price Drop: {route} - Save ${savings:.2f}"

        return self.send_notification(
            user_email=user_email,
            message=message,
            channels=channels,
            subject=subject,
            **kwargs
        )

notification_service = NotificationService()
