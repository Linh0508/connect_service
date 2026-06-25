"""
Alert Storage - Ghi alerts vào database
"""

import logging
from datetime import datetime
from src.core_service.database import DatabaseManager
from src.core_service.models import AlertEvent
import json

logger = logging.getLogger(__name__)


class AlertStorage:
    def __init__(self):
        self.db = DatabaseManager()
    
    async def save_alert(self, alert: AlertEvent) -> bool:
        """Lưu alert vào bảng alerts"""
        try:
            # ✅ SỬA: dùng event_id thay vì eventId
            event_id = str(alert.event_id) if alert.event_id else str(alert.alert_id)
            
            await self.db.execute("""
                INSERT INTO alerts (alert_id, event_id, severity, user_id, gate_id, 
                                   alert_details, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, 
                str(alert.alert_id),          # alert_id
                event_id,                      # event_id
                alert.severity.value,          # severity
                "SYSTEM",                      # user_id
                alert.details.get("location", "UNKNOWN") if alert.details else "UNKNOWN",  # gate_id
                json.dumps(alert.details),     # alert_details
                alert.timestamp or datetime.now()  # created_at
            )
            
            logger.info(f"Alert saved: {alert.alert_id} - {alert.severity.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
            return False
    
    async def get_alerts(self, limit: int = 50, severity: str = None) -> list:
        """Lấy danh sách alerts từ database"""
        if severity:
            return await self.db.fetch("""
                SELECT * FROM alerts 
                WHERE severity = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, severity, limit)
        return await self.db.fetch("""
            SELECT * FROM alerts 
            ORDER BY created_at DESC 
            LIMIT $1
        """, limit)