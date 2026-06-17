"""
Device Registry Service - Quản lý thiết bị IoT
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.core_service.database import DatabaseManager
from src.core_service.models import DeviceRegistry, DeviceStatus

logger = logging.getLogger(__name__)


class DeviceRegistryService:
    def __init__(self):
        self.db = DatabaseManager()
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # 5 phút
        self._cache_timestamp: Optional[datetime] = None

    async def get_device(self, device_id: str) -> Optional[Dict]:
        """Lấy thông tin device từ cache hoặc database"""
        # Kiểm tra cache
        if self._is_cache_valid() and device_id in self._cache:
            return self._cache[device_id]

        # Load từ database
        device = await self.db.get_device_registry(device_id)
        if device:
            self._cache[device_id] = device
            return device
        return None

    async def get_all_devices(self) -> List[Dict]:
        """Lấy tất cả device"""
        if self._is_cache_valid() and self._cache:
            return list(self._cache.values())

        devices = await self.db.get_all_device_registry()
        self._cache = {d["device_id"]: d for d in devices}
        self._cache_timestamp = datetime.now()
        return devices

    def _is_cache_valid(self) -> bool:
        """Kiểm tra cache còn hiệu lực"""
        if self._cache_timestamp is None:
            return False
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl

    async def refresh_cache(self):
        """Refresh cache"""
        devices = await self.db.get_all_device_registry()
        self._cache = {d["device_id"]: d for d in devices}
        self._cache_timestamp = datetime.now()
        logger.info(f"Device registry cache refreshed: {len(self._cache)} devices")


# Global instance
device_registry_service = DeviceRegistryService()