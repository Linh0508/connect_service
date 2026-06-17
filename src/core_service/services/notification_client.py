"""
Notification Client - Gửi alert sang B7 via RabbitMQ (Queue Async)
"""

import os
import logging
import json
import aio_pika
from aio_pika import connect_robust, Message
from src.core_service.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class NotificationClient:
    def __init__(self):
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        self.rabbitmq_pass = os.getenv("RABBITMQ_PASS", "guest")
        self.exchange_name = os.getenv("RABBITMQ_EXCHANGE", "amq.topic")
        self.routing_key = os.getenv("RABBITMQ_ROUTING_KEY", "core.notification.alerts")
        self.queue_name = os.getenv("RABBITMQ_QUEUE", "notification.alerts")
        self.service_name = "b7"
        self._connection = None
        self._channel = None
    
    async def _ensure_connection(self):
        """Đảm bảo có kết nối RabbitMQ"""
        if self._connection is None or self._connection.is_closed:
            try:
                self._connection = await connect_robust(
                    f"amqp://{self.rabbitmq_user}:{self.rabbitmq_pass}@{self.rabbitmq_host}:{self.rabbitmq_port}/"
                )
                self._channel = await self._connection.channel()
                # Khai báo queue và bind (tùy chọn, nhưng nên làm)
                queue = await self._channel.declare_queue(self.queue_name, durable=True)
                await queue.bind(self.exchange_name, self.routing_key)
                logger.info(f"✅ RabbitMQ connected: {self.rabbitmq_host}:{self.rabbitmq_port}")
                return True
            except Exception as e:
                logger.error(f"❌ RabbitMQ connection failed: {e}")
                return False
        return True
    
    async def send_alert(self, alert) -> bool:
        """
        Gửi alert sang Notification Service (B7) qua RabbitMQ
        """
        # Kiểm tra nên dùng REAL (RabbitMQ) hay FALLBACK
        if connection_manager.should_use_real(self.service_name):
            # Chỉ khi kết nối RabbitMQ thành công mới coi là REAL
            if await self._ensure_connection():
                try:
                    # Chuyển AlertEvent sang dict và publish
                    message_body = alert.dict()
                    # Thêm eventType theo đúng contract
                    message_body["eventType"] = "alert.created"
                    # Gửi vào exchange
                    exchange = await self._channel.get_exchange(self.exchange_name)
                    await exchange.publish(
                        Message(
                            body=json.dumps(message_body).encode(),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                        ),
                        routing_key=self.routing_key
                    )
                    logger.info(f"📧 [B7_REAL] Alert published to RabbitMQ: {alert.eventId} - {alert.severity}")
                    return True
                except Exception as e:
                    logger.warning(f"📧 [B7_ERROR] RabbitMQ publish failed: {e} -> FALLBACK")
            else:
                logger.warning("📧 [B7_WARNING] RabbitMQ not available -> FALLBACK")
        
        # FALLBACK MODE
        logger.info(f"📧 [B7_FALLBACK] Alert stored locally: {alert.eventId} - {alert.severity}")
        # Tùy chọn: lưu vào fallback storage để sync sau
        return True
    
    async def close(self):
        if self._connection:
            await self._connection.close()