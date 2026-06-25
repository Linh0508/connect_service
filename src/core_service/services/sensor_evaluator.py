"""
Sensor Evaluator - Phân tích và đánh giá dữ liệu sensor
Version: 2.1 - Trả về dict cho device_registry
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from src.core_service.models import (
    SensorEvent, SensorReading, SensorStatus, AlertLevel,
    SensorEvaluationResult, DeviceRegistry
)
from src.core_service.services.device_registry import device_registry_service
from uuid import uuid4

logger = logging.getLogger(__name__)


class SensorEvaluator:
    def __init__(self):
        # Ngưỡng theo yêu cầu nghiệp vụ
        self.thresholds = {
            "temperature": {
                "warning": 35.0,
                "danger": 40.0
            },
            "humidity": {
                "warning": 85.0
            },
            "co2": {
                "warning": 1200,
                "danger": 1800
            },
            "smoke": {
                "warning": 0.5,
                "danger": 1.0
            },
            "battery": {
                "warning": 20.0
            }
        }
        
        # Map status -> alert_level
        self.alert_level_map = {
            SensorStatus.NORMAL: AlertLevel.LOW,
            SensorStatus.WARNING: AlertLevel.MEDIUM,
            SensorStatus.DANGER: AlertLevel.HIGH,
            SensorStatus.SENSOR_ERROR: AlertLevel.HIGH,
            SensorStatus.INVALID_DEVICE: AlertLevel.CRITICAL,
        }

    async def evaluate(self, event: SensorEvent) -> SensorEvaluationResult:
        """
        Đánh giá dữ liệu sensor - ĐẦY ĐỦ THEO YÊU CẦU NGHIỆP VỤ
        """
        logger.info(f"🔍 Evaluating sensor {event.device_id}")
        
        # ============================================================
        # 1. VALIDATE: Kiểm tra field bắt buộc
        # ============================================================
        if not event.device_id:
            return self._create_error_result(
                event, 
                SensorStatus.INVALID_DEVICE,
                "Missing required field: device_id"
            )
        
        if event.temperature_c is None and event.humidity_percent is None:
            return self._create_error_result(
                event,
                SensorStatus.SENSOR_ERROR,
                "Both temperature and humidity are null"
            )
        
        # ============================================================
        # 2. CHECK DEVICE: Đối chiếu device_registry
        # ============================================================
        device_registry = None
        try:
            device_data = await asyncio.wait_for(
                device_registry_service.get_device(event.device_id),
                timeout=2.0
            )
            # ✅ Chuyển đổi thành dict nếu là object
            if device_data:
                if isinstance(device_data, dict):
                    device_registry = device_data
                elif hasattr(device_data, 'dict'):
                    device_registry = device_data.dict()
                else:
                    # Fallback: tạo dict từ object
                    device_registry = {
                        "device_id": getattr(device_data, 'device_id', event.device_id),
                        "device_type": getattr(device_data, 'device_type', 'unknown'),
                        "location": getattr(device_data, 'location', 'UNKNOWN'),
                        "room": getattr(device_data, 'room', 'UNKNOWN'),
                        "status": getattr(device_data, 'status', 'active')
                    }
            logger.debug(f"Device registry result: {device_registry}")
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Device registry timeout for {event.device_id}")
        except Exception as e:
            logger.warning(f"⚠️ Device registry error: {e}")
        
        # ============================================================
        # 3. INVALID_DEVICE: Thiết bị không có trong registry
        # ============================================================
        if not device_registry:
            return self._create_error_result(
                event,
                SensorStatus.INVALID_DEVICE,
                f"Device {event.device_id} not found in registry"
            )
        
        # ============================================================
        # 4. CLASSIFY: Phân loại trạng thái
        # ============================================================
        status, reasons = self._classify_status(event)
        
        # ============================================================
        # 5. ASSESS: Xác định alert_level
        # ============================================================
        alert_level = self.alert_level_map.get(status, AlertLevel.LOW)
        reason = "; ".join(reasons) if reasons else "All values within normal range"
        
        # ============================================================
        # 6. KIỂM TRA MOTION + TIME (nếu có motion_detected)
        # ============================================================
        motion_reason = None
        if event.motion_detected:
            motion_reason = self._check_motion_time(event, device_registry)
            if motion_reason:
                reasons.append(motion_reason)
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                    alert_level = AlertLevel.HIGH
                reason = "; ".join(reasons)

        # ============================================================
        # 7. TẠO KẾT QUẢ
        # ============================================================
        return SensorEvaluationResult(
            device_id=event.device_id,
            device_registry=device_registry,  # ✅ Đã là dict
            status=status,
            alert_level=alert_level,
            reason=reason,
            alerts=self._build_alerts(event, status, reason),
            readings=SensorReading(
                temperature_c=event.temperature_c,
                humidity_percent=event.humidity_percent,
                light_lux=event.light_lux,
                co2_ppm=event.co2_ppm,
                smoke_ppm=event.smoke_ppm,
                battery_percent=event.battery_percent,
                motion_detected=event.motion_detected
            ),
            timestamp=event.timestamp or datetime.now(),
            correlation_id=event.correlationId or uuid4(),
            raw_event_id=event.event_id
        )

    def _create_error_result(self, event: SensorEvent, status: SensorStatus, reason: str) -> SensorEvaluationResult:
        """Tạo kết quả lỗi"""
        return SensorEvaluationResult(
            device_id=event.device_id,
            device_registry=None,
            status=status,
            alert_level=self.alert_level_map.get(status, AlertLevel.HIGH),
            reason=reason,
            alerts=[{
                "rule_id": status.value.upper(),
                "message": reason,
                "severity": self.alert_level_map.get(status, AlertLevel.HIGH).value.upper()
            }],
            readings=SensorReading(
                temperature_c=event.temperature_c,
                humidity_percent=event.humidity_percent,
                light_lux=event.light_lux,
                co2_ppm=event.co2_ppm,
                smoke_ppm=event.smoke_ppm,
                battery_percent=event.battery_percent,
                motion_detected=event.motion_detected
            ),
            timestamp=event.timestamp or datetime.now(),
            correlation_id=event.correlationId or uuid4(),
            raw_event_id=event.event_id
        )

    def _classify_status(self, event: SensorEvent) -> Tuple[SensorStatus, List[str]]:
        """Phân loại trạng thái dựa trên ngưỡng"""
        reasons = []
        status = SensorStatus.NORMAL
        
        # 1. Temperature
        if event.temperature_c is not None:
            if event.temperature_c >= self.thresholds["temperature"]["danger"]:
                status = SensorStatus.DANGER
                reasons.append(f"Temperature {event.temperature_c}°C exceeds danger threshold ({self.thresholds['temperature']['danger']}°C)")
            elif event.temperature_c >= self.thresholds["temperature"]["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                reasons.append(f"Temperature {event.temperature_c}°C exceeds warning threshold ({self.thresholds['temperature']['warning']}°C)")

        # 2. Humidity
        if event.humidity_percent is not None:
            if event.humidity_percent >= self.thresholds["humidity"]["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                reasons.append(f"Humidity {event.humidity_percent}% exceeds warning threshold ({self.thresholds['humidity']['warning']}%)")

        # 3. CO2
        if event.co2_ppm is not None:
            if event.co2_ppm >= self.thresholds["co2"]["danger"]:
                status = SensorStatus.DANGER
                reasons.append(f"CO₂ {event.co2_ppm}ppm exceeds danger threshold ({self.thresholds['co2']['danger']}ppm)")
            elif event.co2_ppm >= self.thresholds["co2"]["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                reasons.append(f"CO₂ {event.co2_ppm}ppm exceeds warning threshold ({self.thresholds['co2']['warning']}ppm)")

        # 4. Smoke
        if event.smoke_ppm is not None:
            if event.smoke_ppm >= self.thresholds["smoke"]["danger"]:
                status = SensorStatus.DANGER
                reasons.append(f"Smoke {event.smoke_ppm}ppm exceeds danger threshold ({self.thresholds['smoke']['danger']}ppm)")
            elif event.smoke_ppm >= self.thresholds["smoke"]["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                reasons.append(f"Smoke {event.smoke_ppm}ppm exceeds warning threshold ({self.thresholds['smoke']['warning']}ppm)")

        # 5. Battery
        if event.battery_percent is not None:
            if event.battery_percent < self.thresholds["battery"]["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                reasons.append(f"Battery {event.battery_percent}% below warning threshold ({self.thresholds['battery']['warning']}%)")

        # 6. Nếu không có lý do nào → NORMAL
        if not reasons:
            reasons.append("All values within normal range")

        return status, reasons

    def _check_motion_time(self, event: SensorEvent, device: Dict) -> Optional[str]:
        """Kiểm tra motion detection theo khung giờ"""
        if not event.motion_detected:
            return None

        current_time = event.timestamp or datetime.now()
        hour = current_time.hour

        # Khung giờ bất thường: 22:00 - 06:00
        if hour >= 22 or hour < 6:
            location = device.get('location', 'unknown') if device else 'unknown'
            return f"Motion detected at abnormal time {current_time.strftime('%H:%M')} at {location}"

        # Kiểm tra nếu trong khung giờ đóng cửa (Lab đóng cửa sau 18:00)
        room = device.get('room', '') if device else ''
        if room.startswith("LAB") and (hour >= 18 or hour < 7):
            return f"Motion detected in lab after hours: {room} at {current_time.strftime('%H:%M')}"

        return None

    def _build_alerts(self, event: SensorEvent, status: SensorStatus, reason: str) -> List[Dict]:
        """Xây dựng danh sách alerts dựa trên status"""
        alerts = []
        alert_level_map = {
            SensorStatus.NORMAL: "LOW",
            SensorStatus.WARNING: "MEDIUM",
            SensorStatus.DANGER: "HIGH",
            SensorStatus.SENSOR_ERROR: "HIGH",
            SensorStatus.INVALID_DEVICE: "CRITICAL"
        }
        
        if status != SensorStatus.NORMAL:
            alerts.append({
                "rule_id": status.value.upper(),
                "message": reason,
                "severity": alert_level_map.get(status, "MEDIUM")
            })
        
        return alerts


# Global instance
sensor_evaluator = SensorEvaluator()