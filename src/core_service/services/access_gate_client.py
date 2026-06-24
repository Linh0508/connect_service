"""
Access Gate Client - Gọi B3 (Access Gate Service)
"""

import httpx
import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.core_service.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class AccessGateClient:
    def __init__(self):
        self.base_url = os.getenv("ACCESS_GATE_URL", "http://b3-access-gate:8001")
        self.api_key = os.getenv("ACCESS_GATE_API_KEY", "")
        self.timeout = float(os.getenv("ACCESS_GATE_TIMEOUT", "3.0"))
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self.service_name = "b3"
        
        # Đọc trạng thái từ connection_manager
        self._use_real = connection_manager.should_use_real(self.service_name)
        logger.info(f"🚪 AccessGateClient initialized: use_real={self._use_real}")
    
    async def get_access_logs(
        self, 
        from_date: Optional[datetime] = None, 
        to_date: Optional[datetime] = None, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Lấy access logs - tự động REAL/FALLBACK"""
        
        # Kiểm tra nên dùng REAL hay FALLBACK
        if connection_manager.should_use_real(self.service_name):
            try:
                url = f"{self.base_url}/v1/access-logs"
                params = {"limit": limit}
                if from_date:
                    params["from"] = from_date.isoformat()
                if to_date:
                    params["to"] = to_date.isoformat()
                
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-Key"] = self.api_key
                
                logger.debug(f"🚪 Calling B3 access logs: {url}")
                response = await self.client.get(url, params=params, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"✅ [B3_REAL] Retrieved access logs from B3")
                    return response.json()
                else:
                    logger.warning(f"⚠️ [B3_WARNING] B3 returned {response.status_code} -> FALLBACK")
            except httpx.TimeoutException:
                logger.warning(f"⏰ [B3_TIMEOUT] B3 timeout after {self.timeout}s -> FALLBACK")
            except Exception as e:
                logger.warning(f"⚠️ [B3_ERROR] B3 call failed: {e} -> FALLBACK")
        
        # FALLBACK MODE
        logger.info(f"🟡 [B3_FALLBACK] Using fallback access logs")
        return self._fallback_get_logs()
    
    async def get_gate_status(self, gate_id: str) -> Dict[str, Any]:
        """Lấy trạng thái cổng - tự động REAL/FALLBACK"""
        
        if connection_manager.should_use_real(self.service_name):
            try:
                url = f"{self.base_url}/v1/gates/{gate_id}/status"
                headers = {"X-API-Key": self.api_key} if self.api_key else {}
                
                logger.debug(f"🚪 Calling B3 gate status: {url}")
                response = await self.client.get(url, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"✅ [B3_REAL] Gate status retrieved from B3")
                    return response.json()
                else:
                    logger.warning(f"⚠️ [B3_WARNING] B3 gate status returned {response.status_code} -> FALLBACK")
            except httpx.TimeoutException:
                logger.warning(f"⏰ [B3_TIMEOUT] B3 gate status timeout after {self.timeout}s -> FALLBACK")
            except Exception as e:
                logger.warning(f"⚠️ [B3_ERROR] B3 gate status failed: {e} -> FALLBACK")
        
        # FALLBACK MODE
        return self._fallback_get_status(gate_id)
    
    def _fallback_get_logs(self) -> List[Dict]:
        """Tự xử lý log nội bộ khi không kết nối được B3"""
        return [
            {
                "logId": f"fallback_log_{i}",
                "cardId": f"CARD_{i}",
                "gateId": "LAB_01",
                "direction": "IN",
                "status": "GRANTED",
                "timestamp": datetime.now().isoformat(),
                "operatorNote": "Fallback mode - B3 not connected",
                "mock": True
            }
            for i in range(1, 4)
        ]
    
    def _fallback_get_status(self, gate_id: str) -> Dict:
        """Tự xử lý status nội bộ khi không kết nối được B3"""
        return {
            "gateId": gate_id,
            "isOnline": True,
            "lastHeartbeat": datetime.now().isoformat(),
            "currentMode": "normal",
            "mock": True,
            "message": "Fallback mode - B3 not connected"
        }
    
    async def close(self):
        await self.client.aclose()