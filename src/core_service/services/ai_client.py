"""
AI Vision Client - Gọi AI Vision Service (B4) hoặc Fallback AI
"""

import httpx
import os
import logging
from datetime import datetime
import uuid
import random
from enum import Enum
from src.core_service.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class AIMode(Enum):
    REAL = "real"       # Gọi B4 thật
    FALLBACK = "fallback"  # Dùng AI nội bộ


class AIVisionClient:
    def __init__(self):
        # URL của B4 thật (external)
        self.b4_url = os.getenv("B4_AI_VISION_URL", "http://b4-ai-vision:9000")
        # URL của AI fallback nội bộ (container của B6)
        self.fallback_url = os.getenv("AI_VISION_FALLBACK_URL", "http://b6-ai-vision:9000")
        
        self.client = httpx.AsyncClient(timeout=5.0)
        self.mode = AIMode.FALLBACK  # Mặc định là fallback
        self.b4_available = False
        self.last_check = None
    
    async def _check_b4_health(self) -> bool:
        """Kiểm tra xem B4 thật có đang chạy không"""
        try:
            response = await self.client.get(f"{self.b4_url}/health", timeout=2.0)
            if response.status_code == 200:
                logger.info(f"✅ B4 AI Vision is available at {self.b4_url}")
                return True
            else:
                logger.debug(f"B4 health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.debug(f"B4 not reachable: {e}")
            return False
    
    async def detect(self, request):
        """Gọi AI Vision - tự động chọn REAL hoặc FALLBACK"""
        
        # Lấy trạng thái từ connection_manager
        use_real = connection_manager.should_use_real("b4")
        
        if use_real:
            # Gọi B4 thật
            try:
                response = await self.client.post(
                    f"{self.b4_url}/predict",
                    json=request.dict()
                )
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ AI Vision: REAL mode - called B4 successfully")
                    from src.core_service.models import AIDetectionResponse
                    return AIDetectionResponse(**data)
                else:
                    logger.warning(f"B4 returned {response.status_code}, switching to FALLBACK")
                    self.mode = AIMode.FALLBACK
            except Exception as e:
                logger.warning(f"B4 call failed: {e}, switching to FALLBACK")
                self.mode = AIMode.FALLBACK
        
        # FALLBACK MODE - Sử dụng URL fallback từ connection_manager
        fallback_url = connection_manager.get_fallback_url("b4")
        logger.info(f"🟡 AI Vision: FALLBACK mode - calling internal AI at {fallback_url}")
        return await self._fallback_detect(request, fallback_url)
    
    async def _fallback_detect(self, request, fallback_url: str = None):
        """Gọi AI container nội bộ của B6"""
        if fallback_url is None:
            fallback_url = self.fallback_url
        
        try:
            response = await self.client.post(
                f"{fallback_url}/predict",
                json=request.dict(),
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                from src.core_service.models import AIDetectionResponse
                logger.info(f"✅ AI Vision: FALLBACK mode - internal AI returned result")
                return AIDetectionResponse(**data)
            else:
                raise Exception(f"Fallback AI returned {response.status_code}")
        except Exception as e:
            logger.error(f"Fallback AI also failed: {e}")
            # Ultimate fallback - mock response
            return self._mock_response(request)
    
    def _mock_response(self, request):
        """Mock response cuối cùng khi mọi thứ đều lỗi"""
        image_lower = request.imageRef.lower()
        
        if "person" in image_lower or "face" in image_lower:
            confidence = random.uniform(0.75, 0.98)
            matched = confidence >= 0.7
            label = "person"
            status = "matched" if matched else "low_confidence"
        elif "smoke" in image_lower or "fire" in image_lower:
            confidence = random.uniform(0.85, 0.99)
            matched = True
            label = "fire"
            status = "matched"
        else:
            confidence = random.uniform(0.2, 0.5)
            matched = False
            label = "unknown"
            status = "not_matched"
        
        from src.core_service.models import AIDetectionResponse
        return AIDetectionResponse(
            detectionId=request.detectionId or uuid.uuid4(),
            matched=matched,
            label=label,
            confidence=confidence,
            status=status,
            modelVersion="ultimate-fallback",
            processedAt=datetime.now()
        )
    
    async def get_mode(self) -> str:
        """Lấy mode hiện tại để hiển thị trên dashboard"""
        if connection_manager.should_use_real("b4"):
            return "real"
        return "fallback"
    
    async def is_healthy(self) -> bool:
        """Health check cho B6 API"""
        return True
    
    async def close(self):
        await self.client.aclose()