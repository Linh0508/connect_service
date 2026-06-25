from src.core_service.database import DatabaseManager
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self):
        self.db = DatabaseManager()
        self.audit_logs: list = []  # Fallback storage
    
    async def log_decision(self, decision_id: str, service: str, event_type: str,
                          input_summary: Dict[str, Any], output_decision: str,
                          reason: str, severity: Optional[str] = None,
                          correlation_id: Optional[str] = None) -> bool:
        """
        Ghi log audit cho mọi quyết định của B6
        """
        log_entry = {
            "decision_id": decision_id,
            "timestamp": datetime.now().isoformat(),
            "service": service,
            "event_type": event_type,
            "input_summary": input_summary,
            "output_decision": output_decision,
            "reason": reason,
            "severity": severity,
            "correlation_id": correlation_id
        }
        
        # Lưu vào fallback storage
        self.audit_logs.append(log_entry)
        if len(self.audit_logs) > 1000:
            self.audit_logs.pop(0)
        
        try:
            await self.db.execute("""
                INSERT INTO audit_logs 
                (decision_id, timestamp, service, event_type, input_summary, 
                 output_decision, reason, severity, correlation_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, decision_id, datetime.now().isoformat(), service, event_type,
               json.dumps(input_summary), output_decision, reason, severity, correlation_id)
            
            logger.info(f"✅ Audit logged: {decision_id} - {output_decision}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to log audit: {e}")
            return False
    
    async def get_audit_logs(self, limit: int = 50, service: Optional[str] = None) -> list:
        """Lấy danh sách audit logs"""
        if service:
            return [log for log in self.audit_logs[-limit:] if log.get('service') == service]
        return self.audit_logs[-limit:]
    
    async def get_by_id(self, decision_id: str) -> Optional[Dict]:
        """Lấy audit log theo decision_id"""
        for log in self.audit_logs:
            if log.get('decision_id') == decision_id:
                return log
        return None
