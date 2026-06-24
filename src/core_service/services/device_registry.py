"""
Device Registry Service - Quản lý thiết bị IoT
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from src.core_service.database import DatabaseManager
from src.core_service.models import DeviceRegistry, DeviceStatus

logger = logging.getLogger(__name__)


class DeviceRegistryService:
    def __init__(self):
        self.db = DatabaseManager()
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # 5 phút
        self._cache_timestamp: Optional[datetime] = None
        self._fallback_devices = {  # Fallback khi database không có
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
            }
        }

    async def get_device(self, device_id: str) -> Optional[Dict]:
        """Lấy thông tin device từ cache hoặc database - TRẢ VỀ NHANH CHÓNG"""
        
        # 1. Kiểm tra cache
        if self._is_cache_valid() and device_id in self._cache:
            logger.debug(f"Device {device_id} found in cache")
            return self._cache[device_id]
        
        # 2. Kiểm tra fallback devices trước (nếu database disabled)
        if self.db.disabled:
            logger.debug(f"Database disabled, using fallback for {device_id}")
            return self._fallback_devices.get(device_id, {
                "device_id": device_id,
                "device_type": "unknown",
                "location": "UNKNOWN",
                "room": "UNKNOWN",
                "status": "active"
            })

        # 3. Load từ database với timeout
        try:
            logger.debug(f"Querying database for device {device_id}")
            device = await self.db.get_device_registry(device_id)
            if device:
                self._cache[device_id] = device
                self._cache_timestamp = datetime.now()
                return device
        except Exception as e:
            logger.warning(f"Database error for {device_id}: {e}")
            # Trả về fallback device để không bị treo
            return self._fallback_devices.get(device_id, {
                "device_id": device_id,
                "device_type": "unknown",
                "location": "UNKNOWN",
                "room": "UNKNOWN",
                "status": "active"
            })
        
        # 4. Không tìm thấy trong database, trả về None
        return None

    async def get_all_devices(self) -> List[Dict]:
        """Lấy tất cả device"""
        if self._is_cache_valid() and self._cache:
            return list(self._cache.values())

        if self.db.disabled:
            return list(self._fallback_devices.values())

        devices = await self.db.get_all_device_registry()
        if devices:
            self._cache = {d["device_id"]: d for d in devices}
            self._cache_timestamp = datetime.now()
            return devices
        
        return list(self._fallback_devices.values())

    def _is_cache_valid(self) -> bool:
        """Kiểm tra cache còn hiệu lực"""
        if self._cache_timestamp is None:
            return False
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl

    async def refresh_cache(self):
        """Refresh cache"""
        if self.db.disabled:
            return
        devices = await self.db.get_all_device_registry()
        if devices:
            self._cache = {d["device_id"]: d for d in devices}
            self._cache_timestamp = datetime.now()
            logger.info(f"Device registry cache refreshed: {len(self._cache)} devices")


# Global instance
device_registry_service = DeviceRegistryService()