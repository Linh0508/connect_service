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
import json
import re

# ✅ Import aio_pika
import aio_pika
from aio_pika import connect_robust, Message

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
        self._check_failed: Dict[str, bool] = {}
        
        # ============================================================
        # MỖI SERVICE CÓ CẤU HÌNH RIÊNG
        # ============================================================
        self.services_config = {
            "b3": {
                "url": os.getenv("ACCESS_GATE_URL", "http://b3-access-gate:8001"),
                "auto_detect": os.getenv("ACCESS_GATE_AUTO_DETECT", "false").lower() == "true",
                "timeout": float(os.getenv("ACCESS_GATE_TIMEOUT", "3.0")),
                "retry_interval": int(os.getenv("ACCESS_GATE_RETRY_INTERVAL", "60")),
                "retry_enabled": os.getenv("ACCESS_GATE_RETRY_ENABLED", "false").lower() == "true",
                "fallback_url": None
            },
            "b4": {
                "url": os.getenv("B4_AI_VISION_URL", "http://b4-ai-vision:9000"),
                "auto_detect": os.getenv("AI_VISION_AUTO_DETECT", "false").lower() == "true",
                "timeout": float(os.getenv("AI_VISION_TIMEOUT", "3.0")),
                "retry_interval": int(os.getenv("AI_VISION_RETRY_INTERVAL", "60")),
                "retry_enabled": os.getenv("AI_VISION_RETRY_ENABLED", "false").lower() == "true",
                "fallback_url": os.getenv("AI_VISION_FALLBACK_URL", "http://b6-ai-vision:9000")
            },
            "b5": {
                "url": os.getenv("ANALYTICS_URL", "http://26.100.91.226:8000"),
                "auto_detect": os.getenv("ANALYTICS_AUTO_DETECT", "false").lower() == "true",
                "timeout": float(os.getenv("ANALYTICS_TIMEOUT", "5.0")),
                "retry_interval": int(os.getenv("ANALYTICS_RETRY_INTERVAL", "60")),
                "retry_enabled": os.getenv("ANALYTICS_RETRY_ENABLED", "false").lower() == "true",
                "fallback_url": None
            },
            "b7": {
                "url": os.getenv("NOTIFICATION_URL", "http://26.64.54.49:8000"),
                "auto_detect": os.getenv("NOTIFICATION_AUTO_DETECT", "false").lower() == "true",
                "timeout": float(os.getenv("NOTIFICATION_TIMEOUT", "5.0")),
                "retry_interval": int(os.getenv("NOTIFICATION_RETRY_INTERVAL", "60")),
                "retry_enabled": os.getenv("NOTIFICATION_RETRY_ENABLED", "false").lower() == "true",
                "fallback_url": None
            }
        }
        
        # ============================================================
        # LƯU URL VÀ FLAGS VÀO PROPERTIES ĐỂ TƯƠNG THÍCH CODE CŨ
        # ============================================================
        self.urls = {k: v["url"] for k, v in self.services_config.items()}
        self.auto_detect = {k: v["auto_detect"] for k, v in self.services_config.items()}
        self.retry_intervals = {k: v["retry_interval"] for k, v in self.services_config.items()}
        self.connection_timeout = float(os.getenv("CONNECTION_CHECK_TIMEOUT", "2.0"))
        self.retry_enabled = os.getenv("CONNECTION_RETRY_ENABLED", "false").lower() == "true"
        
        # Fallback URLs
        self.fallback_urls = {
            "b4": self.services_config["b4"]["fallback_url"]
        }
        
        # Khởi tạo status
        for service in ["b3", "b4", "b5", "b7"]:
            self.status[service] = ConnectionStatus.FALLBACK
            self._initial_checked[service] = False
            self._check_failed[service] = False
        
        # Khởi tạo status cho RabbitMQ
        self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
        
        # Lưu connection và channel để dùng chung
        self._rabbitmq_connection = None
        self._rabbitmq_channel = None
        self._rabbitmq_keepalive_task = None
        self._rabbitmq_connected = False
        
        # Log cấu hình từng service
        logger.info("🔍 Connection Manager initialized with per-service config:")
        for service, config in self.services_config.items():
            logger.info(f"   {service}: url={config['url']}, auto_detect={config['auto_detect']}, "
                       f"timeout={config['timeout']}s, retry={config['retry_enabled']}, "
                       f"retry_interval={config['retry_interval']}s")
    
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
        """Kiểm tra kết nối - CHỈ GỌI 1 LẦN KHI KHỞI ĐỘNG"""
        
        # Nếu đã fail trước đó, không thử lại
        if self._check_failed.get(service_name, False):
            logger.debug(f"⚠️ {service_name} already failed, skipping")
            return self.status.get(service_name, ConnectionStatus.FALLBACK)
        
        config = self.services_config.get(service_name, {})
        if url is None:
            url = config.get("url", "")
        if timeout is None:
            timeout = config.get("timeout", self.connection_timeout)
        
        # Nếu auto_detect = false, dùng FALLBACK luôn
        if not config.get("auto_detect", False):
            logger.info(f"🔵 {service_name} auto_detect disabled, using FALLBACK")
            self.status[service_name] = ConnectionStatus.FALLBACK
            self._initial_checked[service_name] = True
            self._check_failed[service_name] = True
            return ConnectionStatus.FALLBACK
        
        # Nếu URL là internal, dùng FALLBACK luôn
        if self._is_fallback_url(url):
            logger.info(f"🟡 {service_name} using internal URL: {url} -> FALLBACK mode")
            self.status[service_name] = ConnectionStatus.FALLBACK
            self._initial_checked[service_name] = True
            self._check_failed[service_name] = True
            return ConnectionStatus.FALLBACK
        
        if self._check_in_progress.get(service_name, False):
            logger.debug(f"⚠️ {service_name} check already in progress")
            return self.status.get(service_name, ConnectionStatus.FALLBACK)
        
        self._check_in_progress[service_name] = True
        
        try:
            # Đặc biệt cho B4 (AI Vision) - kiểm tra health khác
            if service_name == "b4":
                return await self._check_b4_connection(url, timeout)
            
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
    
    async def _check_b4_connection(self, url: str, timeout: float = 2.0) -> ConnectionStatus:
        """Kiểm tra kết nối đến B4 (AI Vision)"""
        config = self.services_config.get("b4", {})
        fallback_url = config.get("fallback_url", "http://b6-ai-vision:9000")
        
        if "b6-ai-vision" in url or "localhost" in url or "127.0.0.1" in url:
            logger.info(f"🟡 B4 using internal AI container: {url} -> FALLBACK mode")
            self.status["b4"] = ConnectionStatus.FALLBACK
            self.fallback_urls["b4"] = url
            self._initial_checked["b4"] = True
            return ConnectionStatus.FALLBACK
        
        try:
            health_url = f"{url.rstrip('/')}/health"
            logger.debug(f"Checking B4 health at: {health_url} (timeout={timeout}s)")
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(health_url)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if "model_loaded" in data or "model_version" in data:
                            self.status["b4"] = ConnectionStatus.REAL
                            self._initial_checked["b4"] = True
                            logger.info(f"✅ B4 connected to REAL external AI service: {url}")
                            return ConnectionStatus.REAL
                        else:
                            logger.warning(f"⚠️ B4 response doesn't match expected schema -> FALLBACK")
                            self.status["b4"] = ConnectionStatus.FALLBACK
                            self._initial_checked["b4"] = True
                            return ConnectionStatus.FALLBACK
                    except:
                        logger.warning(f"⚠️ B4 health response not JSON -> FALLBACK")
                        self.status["b4"] = ConnectionStatus.FALLBACK
                        self._initial_checked["b4"] = True
                        return ConnectionStatus.FALLBACK
                else:
                    logger.warning(f"⚠️ B4 health check returned {response.status_code} -> FALLBACK")
                    self.status["b4"] = ConnectionStatus.FALLBACK
                    self._initial_checked["b4"] = True
                    return ConnectionStatus.FALLBACK
                    
        except httpx.TimeoutException:
            logger.warning(f"⏰ B4 timeout after {timeout}s -> FALLBACK mode")
            self.status["b4"] = ConnectionStatus.FALLBACK
            self._initial_checked["b4"] = True
            return ConnectionStatus.FALLBACK
        except Exception as e:
            logger.warning(f"🟡 B4 connection failed: {e} -> FALLBACK mode")
            self.status["b4"] = ConnectionStatus.FALLBACK
            self._initial_checked["b4"] = True
            return ConnectionStatus.FALLBACK
    
    async def initial_check_all(self):
        """Kiểm tra tất cả service - CHỈ 1 LẦN DUY NHẤT KHI KHỞI ĐỘNG"""
        logger.info("🔵 Performing ONE-TIME connection checks...")
        
        for service in ["b3", "b4", "b5", "b7"]:
            config = self.services_config.get(service, {})
            url = config.get("url", "")
            timeout = config.get("timeout", self.connection_timeout)
            
            if not url:
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
                continue
            
            # Nếu auto_detect = false → FALLBACK luôn
            if not config.get("auto_detect", False):
                logger.info(f"🟡 {service}: auto_detect=false → FALLBACK")
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
                continue
            
            # Nếu URL internal → FALLBACK luôn
            if self._is_fallback_url(url):
                logger.info(f"🟡 {service}: internal URL → FALLBACK")
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
                continue
            
            # THỬ CHECK 1 LẦN DUY NHẤT
            try:
                logger.info(f"🔍 Checking {service} at {url} (timeout={timeout}s)...")
                
                status = await asyncio.wait_for(
                    self.check_connection(service, url, timeout),
                    timeout=timeout + 0.5
                )
                
                if status == ConnectionStatus.REAL:
                    logger.info(f"✅ {service} connected to REAL external service")
                else:
                    logger.info(f"🟡 {service} connection failed → using FALLBACK")
                    self.status[service] = ConnectionStatus.FALLBACK
                    self._check_failed[service] = True
                    
            except asyncio.TimeoutError:
                logger.info(f"⏱️ {service} check timeout after {timeout}s → FALLBACK (no retry)")
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
            except Exception as e:
                logger.info(f"⚠️ {service} check error: {e} → FALLBACK (no retry)")
                self.status[service] = ConnectionStatus.FALLBACK
                self._initial_checked[service] = True
                self._check_failed[service] = True
            
            self._initial_checked[service] = True
        
        # RabbitMQ - TẠO CONNECTION VÀ GIỮ MÃI MÃI
        await self._setup_rabbitmq_connection()
        
        logger.info("🔍 One-time connection checks completed")
        self.log_status_summary()
    
    async def _setup_rabbitmq_connection(self):
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "")
        rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")
        rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        rabbitmq_pass = os.getenv("RABBITMQ_PASS", "guest")

        if not rabbitmq_host or rabbitmq_host in ["localhost", "127.0.0.1", ""]:
            logger.info("📧 RabbitMQ disabled or using localhost -> FALLBACK mode")
            self.status["b7_rabbitmq"] = ConnectionStatus.DISABLED
            self._rabbitmq_connected = False
            return

        try:
            connection_url = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"
            logger.info(f"📧 Creating RabbitMQ connection at {rabbitmq_host}:{rabbitmq_port} (KEEP ALIVE FOREVER)...")

            # Tăng timeout lên 10s
            self._rabbitmq_connection = await asyncio.wait_for(
                connect_robust(
                    connection_url,
                    reconnect_interval=5,
                    reconnect_attempts=10,
                    heartbeat=15
                ),
                timeout=10.0
            )

            logger.info(f"📧 Connection established with heartbeat=15s")

            # Tạo channel
            self._rabbitmq_channel = await self._rabbitmq_connection.channel()

            # Declare queue và bind
            queue_name = os.getenv("RABBITMQ_QUEUE", "notification.alerts")
            exchange_name = os.getenv("RABBITMQ_EXCHANGE", "amq.topic")
            routing_key = os.getenv("RABBITMQ_ROUTING_KEY", "notification.alerts")

            logger.info(f"📧 RabbitMQ config: exchange={exchange_name}, queue={queue_name}, routing_key={routing_key}")

            queue = await self._rabbitmq_channel.declare_queue(queue_name, durable=True)
            await queue.bind(exchange_name, routing_key)

            self._rabbitmq_connected = True
            self.status["b7_rabbitmq"] = ConnectionStatus.REAL

            # Khởi động task giữ kết nối sống
            if self._rabbitmq_keepalive_task is None or self._rabbitmq_keepalive_task.done():
                self._rabbitmq_keepalive_task = asyncio.create_task(self._keep_rabbitmq_alive())

            logger.info(f"✅ RabbitMQ connection created and KEEP ALIVE FOREVER: {rabbitmq_host}:{rabbitmq_port}")

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ RabbitMQ connection timeout after 10s, will retry in keepalive task")
            self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
            self._rabbitmq_connected = False
            # Vẫn tạo task keepalive để thử kết nối lại
            if self._rabbitmq_keepalive_task is None or self._rabbitmq_keepalive_task.done():
                self._rabbitmq_keepalive_task = asyncio.create_task(self._keep_rabbitmq_alive())
        except Exception as e:
            logger.warning(f"⚠️ RabbitMQ connection failed: {e} -> FALLBACK")
            self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
            self._rabbitmq_connection = None
            self._rabbitmq_channel = None
            self._rabbitmq_connected = False
    
    async def _keep_rabbitmq_alive(self):
        heartbeat_interval = 20
        while True:
            try:
                await asyncio.sleep(heartbeat_interval)

                # --- THÊM PHẦN NÀY ---
                # Nếu connection đã tồn tại nhưng chưa được đánh dấu connected
                if self._rabbitmq_connection is not None and not self._rabbitmq_connected:
                    if not self._rabbitmq_connection.is_closed:
                        try:
                            # Thử tạo channel để xác nhận kết nối hoạt động
                            self._rabbitmq_channel = await self._rabbitmq_connection.channel()
                            queue_name = os.getenv("RABBITMQ_QUEUE", "notification.alerts")
                            exchange_name = os.getenv("RABBITMQ_EXCHANGE", "amq.topic")
                            routing_key = os.getenv("RABBITMQ_ROUTING_KEY", "notification.alerts")
                            queue = await self._rabbitmq_channel.declare_queue(queue_name, durable=True)
                            await queue.bind(exchange_name, routing_key)
                            self._rabbitmq_connected = True
                            self.status["b7_rabbitmq"] = ConnectionStatus.REAL
                            logger.info("📧 RabbitMQ connection status updated to REAL after initial timeout.")
                        except Exception as e:
                            logger.warning(f"📧 Failed to finalize connection after timeout: {e}")
                    else:
                        logger.warning("📧 Connection is closed, will reconnect")
                        self._rabbitmq_connection = None
                        self._rabbitmq_channel = None
                        await self._setup_rabbitmq_connection()
                        continue
                # --- KẾT THÚC PHẦN THÊM ---

                # Kiểm tra connection
                if self._rabbitmq_connection is None:
                    logger.warning("📧 RabbitMQ connection is None, reconnecting...")
                    self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
                    await self._setup_rabbitmq_connection()
                    continue

                if self._rabbitmq_connection.is_closed:
                    logger.warning("📧 RabbitMQ connection was closed, reconnecting...")
                    self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
                    self._rabbitmq_connection = None
                    self._rabbitmq_channel = None
                    await self._setup_rabbitmq_connection()
                    continue

                # Kiểm tra và tái tạo channel
                if self._rabbitmq_channel is None or self._rabbitmq_channel.is_closed:
                    logger.warning("📧 RabbitMQ channel was closed, recreating...")
                    self._rabbitmq_channel = await self._rabbitmq_connection.channel()
                    queue_name = os.getenv("RABBITMQ_QUEUE", "notification.alerts")
                    exchange_name = os.getenv("RABBITMQ_EXCHANGE", "amq.topic")
                    routing_key = os.getenv("RABBITMQ_ROUTING_KEY", "notification.alerts")
                    queue = await self._rabbitmq_channel.declare_queue(queue_name, durable=True)
                    await queue.bind(exchange_name, routing_key)
                    logger.info("📧 RabbitMQ channel recreated")

                # Gửi heartbeat
                exchange = await self._rabbitmq_channel.get_exchange("amq.topic")
                heartbeat_payload = {
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                    "source": "b6-core"
                }
                await exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(heartbeat_payload).encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        expiration=5000  # int
                    ),
                    routing_key="heartbeat"
                )
                logger.debug("📧 Heartbeat sent to RabbitMQ")

            except asyncio.CancelledError:
                logger.info("📧 RabbitMQ keepalive task cancelled")
                break
            except Exception as e:
                logger.warning(f"📧 RabbitMQ keepalive error: {e}, reconnecting...")
                self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
                self._rabbitmq_connection = None
                self._rabbitmq_channel = None
                await self._setup_rabbitmq_connection()
    
    def get_rabbitmq_connection(self):
        """Lấy connection RabbitMQ đã giữ"""
        return self._rabbitmq_connection
    
    def get_rabbitmq_channel(self):
        """Lấy channel RabbitMQ đã giữ"""
        return self._rabbitmq_channel
    
    async def start_retry_tasks(self):
        """Khởi động retry tasks"""
        logger.info("🔄 Starting connection retry tasks (per-service config)...")
        
        for service in ["b3", "b4", "b5", "b7"]:
            config = self.services_config.get(service, {})
            
            if (config.get("retry_enabled", False) and 
                self.status.get(service) == ConnectionStatus.FALLBACK and
                config.get("auto_detect", False)):
                
                interval = config.get("retry_interval", 60)
                task = asyncio.create_task(self._retry_connection(service, interval))
                self._retry_tasks[service] = task
                logger.info(f"🔄 Retry task started for {service} (interval: {interval}s)")
            else:
                logger.info(f"🔵 {service} retry disabled (retry_enabled={config.get('retry_enabled', False)}, "
                           f"status={self.status.get(service).value})")
    
    async def _retry_connection(self, service_name: str, interval: int):
        """Retry kết nối định kỳ"""
        while True:
            try:
                await asyncio.sleep(interval)
                
                if (self.status.get(service_name) == ConnectionStatus.FALLBACK and 
                    self._initial_checked.get(service_name, False)):
                    
                    config = self.services_config.get(service_name, {})
                    url = config.get("url", "")
                    timeout = config.get("timeout", self.connection_timeout)
                    
                    if url:
                        logger.info(f"🔄 Retrying connection to {service_name} at {url}")
                        await self.check_connection(service_name, url, timeout)
                        
                        if self.status.get(service_name) == ConnectionStatus.REAL:
                            logger.info(f"✅ {service_name} reconnected successfully!")
                            break
            except asyncio.CancelledError:
                logger.info(f"🔄 Retry task for {service_name} cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Retry error for {service_name}: {e}")
    
    async def stop_retry_tasks(self):
        """Dừng tất cả retry tasks"""
        for service, task in self._retry_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"🔄 Retry task stopped for {service}")
        self._retry_tasks.clear()
        
        if self._rabbitmq_keepalive_task:
            self._rabbitmq_keepalive_task.cancel()
            try:
                await self._rabbitmq_keepalive_task
            except asyncio.CancelledError:
                pass
    
    def get_status(self, service_name: str) -> ConnectionStatus:
        return self.status.get(service_name, ConnectionStatus.FALLBACK)
    
    def should_use_real(self, service_name: str) -> bool:
        if self._check_failed.get(service_name, False):
            return False
        if not self._initial_checked.get(service_name, False):
            return False
        return self.get_status(service_name) == ConnectionStatus.REAL
    
    def is_rabbitmq_available(self) -> bool:
        """Kiểm tra RabbitMQ availability - bao gồm cả channel"""
        if not self._rabbitmq_connected:
            return False
        
        if self.status.get("b7_rabbitmq") != ConnectionStatus.REAL:
            return False
        
        if self._rabbitmq_connection is None:
            return False
        
        if self._rabbitmq_connection.is_closed:
            logger.warning("📧 RabbitMQ connection was closed")
            self._rabbitmq_connected = False
            self.status["b7_rabbitmq"] = ConnectionStatus.FALLBACK
            asyncio.create_task(self._setup_rabbitmq_connection())
            return False
        
        # Kiểm tra channel
        if self._rabbitmq_channel is None or self._rabbitmq_channel.is_closed:
            logger.warning("📧 RabbitMQ channel was closed, attempting to recreate...")
            try:
                asyncio.create_task(self._recreate_channel())
            except Exception as e:
                logger.error(f"📧 Failed to recreate channel: {e}")
            return False
        
        return True
    
    async def _recreate_channel(self):
        """Tái tạo channel khi bị mất"""
        try:
            if self._rabbitmq_connection and not self._rabbitmq_connection.is_closed:
                self._rabbitmq_channel = await self._rabbitmq_connection.channel()
                queue_name = os.getenv("RABBITMQ_QUEUE", "notification.alerts")
                exchange_name = os.getenv("RABBITMQ_EXCHANGE", "amq.topic")
                routing_key = os.getenv("RABBITMQ_ROUTING_KEY", "notification.alerts")
                queue = await self._rabbitmq_channel.declare_queue(queue_name, durable=True)
                await queue.bind(exchange_name, routing_key)
                logger.info("📧 RabbitMQ channel recreated successfully")
                self.status["b7_rabbitmq"] = ConnectionStatus.REAL
            else:
                await self._setup_rabbitmq_connection()
        except Exception as e:
            logger.error(f"📧 Failed to recreate channel: {e}")
            await self._setup_rabbitmq_connection()
    
    def log_status_summary(self):
        logger.info("📊 Connection Status Summary:")
        for service in ["b3", "b4", "b5", "b7"]:
            config = self.services_config.get(service, {})
            status = self.get_status(service)
            failed = self._check_failed.get(service, False)
            retry_enabled = config.get("retry_enabled", False)
            logger.info(f"   {service}: {status.value} (failed={failed}, retry_enabled={retry_enabled})")
        rabbit_status = self.get_status("b7_rabbitmq")
        logger.info(f"   b7_rabbitmq: {rabbit_status.value}")
    
    def get_status_display(self) -> Dict[str, str]:
        displays = {}
        for service in ["b3", "b4", "b5", "b7"]:
            status = self.get_status(service)
            config = self.services_config.get(service, {})
            retry_enabled = config.get("retry_enabled", False)
            
            if status == ConnectionStatus.REAL:
                displays[service] = "🟢 Connected (REAL)"
            elif status == ConnectionStatus.OFFLINE:
                displays[service] = "🔴 Offline"
            elif status == ConnectionStatus.DISABLED:
                displays[service] = "⚪ Disabled"
            else:
                displays[service] = f"🟡 Fallback{' (retry enabled)' if retry_enabled else ''}"
        
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