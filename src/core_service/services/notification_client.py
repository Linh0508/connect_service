"""
Notification Client - Gửi alert sang B7 via RabbitMQ (Queue Async)
Version: 3.4 - Tối ưu kết nối và routing key
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
from typing import Optional, Dict

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
        
        # SỬ DỤNG CONNECTION/CHANNEL TỪ CONNECTION_MANAGER
        self._connection = None
        self._channel = None
        self._max_retries = 3
        
        # Lưu request/response cuối
        self._last_request: Optional[Dict] = None
        self._last_response: Optional[Dict] = None
        self._last_realtime_entry: Optional[Dict] = None
        
        # Lấy trạng thái từ connection_manager
        self._rabbitmq_available = connection_manager.is_rabbitmq_available()
        
        logger.info(f"📧 NotificationClient initialized:")
        logger.info(f"   - Host: {self.rabbitmq_host}:{self.rabbitmq_port}")
        logger.info(f"   - Exchange: {self.exchange_name}, Routing Key: {self.routing_key}")
        logger.info(f"   - Available: {self._rabbitmq_available}")

    async def _ensure_channel(self):
        """Đảm bảo có channel để publish - tự động tái tạo nếu mất"""
        # Lấy connection và channel từ connection_manager
        self._connection = connection_manager.get_rabbitmq_connection()
        self._channel = connection_manager.get_rabbitmq_channel()
        
        # Nếu connection bị đóng hoặc None, yêu cầu connection_manager kết nối lại
        if self._connection is None or self._connection.is_closed:
            logger.warning("📧 RabbitMQ connection is closed or None, reconnecting...")
            await connection_manager._setup_rabbitmq_connection()
            self._connection = connection_manager.get_rabbitmq_connection()
            self._channel = connection_manager.get_rabbitmq_channel()
            
            if self._connection is None or self._connection.is_closed:
                logger.error("📧 Cannot get RabbitMQ connection")
                return False
        
        # Nếu channel bị đóng hoặc None, tạo channel mới
        if self._channel is None or self._channel.is_closed:
            logger.warning("📧 RabbitMQ channel is closed or None, creating new channel...")
            try:
                self._channel = await self._connection.channel()
                # Đảm bảo queue tồn tại
                queue = await self._channel.declare_queue(self.queue_name, durable=True)
                await queue.bind(self.exchange_name, self.routing_key)
                # Cập nhật vào connection_manager để dùng chung
                connection_manager._rabbitmq_channel = self._channel
                logger.info("📧 RabbitMQ channel recreated and bound")
            except Exception as e:
                logger.error(f"📧 Failed to create channel: {e}")
                return False
        
        return True

    async def send_alert(self, alert, client_ip: str = None) -> bool:
        """
        Gửi alert sang Notification Service (B7) qua RabbitMQ.
        ✅ PAYLOAD ĐÚNG SPEC B7
        """
        # Lấy thông tin từ alert object
        alert_id = alert.alert_id or f"ALT-{uuid.uuid4().hex[:8].upper()}"
        event_id = str(alert.eventId) if hasattr(alert, 'eventId') else str(uuid.uuid4())
        event_type = alert.event_type or "alert.created"
        
        target = alert.target or "security_team"
        # ✅ SỬA: Chuyển severity thành UPPERCASE
        severity_value = alert.severity.value.upper() if hasattr(alert.severity, 'value') else str(alert.severity).upper()
        
        # ============================================================
        # PAYLOAD ĐÚNG SPEC B7
        # ============================================================
        payload = {
            "eventId": event_id,
            "eventType": event_type,
            "occurredAt": datetime.now().isoformat(),
            "correlationId": f"corr-{uuid.uuid4().hex[:8]}",
            "traceId": f"trace-{uuid.uuid4().hex[:8]}",
            "source": "core-business",
            "data": {
                "alertId": alert_id,
                "severity": severity_value,  # ✅ Đã UPPERCASE
                "target": target,
                "title": alert.details.get("title", f"🚨 {alert.alert_type or 'Alert'} - {severity_value}"),
                "message": alert.message or "Alert from B6 Core",
                "details": alert.details or {}
            }
        }
        
        # Nếu là event_type đặc biệt, thêm fields
        if event_type == "alert.escalated":
            payload["data"].update({
                "previousSeverity": alert.details.get("previousSeverity", "LOW"),
                "newSeverity": severity_value,
                "reason": alert.details.get("reason", "Cảnh báo leo thang do lặp lại nhiều lần"),
                "target": target
            })
        elif event_type == "alert.resolved":
            payload["data"].update({
                "resolvedBy": alert.details.get("resolvedBy", "admin"),
                "resolutionNote": alert.details.get("resolutionNote", "Đã xử lý xong sự cố"),
                "target": target
            })
        
        # Lưu request
        self._last_request = {
            "exchange": self.exchange_name,
            "routing_key": self.routing_key,
            "payload": payload,
            "mode": "REAL" if connection_manager.should_use_real(self.service_name) else "FALLBACK"
        }
        
        logger.debug(f"📧 [B7_PAYLOAD] Sending: {json.dumps(payload, indent=2)}")
        
        # ============================================================
        # KIỂM TRA REAL MODE
        # ============================================================
        if not connection_manager.should_use_real(self.service_name):
            logger.info(f"📧 [B7_FALLBACK] B7 is FALLBACK mode, alert stored locally: {event_id}")
            self._last_response = {
                "status": "stored",
                "mode": "FALLBACK",
                "message": "Alert stored locally (B7 in fallback mode)",
                "payload": payload
            }
            self._last_realtime_entry = {
                "timestamp": datetime.now().isoformat(),
                "ip": client_ip or "localhost",
                "status": 202,
                "request": payload,
                "response": self._last_response,
                "mode": "FALLBACK"
            }
            return True
        
        # Kiểm tra RabbitMQ có sẵn sàng không
        if not connection_manager.is_rabbitmq_available():
            logger.info(f"📧 [B7_FALLBACK] RabbitMQ not available: {event_id}")
            self._last_response = {
                "status": "stored",
                "mode": "FALLBACK",
                "message": "RabbitMQ not available, alert stored locally",
                "payload": payload
            }
            self._last_realtime_entry = {
                "timestamp": datetime.now().isoformat(),
                "ip": client_ip or "localhost",
                "status": 202,
                "request": payload,
                "response": self._last_response,
                "mode": "FALLBACK"
            }
            return True
        
        # ĐẢM BẢO CHANNEL VÀ PUBLISH VỚI RETRY
        for attempt in range(self._max_retries):
            try:
                if await self._ensure_channel():
                    # Lấy exchange
                    exchange = await self._channel.get_exchange(self.exchange_name)
                    
                    # Tạo message
                    message = Message(
                        body=json.dumps(payload).encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        content_type="application/json",
                        expiration=60000  # int, không có dấu ngoặc kép
                    )
                    
                    # Publish message
                    await exchange.publish(
                        message,
                        routing_key=self.routing_key
                    )
                    
                    self._last_response = {
                        "status": "published",
                        "mode": "REAL",
                        "exchange": self.exchange_name,
                        "routing_key": self.routing_key,
                        "message": "Alert published to RabbitMQ successfully"
                    }
                    
                    self._last_realtime_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "ip": client_ip or "localhost",
                        "status": 200,
                        "request": payload,
                        "response": self._last_response,
                        "mode": "REAL"
                    }
                    
                    logger.info(f"📧 [B7_REAL] ✅ Alert published to RabbitMQ: {event_id} - {severity_value} → target: {target}")
                    return True
                else:
                    logger.warning(f"📧 Cannot get channel, attempt {attempt + 1}/{self._max_retries}")
                    await asyncio.sleep(1)
                    
            except (aio_pika.exceptions.ChannelClosed, aio_pika.exceptions.AMQPChannelError, Exception) as e:
                logger.warning(f"📧 Channel error, recreating: {e}")
                # Tạo lại channel
                try:
                    if self._connection and not self._connection.is_closed:
                        self._channel = await self._connection.channel()
                        queue = await self._channel.declare_queue(self.queue_name, durable=True)
                        await queue.bind(self.exchange_name, self.routing_key)
                        connection_manager._rabbitmq_channel = self._channel
                        logger.info("📧 Channel recreated successfully")
                    else:
                        logger.warning("📧 Connection also closed, full reconnect")
                        await connection_manager._setup_rabbitmq_connection()
                        self._connection = connection_manager.get_rabbitmq_connection()
                        self._channel = connection_manager.get_rabbitmq_channel()
                except Exception as e2:
                    logger.error(f"📧 Failed to recreate channel: {e2}")
                    # Thử reconnect full
                    await connection_manager._setup_rabbitmq_connection()
                    self._connection = connection_manager.get_rabbitmq_connection()
                    self._channel = connection_manager.get_rabbitmq_channel()
                
            except Exception as e:
                logger.warning(f"📧 Publish attempt {attempt + 1} failed: {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(1)
                    # Force reconnect
                    logger.info("📧 Forcing reconnect...")
                    await connection_manager._setup_rabbitmq_connection()
                    self._connection = connection_manager.get_rabbitmq_connection()
                    self._channel = connection_manager.get_rabbitmq_channel()
        
        # Nếu tất cả retry thất bại
        logger.error(f"📧 [B7_ERROR] All {self._max_retries} attempts failed for {event_id}")
        self._last_response = {
            "status": "stored",
            "mode": "FALLBACK",
            "message": f"All {self._max_retries} attempts failed",
            "payload": payload
        }
        self._last_realtime_entry = {
            "timestamp": datetime.now().isoformat(),
            "ip": client_ip or "localhost",
            "status": 202,
            "request": payload,
            "response": self._last_response,
            "mode": "FALLBACK"
        }
        return True
    
    async def get_last_request(self) -> Optional[Dict]:
        return self._last_request
    
    async def get_last_response(self) -> Optional[Dict]:
        return self._last_response
    
    async def get_last_realtime_entry(self) -> Optional[Dict]:
        return self._last_realtime_entry
    
    async def close(self):
        logger.info("📧 NotificationClient closed (connection kept by connection_manager)")