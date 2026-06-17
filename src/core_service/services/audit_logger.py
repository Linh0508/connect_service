from src.core_service.database import DatabaseManager
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AuditLogger:
    def __init__(self):
        self.db = DatabaseManager()
    
    async def log(self, decision_id: str, gate_id: str, card_id: str,
                  decision: str, reason_code: str = None,
                  latency_ms: int = 0, correlation_id: str = None):
        """Ghi log audit vào database"""
        masked_card = f"{card_id[:4]}****{card_id[-4:]}" if len(card_id) > 8 else "****"
        
        try:
            await self.db.execute("""
                INSERT INTO audit_logs (decision_id, gate_id, card_id, card_id_masked,
                                       decision, reason_code, latency_ms, correlation_id, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, decision_id, gate_id, card_id, masked_card, decision,
               reason_code, latency_ms, correlation_id, datetime.now())
            
            logger.info(f"Audit logged: {decision_id} - {decision}")    
            return True
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
            return False
    
    async def get_by_id(self, decision_id: str) -> dict:
        return await self.db.fetch_one(
            "SELECT * FROM audit_logs WHERE decision_id = $1", decision_id
        )
    
    async def get_logs(self, from_date, to_date, limit):
        if from_date and to_date:
            return await self.db.fetch("""
                SELECT * FROM audit_logs 
                WHERE timestamp BETWEEN $1 AND $2 
                ORDER BY timestamp DESC 
                LIMIT $3
            """, from_date, to_date, limit)
        return await self.db.fetch("""
            SELECT * FROM audit_logs 
            ORDER BY timestamp DESC 
            LIMIT $1
        """, limit)