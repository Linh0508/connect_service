"""
Device Registry Service - Quản lý thiết bị IoT
Version: 2.0 - Sử dụng Database làm nguồn chính
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from src.core_service.database import DatabaseManager

logger = logging.getLogger(__name__)


class DeviceRegistryService:
    def __init__(self):
        self.db = DatabaseManager()
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # 5 phút
        self._cache_timestamp: Optional[datetime] = None
        
        # FALLBACK DEVICES - CHỈ DÙNG KHI DATABASE KHÔNG CÓ DỮ LIỆU
        self._fallback_devices = {
            "esp32-lab-a101": {
                "device_id": "esp32-lab-a101",
                "device_type": "environment_sensor",
                "location": "Lab A101",
                "room": "A101",
                "status": "active"
            },
            "esp32-lab-a102": {
                "device_id": "esp32-lab-a102",
                "device_type": "environment_sensor",
                "location": "Lab A102",
                "room": "A102",
                "status": "active"
            },
            "esp32-gate-a": {
                "device_id": "esp32-gate-a",
                "device_type": "environment_sensor",
                "location": "Main Gate A",
                "room": "GATE-A",
                "status": "active"
            },
            "esp32-library-01": {
                "device_id": "esp32-library-01",
                "device_type": "environment_sensor",
                "location": "Library 01",
                "room": "LIB-01",
                "status": "active"
            },
            "esp32-hall-b201": {
                "device_id": "esp32-hall-b201",
                "device_type": "environment_sensor",
                "location": "Hall B201",
                "room": "B201",
                "status": "active"
            },
            "esp32-lab-b202": {
                "device_id": "esp32-lab-b202",
                "device_type": "environment_sensor",
                "location": "Lab B202",
                "room": "B202",
                "status": "active"
            },
            "esp32-office-01": {
                "device_id": "esp32-office-01",
                "device_type": "environment_sensor",
                "location": "Office 01",
                "room": "OFF-01",
                "status": "active"
            },
            # Fallback cho các sensor test
            "sensor_01": {
                "device_id": "sensor_01",
                "device_type": "sensor",
                "location": "LAB_01",
                "room": "LAB_01",
                "status": "active"
            },
            "sensor_02": {
                "device_id": "sensor_02",
                "device_type": "sensor",
                "location": "LAB_01",
                "room": "LAB_01",
                "status": "active"
            },
            "sensor_03": {
                "device_id": "sensor_03",
                "device_type": "sensor",
                "location": "LAB_02",
                "room": "LAB_02",
                "status": "active"
            },
            "sensor_04": {
                "device_id": "sensor_04",
                "device_type": "sensor",
                "location": "LAB_02",
                "room": "LAB_02",
                "status": "active"
            },
            "sensor_05": {
                "device_id": "sensor_05",
                "device_type": "sensor",
                "location": "LAB_03",
                "room": "LAB_03",
                "status": "active"
            },
            "sensor_06": {
                "device_id": "sensor_06",
                "device_type": "sensor",
                "location": "LAB_CRITICAL",
                "room": "LAB_CRITICAL",
                "status": "active"
            }
        }

    async def get_device(self, device_id: str) -> Optional[Dict]:
        """
        Lấy thông tin device - ƯU TIÊN TỪ DATABASE
        
        Quy trình:
        1. Kiểm tra cache (nếu cache còn hiệu lực)
        2. Query database
        3. Nếu database không có, dùng fallback
        """
        # 1. Kiểm tra cache
        if self._is_cache_valid() and device_id in self._cache:
            logger.debug(f"Device {device_id} found in cache")
            return self._cache[device_id]
        
        # 2. Query database
        try:
            if not self.db.disabled and not self.db._connection_failed:
                logger.debug(f"Querying database for device {device_id}")
                device = await self.db.get_device_registry(device_id)
                if device:
                    self._cache[device_id] = device
                    self._cache_timestamp = datetime.now()
                    logger.debug(f"Device {device_id} found in database")
                    return device
        except Exception as e:
            logger.warning(f"Database error for {device_id}: {e}")
        
        # 3. Fallback - dùng fallback devices
        logger.info(f"Using fallback device for {device_id}")
        fallback = self._fallback_devices.get(device_id)
        if fallback:
            self._cache[device_id] = fallback
            self._cache_timestamp = datetime.now()
            return fallback
        
        # 4. Không tìm thấy device
        logger.warning(f"Device {device_id} not found in database or fallback")
        return None

    async def get_all_devices(self) -> List[Dict]:
        """Lấy tất cả device - ƯU TIÊN TỪ DATABASE"""
        if self._is_cache_valid() and self._cache:
            return list(self._cache.values())

        try:
            if not self.db.disabled and not self.db._connection_failed:
                devices = await self.db.get_all_device_registry()
                if devices:
                    self._cache = {d["device_id"]: d for d in devices}
                    self._cache_timestamp = datetime.now()
                    return devices
        except Exception as e:
            logger.warning(f"Database error when getting all devices: {e}")

        # Fallback
        return list(self._fallback_devices.values())

    def _is_cache_valid(self) -> bool:
        """Kiểm tra cache còn hiệu lực"""
        if self._cache_timestamp is None:
            return False
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl

    async def refresh_cache(self):
        """Refresh cache từ database"""
        try:
            if not self.db.disabled and not self.db._connection_failed:
                devices = await self.db.get_all_device_registry()
                if devices:
                    self._cache = {d["device_id"]: d for d in devices}
                    self._cache_timestamp = datetime.now()
                    logger.info(f"Device registry cache refreshed: {len(self._cache)} devices")
        except Exception as e:
            logger.warning(f"Failed to refresh device cache: {e}")


# Global instance
device_registry_service = DeviceRegistryService()