"""
B6 Core Business Service - Smart Campus Decision Engine
Version: 1.5.0 - Production Ready
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
print(f"   - AI_VISION_URL: {os.getenv('AI_VISION_URL', 'http://b6-ai-vision:9000')}")
print(f"   - ACCESS_GATE_URL: {os.getenv('ACCESS_GATE_URL', 'http://b3-access-gate:8001')}")

# ============================================================
# IMPORTS
# ============================================================
from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Internal modules
from src.core_service.database import DatabaseManager
from src.core_service.models import (
    AccessCheckRequest, AccessDecision, SensorEvent,
    AIDetectionRequest, AIDetectionResponse, HealthResponse,
    ProblemDetails, AlertEvent, CameraEvent, CameraEventResponse
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

# ============================================================
# Configuration
# ============================================================
API_TITLE = os.getenv("API_TITLE", "Core Business API")
API_VERSION = os.getenv("API_VERSION", "1.5.0")
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

# In-memory cache for idempotency
processed_correlation_ids: Dict[str, tuple] = {}
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", 300))
IDEMPOTENCY_WINDOW = int(os.getenv("IDEMPOTENCY_WINDOW_SECONDS", 60))

# Rate limiting storage
rate_limit_storage: Dict[str, List[datetime]] = {}
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 5000))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))

# Health status tracking
rule_engine_latencies: List[float] = []
RULE_ENGINE_LATENCY_THRESHOLD = int(os.getenv("RULE_ENGINE_LATENCY_THRESHOLD_MS", 150))

# Alert storage for GET /alerts endpoint
alerts_list: List[Dict] = []


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
    logger.info("Starting B6 Core Business Service...")
    
    # 1. Kết nối Database
    db_disabled = os.getenv("DATABASE_DISABLED", "false").lower() == "true"
    if db_disabled:
        logger.info("Database is DISABLED (running in mock mode)")
    else:
        await db_manager.connect()
    
    # 2. Load policies
    await policy_engine.load_policies()
    
    # 3. Kiểm tra kết nối
    await connection_manager.initial_check_all()
    await connection_manager.start_retry_tasks()
    connection_manager.log_status_summary()
    
    logger.info("Service started successfully!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down B6 Core Business Service...")
    await connection_manager.stop_retry_tasks()
    if not db_disabled:
        await db_manager.close()
    await ai_client.close()
    await access_gate_client.close()
    await notification_client.close()
    await analytics_client.close()
    logger.info("Service shutdown complete")


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


# ============================================================
# Middleware - Đọc body 1 lần và lưu vào request.state
# ============================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware để log tất cả request và response"""
    start_time = datetime.now()
    
    # Đọc body và lưu vào request state (chỉ cho POST/PUT/PATCH)
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body_bytes = await request.body()
            if body_bytes:
                try:
                    body = json.loads(body_bytes)
                except:
                    body = {"error": "Cannot parse body"}
            
            # Lưu body vào request state để endpoint dùng lại
            request.state.body = body_bytes
            request.state.body_parsed = body
            
        except Exception as e:
            logger.warning(f"Cannot read body: {e}")
            body = {"error": "Cannot read body"}
            request.state.body = b"{}"
            request.state.body_parsed = {}
    
    # Xử lý request
    try:
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"📥 {request.method} {request.url.path} → {response.status_code} ({duration:.2f}ms)")
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ {request.method} {request.url.path} ERROR: {e} ({duration:.2f}ms)")
        raise
    
    # Lưu log
    log_entry = {
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
# API Endpoint - B3: ACCESS GATE → B6
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
    
    try:
        # Lấy body từ request state
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        # Tạo AccessCheckRequest từ dict
        access_request = AccessCheckRequest(**body)
        
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
        
        # Kiểm tra Gate Authorization
        if token_data.get("gateIds") != ["*"] and access_request.gateId not in token_data.get("gateIds", []):
            alert = AlertEvent(
                eventId=uuid4(),
                correlationId=access_request.correlationId,
                traceId=uuid4(),
                severity="CRITICAL",
                userId=access_request.cardId,
                gateId=access_request.gateId,
                alertDetails={
                    "ruleId": "SECURITY_BREACH",
                    "message": f"Unauthorized gate access attempt: {access_request.cardId} -> {access_request.gateId}",
                    "reason": "Gate not authorized",
                    "cardId": access_request.cardId,
                    "gateId": access_request.gateId
                },
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
        
        policy_result = await policy_engine.evaluate(access_request.cardId, access_request.gateId)
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
            warning_message = f"Policy violation for card {access_request.cardId} at gate {access_request.gateId}"
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
        
        await audit_logger.log(
            decision_id=str(response.decisionId),
            gate_id=access_request.gateId,
            card_id=access_request.cardId,
            decision=decision,
            reason_code=reason_code,
            latency_ms=int((time.time() - start_time) * 1000),
            correlation_id=corr_id_str
        )
        
        await analytics_client.send_decision(
            correlation_id=str(access_request.correlationId),
            decision=decision,
            reason=reason_code or "NONE",
            latency_ms=int((time.time() - start_time) * 1000),
            quota_before=quota_result["before"],
            quota_after=quota_result["remaining"],
            rules_triggered=policy_result.get("rules_triggered", [])
        )
        
        if has_warning or decision == "DENY":
            alert = AlertEvent(
                eventId=uuid4(),
                correlationId=access_request.correlationId,
                traceId=uuid4(),
                severity="WARNING" if has_warning and decision == "ALLOW" else "CRITICAL",
                userId=access_request.cardId,
                gateId=access_request.gateId,
                alertDetails={
                    "ruleId": "ACCESS_CHECK_RULE",
                    "message": warning_message or f"Access denied for card {access_request.cardId}: {reason_code}",
                    "decision": decision,
                    "reasonCode": reason_code,
                    "remainingQuota": quota_result["remaining"],
                    "policyResult": policy_result
                },
                timestamp=datetime.now()
            )
            await alert_storage.save_alert(alert)
            alerts_list.append(alert.dict())
            await notification_client.send_alert(alert)
        
        elapsed_ms = (time.time() - start_time) * 1000
        rule_engine_latencies.append(elapsed_ms)
        if len(rule_engine_latencies) > 120:
            rule_engine_latencies.pop(0)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"check_access error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    if "cardId" in record:
        card = record["cardId"]
        record["cardIdMasked"] = f"{card[:4]}****{card[-4:]}"
        del record["cardId"]
    return record


# ============================================================
# API Endpoint - B1: IoT SENSOR → B6
# ============================================================
@app.post("/internal/evaluate-sensor", tags=["Event Evaluation"])
async def evaluate_sensor(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    IoT Sensor (B1) gửi dữ liệu cảm biến lên B6
    """
    from src.core_service.services.sensor_evaluator import sensor_evaluator
    
    try:
        # Lấy body từ request state
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        # Tạo SensorEvent từ dict
        event = SensorEvent(**body)
        
        # Đánh giá dữ liệu sensor
        result = await sensor_evaluator.evaluate(event)
        
        logger.info(f"Sensor evaluation: device={result.device_id}, status={result.status.value}, alerts={len(result.alerts)}")
        
        # Xử lý alerts
        if result.alerts:
            for alert_data in result.alerts:
                # Lấy location từ device_registry (là dict)
                location = "UNKNOWN"
                if result.device_registry and isinstance(result.device_registry, dict):
                    location = result.device_registry.get("location", "UNKNOWN")
                elif result.device_registry and hasattr(result.device_registry, 'location'):
                    location = result.device_registry.location
                
                alert = AlertEvent(
                    eventId=uuid4(),
                    correlationId=event.correlationId,
                    traceId=uuid4(),
                    severity=alert_data.get("severity", "MEDIUM"),
                    userId="SYSTEM",
                    gateId=location,
                    alertDetails={
                        "ruleId": alert_data.get("rule_id", "SENSOR_THRESHOLD_RULE"),
                        "message": alert_data.get("message", ""),
                        "deviceId": event.device_id,
                        "status": result.status.value,
                        "readings": result.readings.dict(),
                        "device_registry": result.device_registry
                    },
                    timestamp=result.timestamp
                )
                
                await alert_storage.save_alert(alert)
                alerts_list.append(alert.dict())
                await notification_client.send_alert(alert)
                await analytics_client.send_decision(
                    correlation_id=str(event.correlationId),
                    decision=alert_data.get("severity", "ALERT_CREATED"),
                    reason=f"{result.status.value}: {alert_data.get('message', '')}",
                    latency_ms=0,
                    quota_before=0,
                    quota_after=0,
                    rules_triggered=[alert_data.get("rule_id", "SENSOR_THRESHOLD_RULE")]
                )
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Event received for processing",
                "device_id": event.device_id,
                "status": result.status.value,
                "alerts_count": len(result.alerts)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"evaluate_sensor error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API Endpoint - B4: AI VISION → B6
# ============================================================
@app.post("/policies/evaluate-detection", tags=["Event Evaluation"])
async def evaluate_detection_from_ai(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    AI Vision (B4) gửi kết quả phân tích ảnh sang B6
    """
    try:
        # Lấy body từ request state
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        # Tạo AIDetectionResponse từ dict
        detection = AIDetectionResponse(**body)
        
        logger.info(f"Received detection from AI: {detection.detectionId} - {detection.label}")
        
        alert_triggered = False
        alert = None
        
        if detection.matched and detection.label == "person" and detection.confidence > 0.7:
            alert_triggered = True
            alert = AlertEvent(
                eventId=uuid4(),
                correlationId=uuid4(),
                traceId=uuid4(),
                severity="HIGH",
                userId="SYSTEM",
                gateId="UNKNOWN",
                alertDetails={
                    "ruleId": "AI_DETECTION_RULE",
                    "message": f"Person detected with confidence {detection.confidence}",
                    "detectionId": str(detection.detectionId),
                    "label": detection.label,
                    "confidence": detection.confidence
                },
                timestamp=datetime.now()
            )
        
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
        
        return JSONResponse(status_code=200, content={"status": "received"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"evaluate_detection_from_ai error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API Endpoint - B2: CAMERA STREAM → B6
# ============================================================
@app.post("/policies/evaluate-camera-event", response_model=CameraEventResponse, tags=["Camera Integration"])
async def evaluate_camera_event(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    Camera Stream (B2) gửi sự kiện camera sang B6
    """
    try:
        # Lấy body từ request state
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        # Tạo CameraEvent từ dict
        event = CameraEvent(**body)
        
        logger.info(f"Camera event: camera={event.camera_id}, event_type={event.event_type}")
        
        result = await camera_evaluator.evaluate(event)
        
        if result["alert_triggered"] and result["alerts"]:
            for alert in result["alerts"]:
                await alert_storage.save_alert(alert)
                alerts_list.append(alert.dict())
                await notification_client.send_alert(alert)
                await analytics_client.send_decision(
                    correlation_id=str(event.correlationId),
                    decision=alert.severity,
                    reason=f"Camera event: {result['message']}",
                    latency_ms=0,
                    quota_before=0,
                    quota_after=0,
                    rules_triggered=[result["rule_id"]]
                )
        
        return CameraEventResponse(
            status="processed",
            alert_triggered=result["alert_triggered"],
            message=result["message"] or "Event processed successfully",
            correlation_id=event.correlationId
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"evaluate_camera_event error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API Endpoint - B5: ANALYTICS → B6
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
        result = [a for a in result if a.get("severity") == severity]
    return result[-limit:]


# ============================================================
# API Endpoint - B6 → AI VISION (Consumer)
# ============================================================
@app.post("/evaluate-detection", response_model=AIDetectionResponse, tags=["Event Evaluation"])
async def evaluate_detection(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    B6 gọi AI Vision (B4) để phân tích ảnh
    """
    try:
        # Lấy body từ request state
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        ai_request = AIDetectionRequest(**body)
        
        result = await ai_client.detect(ai_request)
        return result
    except Exception as e:
        logger.error(f"AI Vision error: {e}")
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
# API Endpoint - B6 → ACCESS GATE (Consumer)
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
# API Endpoints - TEST: B6 → B5 & B6 → B7
# ============================================================

@app.post("/internal/send-test-decision", tags=["System Admin"])
async def send_test_decision(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    Test endpoint để gửi decision trực tiếp đến B5 (Analytics)
    Dùng để kiểm tra kết nối đến Analytics Service
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


@app.post("/internal/send-test-alert", tags=["System Admin"])
async def send_test_alert(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    Test endpoint để gửi alert trực tiếp đến B7 (Notification)
    Dùng để kiểm tra kết nối đến Notification Service
    """
    try:
        if hasattr(request.state, 'body_parsed') and request.state.body_parsed:
            body = request.state.body_parsed
        else:
            body = await request.json()
        
        alert = AlertEvent(
            eventId=uuid4(),
            correlationId=uuid4(),
            traceId=uuid4(),
            severity=body.get("severity", "MEDIUM"),
            userId="SYSTEM",
            gateId="TEST",
            alertDetails={
                "ruleId": "TEST_RULE",
                "message": body.get("message", "Test alert from B6 dashboard")
            },
            timestamp=datetime.now()
        )
        
        sent = await notification_client.send_alert(alert)
        alerts_list.append(alert.dict())
        
        return JSONResponse(
            status_code=200 if sent else 202,
            content={
                "status": "sent" if sent else "queued",
                "alertId": str(alert.eventId),
                "severity": alert.severity,
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
    """
    Lấy danh sách decisions đã lưu trong fallback storage
    Dùng để kiểm tra dữ liệu đã được lưu khi B5 offline
    """
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
            "ai_vision": {"status": ai_status, "url": os.getenv("AI_VISION_URL", "http://b6-ai-vision:9000")},
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