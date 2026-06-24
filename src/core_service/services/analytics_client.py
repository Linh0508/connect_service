"""
Analytics Client - Gửi decision sang B5 (Analytics Service)
"""

import httpx
import os
import logging
import asyncio
from typing import List, Dict, Any
from datetime import datetime
from src.core_service.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class AnalyticsClient:
    def __init__(self):
        self.base_url = os.getenv("ANALYTICS_URL", "http://26.100.91.226:8000")
        self.webhook_path = os.getenv("ANALYTICS_WEBHOOK_PATH", "/webhook/decisions")
        self.timeout = float(os.getenv("ANALYTICS_TIMEOUT", "3.0"))
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self.service_name = "b5"
        self.fallback_storage: List[Dict] = []
        
        # Đọc trạng thái từ connection_manager
        self._use_real = connection_manager.should_use_real(self.service_name)
        logger.info(f"📊 AnalyticsClient initialized: use_real={self._use_real}")
    
    async def send_decision(
        self,
        correlation_id: str,
        decision: str,
        reason: str,
        latency_ms: int,
        quota_before: int,
        quota_after: int,
        rules_triggered: List[str]
    ) -> bool:
        """Gửi decision sang Analytics Service (B5) - tự động REAL/FALLBACK"""
        
        # Kiểm tra nên dùng REAL hay FALLBACK
        if connection_manager.should_use_real(self.service_name):
            try:
                payload = {
                    "correlationId": correlation_id,
                    "decision": decision,
                    "reason": reason,
                    "latencyMs": latency_ms,
                    "quotaBefore": quota_before,
                    "quotaAfter": quota_after,
                    "rulesTriggered": rules_triggered,
                    "timestamp": datetime.now().isoformat()
                }
                
                url = f"{self.base_url}{self.webhook_path}"
                logger.debug(f"📊 Sending decision to B5: {url}")
                
                response = await self.client.post(url, json=payload)
                
                if response.status_code in [200, 202, 204]:
                    logger.info(f"📊 [ANALYTICS_REAL] Decision sent to B5: {correlation_id[:8]}... - {decision}")
                    return True
                else:
                    logger.warning(f"📊 [ANALYTICS_WARNING] B5 returned {response.status_code} -> FALLBACK")
                    self._store_fallback(correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered)
                    return True
            except httpx.TimeoutException:
                logger.warning(f"⏰ [ANALYTICS_TIMEOUT] B5 timeout after {self.timeout}s -> FALLBACK")
                self._store_fallback(correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered)
                return True
            except Exception as e:
                logger.warning(f"📊 [ANALYTICS_ERROR] B5 call failed: {e} -> FALLBACK")
                self._store_fallback(correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered)
                return True
        else:
            # FALLBACK MODE
            logger.info(f"📊 [ANALYTICS_FALLBACK] Decision stored locally: {correlation_id[:8]}... - {decision}")
            self._store_fallback(correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered)
            return True
    
    def _store_fallback(self, correlation_id: str, decision: str, reason: str,
                       latency_ms: int, quota_before: int, quota_after: int,
                       rules_triggered: List[str]):
        """Lưu decision vào fallback storage"""
        fallback_entry = {
            "correlationId": correlation_id,
            "decision": decision,
            "reason": reason,
            "latencyMs": latency_ms,
            "quotaBefore": quota_before,
            "quotaAfter": quota_after,
            "rulesTriggered": rules_triggered,
            "timestamp": datetime.now().isoformat(),
            "mode": "fallback"
        }
        self.fallback_storage.append(fallback_entry)
        if len(self.fallback_storage) > 1000:
            self.fallback_storage.pop(0)
        logger.debug(f"📊 [ANALYTICS_STORAGE] Fallback storage size: {len(self.fallback_storage)}")
    
    async def get_fallback_decisions(self, limit: int = 100) -> List[Dict]:
        return self.fallback_storage[-limit:]
    
    async def close(self):
        await self.client.aclose()