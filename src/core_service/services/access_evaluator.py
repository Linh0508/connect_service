"""
Access Evaluator - Xử lý sự kiện từ Access Gate
Version: 1.0
"""

import logging
import csv
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.core_service.models import AccessEvent, AccessResult, AlertLevel

logger = logging.getLogger(__name__)


class AccessEvaluator:
    def __init__(self):
        self.whitelist: Dict[str, Dict] = {}
        self._load_whitelist()
        
        # Map kết quả -> alert_level
        self.alert_level_map = {
            AccessResult.GRANTED: AlertLevel.LOW,
            AccessResult.DENIED: AlertLevel.MEDIUM,
        }

    def _load_whitelist(self):
        """Tải uid_whitelist.csv lúc khởi động"""
        whitelist_path = os.getenv("UID_WHITELIST_PATH", "data/uid_whitelist.csv")
        
        try:
            if os.path.exists(whitelist_path):
                with open(whitelist_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        uid = row.get('uid', '').strip()
                        if uid:
                            self.whitelist[uid] = {
                                'student_id': row.get('student_id', '').strip(),
                                'full_name': row.get('full_name', '').strip(),
                                'class_name': row.get('class_name', '').strip(),
                            }
                logger.info(f"✅ Loaded {len(self.whitelist)} UIDs from whitelist")
            else:
                # Fallback data cho test
                self._load_fallback_whitelist()
                logger.warning(f"⚠️ Whitelist file not found, using fallback data")
        except Exception as e:
            logger.error(f"❌ Failed to load whitelist: {e}")
            self._load_fallback_whitelist()

    def _load_fallback_whitelist(self):
        """Fallback whitelist cho test"""
        self.whitelist = {
            "04:A1:B2:C3:D4:03": {
                'student_id': 'SV003',
                'full_name': 'Le Minh Cuong',
                'class_name': 'CNTT-K19'
            },
            "05:B2:C3:D4:E5:04": {
                'student_id': 'SV004',
                'full_name': 'Tran Thi Mai',
                'class_name': 'CNTT-K20'
            },
            "06:C3:D4:E5:F6:05": {
                'student_id': 'SV005',
                'full_name': 'Nguyen Van An',
                'class_name': 'CNTT-K19'
            }
        }
        logger.info(f"✅ Loaded {len(self.whitelist)} fallback UIDs")

    async def evaluate(self, event: AccessEvent) -> Dict[str, Any]:
        """
        Đánh giá sự kiện Access - ĐẦY ĐỦ THEO YÊU CẦU
        
        Quy trình:
        1. VALIDATE: Kiểm tra field bắt buộc
        2. LOOKUP: Đối chiếu uid với whitelist
        3. DECIDE: Quyết định granted/denied
        4. ENRICH: Bổ sung thông tin sinh viên
        5. PRODUCE: Tạo kết quả
        """
        logger.info(f"🚪 Evaluating access for UID: {event.uid}")
        
        # ============================================================
        # 1. VALIDATE: Kiểm tra field bắt buộc
        # ============================================================
        if not event.uid:
            return self._create_result(event, AccessResult.DENIED, "Missing UID", None)
        
        if not event.door_id:
            return self._create_result(event, AccessResult.DENIED, "Missing door_id", None)

        # ============================================================
        # 2. LOOKUP: Đối chiếu uid với whitelist
        # ============================================================
        user_info = self.whitelist.get(event.uid)
        
        # ============================================================
        # 3. DECIDE + 4. ENRICH
        # ============================================================
        if user_info:
            return self._create_result(
                event,
                AccessResult.GRANTED,
                "uid_matched",
                user_info
            )
        else:
            return self._create_result(
                event,
                AccessResult.DENIED,
                "uid_not_found",
                None
            )

    def _create_result(self, event: AccessEvent, result: AccessResult, reason: str, user_info: Optional[Dict]):
        """Tạo kết quả đánh giá"""
        alert_level = self.alert_level_map.get(result, AlertLevel.MEDIUM)
        
        return {
            "event": event,
            "access_result": result,
            "reason": reason,
            "alert_level": alert_level,
            "student_id": user_info.get('student_id') if user_info else None,
            "full_name": user_info.get('full_name') if user_info else None,
            "class_name": user_info.get('class_name') if user_info else None,
            "timestamp": datetime.now()
        }


# Global instance
access_evaluator = AccessEvaluator()