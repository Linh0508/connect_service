"""
Connection Manager - Tự động phát hiện và quản lý kết nối đến các B khác
"""

import httpx
import os
import logging
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    REAL = "real"           # Đã kết nối, gọi thật
    FALLBACK = "fallback"   # Chưa kết nối, dùng logic nội bộ
    OFFLINE = "offline"     # Không thể kết nối


class ConnectionManager:
    def __init__(self):
        self.status: Dict[str, ConnectionStatus] = {
            "b3": ConnectionStatus.FALLBACK,
            "b4": ConnectionStatus.FALLBACK,
            "b5": ConnectionStatus.FALLBACK,
            "b7": ConnectionStatus.FALLBACK
        }
        self.last_check: Dict[str, datetime] = {}
        self.check_interval = 30
        self.urls: Dict[str, str] = {}
        
        # Load URLs from env
        self.urls["b3"] = os.getenv("ACCESS_GATE_URL", "http://b3-access-gate:8001")
        self.urls["b4"] = os.getenv("AI_VISION_URL", "http://b4-ai-vision:9000")
        self.urls["b5"] = os.getenv("ANALYTICS_URL", "http://b5-analytics:8003")
        self.urls["b7"] = os.getenv("NOTIFICATION_URL", "http://b7-notification:8002")
        
        # Fallback URLs - AI server nội bộ của B6
        self.fallback_urls = {
            "b4": os.getenv("AI_VISION_FALLBACK_URL", "http://b6-ai-vision:9000")
        }
        
        # Auto-detect flags
        self.auto_detect = {
            "b3": os.getenv("ACCESS_GATE_AUTO_DETECT", "true").lower() == "true",
            "b4": os.getenv("AI_VISION_AUTO_DETECT", "true").lower() == "true",
            "b5": os.getenv("ANALYTICS_AUTO_DETECT", "true").lower() == "true",
            "b7": os.getenv("NOTIFICATION_AUTO_DETECT", "true").lower() == "true"
        }
        
        logger.info("🔍 Connection Manager initialized")
        logger.info(f"   B3: {self.urls['b3']} (auto_detect={self.auto_detect['b3']})")
        logger.info(f"   B4: {self.urls['b4']} (auto_detect={self.auto_detect['b4']})")
        logger.info(f"   B5: {self.urls['b5']} (auto_detect={self.auto_detect['b5']})")
        logger.info(f"   B7: {self.urls['b7']} (auto_detect={self.auto_detect['b7']})")
        logger.info(f"   B4 FALLBACK URL: {self.fallback_urls['b4']}")
    
    def _is_fallback_url(self, url: str) -> bool:
        """Kiểm tra URL có phải là fallback (internal) không"""
        fallback_patterns = [
            r'b3-access-gate',
            r'b6-ai-vision',
            r'b5-analytics',
            # r'b7-notification',
            r'localhost',
            r'127\.0\.0\.1',
            r'0\.0\.0\.0',
        ]
        
        for pattern in fallback_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def get_fallback_url(self, service_name: str) -> str:
        """Lấy fallback URL cho service"""
        return self.fallback_urls.get(service_name, self.urls.get(service_name, ""))
    
    async def check_connection(self, service_name: str, url: str = None, timeout: float = 3.0) -> ConnectionStatus:
        """Kiểm tra kết nối đến một service bên ngoài (B3, B4, B5, B7)"""
        
        if url is None:
            url = self.urls.get(service_name, "")
        
        if not self.auto_detect.get(service_name, True):
            logger.info(f"🔵 {service_name} auto_detect disabled, using FALLBACK")
            self.status[service_name] = ConnectionStatus.FALLBACK
            return ConnectionStatus.FALLBACK
        
        # Đặc biệt cho B4 (AI Vision) - Luôn kiểm tra cẩn thận
        if service_name == "b4":
            return await self._check_b4_connection(url, timeout)
        
        if self._is_fallback_url(url):
            logger.info(f"🟡 {service_name} using internal URL: {url} -> FALLBACK mode")
            self.status[service_name] = ConnectionStatus.FALLBACK
            return ConnectionStatus.FALLBACK
        
        try:
            health_url = f"{url.rstrip('/')}/health"
            logger.debug(f"Checking {service_name} health at: {health_url}")
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(health_url)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        status = data.get("status", "").upper()
                        if status in ["UP", "OK"]:
                            self.status[service_name] = ConnectionStatus.REAL
                            logger.info(f"✅ {service_name} connected to REAL external service: {url}")
                            return ConnectionStatus.REAL
                        else:
                            logger.warning(f"⚠️ {service_name} health status: {status} -> using FALLBACK")
                            self.status[service_name] = ConnectionStatus.FALLBACK
                            return ConnectionStatus.FALLBACK
                    except:
                        self.status[service_name] = ConnectionStatus.REAL
                        logger.info(f"✅ {service_name} connected to REAL external service (non-JSON health): {url}")
                        return ConnectionStatus.REAL
                else:
                    logger.warning(f"⚠️ {service_name} health check returned {response.status_code} -> FALLBACK")
                    self.status[service_name] = ConnectionStatus.FALLBACK
                    return ConnectionStatus.FALLBACK
                    
        except httpx.TimeoutException:
            logger.warning(f"⏰ {service_name} timeout -> FALLBACK mode")
            self.status[service_name] = ConnectionStatus.FALLBACK
            return ConnectionStatus.FALLBACK
        except Exception as e:
            logger.warning(f"🟡 {service_name} connection failed: {e} -> FALLBACK mode")
            self.status[service_name] = ConnectionStatus.FALLBACK
            return ConnectionStatus.FALLBACK
    
    async def _check_b4_connection(self, url: str, timeout: float = 3.0) -> ConnectionStatus:
        """
        Kiểm tra kết nối đến B4 (AI Vision) một cách cẩn thận
        - Nếu URL là b6-ai-vision -> LUÔN FALLBACK (AI nội bộ của B6)
        - Nếu URL là b4-ai-vision -> Kiểm tra health, nếu UP thì REAL
        - Nếu không kết nối được -> FALLBACK (dùng AI nội bộ)
        """
        # Nếu URL là fallback (b6-ai-vision) -> luôn là FALLBACK
        if "b6-ai-vision" in url or "localhost" in url or "127.0.0.1" in url:
            logger.info(f"🟡 B4 using internal AI container: {url} -> FALLBACK mode")
            self.status["b4"] = ConnectionStatus.FALLBACK
            # Cập nhật fallback URL
            self.fallback_urls["b4"] = url
            return ConnectionStatus.FALLBACK
        
        # URL có thể là B4 thật, kiểm tra
        try:
            health_url = f"{url.rstrip('/')}/health"
            logger.debug(f"Checking B4 health at: {health_url}")
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(health_url)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # B4 thật thường có model_loaded, version, v.v.
                        if "model_loaded" in data or "model_version" in data:
                            self.status["b4"] = ConnectionStatus.REAL
                            logger.info(f"✅ B4 connected to REAL external AI service: {url}")
                            return ConnectionStatus.REAL
                        else:
                            logger.warning(f"⚠️ B4 response doesn't match expected schema -> FALLBACK")
                            self.status["b4"] = ConnectionStatus.FALLBACK
                            # Chuyển sang fallback URL
                            self.fallback_urls["b4"] = os.getenv("AI_VISION_FALLBACK_URL", "http://b6-ai-vision:9000")
                            return ConnectionStatus.FALLBACK
                    except:
                        logger.warning(f"⚠️ B4 health response not JSON -> FALLBACK")
                        self.status["b4"] = ConnectionStatus.FALLBACK
                        self.fallback_urls["b4"] = os.getenv("AI_VISION_FALLBACK_URL", "http://b6-ai-vision:9000")
                        return ConnectionStatus.FALLBACK
                else:
                    logger.warning(f"⚠️ B4 health check returned {response.status_code} -> FALLBACK")
                    self.status["b4"] = ConnectionStatus.FALLBACK
                    self.fallback_urls["b4"] = os.getenv("AI_VISION_FALLBACK_URL", "http://b6-ai-vision:9000")
                    return ConnectionStatus.FALLBACK
                    
        except httpx.TimeoutException:
            logger.warning(f"⏰ B4 timeout -> FALLBACK mode")
            self.status["b4"] = ConnectionStatus.FALLBACK
            self.fallback_urls["b4"] = os.getenv("AI_VISION_FALLBACK_URL", "http://b6-ai-vision:9000")
            return ConnectionStatus.FALLBACK
        except Exception as e:
            logger.warning(f"🟡 B4 connection failed: {e} -> FALLBACK mode")
            self.status["b4"] = ConnectionStatus.FALLBACK
            self.fallback_urls["b4"] = os.getenv("AI_VISION_FALLBACK_URL", "http://b6-ai-vision:9000")
            return ConnectionStatus.FALLBACK
    
    def get_status(self, service_name: str) -> ConnectionStatus:
        """Lấy trạng thái hiện tại của service"""
        return self.status.get(service_name, ConnectionStatus.FALLBACK)
    
    def should_use_real(self, service_name: str) -> bool:
        """Có nên gọi thật không?"""
        return self.get_status(service_name) == ConnectionStatus.REAL
    
    def get_status_display(self) -> Dict[str, str]:
        """Lấy trạng thái hiển thị cho dashboard"""
        displays = {}
        for service in ["b3", "b4", "b5", "b7"]:
            status = self.get_status(service)
            if status == ConnectionStatus.REAL:
                displays[service] = "🟢 Connected (REAL)"
            elif status == ConnectionStatus.OFFLINE:
                displays[service] = "🔴 Offline"
            else:
                displays[service] = "🟡 Fallback"
        return displays


# Global instance
connection_manager = ConnectionManager()