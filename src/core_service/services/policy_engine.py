"""
Policy Engine - Business logic for access control
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, time
import json
import logging
from src.core_service.database import DatabaseManager

logger = logging.getLogger(__name__)


class PolicyEngine:
    def __init__(self):
        self.db = DatabaseManager()
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def load_policies(self):
        """Load all policies from database (or use defaults)"""
        # Default policies for mock mode
        self.cache["POL_STUDENT_001"] = {
            "policyId": "POL_STUDENT_001",
            "name": "Student Access Policy - Lab Hours",
            "quotaPerDay": 5,
            "allowedTimeWindows": [{"start": "08:00:00", "end": "22:00:00"}],
            "allowedGateIds": ["LAB_01", "LAB_02", "LIB_01", "LOBBY_01"],
            "loaded_at": datetime.now()
        }
        
        self.cache["POL_STAFF_001"] = {
            "policyId": "POL_STAFF_001",
            "name": "Staff Access Policy - Extended Hours",
            "quotaPerDay": 10,
            "allowedTimeWindows": [{"start": "06:00:00", "end": "23:59:00"}],
            "allowedGateIds": ["LAB_01", "LAB_02", "LIB_01", "LOBBY_01", "OFFICE_01"],
            "loaded_at": datetime.now()
        }
        
        # Try to load from database if available
        try:
            policies = await self.db.fetch_all("SELECT * FROM policies")
            for policy in policies:
                policy_id = policy["policy_id"]
                time_windows = policy.get("allowed_time_windows")
                gate_ids = policy.get("allowed_gate_ids")
                
                if time_windows and isinstance(time_windows, str):
                    time_windows = json.loads(time_windows)
                if gate_ids and isinstance(gate_ids, str):
                    gate_ids = json.loads(gate_ids)
                
                self.cache[policy_id] = {
                    "policyId": policy_id,
                    "name": policy["name"],
                    "quotaPerDay": policy["quota_per_day"],
                    "allowedTimeWindows": time_windows or [{"start": "08:00:00", "end": "22:00:00"}],
                    "allowedGateIds": gate_ids or ["LAB_01", "LAB_02", "LIB_01", "LOBBY_01"],
                    "loaded_at": datetime.now()
                }
            logger.info(f"Loaded {len(self.cache)} policies")
        except Exception as e:
            logger.info(f"Using default policies (database not available): {e}")
    
    async def evaluate(self, card_id: str, gate_id: str) -> Dict[str, Any]:
        """Evaluate access policy for a card and gate"""
        result = {
            "allowed": True,
            "rules_triggered": [],
            "policy_id": "POL_STUDENT_001"
        }
        
        # Lấy policy từ cache
        policy = self.cache.get("POL_STUDENT_001", {})
        allowed_windows = policy.get("allowedTimeWindows", [{"start": "08:00:00", "end": "22:00:00"}])
        allowed_gates = policy.get("allowedGateIds", ["LAB_01", "LAB_02", "LIB_01", "LOBBY_01"])
        
        # Check time window
        current_time = datetime.now().time()
        
        within_window = False
        for window in allowed_windows:
            try:
                start_str = window.get("start", "08:00:00")
                end_str = window.get("end", "22:00:00")
                start = datetime.strptime(start_str, "%H:%M:%S").time()
                end = datetime.strptime(end_str, "%H:%M:%S").time()
                if start <= current_time <= end:
                    within_window = True
                    break
            except Exception:
                within_window = True
        
        if not within_window:
            result["allowed"] = False
            result["rules_triggered"].append("TIME_WINDOW_VIOLATION")
        
        # Check gate access
        if gate_id not in allowed_gates and "*" not in allowed_gates:
            result["allowed"] = False
            result["rules_triggered"].append("GATE_NOT_ALLOWED")
        
        return result
    
    async def get_policy(self, policy_id: str) -> Optional[Dict]:
        """Get policy by ID"""
        return self.cache.get(policy_id)
    
    async def invalidate_cache(self, policy_id: str):
        """Invalidate cache for a policy"""
        if policy_id in self.cache:
            del self.cache[policy_id]
            # Reload default
            await self.load_policies()
        logger.info(f"Cache invalidated for policy: {policy_id}")
