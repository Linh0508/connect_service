import asyncpg
import os
import logging
from typing import Optional, List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv("DATABASE_URL", "")
        self.disabled = os.getenv("DATABASE_DISABLED", "false").lower() == "true"
        self._connecting = False
        self._connection_failed = False  # Đánh dấu đã fail để không thử lại
    
    async def connect(self, retry_count=3, retry_delay=2):
        """Create database connection pool with retry - CHỈ GỌI 1 LẦN KHI STARTUP"""
        if self.disabled:
            logger.info("Database disabled - running in mock mode")
            return True
        
        # Nếu đã fail trước đó, không thử lại
        if self._connection_failed:
            logger.info("Database connection previously failed, using mock mode")
            self.disabled = True
            return False
        
        if self._connecting:
            logger.warning("Database connection already in progress, waiting...")
            # Chờ tối đa 5s
            for _ in range(10):
                await asyncio.sleep(0.5)
                if self.pool is not None:
                    return True
            return False
        
        self._connecting = True
        
        try:
            for attempt in range(retry_count):
                try:
                    logger.info(f"Database connection attempt {attempt + 1}/{retry_count}...")
                    self.pool = await asyncpg.create_pool(
                        self.database_url,
                        min_size=1,
                        max_size=5,
                        command_timeout=5.0,  # Giảm timeout
                        max_inactive_connection_lifetime=60,
                        timeout=3.0  # Timeout cho create_pool
                    )
                    # Kiểm tra kết nối
                    async with self.pool.acquire() as conn:
                        await conn.execute("SELECT 1")
                    logger.info("✅ Database connected successfully")
                    self._connecting = False
                    self._connection_failed = False
                    return True
                except asyncio.TimeoutError:
                    logger.warning(f"Database connection attempt {attempt + 1} timeout")
                    if attempt < retry_count - 1:
                        await asyncio.sleep(retry_delay)
                except Exception as e:
                    logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                    if attempt < retry_count - 1:
                        await asyncio.sleep(retry_delay)
            
            logger.error("❌ All database connection attempts failed")
            self.disabled = True
            self._connection_failed = True
            self.pool = None
            return False
        finally:
            self._connecting = False
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")
    
    async def _ensure_connection(self) -> bool:
        """Ensure database connection is available - NHANH CHÓNG TRẢ VỀ"""
        if self.disabled:
            return False
        if self._connection_failed:
            self.disabled = True
            return False
        if self.pool is None:
            # KHÔNG THỬ KẾT NỐI LẠI - trả về False ngay
            logger.warning("Database pool is None, using mock mode")
            self.disabled = True
            return False
        return True
    
    async def execute(self, query: str, *args) -> str:
        if not await self._ensure_connection():
            return "MOCK_OK"
        try:
            async with asyncio.timeout(3.0):  # Timeout 3s
                async with self.pool.acquire() as conn:
                    return await conn.execute(query, *args)
        except asyncio.TimeoutError:
            logger.error(f"Database execute timeout")
            self.disabled = True
            return "MOCK_OK"
        except Exception as e:
            logger.error(f"Database execute failed: {e}")
            self.disabled = True
            return "MOCK_OK"
    
    async def fetch(self, query: str, *args) -> List[Dict]:
        if not await self._ensure_connection():
            return []
        try:
            async with asyncio.timeout(3.0):
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(query, *args)
                    return [dict(row) for row in rows]
        except asyncio.TimeoutError:
            logger.error(f"Database fetch timeout")
            self.disabled = True
            return []
        except Exception as e:
            logger.error(f"Database fetch failed: {e}")
            self.disabled = True
            return []
    
    async def fetch_all(self, query: str, *args) -> List[Dict]:
        return await self.fetch(query, *args)
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict]:
        if not await self._ensure_connection():
            return None
        try:
            async with asyncio.timeout(3.0):
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(query, *args)
                    return dict(row) if row else None
        except asyncio.TimeoutError:
            logger.error(f"Database fetch_one timeout")
            self.disabled = True
            return None
        except Exception as e:
            logger.error(f"Database fetch_one failed: {e}")
            self.disabled = True
            return None
    
    async def is_healthy(self) -> bool:
        if self.disabled:
            return True
        if not await self._ensure_connection():
            return False
        try:
            async with asyncio.timeout(2.0):
                async with self.pool.acquire() as conn:
                    await conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    # ============================================================
    # DEVICE REGISTRY FUNCTIONS - TRẢ VỀ NONE NHANH CHÓNG
    # ============================================================
    async def get_device_registry(self, device_id: str) -> Optional[Dict]:
        """Lấy thông tin device từ database - TRẢ VỀ NONE NẾU LỖI"""
        if self.disabled or self._connection_failed:
            return None
        
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
        if self.disabled or self._connection_failed:
            return []
        
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
        if self.disabled or self._connection_failed:
            return False
        
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
    
    # ============================================================
    # ALERT FUNCTIONS
    # ============================================================
    async def save_alert(self, alert_data: dict) -> bool:
        if self.disabled or self._connection_failed:
            return False
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
        if self.disabled or self._connection_failed:
            return []
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