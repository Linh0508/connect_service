import asyncpg
import os
import logging
from typing import Optional, List, Dict, Any
import time
import asyncio

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv("DATABASE_URL", "")
        self.disabled = os.getenv("DATABASE_DISABLED", "false").lower() == "true"
    
    async def connect(self, retry_count=10, retry_delay=5):
        """Create database connection pool with retry"""
        if self.disabled:
            logger.info("Database disabled - running in mock mode")
            return True
        
        for attempt in range(retry_count):
            try:
                logger.info(f"Database connection attempt {attempt + 1}/{retry_count}...")
                self.pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=1,
                    max_size=10,
                    command_timeout=60,
                    max_inactive_connection_lifetime=300
                )
                # Kiểm tra kết nối
                async with self.pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                logger.info("✅ Database connected successfully")
                return True
            except Exception as e:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("❌ All database connection attempts failed")
                    self.disabled = True
                    return False
        return False
    
    async def disconnect(self):
        """Legacy method - kept for compatibility"""
        pass
    
    async def close(self):
        """Close database connection pool - call only on shutdown"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")
    
    async def _ensure_connection(self) -> bool:
        """Ensure database connection is available, reconnect if needed"""
        if self.disabled:
            return False
        if self.pool is None:
            logger.warning("Database pool is None, attempting to reconnect...")
            return await self.connect()
        return True
    
    async def execute(self, query: str, *args) -> str:
        if not await self._ensure_connection():
            return "MOCK_OK"
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *args)
        except Exception as e:
            logger.error(f"Database execute failed: {e}")
            self.pool = None
            return "MOCK_OK"
    
    async def fetch(self, query: str, *args) -> List[Dict]:
        if not await self._ensure_connection():
            return []
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Database fetch failed: {e}")
            self.pool = None
            return []
    
    async def fetch_all(self, query: str, *args) -> List[Dict]:
        return await self.fetch(query, *args)
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict]:
        if not await self._ensure_connection():
            return None
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Database fetch_one failed: {e}")
            self.pool = None
            return None
    
    async def is_healthy(self) -> bool:
        if self.disabled:
            return True
        if not await self._ensure_connection():
            return False
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    # ============================================================
    # CÁC HÀM HỖ TRỢ LƯU ALERTS
    # ============================================================
    async def save_alert(self, alert_data: dict) -> bool:
        """Lưu alert vào database"""
        try:
            await self.execute("""
                INSERT INTO alerts (alert_id, event_id, severity, user_id, gate_id, 
                                   alert_details, created_at)
                VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, $6)
            """, alert_data.get("eventId"), alert_data.get("severity"),
               alert_data.get("userId"), alert_data.get("gateId"),
               alert_data.get("alertDetails"), alert_data.get("timestamp"))
            return True
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
            return False
    
    async def get_alerts(self, limit: int = 50, severity: str = None) -> List[Dict]:
        """Lấy danh sách alerts từ database"""
        if severity:
            return await self.fetch("""
                SELECT * FROM alerts 
                WHERE severity = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, severity, limit)
        return await self.fetch("""
            SELECT * FROM alerts 
            ORDER BY created_at DESC 
            LIMIT $1
        """, limit)
    
    # ============================================================
    # DEVICE REGISTRY FUNCTIONS
    # ============================================================
    async def get_device_registry(self, device_id: str) -> Optional[Dict]:
        """Lấy thông tin device từ database"""
        try:
            return await self.fetch_one("""
                SELECT device_id, device_type, location, room, status, created_at, updated_at
                FROM device_registry
                WHERE device_id = $1
            """, device_id)
        except Exception as e:
            logger.error(f"Failed to get device registry for {device_id}: {e}")
            return None

    async def get_all_device_registry(self) -> List[Dict]:
        """Lấy tất cả device registry"""
        try:
            return await self.fetch("""
                SELECT device_id, device_type, location, room, status, created_at, updated_at
                FROM device_registry
                WHERE status = 'active'
            """)
        except Exception as e:
            logger.error(f"Failed to get device registry: {e}")
            return []

    async def update_device_registry_status(self, device_id: str, status: str) -> bool:
        """Cập nhật trạng thái device"""
        try:
            await self.execute("""
                UPDATE device_registry
                SET status = $1, updated_at = NOW()
                WHERE device_id = $2
            """, status, device_id)
            return True
        except Exception as e:
            logger.error(f"Failed to update device registry for {device_id}: {e}")
            return False