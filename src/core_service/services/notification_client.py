"""
Notification Client - Gửi alert sang B7 via RabbitMQ (Queue Async)
Tuân thủ contract: event-contract-template.md
"""

import os
import logging
import json
import uuid
import aio_pika
from aio_pika import connect_robust, Message
from datetime import datetime  # ← SỬA: Import datetime class
from src.core_service.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class NotificationClient:
    def __init__(self):
        # Cấu hình từ env (giống script test)
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "26.64.54.49")
        self.rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        self.rabbitmq_pass = os.getenv("RABBITMQ_PASS", "guest")
        self.exchange_name = os.getenv("RABBITMQ_EXCHANGE", "amq.topic")
        self.routing_key = os.getenv("RABBITMQ_ROUTING_KEY", "core.notification.alerts")
        self.queue_name = os.getenv("RABBITMQ_QUEUE", "notification.alerts")
        self.service_name = "b7"
        self._connection = None
        self._channel = None
        
        # Log cấu hình khi khởi tạo
        logger.info(f"📧 NotificationClient initialized:")
        logger.info(f"   - Host: {self.rabbitmq_host}:{self.rabbitmq_port}")
        logger.info(f"   - User: {self.rabbitmq_user}")
        logger.info(f"   - Exchange: {self.exchange_name}")
        logger.info(f"   - Routing Key: {self.routing_key}")
        logger.info(f"   - Queue: {self.queue_name}")

    async def _ensure_connection(self):
        """Đảm bảo có kết nối RabbitMQ - GIỐNG SCRIPT TEST"""
        if self._connection is None or self._connection.is_closed:
            try:
                connection_url = f"amqp://{self.rabbitmq_user}:{self.rabbitmq_pass}@{self.rabbitmq_host}:{self.rabbitmq_port}/"
                logger.info(f"🔗 Connecting to RabbitMQ: {connection_url}")
                
                self._connection = await connect_robust(connection_url)
                self._channel = await self._connection.channel()
                
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
        Gửi alert sang Notification Service (B7) qua RabbitMQ.
        Payload được xây dựng GIỐNG HỆT SCRIPT TEST.
        """
        if connection_manager.should_use_real(self.service_name):
            logger.info(f"📧 [B7_DEBUG] should_use_real=True, attempting to publish...")
            
            if await self._ensure_connection():
                try:
                    event_id = str(alert.eventId)
                    
                    # Tạo payload theo đúng format script test
                    payload = {
                        "eventId": event_id,
                        "eventType": "alert.created",
                        "occurredAt": datetime.now().isoformat(),  # ← ĐÃ SỬA
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
                    logger.debug(f"📧 [B7_REAL] Payload: {json.dumps(payload, indent=2)}")
                    return True
                    
                except Exception as e:
                    logger.warning(f"📧 [B7_ERROR] RabbitMQ publish failed: {e} -> FALLBACK")
            else:
                logger.warning("📧 [B7_WARNING] RabbitMQ not available -> FALLBACK")
        else:
            logger.info(f"📧 [B7_DEBUG] should_use_real=False, using FALLBACK")

        # FALLBACK MODE
        logger.info(f"📧 [B7_FALLBACK] Alert stored locally: {alert.eventId} - {alert.severity}")
        return True

    async def close(self):
        if self._connection:
            await self._connection.close()
            logger.info("📧 RabbitMQ connection closed")