"""
Sensor Evaluator - Phân tích và đánh giá dữ liệu sensor
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, time
from src.core_service.models import (
    SensorEvent, SensorReading, SensorStatus, 
    SensorEvaluationResult, DeviceRegistry, AlertEvent
)
from src.core_service.services.device_registry import device_registry_service
from uuid import uuid4

logger = logging.getLogger(__name__)


class SensorEvaluator:
    def __init__(self):
        self.temperature_thresholds = {
            "warning": 35.0,
            "danger": 40.0
        }
        self.humidity_thresholds = {
            "warning": 85.0
        }
        self.co2_thresholds = {
            "warning": 1200,
            "danger": 1800
        }
        self.smoke_thresholds = {
            "warning": 0.5,
            "danger": 1.0
        }
        self.battery_thresholds = {
            "warning": 20.0
        }

    async def evaluate(self, event: SensorEvent) -> SensorEvaluationResult:
        """Đánh giá dữ liệu sensor"""
        # 1. Kiểm tra device registry
        device_registry = await device_registry_service.get_device(event.device_id)
        
        if not device_registry:
            return SensorEvaluationResult(
                device_id=event.device_id,
                device_registry=None,
                status=SensorStatus.INVALID_DEVICE,
                alerts=[{
                    "rule_id": "INVALID_DEVICE",
                    "message": f"Device {event.device_id} not found in registry",
                    "severity": "CRITICAL"
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
                correlation_id=event.correlationId or uuid4()
            )

        # 2. Kiểm tra lỗi sensor (null values)
        if event.temperature_c is None and event.humidity_percent is None:
            return SensorEvaluationResult(
                device_id=event.device_id,
                device_registry=device_registry,
                status=SensorStatus.SENSOR_ERROR,
                alerts=[{
                    "rule_id": "SENSOR_ERROR",
                    "message": f"Sensor data missing for device {event.device_id}",
                    "severity": "HIGH"
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
                correlation_id=event.correlationId or uuid4()
            )

        # 3. Phân loại trạng thái
        status, alerts = self._classify_status(event, device_registry)
        
        # 4. Kiểm tra motion + time (nếu có motion_detected)
        if event.motion_detected:
            motion_alerts = self._check_motion_time(event, device_registry)
            alerts.extend(motion_alerts)
            if motion_alerts:
                status = SensorStatus.WARNING if status == SensorStatus.NORMAL else status

        return SensorEvaluationResult(
            device_id=event.device_id,
            device_registry=device_registry,
            status=status,
            alerts=alerts,
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
            correlation_id=event.correlationId or uuid4()
        )

    def _classify_status(self, event: SensorEvent, device: Dict) -> tuple:
        """Phân loại trạng thái dựa trên ngưỡng"""
        alerts = []
        status = SensorStatus.NORMAL

        # Kiểm tra temperature
        if event.temperature_c is not None:
            if event.temperature_c >= self.temperature_thresholds["danger"]:
                status = SensorStatus.DANGER
                alerts.append({
                    "rule_id": "TEMP_DANGER",
                    "message": f"Temperature {event.temperature_c}°C exceeds danger threshold ({self.temperature_thresholds['danger']}°C)",
                    "severity": "CRITICAL"
                })
            elif event.temperature_c >= self.temperature_thresholds["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                alerts.append({
                    "rule_id": "TEMP_WARNING",
                    "message": f"Temperature {event.temperature_c}°C exceeds warning threshold ({self.temperature_thresholds['warning']}°C)",
                    "severity": "HIGH"
                })

        # Kiểm tra humidity
        if event.humidity_percent is not None:
            if event.humidity_percent >= self.humidity_thresholds["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                alerts.append({
                    "rule_id": "HUMIDITY_WARNING",
                    "message": f"Humidity {event.humidity_percent}% exceeds warning threshold ({self.humidity_thresholds['warning']}%)",
                    "severity": "MEDIUM"
                })

        # Kiểm tra CO2
        if event.co2_ppm is not None:
            if event.co2_ppm >= self.co2_thresholds["danger"]:
                status = SensorStatus.DANGER
                alerts.append({
                    "rule_id": "CO2_DANGER",
                    "message": f"CO2 {event.co2_ppm}ppm exceeds danger threshold ({self.co2_thresholds['danger']}ppm)",
                    "severity": "CRITICAL"
                })
            elif event.co2_ppm >= self.co2_thresholds["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                alerts.append({
                    "rule_id": "CO2_WARNING",
                    "message": f"CO2 {event.co2_ppm}ppm exceeds warning threshold ({self.co2_thresholds['warning']}ppm)",
                    "severity": "HIGH"
                })

        # Kiểm tra smoke
        if event.smoke_ppm is not None:
            if event.smoke_ppm >= self.smoke_thresholds["danger"]:
                status = SensorStatus.DANGER
                alerts.append({
                    "rule_id": "SMOKE_DANGER",
                    "message": f"Smoke {event.smoke_ppm}ppm exceeds danger threshold ({self.smoke_thresholds['danger']}ppm)",
                    "severity": "CRITICAL"
                })
            elif event.smoke_ppm >= self.smoke_thresholds["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                alerts.append({
                    "rule_id": "SMOKE_WARNING",
                    "message": f"Smoke {event.smoke_ppm}ppm exceeds warning threshold ({self.smoke_thresholds['warning']}ppm)",
                    "severity": "HIGH"
                })

        # Kiểm tra battery
        if event.battery_percent is not None:
            if event.battery_percent < self.battery_thresholds["warning"]:
                if status != SensorStatus.DANGER:
                    status = SensorStatus.WARNING
                alerts.append({
                    "rule_id": "BATTERY_WARNING",
                    "message": f"Battery {event.battery_percent}% below warning threshold ({self.battery_thresholds['warning']}%)",
                    "severity": "MEDIUM"
                })

        return status, alerts

    def _check_motion_time(self, event: SensorEvent, device: Dict) -> List[Dict]:
        """Kiểm tra motion detection theo khung giờ"""
        alerts = []
        if not event.motion_detected:
            return alerts

        # Khung giờ bất thường: 22:00 - 06:00
        current_time = event.timestamp or datetime.now()
        hour = current_time.hour
        minute = current_time.minute

        # Kiểm tra nếu trong khung giờ bất thường (22:00-06:00)
        if hour >= 22 or hour < 6:
            alerts.append({
                "rule_id": "MOTION_ABNORMAL_TIME",
                "message": f"Motion detected at abnormal time {current_time.strftime('%H:%M')} at {device.get('location', 'unknown')}",
                "severity": "HIGH"
            })

        # Kiểm tra nếu trong khung giờ đóng cửa (ví dụ: Lab đóng cửa sau 18:00)
        room = device.get("room", "")
        if room.startswith("LAB") and (hour >= 18 or hour < 7):
            alerts.append({
                "rule_id": "MOTION_AFTER_HOURS_LAB",
                "message": f"Motion detected in lab after hours: {room} at {current_time.strftime('%H:%M')}",
                "severity": "HIGH"
            })

        return alerts


# Global instance
sensor_evaluator = SensorEvaluator()