"""
Camera Event Evaluator - Xử lý sự kiện từ Camera Stream (B2)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, time
from src.core_service.models import CameraEvent, AlertEvent
from src.core_service.services.device_registry import device_registry_service
from uuid import uuid4

logger = logging.getLogger(__name__)


class CameraEvaluator:
    def __init__(self):
        # Các khu vực nhạy cảm (cần giám sát đặc biệt)
        self.sensitive_locations = [
            "SERVER_ROOM",
            "DATA_CENTER",
            "RESTRICTED_ZONE",
            "VAULT",
            "LAB_CRITICAL"
        ]
        
        # Khung giờ cấm (không ai được phép xuất hiện)
        self.restricted_hours = {
            "start": 22,  # 22:00
            "end": 6      # 06:00
        }
        
        # Ngưỡng thời gian bất thường (phút)
        self.motion_duration_threshold = 5  # 5 phút
    
    async def evaluate(self, event: CameraEvent) -> Dict[str, Any]:
        """
        Đánh giá sự kiện camera và xác định có cần cảnh báo không
        """
        alerts = []
        alert_triggered = False
        severity = None
        message = None
        rule_id = None
        
        # 1. Kiểm tra loại sự kiện
        if event.event_type == "camera_offline":
            alert_triggered = True
            severity = "CRITICAL"
            rule_id = "CAMERA_OFFLINE"
            message = f"Camera {event.camera_id} is offline at {event.location or 'unknown location'}"
            
        elif event.event_type == "obstruction":
            alert_triggered = True
            severity = "HIGH"
            rule_id = "CAMERA_OBSTRUCTION"
            message = f"Camera {event.camera_id} is obstructed at {event.location or 'unknown location'}"
        
        # 2. Kiểm tra chuyển động bất thường
        elif event.event_type == "motion_detected" and event.motion_detected:
            # Kiểm tra vị trí nhạy cảm
            if event.location and any(loc in event.location.upper() for loc in self.sensitive_locations):
                alert_triggered = True
                severity = "CRITICAL"
                rule_id = "MOTION_SENSITIVE_AREA"
                message = f"Motion detected in sensitive area: {event.location} - Camera: {event.camera_id}"
            
            # Kiểm tra khung giờ cấm
            else:
                current_hour = event.timestamp.hour
                if current_hour >= self.restricted_hours["start"] or current_hour < self.restricted_hours["end"]:
                    alert_triggered = True
                    severity = "HIGH"
                    rule_id = "MOTION_RESTRICTED_HOURS"
                    message = f"Motion detected during restricted hours ({event.timestamp.strftime('%H:%M')}) at {event.location or 'unknown location'} - Camera: {event.camera_id}"
        
        # 3. Nếu có cảnh báo, tạo alert
        if alert_triggered:
            alert = AlertEvent(
                eventId=uuid4(),
                correlationId=event.correlationId,
                traceId=uuid4(),
                severity=severity,
                userId="SYSTEM",
                gateId=event.location or "CAMERA_SYSTEM",
                alertDetails={
                    "ruleId": rule_id,
                    "message": message,
                    "camera_id": event.camera_id,
                    "event_type": event.event_type,
                    "motion_detected": event.motion_detected,
                    "frame_url": event.frame_url,
                    "location": event.location,
                    "timestamp": event.timestamp.isoformat()
                },
                timestamp=datetime.now()
            )
            alerts.append(alert)
        
        return {
            "alert_triggered": alert_triggered,
            "alerts": alerts,
            "severity": severity,
            "message": message,
            "rule_id": rule_id,
            "camera_id": event.camera_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp
        }

# Global instance
camera_evaluator = CameraEvaluator()