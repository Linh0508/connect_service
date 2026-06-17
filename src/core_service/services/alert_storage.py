"""
Alert Storage - Ghi alerts vào database
"""

import logging
from datetime import datetime
from src.core_service.database import DatabaseManager
from src.core_service.models import AlertEvent

logger = logging.getLogger(__name__)


class AlertStorage:
    def __init__(self):
        self.db = DatabaseManager()
    
    async def save_alert(self, alert: AlertEvent) -> bool:
        """Lưu alert vào bảng alerts"""
        try:
            await self.db.execute("""
                INSERT INTO alerts (alert_id, event_id, severity, user_id, gate_id, 
                                   alert_details, created_at)
                VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, $6)
            """, str(alert.eventId), alert.severity, alert.userId, 
               alert.gateId, alert.alertDetails, datetime.now())
            
            logger.info(f"Alert saved: {alert.eventId} - {alert.severity}")
            return True
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
            return False