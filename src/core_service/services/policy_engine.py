"""
Policy Engine - Business logic for access control và alert decision
Version: 2.2 - Sửa lỗi time window với timestamp
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import json
import logging
from collections import deque
from src.core_service.database import DatabaseManager
from src.core_service.models import Severity, AlertLevel

logger = logging.getLogger(__name__)


class PolicyEngine:
    def __init__(self):
        self.db = DatabaseManager()
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300
        
        self.window_duration = 120
        self.event_window: Dict[str, deque] = {}
        self.processed_alerts: Dict[str, datetime] = {}
        self.dedup_window = 300
        
        self.policies = {}
        self._load_default_policies()
    
    async def load_policies(self):
        self._load_default_policies()
        logger.info(f"✅ Loaded {len(self.policies)} policies")
        return self.policies
    
    def _load_default_policies(self):
        self.policies = {
            "POL_STUDENT_001": {
                "policyId": "POL_STUDENT_001",
                "name": "Student Access Policy - Lab Hours",
                "quotaPerDay": 5,
                "allowedTimeWindows": [{"start": "08:00:00", "end": "22:00:00"}],
                "allowedGateIds": ["LAB_01", "LAB_02", "LIB_01", "LOBBY_01"],
            },
            "POL_STAFF_001": {
                "policyId": "POL_STAFF_001",
                "name": "Staff Access Policy - Extended Hours",
                "quotaPerDay": 10,
                "allowedTimeWindows": [{"start": "06:00:00", "end": "23:59:00"}],
                "allowedGateIds": ["LAB_01", "LAB_02", "LIB_01", "LOBBY_01", "OFFICE_01"],
            },
            "POL_STAFF_002": {
                "policyId": "POL_STAFF_002",
                "name": "Staff Access Policy - All Areas",
                "quotaPerDay": 10,
                "allowedTimeWindows": [{"start": "00:00:00", "end": "23:59:59"}],
                "allowedGateIds": ["*"],
            }
        }

    # ============================================================
    # ACCESS POLICY - SỬA LỖI TIME WINDOW VỚI TIMESTAMP
    # ============================================================
    async def evaluate_access(self, card_id: str, gate_id: str, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Evaluate access policy for a card and gate"""
        result = {
            "allowed": True,
            "rules_triggered": [],
            "policy_id": "POL_STUDENT_001",
            "reason": "Access allowed"
        }
        
        # ✅ Xác định policy dựa trên card_id
        if card_id.startswith("STAFF"):
            policy_id = "POL_STAFF_002"
        else:
            policy_id = "POL_STUDENT_001"
        
        result["policy_id"] = policy_id
        policy = self.policies.get(policy_id, {})
        
        # ✅ Lấy time windows từ policy
        allowed_windows = policy.get("allowedTimeWindows", [{"start": "08:00:00", "end": "22:00:00"}])
        allowed_gates = policy.get("allowedGateIds", ["LAB_01", "LAB_02", "LIB_01", "LOBBY_01"])
        
        # ✅ SỬA: Dùng timestamp từ request nếu có, nếu không dùng current time
        if timestamp:
            check_time = timestamp.time()
        else:
            check_time = datetime.now().time()
        
        # ✅ Check time window
        within_window = False
        for window in allowed_windows:
            try:
                start_str = window.get("start", "08:00:00")
                end_str = window.get("end", "22:00:00")
                start = datetime.strptime(start_str, "%H:%M:%S").time()
                end = datetime.strptime(end_str, "%H:%M:%S").time()
                
                if start <= end:
                    within_window = start <= check_time <= end
                else:
                    # Qua midnight: 22:00-06:00
                    within_window = check_time >= start or check_time <= end
                
                if within_window:
                    break
            except Exception as e:
                logger.warning(f"Error parsing time window: {e}")
                within_window = True
        
        if not within_window:
            result["allowed"] = False
            result["rules_triggered"].append("TIME_WINDOW_VIOLATION")
            result["reason"] = f"Outside allowed time window (current: {check_time.strftime('%H:%M')}, allowed: {allowed_windows})"
            return result
        
        # ✅ Check gate access
        if "*" in allowed_gates:
            pass
        elif gate_id not in allowed_gates:
            result["allowed"] = False
            result["rules_triggered"].append("GATE_NOT_ALLOWED")
            result["reason"] = f"Gate {gate_id} not allowed for this policy"
        
        return result

    # ============================================================
    # ALERT POLICY
    # ============================================================
    async def should_create_alert(self, event_type: str, data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Severity]]:
        """Quyết định có tạo alert không"""
        
        if event_type == "sensor" and data.get("status") == "danger":
            alert_hash = f"sensor_{data.get('device_id')}_{data.get('timestamp')}"
            if not self._is_duplicate(alert_hash):
                return True, data.get("status", "sensor_danger"), Severity.CRITICAL
        
        if event_type == "sensor" and data.get("status") == "warning":
            alert_hash = f"sensor_warning_{data.get('device_id')}"
            if not self._is_duplicate(alert_hash):
                return True, "sensor_warning", Severity.HIGH
        
        if event_type == "access" and data.get("access_result") == "denied":
            denied_count = self._count_denied_access(data.get("uid"), window=60)
            if denied_count >= 3:
                alert_hash = f"access_repeated_{data.get('uid')}"
                if not self._is_duplicate(alert_hash):
                    return True, "repeated_access_denied", Severity.MEDIUM
        
        if event_type == "camera" and data.get("unknown_person", False):
            alert_hash = f"camera_unknown_{data.get('camera_id')}"
            if not self._is_duplicate(alert_hash):
                return True, "unknown_person", Severity.HIGH
        
        if event_type == "sensor" and data.get("status") in ["danger", "warning"]:
            location = data.get("location")
            if location and self._has_camera_motion(location):
                alert_hash = f"combined_{location}_{data.get('timestamp')}"
                if not self._is_duplicate(alert_hash):
                    return True, "combined_sensor_camera", Severity.CRITICAL
        
        return False, None, None

    def _has_camera_motion(self, location: str) -> bool:
        if location not in self.event_window:
            return False
        for entry in self.event_window[location]:
            event = entry["event"]
            if event.get("event_type") == "camera" and event.get("motion_detected", False):
                return True
        return False

    def _count_denied_access(self, uid: str, window: int = 60) -> int:
        count = 0
        cutoff = datetime.now() - timedelta(seconds=window)
        for location, entries in self.event_window.items():
            for entry in entries:
                if entry["timestamp"] < cutoff:
                    continue
                event = entry["event"]
                if (event.get("event_type") == "access" and 
                    event.get("uid") == uid and 
                    event.get("access_result") == "denied"):
                    count += 1
        return count

    def _is_duplicate(self, alert_hash: str) -> bool:
        if alert_hash in self.processed_alerts:
            elapsed = (datetime.now() - self.processed_alerts[alert_hash]).total_seconds()
            if elapsed < self.dedup_window:
                return True
            else:
                del self.processed_alerts[alert_hash]
        self.processed_alerts[alert_hash] = datetime.now()
        return False

    async def get_policy(self, policy_id: str) -> Optional[Dict]:
        return self.policies.get(policy_id)
    
    async def invalidate_cache(self, policy_id: str):
        if policy_id in self.policies:
            del self.policies[policy_id]
            self._load_default_policies()
        logger.info(f"Cache invalidated for policy: {policy_id}")   