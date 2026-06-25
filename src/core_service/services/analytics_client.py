"""
Analytics Client - Gửi decision sang B5 (Analytics Service)
Version: 2.3 - Thêm client_ip và log đầy đủ
"""

import httpx
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
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
        self._last_request: Optional[Dict] = None
        self._last_response: Optional[Dict] = None
        self._last_realtime_entry: Optional[Dict] = None
        
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
        rules_triggered: List[str],
        client_ip: str = None  # ✅ Thêm tham số client_ip
    ) -> bool:
        """Gửi decision sang Analytics Service (B5) - tự động REAL/FALLBACK"""
        
        payload = {
            "correlationId": correlation_id,
            "decision": decision,
            "reason": reason,
            "latencyMs": latency_ms,
            "quotaBefore": quota_before,
            "quotaAfter": quota_after,
            "rulesTriggered": rules_triggered,
            "timestamp": datetime.now().isoformat(),
            "clientIp": client_ip or "localhost"  # ✅ Thêm client_ip vào payload
        }
        
        # Lưu request để hiển thị
        self._last_request = {
            "url": f"{self.base_url}{self.webhook_path}",
            "method": "POST",
            "payload": payload,
            "mode": "REAL" if connection_manager.should_use_real(self.service_name) else "FALLBACK"
        }
        
        # Kiểm tra nên dùng REAL hay FALLBACK
        if connection_manager.should_use_real(self.service_name):
            try:
                url = f"{self.base_url}{self.webhook_path}"
                logger.debug(f"📊 Sending decision to B5: {url}")
                
                response = await self.client.post(url, json=payload)
                
                # Lưu response
                self._last_response = {
                    "status_code": response.status_code,
                    "body": response.json() if response.text else {},
                    "mode": "REAL"
                }
                
                if response.status_code in [200, 202, 204]:
                    logger.info(f"📊 [ANALYTICS_REAL] Decision sent to B5: {correlation_id[:8]}... - {decision}")
                    # ✅ Lưu realtime entry với IP đúng
                    self._last_realtime_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "ip": client_ip or "localhost",
                        "status": response.status_code,
                        "request": payload,
                        "response": self._last_response.get("body", {}),
                        "mode": "REAL"
                    }
                    return True
                else:
                    logger.warning(f"📊 [ANALYTICS_WARNING] B5 returned {response.status_code} -> FALLBACK")
                    self._store_fallback(correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered)
                    # Lưu response fallback
                    self._last_response = {
                        "status_code": 202,
                        "body": {"status": "fallback", "message": f"B5 returned {response.status_code}, stored locally"},
                        "mode": "FALLBACK"
                    }
                    self._last_realtime_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "ip": client_ip or "localhost",
                        "status": 202,
                        "request": payload,
                        "response": self._last_response.get("body", {}),
                        "mode": "FALLBACK"
                    }
                    return True
            except httpx.TimeoutException:
                logger.warning(f"⏰ [ANALYTICS_TIMEOUT] B5 timeout after {self.timeout}s -> FALLBACK")
                self._store_fallback(correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered)
                self._last_response = {
                    "status_code": 408,
                    "body": {"status": "fallback", "message": f"Timeout after {self.timeout}s"},
                    "mode": "FALLBACK"
                }
                self._last_realtime_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "ip": client_ip or "localhost",
                    "status": 408,
                    "request": payload,
                    "response": self._last_response.get("body", {}),
                    "mode": "FALLBACK"
                }
                return True
            except Exception as e:
                logger.warning(f"📊 [ANALYTICS_ERROR] B5 call failed: {e} -> FALLBACK")
                self._store_fallback(correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered)
                self._last_response = {
                    "status_code": 500,
                    "body": {"status": "fallback", "message": str(e)},
                    "mode": "FALLBACK"
                }
                self._last_realtime_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "ip": client_ip or "localhost",
                    "status": 500,
                    "request": payload,
                    "response": self._last_response.get("body", {}),
                    "mode": "FALLBACK"
                }
                return True
        else:
            # FALLBACK MODE
            logger.info(f"📊 [ANALYTICS_FALLBACK] Decision stored locally: {correlation_id[:8]}... - {decision}")
            self._store_fallback(correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered)
            
            # Giả lập response thành công
            self._last_response = {
                "status_code": 202,
                "body": {
                    "status": "accepted",
                    "correlationId": correlation_id,
                    "decision": decision,
                    "mode": "fallback",
                    "message": "Decision stored locally (B5 in fallback mode)"
                },
                "mode": "FALLBACK"
            }
            self._last_realtime_entry = {
                "timestamp": datetime.now().isoformat(),
                "ip": client_ip or "localhost",
                "status": 202,
                "request": payload,
                "response": self._last_response.get("body", {}),
                "mode": "FALLBACK"
            }
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
    
    async def get_last_request(self) -> Optional[Dict]:
        return self._last_request
    
    async def get_last_response(self) -> Optional[Dict]:
        return self._last_response
    
    async def get_last_realtime_entry(self) -> Optional[Dict]:
        """✅ Lấy realtime entry mới nhất"""
        return self._last_realtime_entry
    
    async def close(self):
        await self.client.aclose()