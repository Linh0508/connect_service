"""
Models - Định nghĩa dữ liệu cho B6 Core
Version: 2.1 - Thêm target và traceId cho AlertEvent
"""

from pydantic import BaseModel, Field, UUID4, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4
from enum import Enum


# ============================================================
# ENUMS CHUẨN
# ============================================================
class SensorStatus(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    DANGER = "danger"
    SENSOR_ERROR = "sensor_error"
    INVALID_DEVICE = "invalid_device"


class AlertLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AccessResult(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"


class EventType(str, Enum):
    SENSOR_PROCESSED = "sensor.data.processed"
    ACCESS_PROCESSED = "access.swipe.processed"
    CAMERA_PROCESSED = "camera.motion.processed"
    ALERT_CREATED = "core.alert.created"
    POLICY_DECISION = "core.policy.decision"


class Severity(str, Enum):
    LOW = "LOW"        # ✅ SỬA: thành UPPERCASE
    MEDIUM = "MEDIUM"  # ✅ SỬA: thành UPPERCASE
    HIGH = "HIGH"      # ✅ SỬA: thành UPPERCASE
    CRITICAL = "CRITICAL"  # ✅ SỬA: thành UPPERCASE


# ============================================================
# ACCESS MODELS
# ============================================================
class AccessCheckRequest(BaseModel):
    cardId: str = Field(..., min_length=1, max_length=50)
    gateId: str = Field(..., pattern=r'^[A-Z0-9_]{3,20}$')
    correlationId: UUID4
    direction: Optional[str] = Field("IN", pattern=r'^(IN|OUT)$')
    timestamp: Optional[datetime] = None
    client_ip: Optional[str] = Field(None, alias="clientIp")


class AccessDecision(BaseModel):
    decision: str
    reasonCode: Optional[str] = None
    decisionId: UUID4
    remainingQuota: Optional[int] = None
    isDuplicate: bool = False
    expiresAt: Optional[datetime] = None


# ============================================================
# AI MODELS
# ============================================================
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
    traceId: Optional[UUID4] = None


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
# SENSOR DATA MODELS - ĐẦY ĐỦ THEO YÊU CẦU
# ============================================================
class SensorReading(BaseModel):
    temperature_c: Optional[float] = Field(None, ge=-50, le=100)
    humidity_percent: Optional[float] = Field(None, ge=0, le=100)
    light_lux: Optional[float] = Field(None, ge=0)
    co2_ppm: Optional[float] = Field(None, ge=0)
    smoke_ppm: Optional[float] = Field(None, ge=0)
    battery_percent: Optional[float] = Field(None, ge=0, le=100)
    motion_detected: Optional[bool] = False


class SensorEvent(BaseModel):
    """Sensor Event - Đầu vào từ B1 (IoT Ingestion)"""
    event_id: Optional[str] = None
    event_type: str = Field(default="sensor.data.processed", pattern=r'^sensor\..+$')
    source_service: str = Field(default="team-iot", pattern=r'^team-.*$')
    raw_event_id: Optional[str] = None
    device_id: str = Field(..., min_length=1)
    location: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    temperature_c: Optional[float] = Field(None, ge=-50, le=100)
    humidity_percent: Optional[float] = Field(None, ge=0, le=100)
    light_lux: Optional[float] = Field(None, ge=0)
    co2_ppm: Optional[float] = Field(None, ge=0)
    smoke_ppm: Optional[float] = Field(None, ge=0)
    battery_percent: Optional[float] = Field(None, ge=0, le=100)
    motion_detected: Optional[bool] = False
    
    status: Optional[SensorStatus] = None
    alert_level: Optional[AlertLevel] = None
    reason: Optional[str] = None
    
    correlationId: Optional[UUID4] = None
    scenario_hint_for_teacher: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID4: lambda v: str(v),
            SensorStatus: lambda v: v.value,
            AlertLevel: lambda v: v.value,
        }
    
    @validator('event_id', pre=True, always=True)
    def set_event_id(cls, v):
        if v is None:
            return f"event-{uuid4().hex[:12]}"
        return v
    
    @validator('correlationId', pre=True, always=True)
    def set_correlation_id(cls, v):
        if v is None:
            return uuid4()
        return v


# ============================================================
# ACCESS EVENT
# ============================================================
class AccessEvent(BaseModel):
    """Access Event - Đầu vào từ B3 (Access Gate)"""
    event_id: Optional[str] = None
    event_type: str = Field(default="access.swipe.processed", pattern=r'^access\..+$')
    source_service: str = Field(default="team-gate", pattern=r'^team-.*$')
    raw_event_id: Optional[str] = None
    uid: str = Field(..., min_length=1, description="UID thẻ RFID")
    door_id: str = Field(..., min_length=1)
    location: str
    direction: str = Field(..., pattern=r'^(IN|OUT)$')
    timestamp: datetime = Field(default_factory=datetime.now)
    
    access_result: Optional[AccessResult] = None
    reason: Optional[str] = None
    student_id: Optional[str] = None
    full_name: Optional[str] = None
    class_name: Optional[str] = None
    
    correlationId: Optional[UUID4] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID4: lambda v: str(v),
            AccessResult: lambda v: v.value,
        }
    
    @validator('event_id', pre=True, always=True)
    def set_event_id(cls, v):
        if v is None:
            return f"access-{uuid4().hex[:12]}"
        return v
    
    @validator('correlationId', pre=True, always=True)
    def set_correlation_id(cls, v):
        if v is None:
            return uuid4()
        return v


# ============================================================
# ALERT EVENT - ĐẦU RA CHO B7 (Notification) - ĐÃ SỬA
# ============================================================
# Trong models.py, sửa AlertEvent

class AlertEvent(BaseModel):
    """Alert Event - Đầu ra cho B7 (Notification)"""
    event_id: Optional[str] = None
    event_type: str = Field(default="alert.created")
    source_service: str = Field(default="core-business")
    alert_id: str
    alert_type: str
    severity: Severity
    target: Optional[str] = Field(default="security_team")
    title: Optional[str] = Field(None, description="Tiêu đề alert")  # ✅ THÊM title
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    correlationId: Optional[UUID4] = None
    traceId: Optional[UUID4] = Field(default_factory=uuid4)
    
    @property
    def eventId(self) -> str:
        return self.event_id or self.alert_id
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID4: lambda v: str(v),
            Severity: lambda v: v.value,
        }
    
    @validator('event_id', pre=True, always=True)
    def set_event_id(cls, v):
        if v is None:
            return f"alert-{uuid4().hex[:12]}"
        return v
    
    @validator('traceId', pre=True, always=True)
    def set_trace_id(cls, v):
        if v is None:
            return uuid4()
        return v
    
    @validator('title', pre=True, always=True)
    def set_title(cls, v, values):
        if v is None:
            alert_type = values.get('alert_type', 'Alert')
            severity = values.get('severity', Severity.MEDIUM)
            return f"🚨 {alert_type} - {severity.value.upper()}"
        return v
    
    def dict(self, *args, **kwargs):
        """Override dict để thêm eventId cho tương thích"""
        d = super().dict(*args, **kwargs)
        d['eventId'] = self.eventId
        return d


# ============================================================
# POLICY DECISION - ĐẦU RA CHO B5 (Analytics)
# ============================================================
class PolicyDecisionEvent(BaseModel):
    """Policy Decision - Đầu ra cho B5 (Analytics)"""
    event_id: Optional[str] = None
    event_type: str = Field(default="core.policy.decision")
    source_service: str = Field(default="team-core")
    decision_id: str
    decision: str
    severity: Optional[Severity] = None
    reason: str
    rules_triggered: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    correlationId: Optional[UUID4] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID4: lambda v: str(v),
            Severity: lambda v: v.value,
        }
    
    @validator('event_id', pre=True, always=True)
    def set_event_id(cls, v):
        if v is None:
            return f"policy-{uuid4().hex[:12]}"
        return v


# ============================================================
# SENSOR EVALUATION RESULT (NỘI BỘ)
# ============================================================
class SensorEvaluationResult(BaseModel):
    device_id: str
    device_registry: Optional[DeviceRegistry] = None
    status: SensorStatus
    alert_level: AlertLevel
    reason: str
    alerts: List[Dict[str, Any]] = []
    readings: SensorReading
    timestamp: datetime
    correlation_id: UUID4
    raw_event_id: Optional[str] = None


# ============================================================
# HEALTH
# ============================================================
class HealthResponse(BaseModel):
    status: str
    components: Dict[str, Any]
    timestamp: datetime


class ProblemDetails(BaseModel):
    title: str
    status: int
    detail: Optional[str] = None


# ============================================================
# AUDIT LOG
# ============================================================
class AuditLogEntry(BaseModel):
    decision_id: str
    timestamp: datetime
    service: str
    event_type: str
    input_summary: Dict[str, Any]
    output_decision: str
    reason: str
    severity: Optional[str] = None
    correlation_id: Optional[str] = None