"""
Notification Client - Gửi alert sang B7 via RabbitMQ (Queue Async)
"""

import os
import logging
import json
import uuid
import asyncio
import aio_pika
from aio_pika import connect_robust, Message
from datetime import datetime
from src.core_service.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class NotificationClient:
    def __init__(self):
        # Cấu hình từ env
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "26.64.54.49")
        self.rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        self.rabbitmq_pass = os.getenv("RABBITMQ_PASS", "guest")
        self.exchange_name = os.getenv("RABBITMQ_EXCHANGE", "amq.topic")
        self.routing_key = os.getenv("RABBITMQ_ROUTING_KEY", "notification.alerts")
        self.queue_name = os.getenv("RABBITMQ_QUEUE", "notification.alerts")
        self.service_name = "b7"
        self._connection = None
        self._channel = None
        self._connection_timeout = float(os.getenv("RABBITMQ_CONNECTION_TIMEOUT", "3.0"))
        
        # Trạng thái kết nối - đọc từ connection_manager
        self._rabbitmq_available = connection_manager.is_rabbitmq_available()
        self._connection_attempted = False
        
        # Log cấu hình
        logger.info(f"📧 NotificationClient initialized:")
        logger.info(f"   - Host: {self.rabbitmq_host}:{self.rabbitmq_port}")
        logger.info(f"   - Timeout: {self._connection_timeout}s")
        logger.info(f"   - Available: {self._rabbitmq_available}")

    async def _ensure_connection(self):
        """
        Đảm bảo có kết nối RabbitMQ.
        CHỈ KẾT NỐI KHI B7 Ở REAL MODE VÀ RABBITMQ AVAILABLE
        """
        
        # ============================================================
        # QUAN TRỌNG: CHỈ KẾT NỐI KHI B7 Ở REAL MODE
        # ============================================================
        if not connection_manager.should_use_real(self.service_name):
            logger.debug("📧 B7 is in FALLBACK mode, skipping RabbitMQ connection")
            return False
        
        # Nếu đã thử kết nối trước đó và thất bại, KHÔNG THỬ LẠI
        if self._connection_attempted:
            logger.debug("📧 Connection already attempted, skipping")
            return False
        
        # Nếu đã có kết nối và còn sống, dùng lại
        if self._connection is not None and not self._connection.is_closed:
            return True
        
        try:
            # Nếu host là localhost hoặc empty, bỏ qua
            if self.rabbitmq_host in ["localhost", "127.0.0.1", ""]:
                logger.info(f"📧 RabbitMQ disabled (host={self.rabbitmq_host})")
                self._connection_attempted = True
                return False
            
            connection_url = f"amqp://{self.rabbitmq_user}:{self.rabbitmq_pass}@{self.rabbitmq_host}:{self.rabbitmq_port}/"
            logger.info(f"📧 Connecting to RabbitMQ (B7 is REAL mode)...")
            
            # Tắt auto-reconnect
            self._connection = await asyncio.wait_for(
                connect_robust(
                    connection_url,
                    reconnect_interval=0,      # Tắt auto-reconnect
                    reconnect_attempts=1       # Chỉ thử 1 lần
                ),
                timeout=self._connection_timeout
            )
            self._channel = await self._connection.channel()
            
            queue = await self._channel.declare_queue(self.queue_name, durable=True)
            await queue.bind(self.exchange_name, self.routing_key)
            
            logger.info(f"✅ RabbitMQ connected: {self.rabbitmq_host}:{self.rabbitmq_port}")
            self._rabbitmq_available = True
            self._connection_attempted = True
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ RabbitMQ connection timeout after {self._connection_timeout}s")
            self._rabbitmq_available = False
            self._connection = None
            self._connection_attempted = True
            return False
        except Exception as e:
            logger.warning(f"❌ RabbitMQ connection failed: {e}")
            self._rabbitmq_available = False
            self._connection = None
            self._connection_attempted = True
            return False

    async def send_alert(self, alert) -> bool:
        """
        Gửi alert sang Notification Service (B7) qua RabbitMQ.
        Nếu không kết nối được -> FALLBACK
        """
        # ============================================================
        # QUAN TRỌNG: CHỈ GỬI REAL KHI B7 Ở REAL MODE
        # ============================================================
        if not connection_manager.should_use_real(self.service_name):
            logger.debug(f"📧 [B7_FALLBACK] B7 is FALLBACK mode, alert stored locally: {alert.eventId}")
            return True
        
        # Kiểm tra RabbitMQ có sẵn sàng không
        if not connection_manager.is_rabbitmq_available():
            logger.debug(f"📧 [B7_FALLBACK] RabbitMQ not available: {alert.eventId}")
            return True
        
        # Nếu đã thử kết nối và thất bại, không thử lại
        if self._connection_attempted and self._connection is None:
            logger.debug(f"📧 [B7_FALLBACK] Connection already failed, skipping: {alert.eventId}")
            return True
        
        # Thử gửi qua RabbitMQ (chỉ 1 lần)
        if await self._ensure_connection():
            try:
                event_id = str(alert.eventId)
                
                payload = {
                    "eventId": event_id,
                    "eventType": "alert.created",
                    "occurredAt": datetime.now().isoformat(),
                    "correlationId": str(alert.correlationId),
                    "traceId": str(alert.traceId),
                    "source": "core-business",
                    "data": {
                        "alertId": alert.gateId or str(uuid.uuid4()),
                        "severity": alert.severity,
                        "userId": alert.userId,
                        "title": f"🔥 {event_id[:8]} {alert.severity} Alert",
                        "message": alert.alertDetails.get("message", "Alert from B6")
                    }
                }

                exchange = await self._channel.get_exchange(self.exchange_name)
                await exchange.publish(
                    Message(
                        body=json.dumps(payload).encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                    ),
                    routing_key=self.routing_key
                )
                
                logger.info(f"📧 [B7_REAL] Alert published to RabbitMQ: {event_id} - {alert.severity}")
                return True
                
            except Exception as e:
                logger.warning(f"📧 [B7_ERROR] RabbitMQ publish failed: {e} -> FALLBACK")
                self._connection = None
                return True
        else:
            return True

    async def close(self):
        if self._connection:
            await self._connection.close()
            logger.info("📧 RabbitMQ connection closed")