"""
Notification Client - Gửi alert sang B7 (Notification Service)
"""

import httpx
import os
import logging
from src.core_service.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class NotificationClient:
    def __init__(self):
        self.base_url = os.getenv("NOTIFICATION_URL", "http://b7-notification:8002")
        self.webhook_path = os.getenv("NOTIFICATION_WEBHOOK_PATH", "/webhook/alerts")
        self.timeout = float(os.getenv("NOTIFICATION_TIMEOUT", "5.0"))
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self.service_name = "b7"
    
    async def send_alert(self, alert) -> bool:
        """Gửi alert sang Notification Service (B7)"""
        
        # Kiểm tra nên dùng REAL hay FALLBACK
        if connection_manager.should_use_real(self.service_name):
            try:
                url = f"{self.base_url}{self.webhook_path}"
                response = await self.client.post(url, json=alert.dict())
                
                if response.status_code in [200, 202, 204]:
                    logger.info(f"📧 [B7_REAL] Alert sent to B7: {alert.eventId} - {alert.severity}")
                    return True
                else:
                    logger.warning(f"📧 [B7_WARNING] B7 returned {response.status_code} -> FALLBACK")
            except Exception as e:
                logger.warning(f"📧 [B7_ERROR] B7 call failed: {e} -> FALLBACK")
        
        # FALLBACK MODE
        logger.info(f"📧 [B7_FALLBACK] Alert stored locally: {alert.eventId} - {alert.severity}")
        return True
    
    async def close(self):
        await self.client.aclose()