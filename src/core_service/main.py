"""
B6 Core Business Service - Smart Campus Decision Engine
Version: 2.0.0 - Đầy đủ nghiệp vụ theo yêu cầu
"""

import os
import sys
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from uuid import uuid4
from collections import deque
import traceback

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================
from dotenv import load_dotenv

IS_DOCKER = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_ENV") == "true"

if IS_DOCKER:
    env_file = ".env"
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"✅ Loaded environment from {env_file} (Docker mode)")
else:
    if os.path.exists(".env.local"):
        load_dotenv(".env.local", override=True)
        print("✅ Loaded environment from .env.local (Local mode)")
    elif os.path.exists(".env"):
        load_dotenv(".env", override=True)
        print("✅ Loaded environment from .env (Local mode)")
    else:
        print("⚠️ No .env file found, using defaults")

print(f"📋 Configuration:")
print(f"   - Mode: {'DOCKER' if IS_DOCKER else 'LOCAL'}")
print(f"   - DEBUG: {os.getenv('DEBUG', 'false')}")
print(f"   - DATABASE_DISABLED: {os.getenv('DATABASE_DISABLED', 'false')}")

# ============================================================
# IMPORTS
# ============================================================
from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware

# Internal modules
from src.core_service.database import DatabaseManager
from src.core_service.models import (
    AccessCheckRequest, AccessDecision, SensorEvent, AccessEvent,
    AIDetectionRequest, AIDetectionResponse, HealthResponse,
    ProblemDetails, AlertEvent, PolicyDecisionEvent,
    CameraEvent, CameraEventResponse, SensorEvaluationResult,
    Severity, AlertLevel, SensorStatus, AccessResult
)
from src.core_service.services.policy_engine import PolicyEngine
from src.core_service.services.quota_manager import QuotaManager
from src.core_service.services.audit_logger import AuditLogger
from src.core_service.services.ai_client import AIVisionClient
from src.core_service.services.alert_storage import AlertStorage
from src.core_service.services.access_gate_client import AccessGateClient
from src.core_service.services.notification_client import NotificationClient
from src.core_service.services.analytics_client import AnalyticsClient
from src.core_service.services.connection_manager import connection_manager, ConnectionStatus
from src.core_service.services.camera_evaluator import camera_evaluator
from src.core_service.services.sensor_evaluator import sensor_evaluator
from src.core_service.services.access_evaluator import access_evaluator
from src.core_service.services.device_registry import device_registry_service

# ============================================================
# Configuration
# ============================================================
API_TITLE = os.getenv("API_TITLE", "Core Business API")
API_VERSION = os.getenv("API_VERSION", "2.0.0")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

request_logs = deque(maxlen=1000)

# ============================================================
# Services Initialization
# ============================================================
logger.info("Initializing services...")

db_manager = DatabaseManager()
policy_engine = PolicyEngine()
quota_manager = QuotaManager()
audit_logger = AuditLogger()
ai_client = AIVisionClient()
alert_storage = AlertStorage()
access_gate_client = AccessGateClient()
notification_client = NotificationClient()
analytics_client = AnalyticsClient()

logger.info("All services initialized")

# ============================================================
# In-memory caches
# ============================================================
processed_correlation_ids: Dict[str, tuple] = {}
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", 300))
IDEMPOTENCY_WINDOW = int(os.getenv("IDEMPOTENCY_WINDOW_SECONDS", 60))

rate_limit_storage: Dict[str, List[datetime]] = {}
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 5000))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))

rule_engine_latencies: List[float] = []
RULE_ENGINE_LATENCY_THRESHOLD = int(os.getenv("RULE_ENGINE_LATENCY_THRESHOLD_MS", 150))

# Alert storage
alerts_list: List[Dict] = []
audit_logs_list: List[Dict] = []

# ============================================================
# Security
# ============================================================
security = HTTPBearer(auto_error=False)

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        if DEBUG:
            return {"scopes": ["access:read", "admin:policies", "admin:audit"], "gateIds": ["*"]}
        raise HTTPException(status_code=401, detail="Missing authorization token")
    
    token = credentials.credentials
    if token.startswith("mock"):
        return {"scopes": ["access:read"], "gateIds": ["LOBBY_01", "LAB_01"]}
    
    raise HTTPException(status_code=401, detail="Invalid token")


def check_rate_limit(client_ip: str) -> bool:
    now = datetime.now()
    if client_ip not in rate_limit_storage:
        rate_limit_storage[client_ip] = []
    
    rate_limit_storage[client_ip] = [
        req_time for req_time in rate_limit_storage[client_ip]
        if (now - req_time).total_seconds() < RATE_LIMIT_WINDOW
    ]
    
    if len(rate_limit_storage[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    
    rate_limit_storage[client_ip].append(now)
    return True


# ============================================================
# Lifespan Management
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting B6 Core Business Service v2.0...")
    
    # 1. Kết nối Database
    db_disabled = os.getenv("DATABASE_DISABLED", "false").lower() == "true"
    if db_disabled:
        logger.info("Database is DISABLED (running in mock mode)")
    else:
        await db_manager.connect()
    
    # 2. Load policies
    await policy_engine.load_policies()
    
    # 3. Load device registry cache - THÊM TRY/CATCH
    try:
        await device_registry_service.refresh_cache()
        logger.info("✅ Device registry cache loaded")
    except Exception as e:
        logger.warning(f"⚠️ Failed to load device registry cache: {e}, using fallback")
    
    # 4. Kiểm tra kết nối
    await connection_manager.initial_check_all()
    await connection_manager.start_retry_tasks()
    connection_manager.log_status_summary()
    
    logger.info("✅ Service started successfully!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down B6 Core Business Service...")
    await connection_manager.stop_retry_tasks()
    if not db_disabled:
        await db_manager.close()
    await ai_client.close()
    await access_gate_client.close()
    await notification_client.close()
    await analytics_client.close()
    logger.info("✅ Service shutdown complete")


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description="Smart Campus Decision Engine - Policy evaluation and alert coordination",
    lifespan=lifespan,
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = "src/core_service/static"
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = "src/core_service/templates"
if os.path.exists(templates_dir):
    templates = Jinja2Templates(directory=templates_dir)
    
    @app.get("/dashboard", response_class=HTMLResponse, tags=["UI"])
    async def dashboard(request: Request):
        return templates.TemplateResponse("api_dashboard.html", {"request": request})
    
    @app.get("/", response_class=HTMLResponse, tags=["UI"])
    async def root(request: Request):
        return templates.TemplateResponse("api_dashboard.html", {"request": request})
else:
    logger.warning(f"Templates directory not found: {templates_dir}")


# ============================================================
# Helper Functions
# ============================================================
def update_health_status():
    if len(rule_engine_latencies) > 60:
        avg_latency = sum(rule_engine_latencies[-60:]) / 60
        if avg_latency > RULE_ENGINE_LATENCY_THRESHOLD:
            return "DEGRADED"
    return "UP"


def severity_to_alert_level(severity: str) -> str:
    """Map severity to alert level"""
    mapping = {
        "LOW": "low",
        "MEDIUM": "medium", 
        "HIGH": "high",
        "CRITICAL": "critical"
    }
    return mapping.get(severity.upper(), "low")


def get_location_from_registry(registry) -> Optional[str]:
    """Lấy location từ device_registry an toàn (hỗ trợ cả dict và object)"""
    if not registry:
        return None
    if isinstance(registry, dict):
        return registry.get("location")
    if hasattr(registry, 'location'):
        return registry.location
    if hasattr(registry, 'get'):
        return registry.get("location")
    return None


def get_device_id_from_registry(registry, default: str) -> str:
    """Lấy device_id từ device_registry an toàn"""
    if not registry:
        return default
    if isinstance(registry, dict):
        return registry.get("device_id", default)
    if hasattr(registry, 'device_id'):
        return registry.device_id
    if hasattr(registry, 'get'):
        return registry.get("device_id", default)
    return default


def create_alert_from_sensor(result: SensorEvaluationResult) -> AlertEvent:
    """Tạo AlertEvent từ SensorEvaluationResult"""
    severity_map = {
        AlertLevel.LOW: Severity.LOW,
        AlertLevel.MEDIUM: Severity.MEDIUM,
        AlertLevel.HIGH: Severity.HIGH,
        AlertLevel.CRITICAL: Severity.CRITICAL,
    }
    
    # ✅ Lấy location và device_id an toàn
    location = get_location_from_registry(result.device_registry)
    device_id = get_device_id_from_registry(result.device_registry, result.device_id)
    
    return AlertEvent(
        event_id=f"alert-{uuid4().hex[:12]}",
        alert_id=f"ALT-{uuid4().hex[:8].upper()}",
        alert_type=result.status.value,
        severity=severity_map.get(result.alert_level, Severity.MEDIUM),
        target="security_team",
        message=result.reason,
        details={
            "device_id": device_id,
            "status": result.status.value,
            "alert_level": result.alert_level.value,
            "readings": result.readings.dict(),
            "location": location,
            "raw_event_id": result.raw_event_id
        },
        correlationId=result.correlation_id,
        timestamp=result.timestamp
    )


def create_policy_decision_event(decision_id: str, decision: str, reason: str, 
                                  severity: Optional[str], rules_triggered: List[str],
                                  inputs: Dict[str, Any]) -> PolicyDecisionEvent:
    """Tạo PolicyDecisionEvent"""
    severity_map = {
        "LOW": Severity.LOW,
        "MEDIUM": Severity.MEDIUM,
        "HIGH": Severity.HIGH,
        "CRITICAL": Severity.CRITICAL,
    }
    
    return PolicyDecisionEvent(
        event_id=f"policy-{uuid4().hex[:12]}",
        decision_id=decision_id,
        decision=decision,
        severity=severity_map.get(severity.upper()) if severity else None,
        reason=reason,
        rules_triggered=rules_triggered,
        inputs=inputs,
        timestamp=datetime.now()
    )

# ============================================================
# Middleware
# ============================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware để log tất cả request và response"""
    request_id = str(uuid4())[:8]
    start_time = datetime.now()
    
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body_bytes = await request.body()
            if body_bytes:
                try:
                    body = json.loads(body_bytes)
                except:
                    body = {"error": "Cannot parse body"}
            
            request.state.body = body_bytes
            request.state.body_parsed = body
            
        except Exception as e:
            logger.warning(f"Cannot read body: {e}")
            body = {"error": "Cannot read body"}
            request.state.body = b"{}"
            request.state.body_parsed = {}
    
    try:
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"📥 {request.method} {request.url.path} → {response.status_code} ({duration:.2f}ms)")
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ {request.method} {request.url.path} ERROR: {e} ({duration:.2f}ms)")
        raise
    
    log_entry = {
        "request_id": request_id,
        "timestamp": start_time.isoformat(),
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else "unknown",
        "status_code": response.status_code,
        "duration_ms": round(duration, 2),
        "body": body,
        "headers": dict(request.headers),
        "query_params": dict(request.query_params)
    }
    request_logs.append(log_entry)
    
    return response


# ============================================================
# API Endpoint - GET REQUEST LOGS
# ============================================================
@app.get("/internal/request-logs", tags=["System Admin"])
async def get_request_logs(
    limit: int = 50,
    service: Optional[str] = None,
    status_code: Optional[int] = None,
    token_data: dict = Depends(verify_token)
):
    logs = list(request_logs)
    
    if service:
        service_paths = {
            "B1": "/internal/evaluate-sensor",
            "B2": "/policies/evaluate-camera-event",
            "B3": "/access/check",
            "B4": "/policies/evaluate-detection",
            "B5": "/alerts"
        }
        path = service_paths.get(service)
        if path:
            logs = [log for log in logs if path in log["path"]]
    
    if status_code:
        logs = [log for log in logs if log["status_code"] == status_code]
    
    logs = sorted(logs, key=lambda x: x["timestamp"], reverse=True)
    return {"total": len(logs), "logs": logs[:limit]}


# ============================================================
# API Endpoint - B1: IoT SENSOR → B6 (REST - TẠM THỜI GIỮ)
# ============================================================
@app.post("/internal/evaluate-sensor", tags=["Event Evaluation"])
async def evaluate_sensor(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    IoT Sensor (B1) gửi dữ liệu cảm biến lên B6
    ĐẦY ĐỦ NGHIỆP VỤ: Validate, Normalize, Enrich, Classify, Produce
    """
    request_id = str(uuid4())[:8]
    
    try:
        # Lấy body từ request state
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        # Tạo SensorEvent từ dict
        event = SensorEvent(**body)
        logger.info(f"📥 [REQ-{request_id}] Sensor event: {event.device_id}")
        
        # ============================================================
        # 1. VALIDATE + 2. NORMALIZE + 3. ENRICH + 4. CLASSIFY
        # ============================================================
        result = await sensor_evaluator.evaluate(event)
        
        logger.info(f"✅ [REQ-{request_id}] Sensor evaluation: {result.device_id} → {result.status.value} (alert: {result.alert_level.value})")
        
        # ============================================================
        # Lấy location từ device_registry - SỬA LỖI
        # ============================================================
        location = None
        if result.device_registry:
            if isinstance(result.device_registry, dict):
                location = result.device_registry.get("location")
            elif hasattr(result.device_registry, 'location'):
                location = result.device_registry.location
            elif hasattr(result.device_registry, 'get'):
                location = result.device_registry.get("location")
        
        # ============================================================
        # 5. APPLY POLICY + 6. DECIDE
        # ============================================================
        should_alert, alert_type, severity = await policy_engine.should_create_alert(
            "sensor",
            {
                "device_id": result.device_id,
                "status": result.status.value,
                "location": location,
                "timestamp": result.timestamp.isoformat()
            }
        )
        
        # ============================================================
        # 7. CREATE ALERT (nếu cần)
        # ============================================================
        if should_alert and severity:
            alert = create_alert_from_sensor(result)
            # Ghi đè severity từ policy
            alert.severity = severity
            
            # Lưu alert
            await alert_storage.save_alert(alert)
            alerts_list.append(alert.dict())
            
            # Gửi sang Notification (B7)
            await notification_client.send_alert(alert)
            logger.info(f"🔔 [REQ-{request_id}] Alert sent to B7: {alert.alert_id} - {severity.value}")
            
            # Gửi sang Analytics (B5)
            policy_event = create_policy_decision_event(
                decision_id=str(uuid4()),
                decision="ALERT_CREATED",
                reason=result.reason,
                severity=severity.value,
                rules_triggered=[f"SENSOR_{result.status.value.upper()}"],
                inputs={
                    "device_id": result.device_id,
                    "status": result.status.value,
                    "readings": result.readings.dict()
                }
            )
            await analytics_client.send_decision(
                correlation_id=str(policy_event.correlationId or uuid4()),
                decision="ALERT_CREATED",
                reason=result.reason,
                latency_ms=0,
                quota_before=0,
                quota_after=0,
                rules_triggered=[f"SENSOR_{result.status.value.upper()}"]
            )
            logger.info(f"📊 [REQ-{request_id}] Decision sent to B5: {policy_event.decision_id}")
        
        # ============================================================
        # 8. AUDIT
        # ============================================================
        await audit_logger.log_decision(
            decision_id=str(uuid4()),
            service="B6-Core",
            event_type="sensor.evaluation",
            input_summary={"device_id": result.device_id, "readings": result.readings.dict()},
            output_decision=result.status.value,
            reason=result.reason,
            severity=result.alert_level.value if result.alert_level else None,
            correlation_id=str(event.correlationId)
        )
        
        # ============================================================
        # 9. PRODUCE - Trả response cho B1
        # ============================================================
        return JSONResponse(
            status_code=202,
            content={
                "message": "Event received and processed",
                "device_id": event.device_id,
                "status": result.status.value,
                "alert_level": result.alert_level.value if result.alert_level else "low",
                "reason": result.reason,
                "alerts_count": 1 if should_alert else 0,
                "correlation_id": str(event.correlationId)
            }
        )
        
    except Exception as e:
        logger.error(f"❌ [REQ-{request_id}] evaluate_sensor error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API Endpoint - B2: CAMERA STREAM → B6 (REST - TẠM THỜI GIỮ)
# ============================================================
@app.post("/policies/evaluate-camera-event", response_model=CameraEventResponse, tags=["Camera Integration"])
async def evaluate_camera_event(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    Camera Stream (B2) gửi sự kiện camera sang B6
    """
    request_id = str(uuid4())[:8]
    
    try:
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        event = CameraEvent(**body)
        logger.info(f"📹 [REQ-{request_id}] Camera event: {event.camera_id} - {event.event_type}")
        
        # Đánh giá sự kiện camera
        result = await camera_evaluator.evaluate(event)
        
        # Áp policy
        should_alert, alert_type, severity = await policy_engine.should_create_alert(
            "camera",
            {
                "camera_id": event.camera_id,
                "event_type": event.event_type,
                "motion_detected": event.motion_detected,
                "location": event.location,
                "unknown_person": result.get("unknown_person", False)
            }
        )
        
        # ✅ SỬA: Xử lý alerts từ result
        if result["alert_triggered"] and result["alerts"]:
            for alert in result["alerts"]:
                # Ghi đè severity từ policy nếu có
                if should_alert and severity:
                    alert.severity = severity
                
                # Lưu alert
                await alert_storage.save_alert(alert)
                alerts_list.append(alert.dict())
                
                # Gửi sang Notification (B7)
                await notification_client.send_alert(alert)
                logger.info(f"🔔 [REQ-{request_id}] Camera alert sent to B7: {alert.alert_id}")
                
                # Gửi sang Analytics (B5)
                await analytics_client.send_decision(
                    correlation_id=str(event.correlationId),
                    decision=alert.severity.value,
                    reason=f"Camera event: {result.get('message', '')}",
                    latency_ms=0,
                    quota_before=0,
                    quota_after=0,
                    rules_triggered=[result.get("rule_id", "CAMERA_EVENT")]
                )
                logger.info(f"📊 [REQ-{request_id}] Camera decision sent to B5")
        
        return CameraEventResponse(
            status="processed",
            alert_triggered=result["alert_triggered"],
            message=result["message"] or "Event processed successfully",
            correlation_id=event.correlationId
        )
        
    except Exception as e:
        logger.error(f"❌ [REQ-{request_id}] evaluate_camera_event error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API Endpoint - B3: ACCESS GATE → B6 (REST)
# ============================================================
@app.post("/access/check", response_model=AccessDecision, tags=["Access Control"])
async def check_access(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    Access Gate (B3) gọi để kiểm tra quyền ra vào real-time
    """
    import time
    start_time = time.time()
    request_id = str(uuid4())[:8]
    
    try:
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        access_request = AccessCheckRequest(**body)
        logger.info(f"🚪 [REQ-{request_id}] Access check: {access_request.cardId} → {access_request.gateId}")
        
        client_ip = getattr(access_request, 'client_ip', "unknown")
        if not check_rate_limit(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        corr_id_str = str(access_request.correlationId)
        if corr_id_str in processed_correlation_ids:
            response, timestamp = processed_correlation_ids[corr_id_str]
            if (datetime.now() - timestamp).total_seconds() < IDEMPOTENCY_WINDOW:
                return response
            else:
                del processed_correlation_ids[corr_id_str]
        
        # ✅ Kiểm tra Gate Authorization - CHỈ CHECK NẾU KHÔNG PHẢI STAFF
        if token_data.get("gateIds") != ["*"] and access_request.gateId not in token_data.get("gateIds", []):
            # ✅ STAFF có thể vào OFFICE_01 ngay cả khi token không có
            if access_request.cardId.startswith("STAFF") and access_request.gateId == "OFFICE_01":
                # Cho phép staff vào office
                pass
            else:
                alert = AlertEvent(
                    event_id=f"alert-{uuid4().hex[:12]}",
                    alert_id=f"ALT-{uuid4().hex[:8].upper()}",
                    alert_type="security_breach",
                    severity=Severity.CRITICAL,
                    target="security_team",
                    message=f"Unauthorized gate access attempt: {access_request.cardId} -> {access_request.gateId}",
                    details={
                        "rule_id": "SECURITY_BREACH",
                        "card_id": access_request.cardId,
                        "gate_id": access_request.gateId
                    },
                    correlationId=access_request.correlationId,
                    timestamp=datetime.now()
                )
                await alert_storage.save_alert(alert)
                alerts_list.append(alert.dict())
                await notification_client.send_alert(alert)
                await analytics_client.send_decision(
                    correlation_id=str(access_request.correlationId),
                    decision="DENY",
                    reason="GATE_NOT_AUTHORIZED",
                    latency_ms=int((time.time() - start_time) * 1000),
                    quota_before=0,
                    quota_after=0,
                    rules_triggered=["GATE_AUTHORIZATION_FAILED"]
                )
                raise HTTPException(status_code=403, detail="Gate not authorized")
        
        # ============================================================
        # 1. EVALUATE POLICY - TRUYỀN TIMESTAMP
        # ============================================================
        policy_result = await policy_engine.evaluate_access(
            access_request.cardId, 
            access_request.gateId,
            access_request.timestamp  # ✅ Truyền timestamp từ request
        )
        quota_result = await quota_manager.check_and_decrement(access_request.cardId)
        
        decision = "DENY"
        reason_code = None
        has_warning = False
        warning_message = None
        
        if quota_result["remaining"] <= 0:
            decision = "DENY"
            reason_code = "QUOTA_EXCEEDED"
            has_warning = True
            warning_message = f"Quota exceeded for card {access_request.cardId}, remaining: 0"
        elif not policy_result["allowed"]:
            decision = "DENY"
            reason_code = "POLICY_VIOLATION"
            has_warning = True
            warning_message = policy_result.get("reason", "Policy violation")
        else:
            decision = "ALLOW"
            reason_code = "VALID"
            if quota_result["remaining"] <= 1:
                has_warning = True
                warning_message = f"Quota almost exhausted for card {access_request.cardId}, remaining: {quota_result['remaining']}"
        
        response = AccessDecision(
            decision=decision,
            reasonCode=reason_code if decision == "DENY" else None,
            decisionId=uuid4(),
            remainingQuota=quota_result["remaining"],
            isDuplicate=False,
            expiresAt=datetime.now() + timedelta(hours=24) if decision == "ALLOW" else None
        )
        
        processed_correlation_ids[corr_id_str] = (response, datetime.now())
        
        # ============================================================
        # 2. AUDIT LOG
        # ============================================================
        await audit_logger.log_decision(
            decision_id=str(response.decisionId),
            service="B6-Core",
            event_type="access.check",
            input_summary={"card_id": access_request.cardId, "gate_id": access_request.gateId},
            output_decision=decision,
            reason=warning_message or reason_code or "VALID",
            severity="CRITICAL" if decision == "DENY" else "LOW",
            correlation_id=corr_id_str
        )
        
        # ============================================================
        # 3. SEND TO ANALYTICS (B5)
        # ============================================================
        await analytics_client.send_decision(
            correlation_id=str(access_request.correlationId),
            decision=decision,
            reason=reason_code or "NONE",
            latency_ms=int((time.time() - start_time) * 1000),
            quota_before=quota_result["before"],
            quota_after=quota_result["remaining"],
            rules_triggered=policy_result.get("rules_triggered", [])
        )
        
        # ============================================================
        # 4. CREATE ALERT (nếu có warning hoặc deny)
        # ============================================================
        if has_warning or decision == "DENY":
            alert_severity = Severity.CRITICAL if decision == "DENY" else Severity.HIGH
            alert = AlertEvent(
                event_id=f"alert-{uuid4().hex[:12]}",
                alert_id=f"ALT-{uuid4().hex[:8].upper()}",
                alert_type="access_alert",
                severity=alert_severity,
                target="security_team",
                message=warning_message or f"Access denied for card {access_request.cardId}: {reason_code}",
                details={
                    "card_id": access_request.cardId,
                    "gate_id": access_request.gateId,
                    "decision": decision,
                    "reason_code": reason_code,
                    "remaining_quota": quota_result["remaining"],
                    "policy_result": policy_result
                },
                correlationId=access_request.correlationId,
                timestamp=datetime.now()
            )
            await alert_storage.save_alert(alert)
            alerts_list.append(alert.dict())
            await notification_client.send_alert(alert)
            logger.info(f"🔔 [REQ-{request_id}] Access alert sent to B7: {alert.alert_id}")
        
        elapsed_ms = (time.time() - start_time) * 1000
        rule_engine_latencies.append(elapsed_ms)
        if len(rule_engine_latencies) > 120:
            rule_engine_latencies.pop(0)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [REQ-{request_id}] check_access error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    

# ============================================================
# API Endpoint - B4: AI VISION → B6 (REST)
# ============================================================
@app.post("/policies/evaluate-detection", tags=["Event Evaluation"])
async def evaluate_detection_from_ai(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    AI Vision (B4) gửi kết quả phân tích ảnh sang B6
    """
    request_id = str(uuid4())[:8]
    
    try:
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        detection = AIDetectionResponse(**body)
        logger.info(f"👁️ [REQ-{request_id}] Detection: {detection.detectionId} - {detection.label}")
        
        alert_triggered = False
        alert = None
        
        if detection.matched and detection.label == "person" and detection.confidence > 0.7:
            alert_triggered = True
            alert = AlertEvent(
                event_id=f"alert-{uuid4().hex[:12]}",
                alert_id=f"ALT-{uuid4().hex[:8].upper()}",
                alert_type="ai_detection",
                severity=Severity.HIGH,
                target="security_team",
                message=f"Person detected with confidence {detection.confidence}",
                details={
                    "rule_id": "AI_DETECTION_RULE",
                    "detection_id": str(detection.detectionId),
                    "label": detection.label,
                    "confidence": detection.confidence
                },
                correlationId=detection.detectionId,
                timestamp=datetime.now()
            )
            logger.info(f"🔔 [REQ-{request_id}] AI Alert created: {alert.alert_id}")
        
        if alert_triggered and alert:
            await alert_storage.save_alert(alert)
            alerts_list.append(alert.dict())
            await notification_client.send_alert(alert)
            await analytics_client.send_decision(
                correlation_id=str(detection.detectionId),
                decision="AI_DETECTION",
                reason=f"Person detected with confidence {detection.confidence}",
                latency_ms=0,
                quota_before=0,
                quota_after=0,
                rules_triggered=["AI_DETECTION_RULE"]
            )
            logger.info(f"📊 [REQ-{request_id}] AI decision sent to B5")
        
        return JSONResponse(status_code=200, content={"status": "received"})
        
    except Exception as e:
        logger.error(f"❌ [REQ-{request_id}] evaluate_detection_from_ai error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API Endpoint - B5: ANALYTICS → B6 (GET /alerts)
# ============================================================
@app.get("/alerts", tags=["Analytics"])
async def get_alerts(
    limit: int = 50,
    severity: Optional[str] = None,
    token_data: dict = Depends(verify_token)
):
    """
    Analytics (B5) gọi để lấy danh sách cảnh báo
    """
    result = alerts_list.copy()
    if severity:
        result = [a for a in result if a.get("severity") == severity.upper()]
    return result[-limit:]


# ============================================================
# API Endpoint - B6 → B4: AI VISION (Consumer)
# ============================================================
@app.post("/evaluate-detection", response_model=AIDetectionResponse, tags=["Event Evaluation"])
async def evaluate_detection(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    B6 gọi AI Vision (B4) để phân tích ảnh
    """
    request_id = str(uuid4())[:8]
    
    try:
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        ai_request = AIDetectionRequest(**body)
        logger.info(f"🤖 [REQ-{request_id}] Calling AI Vision for {ai_request.imageRef}")
        
        result = await ai_client.detect(ai_request)
        return result
    except Exception as e:
        logger.error(f"❌ [REQ-{request_id}] AI Vision error: {e}")
        return AIDetectionResponse(
            detectionId=uuid4(),
            matched=False,
            label="unknown",
            confidence=0.0,
            status="error",
            modelVersion="fallback",
            processedAt=datetime.now()
        )


# ============================================================
# API Endpoint - B6 → B3: ACCESS GATE (Consumer)
# ============================================================
@app.get("/internal/access-logs", tags=["Access Control"])
async def get_access_logs(
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 20,
    token_data: dict = Depends(verify_token)
):
    """B6 gọi Access Gate (B3) để lấy logs"""
    return await access_gate_client.get_access_logs(from_date, to_date, limit)


@app.get("/internal/gates/{gateId}/status", tags=["Access Control"])
async def get_gate_status(
    gateId: str,
    token_data: dict = Depends(verify_token)
):
    """B6 gọi Access Gate (B3) để lấy status"""
    return await access_gate_client.get_gate_status(gateId)


# ============================================================
# API Endpoint - AUDIT LOGS
# ============================================================
@app.get("/internal/audit-logs", tags=["System Admin"])
async def get_audit_logs(
    limit: int = 50,
    service: Optional[str] = None,
    token_data: dict = Depends(verify_token)
):
    """
    Lấy danh sách audit logs
    """
    return await audit_logger.get_audit_logs(limit, service)


@app.get("/policies/access/{policyId}", tags=["Access Control"])
async def get_policy(policyId: str, token_data: dict = Depends(verify_token)):
    policy = await policy_engine.get_policy(policyId)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.get("/decisions/{decisionId}", tags=["Audit & Policy"])
async def get_decision(decisionId: str, token_data: dict = Depends(verify_token)):
    record = await audit_logger.get_by_id(decisionId)
    if not record:
        raise HTTPException(status_code=404, detail="Decision not found")
    return record


# ============================================================
# API Endpoint - TEST: B6 → B5
# ============================================================
@app.post("/internal/send-test-decision", tags=["System Admin"])
async def send_test_decision(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    Test endpoint để gửi decision trực tiếp đến B5 (Analytics)
    """
    try:
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        correlation_id = body.get("correlationId", str(uuid4()))
        decision = body.get("decision", "ALLOW")
        reason = body.get("reason", "TEST")
        
        sent = await analytics_client.send_decision(
            correlation_id=correlation_id,
            decision=decision,
            reason=reason,
            latency_ms=10,
            quota_before=5,
            quota_after=4,
            rules_triggered=["TEST_RULE"]
        )
        
        return JSONResponse(
            status_code=200 if sent else 202,
            content={
                "status": "sent" if sent else "queued",
                "correlationId": correlation_id,
                "decision": decision,
                "mode": "real" if sent else "fallback",
                "message": "Decision sent successfully" if sent else "Decision queued (fallback mode)"
            }
        )
    except Exception as e:
        logger.error(f"send_test_decision error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API Endpoint - TEST: B6 → B7
# ============================================================
@app.post("/internal/send-test-alert", tags=["System Admin"])
async def send_test_alert(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    Test endpoint để gửi alert trực tiếp đến B7 (Notification)
    """
    try:
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        alert = AlertEvent(
            event_id=f"alert-{uuid4().hex[:12]}",
            alert_id=f"ALT-{uuid4().hex[:8].upper()}",
            alert_type="test_alert",
            severity=Severity(body.get("severity", "MEDIUM")),
            target="admin",
            message=body.get("message", "Test alert from B6 dashboard"),
            details={"test": True},
            timestamp=datetime.now()
        )
        
        sent = await notification_client.send_alert(alert)
        alerts_list.append(alert.dict())
        
        return JSONResponse(
            status_code=200 if sent else 202,
            content={
                "status": "sent" if sent else "queued",
                "alertId": alert.alert_id,
                "severity": alert.severity.value,
                "mode": "real" if sent else "fallback",
                "message": "Alert sent successfully" if sent else "Alert queued (fallback mode)"
            }
        )
    except Exception as e:
        logger.error(f"send_test_alert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/internal/fallback-decisions", tags=["System Admin"])
async def get_fallback_decisions(
    limit: int = 10,
    token_data: dict = Depends(verify_token)
):
    """Lấy danh sách decisions đã lưu fallback"""
    return await analytics_client.get_fallback_decisions(limit)


# ============================================================
# API Endpoints - System Admin
# ============================================================
@app.get("/connection-status", tags=["System Admin"])
async def get_connection_status(token_data: dict = Depends(verify_token)):
    """Lấy trạng thái kết nối đến các B khác"""
    return {
        "b3": {
            "status": connection_manager.get_status("b3").value,
            "display": connection_manager.get_status_display()["b3"],
            "auto_detect": connection_manager.auto_detect["b3"],
            "retry_interval": connection_manager.retry_intervals["b3"]
        },
        "b4": {
            "status": connection_manager.get_status("b4").value,
            "display": connection_manager.get_status_display()["b4"],
            "fallback_url": connection_manager.get_fallback_url("b4"),
            "auto_detect": connection_manager.auto_detect["b4"],
            "retry_interval": connection_manager.retry_intervals["b4"]
        },
        "b5": {
            "status": connection_manager.get_status("b5").value,
            "display": connection_manager.get_status_display()["b5"],
            "auto_detect": connection_manager.auto_detect["b5"],
            "retry_interval": connection_manager.retry_intervals["b5"]
        },
        "b7": {
            "status": connection_manager.get_status("b7").value,
            "display": connection_manager.get_status_display()["b7"],
            "auto_detect": connection_manager.auto_detect["b7"],
            "retry_interval": connection_manager.retry_intervals["b7"]
        },
        "rabbitmq": {
            "status": connection_manager.get_status("b7_rabbitmq").value,
            "display": connection_manager.get_status_display()["rabbitmq"],
            "host": os.getenv("RABBITMQ_HOST", "not configured")
        },
        "retry_enabled": connection_manager.retry_enabled
    }


@app.get("/health", response_model=HealthResponse, tags=["System Admin"])
async def health_check():
    db_disabled = os.getenv("DATABASE_DISABLED", "false").lower() == "true"
    
    if db_disabled:
        db_status = "UP (Mock Mode)"
        overall_status = "UP"
    else:
        db_status = "UP" if await db_manager.is_healthy() else "DOWN"
        overall_status = "UP" if db_status == "UP" else "DOWN"
    
    ai_status = "UP" if await ai_client.is_healthy() else "DOWN"
    
    if overall_status != "DOWN" and update_health_status() == "DEGRADED":
        overall_status = "DEGRADED"
    
    return HealthResponse(
        status=overall_status,
        components={
            "database": db_status,
            "cache": "UP",
            "rule_engine": {
                "status": update_health_status(),
                "avg_latency_ms": sum(rule_engine_latencies[-60:]) / 60 if rule_engine_latencies else 0
            },
            "ai_vision": {"status": ai_status, "url": os.getenv("B4_AI_VISION_URL", "http://b4-ai-vision:9000")},
            "access_gate": {"url": os.getenv("ACCESS_GATE_URL", "http://b3-access-gate:8001")}
        },
        timestamp=datetime.now()
    )


# ============================================================
# Exception Handlers
# ============================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ProblemDetails(
            title=exc.detail or "Error",
            status=exc.status_code,
            detail=str(exc.detail)
        ).dict()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=DEBUG
    )