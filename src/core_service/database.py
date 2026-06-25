import asyncpg
import os
import logging
from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv("DATABASE_URL", "")
        self.disabled = os.getenv("DATABASE_DISABLED", "false").lower() == "true"
        self._connecting = False
        self._connection_failed = False
    
    async def connect(self, retry_count=3, retry_delay=2):
        if self.disabled:
            logger.info("Database disabled - running in mock mode")
            return True
        
        if self._connection_failed:
            logger.info("Database connection previously failed, using mock mode")
            self.disabled = True
            return False
        
        if self._connecting:
            logger.warning("Database connection already in progress")
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
                        command_timeout=5.0,
                        max_inactive_connection_lifetime=60,
                        timeout=3.0
                    )
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
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")
    
    async def _ensure_connection(self) -> bool:
        if self.disabled:
            return False
        if self._connection_failed:
            # KHÔNG set disabled ở đây, chỉ trả về False
            return False
        if self.pool is None:
            # KHÔNG set disabled ở đây, chỉ trả về False
            logger.warning("Database pool is None")
            return False
        return True
    
    async def execute(self, query: str, *args) -> str:
        if not await self._ensure_connection():
            return "MOCK_OK"
        try:
            async with asyncio.timeout(3.0):
                async with self.pool.acquire() as conn:
                    return await conn.execute(query, *args)
        except asyncio.TimeoutError:
            logger.error(f"Database execute timeout")
            # ✅ KHÔNG disabled
            return "MOCK_OK"
        except Exception as e:
            logger.error(f"Database execute failed: {e}")
            # ✅ KHÔNG disabled
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
            # ✅ KHÔNG disabled
            return []
        except Exception as e:
            logger.error(f"Database fetch failed: {e}")
            # ✅ KHÔNG disabled
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
            # ✅ KHÔNG disabled
            return None
        except Exception as e:
            logger.error(f"Database fetch_one failed: {e}")
            # ✅ KHÔNG disabled
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
    # DEVICE REGISTRY FUNCTIONS
    # ============================================================
    async def get_device_registry(self, device_id: str) -> Optional[Dict]:
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
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, 
                alert_data.get("alert_id"),
                alert_data.get("event_id"),
                alert_data.get("severity"),
                alert_data.get("user_id", "SYSTEM"),
                alert_data.get("gate_id", "UNKNOWN"),
                alert_data.get("alert_details", {}),
                alert_data.get("timestamp", datetime.now())
            )
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