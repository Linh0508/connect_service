import asyncio
import aio_pika
import json
from datetime import datetime
import uuid

TARGET = "security_team"
SEVERITY = "HIGH"
EVENT_TYPE = "alert.created"
ALERT_ID = "alert-test-001"
TITLE = "Quang Tùng MasterD"
MESSAGE = "Quang Tùng MasterD"

async def publish():
    connection = None
    try:
        connection = await aio_pika.connect_robust(
            "amqp://guest:guest@26.64.54.49:5672/"
        )
        channel = await connection.channel()
        event_id = str(uuid.uuid4())

        event = {
            "eventId": event_id,
            "eventType": EVENT_TYPE,
            "occurredAt": datetime.now().isoformat(),
            "correlationId": "corr-" + str(uuid.uuid4())[:8],
            "traceId": "trace-" + str(uuid.uuid4())[:8],
            "source": "core-business",
            "data": {
                "alertId": ALERT_ID,
                "severity": SEVERITY,
                "target": TARGET,
                "title": TITLE,
                "message": MESSAGE
            }
        }

        if EVENT_TYPE == "alert.escalated":
            event["data"].update({
                "previousSeverity": "LOW",
                "newSeverity": SEVERITY,
                "reason": "Cảnh báo leo thang do lặp lại nhiều lần",
                "target": TARGET
            })
        elif EVENT_TYPE == "alert.resolved":
            event["data"].update({
                "resolvedBy": "admin",
                "resolutionNote": "Đã xử lý xong sự cố",
                "target": TARGET
            })

        routing_key = "notification.alerts"
        exchange = await channel.get_exchange("amq.topic")

        # Gửi message
        await exchange.publish(
            aio_pika.Message(body=json.dumps(event).encode()),
            routing_key=routing_key
        )

        # ⭐ Chờ 0.5 giây để đảm bảo dữ liệu được đẩy ra socket
        await asyncio.sleep(0.5)

        print(f"✅ Đã publish event tới {routing_key} qua amq.topic")
        print(f"   Event ID  : {event_id}")
        print(f"   Type      : {EVENT_TYPE}")
        print(f"   Target    : {TARGET}")
        print(f"   Severity  : {SEVERITY}")

    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        if connection and not connection.is_closed:
            await connection.close()

if __name__ == "__main__":
    asyncio.run(publish())