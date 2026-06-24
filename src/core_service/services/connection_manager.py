"""
Connection Manager - Tự động phát hiện và quản lý kết nối đến các B khác
"""

import httpx
import os
import logging
import asyncio
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    REAL = "real"
    FALLBACK = "fallback"
    OFFLINE = "offline"
    DISABLED = "disabled"


class ConnectionManager:
    def __init__(self):
        self.status: Dict[str, ConnectionStatus] = {}
        self.last_check: Dict[str, datetime] = {}
        self.urls: Dict[str, str] = {}
        self._check_in_progress: Dict[str, bool] = {}
        self._initial_checked: Dict[str, bool] = {}
        self._retry_tasks: Dict[str, asyncio.Task] = {}
        self._check_failed: Dict[str, bool] = {}  # Đánh dấu đã fail
        
        # Load URLs từ env
        self.urls["b3"] = os.getenv("ACCESS_GATE_URL", "http://b3-access-gate:8001")
        self.urls["b4"] = os.getenv("AI_VISION_URL", "http://b4-ai-vision:9000")
        self.urls["b5"] = os.getenv("ANALYTICS_URL", "http://26.100.91.226:8000")
        self.urls["b7"] = os.getenv("NOTIFICATION_URL", "http://26.64.54.49:8000")
        
        # Fallback URLs
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
        
        # Retry interval
        self.retry_intervals = {
            "b3": int(os.getenv("ACCESS_GATE_RETRY_INTERVAL", "60")),
            "b4": int(os.getenv("AI_VISION_RETRY_INTERVAL", "60")),
            "b5": int(os.getenv("ANALYTICS_RETRY_INTERVAL", "60")),
            "b7": int(os.getenv("NOTIFICATION_RETRY_INTERVAL", "60"))
        }
        
        self.connection_timeout = float(os.getenv("CONNECTION_CHECK_TIMEOUT", "2.0"))
        self.retry_enabled = os.getenv("CONNECTION_RETRY_ENABLED", "false").lower() == "true"
        
        # Khởi tạo status
        for service in ["b3", "b4", "b5", "b7"]:
            self.status[service] = ConnectionStatus.FALLBACK
            self._initial_checked[service] = False
            self._check_failed[service] = False
        
        logger.info("🔍 Connection Manager initialized")
        logger.info(f"   Connection timeout: {self.connection_timeout}s")
        logger.info(f"   Retry enabled: {self.retry_enabled}")
        logger.info(f"   B3: {self.urls['b3']} (auto_detect={self.auto_detect['b3']})")
        logger.info(f"   B4: {self.urls['b4']} (auto_detect={self.auto_detect['b4']})")
        logger.info(f"   B5: {self.urls['b5']} (auto_detect={self.auto_detect['b5']})")
        logger.info(f"   B7: {self.urls['b7']} (auto_detect={self.auto_detect['b7']})")
    
    def _is_fallback_url(self, url: str) -> bool:
        fallback_patterns = [
            r'b3-access-gate',
            r'b6-ai-vision',
            r'b5-analytics',
            r'localhost',
            r'127\.0\.0\.1',
            r'0\.0\.0\.0',
        ]
        for pattern in fallback_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def get_fallback_url(self, service_name: str) -> str:
        return self.fallback_urls.get(service_name, self.urls.get(service_name, ""))
    
    async def check_connection(self, service_name: str, url: str = None, timeout: float = None) -> ConnectionStatus:
        """Kiểm tra kết nối - CHỈ GỌI 1 LẦN, KHÔNG RETRY"""
        
        # Nếu đã fail trước đó, không thử lại
        if self._check_failed.get(service_name, False):
            logger.debug(f"⚠️ {service_name} already failed, skipping")
            return self.status.get(service_name, ConnectionStatus.FALLBACK)
        
        if timeout is None:
            timeout = self.connection_timeout
        
        if self._check_in_progress.get(service_name, False):
            logger.debug(f"⚠️ {service_name} check already in progress")
            return self.status.get(service_name, ConnectionStatus.FALLBACK)
        
        self._check_in_progress[service_name] = True
        
        try:
            if url is None:
                url = self.urls.get(service_name, "")
            
            # Nếu auto_detect = false, dùng FALLBACK luôn
            if not self.auto_detect.get(service_name, True):
                logger.info(f"🔵 {service_name} auto_detect disabled, using FALLBACK")
                self.status[service_name] = ConnectionStatus.FALLBACK
                self._initial_checked[service_name] = True
                self._check_failed[service_name] = True  # Đánh dấu đã fail
                return ConnectionStatus.FALLBACK
            
            # Nếu URL là internal, dùng FALLBACK luôn
            if self._is_fallback_url(url):
                logger.info(f"🟡 {service_name} using internal URL: {url} -> FALLBACK mode")
                self.status[service_name] = ConnectionStatus.FALLBACK
                self._initial_checked[service_name] = True
                self._check_failed[service_name] = True
                return ConnectionStatus.FALLBACK
            
            # Kiểm tra health
            try:
                health_url = f"{url.rstrip('/')}/health"
                logger.debug(f"Checking {service_name} health at: {health_url} (timeout={timeout}s)")
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(health_url)
                    
                    if response.status_code == 200:
                        self.status[service_name] = ConnectionStatus.REAL
                        self._initial_checked[service_name] = True
                        self._check_failed[service_name] = False
                        logger.info(f"✅ {service_name} connected to REAL external service: {url}")
                        return ConnectionStatus.REAL
                    else:
                        logger.warning(f"⚠️ {service_name} health check returned {response.status_code} -> FALLBACK")
                        self.status[service_name] = ConnectionStatus.FALLBACK
                        self._initial_checked[service_name] = True
                        self._check_failed[service_name] = True
                        return ConnectionStatus.FALLBACK
                        
            except httpx.TimeoutException:
                logger.warning(f"⏰ {service_name} timeout after {timeout}s -> FALLBACK mode")
                self.status[service_name] = ConnectionStatus.FALLBACK
                self._initial_checked[service_name] = True
                self._check_failed[service_name] = True
                return ConnectionStatus.FALLBACK
            except Exception as e:
                logger.warning(f"🟡 {service_name} connection failed: {e} -> FALLBACK mode")
                self.status[service_name] = ConnectionStatus.FALLBACK
                self._initial_checked[service_name] = True
                self._check_failed[service_name] = True
                return ConnectionStatus.FALLBACK
                
        finally:
            self._check_in_progress[service_name] = False
            self.last_check[service_name] = datetime.now()
    
    async def initial_check_all(self):
        """Kiểm tra tất cả service - CHỈ 1 LẦN DUY NHẤT"""
        logger.info("🔵 Performing ONE-TIME connection checks...")
        
        for service in ["b3", "b4", "b5", "b7"]:
            url = self.urls.get(service, "")
            if not url:
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
                continue
            
            # Nếu auto_detect = false hoặc URL internal → FALLBACK luôn
            if not self.auto_detect.get(service, True) or self._is_fallback_url(url):
                logger.info(f"🟡 {service}: auto_detect=false or internal URL → FALLBACK")
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
                continue
            
            # THỬ CHECK 1 LẦN DUY NHẤT
            try:
                logger.info(f"🔍 Checking {service} at {url} (timeout={self.connection_timeout}s)...")
                
                # Gọi check_connection với timeout
                status = await asyncio.wait_for(
                    self.check_connection(service, url),
                    timeout=self.connection_timeout + 0.5
                )
                
                if status == ConnectionStatus.REAL:
                    logger.info(f"✅ {service} connected to REAL external service")
                else:
                    logger.info(f"🟡 {service} connection failed → using FALLBACK")
                    self.status[service] = ConnectionStatus.FALLBACK
                    self._check_failed[service] = True
                    
            except asyncio.TimeoutError:
                logger.info(f"⏱️ {service} check timeout after {self.connection_timeout}s → FALLBACK (no retry)")
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
            except Exception as e:
                logger.info(f"⚠️ {service} check error: {e} → FALLBACK (no retry)")
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
            
            self._initial_checked[service] = True
        
        # RabbitMQ - check 1 lần
        await self._check_rabbitmq_once()
        
        logger.info("🔍 One-time connection checks completed")
        self.log_status_summary()
    
    async def _check_rabbitmq_once(self):
        """Kiểm tra RabbitMQ 1 lần duy nhất"""
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "")
        if not rabbitmq_host or rabbitmq_host in ["localhost", "127.0.0.1", ""]:
            logger.info("📧 RabbitMQ disabled or using localhost -> FALLBACK mode")
            self.status["b7_rabbitmq"] = ConnectionStatus.DISABLED
            return
        
        try:
            import aio_pika
            from aio_pika import connect_robust
            
            connection_url = f"amqp://{os.getenv('RABBITMQ_USER', 'guest')}:{os.getenv('RABBITMQ_PASS', 'guest')}@{rabbitmq_host}:{os.getenv('RABBITMQ_PORT', '5672')}/"
            
            logger.info(f"📧 Checking RabbitMQ connection to {rabbitmq_host} (one-time)...")
            
            connection = await asyncio.wait_for(
                connect_robust(connection_url),
                timeout=float(os.getenv("RABBITMQ_CONNECTION_TIMEOUT", "3.0"))
            )
            await connection.close()
            
            logger.info(f"✅ RabbitMQ connected successfully to {rabbitmq_host}")
            self.status["b7_rabbitmq"] = ConnectionStatus.REAL
        except asyncio.TimeoutError:
            logger.info(f"⏱️ RabbitMQ check timeout -> FALLBACK")
            self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
        except Exception as e:
            logger.info(f"⚠️ RabbitMQ check failed: {e} -> FALLBACK")
            self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
    
    async def start_retry_tasks(self):
        """Khởi động retry tasks - CHỈ KHI retry_enabled = true"""
        if not self.retry_enabled:
            logger.info("🔵 Connection retry disabled, no retry tasks started")
            return
        
        logger.info("🔄 Starting connection retry tasks...")
        # Implement retry logic nếu cần
        # (Hiện tại đang disabled)
    
    async def stop_retry_tasks(self):
        """Dừng retry tasks"""
        for service, task in self._retry_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._retry_tasks.clear()
    
    def get_status(self, service_name: str) -> ConnectionStatus:
        return self.status.get(service_name, ConnectionStatus.FALLBACK)
    
    def should_use_real(self, service_name: str) -> bool:
        """Có nên gọi thật không? - TRẢ VỀ FALSE NHANH"""
        # Nếu đã fail, luôn trả về False
        if self._check_failed.get(service_name, False):
            return False
        if not self._initial_checked.get(service_name, False):
            return False
        return self.get_status(service_name) == ConnectionStatus.REAL
    
    def is_rabbitmq_available(self) -> bool:
        return self.get_status("b7_rabbitmq") == ConnectionStatus.REAL
    
    def log_status_summary(self):
        logger.info("📊 Connection Status Summary:")
        logger.info(f"   Retry Enabled: {self.retry_enabled}")
        for service in ["b3", "b4", "b5", "b7"]:
            status = self.get_status(service)
            failed = self._check_failed.get(service, False)
            logger.info(f"   {service}: {status.value} (failed={failed})")
        logger.info(f"   b7_rabbitmq: {self.get_status('b7_rabbitmq').value}")
    
    def get_status_display(self) -> Dict[str, str]:
        displays = {}
        for service in ["b3", "b4", "b5", "b7"]:
            status = self.get_status(service)
            if status == ConnectionStatus.REAL:
                displays[service] = "🟢 Connected (REAL)"
            elif status == ConnectionStatus.OFFLINE:
                displays[service] = "🔴 Offline"
            elif status == ConnectionStatus.DISABLED:
                displays[service] = "⚪ Disabled"
            else:
                displays[service] = "🟡 Fallback"
        
        rabbit_status = self.get_status("b7_rabbitmq")
        if rabbit_status == ConnectionStatus.REAL:
            displays["rabbitmq"] = "🟢 Connected"
        elif rabbit_status == ConnectionStatus.DISABLED:
            displays["rabbitmq"] = "⚪ Disabled"
        else:
            displays["rabbitmq"] = "🟡 Fallback"
        
        return displays


# Global instance
connection_manager = ConnectionManager()