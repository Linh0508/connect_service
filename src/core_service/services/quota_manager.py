"""
Quota Manager - Daily quota management for cardholders
"""

from typing import Dict, Any
from datetime import date
import logging
from src.core_service.database import DatabaseManager

logger = logging.getLogger(__name__)


class QuotaManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.mock_storage: Dict[str, Dict[str, int]] = {}  # Mock storage for local test
    
    async def check_and_decrement(self, card_id: str) -> Dict[str, Any]:
        """Check remaining quota and decrement if available"""
        today = date.today().isoformat()
        key = f"{card_id}_{today}"
        
        # Check if database is disabled (mock mode)
        if self.db.disabled:
            # Mock mode - use in-memory storage
            if key not in self.mock_storage:
                self.mock_storage[key] = {"remaining": 5, "used": 0}
            
            before = self.mock_storage[key]["remaining"]
            
            if before > 0:
                self.mock_storage[key]["remaining"] -= 1
                self.mock_storage[key]["used"] += 1
            
            return {
                "before": before,
                "remaining": self.mock_storage[key]["remaining"],
                "used_today": self.mock_storage[key]["used"],
                "reset_at": f"{today}T00:00:00Z"
            }
        
        # Real database mode
        row = await self.db.fetch_one(
            "SELECT remaining_quota, used_today FROM quota_records WHERE card_id = $1 AND quota_date = $2",
            card_id, today
        )
        
        if row:
            remaining = row["remaining_quota"]
            used = row["used_today"]
        else:
            remaining = 5
            used = 0
            await self.db.execute(
                "INSERT INTO quota_records (card_id, quota_date, remaining_quota, used_today) VALUES ($1, $2, $3, $4)",
                card_id, today, remaining, used
            )
        
        before = remaining
        
        if remaining > 0:
            remaining -= 1
            used += 1
            await self.db.execute(
                "UPDATE quota_records SET remaining_quota = $1, used_today = $2 WHERE card_id = $3 AND quota_date = $4",
                remaining, used, card_id, today
            )
        
        return {
            "before": before,
            "remaining": remaining,
            "used_today": used,
            "reset_at": f"{today}T00:00:00Z"
        }
