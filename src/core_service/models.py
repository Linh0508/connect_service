from pydantic import BaseModel, Field, UUID4, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4
from enum import Enum

class AccessCheckRequest(BaseModel):
    cardId: str = Field(..., min_length=1, max_length=50)
    gateId: str = Field(..., pattern=r'^[A-Z0-9_]{3,20}$')
    correlationId: UUID4
    direction: Optional[str] = Field("IN", pattern=r'^(IN|OUT)$')
    timestamp: Optional[datetime] = None
    client_ip: Optional[str] = Field(None, alias="clientIp")  # THÊM DÒNG NÀY

class AccessDecision(BaseModel):
    decision: str
    reasonCode: Optional[str] = None
    decisionId: UUID4
    remainingQuota: Optional[int] = None
    isDuplicate: bool = False
    expiresAt: Optional[datetime] = None

class AIDetectionRequest(BaseModel):
    correlationId: UUID4
    imageRef: str
    faceEmbedding: Optional[List[float]] = None
    detectionId: Optional[UUID4] = None

class AIDetectionResponse(BaseModel):
    detectionId: UUID4
    matched: bool
    label: str
    confidence: float
    status: str
    modelVersion: str
    processedAt: datetime
    traceId: Optional[UUID4] = None  # ← THÊM DÒNG NÀY

class HealthResponse(BaseModel):
    status: str
    components: Dict[str, Any]
    timestamp: datetime

class ProblemDetails(BaseModel):
    title: str
    status: int
    detail: Optional[str] = None

class AlertEvent(BaseModel):
    eventId: UUID4
    correlationId: UUID4
    traceId: UUID4
    severity: str
    userId: str
    gateId: str
    alertDetails: Dict[str, Any]
    timestamp: datetime

class AnalyticsEvent(BaseModel):
    correlationId: UUID4
    decision: str
    reason: str
    latencyMs: int
    quotaBefore: int
    quotaAfter: int
    rulesTriggered: List[str]
    timestamp: Optional[datetime] = None
    policyId: Optional[str] = None      # ← THÊM DÒNG NÀY
    subjectId: Optional[str] = None     # ← THÊM DÒNG NÀY (cardId hoặc deviceId)

class AuditRecord(BaseModel):
    decisionId: str
    timestamp: datetime
    gateId: str
    cardIdMasked: str
    decision: str
    reasonCode: Optional[str]
    latencyMs: int

# ============================================================
# DEVICE REGISTRY MODELS
# ============================================================
class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    INVALID = "invalid_device"

class DeviceRegistry(BaseModel):
    device_id: str
    device_type: str
    location: str
    room: str
    status: DeviceStatus = DeviceStatus.ACTIVE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ============================================================
# SENSOR DATA MODELS (CẬP NHẬT)
# ============================================================
class SensorReading(BaseModel):
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    light_lux: Optional[float] = None
    co2_ppm: Optional[float] = None
    smoke_ppm: Optional[float] = None
    battery_percent: Optional[float] = None
    motion_detected: Optional[bool] = False

class SensorEvent(BaseModel):
    source_service: str = "team-iot"
    timestamp: datetime = Field(default_factory=datetime.now)
    device_id: str
    location: Optional[str] = None
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    light_lux: Optional[float] = None
    co2_ppm: Optional[float] = None
    smoke_ppm: Optional[float] = None
    battery_percent: Optional[float] = None
    motion_detected: Optional[bool] = False
    correlationId: Optional[UUID4] = None  # Thêm correlationId
    
    @validator('correlationId', pre=True, always=True)
    def set_correlation_id(cls, v):
        if v is None:
            return uuid4()
        return v

# ============================================================
# SENSOR EVALUATION RESULT
# ============================================================
class SensorStatus(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    DANGER = "danger"
    SENSOR_ERROR = "sensor_error"
    INVALID_DEVICE = "invalid_device"

class SensorEvaluationResult(BaseModel):
    device_id: str
    device_registry: Optional[DeviceRegistry] = None
    status: SensorStatus
    alerts: List[Dict[str, Any]] = []
    readings: SensorReading
    timestamp: datetime
    correlation_id: UUID4

# ============================================================
# CAMERA EVENT MODELS (TỪ B2)
# ============================================================
class CameraEvent(BaseModel):
    """Sự kiện từ Camera Stream (B2)"""
    camera_id: str = Field(..., description="Định danh camera")
    event_type: str = Field(..., description="Loại sự kiện: motion_detected, camera_offline, obstruction, etc.")
    motion_detected: bool = Field(False, description="Có phát hiện chuyển động không")
    frame_url: Optional[str] = Field(None, description="Đường dẫn ảnh tĩnh tại thời điểm sự kiện")
    location: Optional[str] = Field(None, description="Vị trí camera")
    timestamp: datetime = Field(default_factory=datetime.now, description="Thời gian xảy ra sự kiện")
    correlationId: Optional[UUID4] = Field(None, description="ID định danh cho request")

    @validator('correlationId', pre=True, always=True)
    def set_correlation_id(cls, v):
        if v is None:
            return uuid4()
        return v

class CameraEventResponse(BaseModel):
    """Phản hồi từ B6 cho B2"""
    status: str = Field(..., description="Trạng thái xử lý: processed, rejected")
    alert_triggered: bool = Field(False, description="Có kích hoạt cảnh báo không")
    message: Optional[str] = Field(None, description="Thông báo chi tiết")
    correlation_id: UUID4 = Field(..., description="ID định danh request")