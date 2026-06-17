"""
B6 Core Business Service - Smart Campus Decision Engine
Version: 1.3.0 - Production Ready
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
import asyncio

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
    ProblemDetails, AlertEvent, AnalyticsEvent, AuditRecord,
    CameraEvent, CameraEventResponse
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
API_VERSION = os.getenv("API_VERSION", "1.3.0")
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
db_manager = DatabaseManager()
policy_engine = PolicyEngine()
quota_manager = QuotaManager()
audit_logger = AuditLogger()
ai_client = AIVisionClient()
alert_storage = AlertStorage()
access_gate_client = AccessGateClient()
notification_client = NotificationClient()
analytics_client = AnalyticsClient()

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
    
    db_disabled = os.getenv("DATABASE_DISABLED", "false").lower() == "true"
    if db_disabled:
        logger.info("Database is DISABLED (running in mock mode)")
    else:
        await db_manager.connect()
    
    await policy_engine.load_policies()
    logger.info("Service started successfully")
    
    # Kiểm tra kết nối đến các B khác
    logger.info("Checking connections to other services...")

    # Kiểm tra B3 (Access Gate)
    b3_url = os.getenv("ACCESS_GATE_URL", "http://b3-access-gate:8001")
    status = await connection_manager.check_connection("b3", b3_url)
    logger.info(f"B3 connection status: {status.value}")

    # Kiểm tra B4 (AI Vision) - ĐÃ CÓ LOGIC ĐẶC BIỆT
    b4_url = os.getenv("AI_VISION_URL", "http://b4-ai-vision:9000")
    status = await connection_manager.check_connection("b4", b4_url)
    logger.info(f"B4 connection status: {status.value}")

    # Kiểm tra B5 (Analytics)
    b5_url = os.getenv("ANALYTICS_URL", "http://b5-analytics:8003")
    status = await connection_manager.check_connection("b5", b5_url)
    logger.info(f"B5 connection status: {status.value}")

    # Kiểm tra B7 (Notification)
    b7_url = os.getenv("NOTIFICATION_URL", "http://b7-notification:8002")
    status = await connection_manager.check_connection("b7", b7_url)
    logger.info(f"B7 connection status: {status.value}")
        
    logger.info("Service started successfully")
    
    yield
    
    logger.info("Shutting down B6 Core Business Service...")
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

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware để log tất cả request và response"""
    start_time = datetime.now()
    
    # Đọc body (chỉ cho POST/PUT/PATCH)
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body_bytes = await request.body()
            if body_bytes:
                body = json.loads(body_bytes)
        except:
            body = {"error": "Cannot parse body"}
    
    # Xử lý request
    response = await call_next(request)
    
    # Tính thời gian
    duration = (datetime.now() - start_time).total_seconds() * 1000
    
    # Lưu log
    log_entry = {
        "timestamp": start_time.isoformat(),
        "method": request.method,
        "path": request.url.path,  # ← SỬA: dùng request.url.path
        "client_ip": request.client.host if request.client else "unknown",
        "status_code": response.status_code,
        "duration_ms": round(duration, 2),
        "body": body,
        "headers": dict(request.headers),
        "query_params": dict(request.query_params)
    }
    request_logs.append(log_entry)
    
    # Log ra console - SỬA: dùng request.url.path
    logger.info(f"📥 {request.method} {request.url.path} from {request.client.host} → {response.status_code} ({duration:.2f}ms)")
    
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
    """
    Lấy danh sách request logs để hiển thị trên dashboard.
    Có thể lọc theo service (B1, B2, B3, B4, B5) và status code.
    """
    logs = list(request_logs)
    
    # Lọc theo service (dựa trên path)
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
    
    # Lọc theo status code
    if status_code:
        logs = [log for log in logs if log["status_code"] == status_code]
    
    # Sắp xếp theo thời gian mới nhất
    logs = sorted(logs, key=lambda x: x["timestamp"], reverse=True)
    
    # Giải thích dữ liệu
    for log in logs:
        log["explanation"] = explain_request(log)
    
    return {
        "total": len(logs),
        "logs": logs[:limit]
    }

def explain_request(log: dict) -> dict:
    """Giải thích ý nghĩa của request"""
    explanation = {
        "service": "Unknown",
        "action": "Unknown",
        "data_summary": {},
        "meaning": ""
    }
    
    path = log["path"]
    body = log.get("body", {})
    status = log["status_code"]
    
    # Xác định service
    if "/internal/evaluate-sensor" in path:
        explanation["service"] = "B1 (IoT Sensor)"
        explanation["action"] = "Gửi dữ liệu cảm biến"
        if body:
            device = body.get("device_id", "unknown")
            temp = body.get("temperature_c", "N/A")
            co2 = body.get("co2_ppm", "N/A")
            smoke = body.get("smoke_ppm", "N/A")
            motion = body.get("motion_detected", False)
            explanation["data_summary"] = {
                "Thiết bị": device,
                "Nhiệt độ": f"{temp}°C",
                "CO2": f"{co2} ppm",
                "Khói": f"{smoke} ppm",
                "Chuyển động": "✅ Có" if motion else "❌ Không"
            }
            explanation["meaning"] = f"📊 Dữ liệu từ cảm biến {device}"
    
    elif "/policies/evaluate-camera-event" in path:
        explanation["service"] = "B2 (Camera Stream)"
        explanation["action"] = "Gửi sự kiện camera"
        if body:
            camera = body.get("camera_id", "unknown")
            event_type = body.get("event_type", "unknown")
            location = body.get("location", "unknown")
            motion = body.get("motion_detected", False)
            explanation["data_summary"] = {
                "Camera": camera,
                "Sự kiện": event_type,
                "Vị trí": location,
                "Chuyển động": "✅ Có" if motion else "❌ Không"
            }
            explanation["meaning"] = f"📹 Sự kiện camera {event_type} từ {camera}"
    
    elif "/access/check" in path:
        explanation["service"] = "B3 (Access Gate)"
        explanation["action"] = "Kiểm tra quyền truy cập"
        if body:
            card = body.get("cardId", "unknown")
            gate = body.get("gateId", "unknown")
            direction = body.get("direction", "IN")
            explanation["data_summary"] = {
                "Thẻ": card,
                "Cổng": gate,
                "Hướng": direction
            }
            explanation["meaning"] = f"🚪 Kiểm tra thẻ {card} tại cổng {gate}"
    
    elif "/policies/evaluate-detection" in path:
        explanation["service"] = "B4 (AI Vision)"
        explanation["action"] = "Gửi kết quả nhận diện"
        if body:
            label = body.get("label", "unknown")
            confidence = body.get("confidence", 0)
            matched = body.get("matched", False)
            explanation["data_summary"] = {
                "Nhãn": label,
                "Độ tin cậy": f"{confidence*100:.1f}%",
                "Khớp": "✅" if matched else "❌"
            }
            explanation["meaning"] = f"👁️ Phát hiện {label} với độ tin cậy {confidence*100:.1f}%"
    
    elif "/alerts" in path:
        explanation["service"] = "B5 (Analytics)"
        explanation["action"] = "Lấy danh sách cảnh báo"
        params = log.get("query_params", {})
        limit = params.get("limit", "20")
        severity = params.get("severity", "Tất cả")
        explanation["data_summary"] = {
            "Số lượng": limit,
            "Severity": severity
        }
        explanation["meaning"] = f"📋 Lấy danh sách cảnh báo (limit={limit})"
    
    # Giải thích status code
    status_explanations = {
        200: "✅ Thành công",
        202: "✅ Đã tiếp nhận (xử lý async)",
        400: "❌ Request không hợp lệ",
        401: "🔒 Chưa xác thực",
        403: "🔒 Không có quyền truy cập",
        404: "❌ Endpoint không tồn tại",
        429: "⚠️ Quá rate limit",
        500: "❌ Lỗi server"
    }
    explanation["status_meaning"] = status_explanations.get(status, f"Status {status}")
    
    return explanation

# ============================================================
# API Endpoints - CẶP 10: ACCESS GATE → B6 (Provider)
# ============================================================
@app.post("/access/check", response_model=AccessDecision, tags=["Access Control"])
async def check_access(
    request: AccessCheckRequest,
    token_data: dict = Depends(verify_token)
):
    """
    Access Gate gọi để kiểm tra quyền ra vào real-time
    - SLA: P99 < 100ms
    - Idempotency: correlationId window 60 seconds
    """
    import time
    start_time = time.time()
    
    client_ip = getattr(request, 'client_ip', "unknown")
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    corr_id_str = str(request.correlationId)
    if corr_id_str in processed_correlation_ids:
        response, timestamp = processed_correlation_ids[corr_id_str]
        if (datetime.now() - timestamp).total_seconds() < IDEMPOTENCY_WINDOW:
            return response
        else:
            del processed_correlation_ids[corr_id_str]
    
    # ============================================================
    # KIỂM TRA GATE AUTHORIZATION
    # ============================================================
    gate_authorized = True
    gate_error = None
    
    if token_data.get("gateIds") != ["*"] and request.gateId not in token_data.get("gateIds", []):
        gate_authorized = False
        gate_error = "Gate not authorized"
        
        # 🔔 GỬI ALERT NGAY KHI PHÁT HIỆN GATE KHÔNG ĐƯỢC PHÉP
        alert = AlertEvent(
            eventId=uuid4(),
            correlationId=request.correlationId,
            traceId=uuid4(),
            severity="CRITICAL",
            userId=request.cardId,
            gateId=request.gateId,
            alertDetails={
                "ruleId": "SECURITY_BREACH",
                "message": f"Unauthorized gate access attempt: {request.cardId} -> {request.gateId}",
                "reason": "Gate not authorized",
                "cardId": request.cardId,
                "gateId": request.gateId
            },
            timestamp=datetime.now()
        )
        # Lưu alert
        await alert_storage.save_alert(alert)
        alerts_list.append(alert.dict())
        
        # Gửi alert sang Notification (B7)
        await notification_client.send_alert(alert)
        logger.info(f"🔔 Alert sent to B7 for unauthorized gate: {request.cardId} -> {request.gateId}")
        
        # Gửi decision sang Analytics (B5)
        await analytics_client.send_decision(
            correlation_id=str(request.correlationId),
            decision="DENY",
            reason="GATE_NOT_AUTHORIZED",
            latency_ms=int((time.time() - start_time) * 1000),
            quota_before=0,
            quota_after=0,
            rules_triggered=["GATE_AUTHORIZATION_FAILED"]
        )
        
        raise HTTPException(status_code=403, detail="Gate not authorized")
    
    if token_data.get("gateIds") != ["*"] and request.gateId not in token_data.get("gateIds", []):
        raise HTTPException(status_code=403, detail="Gate not authorized")
    
    policy_result = await policy_engine.evaluate(request.cardId, request.gateId)
    quota_result = await quota_manager.check_and_decrement(request.cardId)
    
    decision = "DENY"
    reason_code = None
    has_warning = False
    warning_message = None
    
    if quota_result["remaining"] <= 0:
        decision = "DENY"
        reason_code = "QUOTA_EXCEEDED"
        has_warning = True
        warning_message = f"Quota exceeded for card {request.cardId}, remaining: 0"
    elif not policy_result["allowed"]:
        decision = "DENY"
        reason_code = "POLICY_VIOLATION"
        has_warning = True
        warning_message = f"Policy violation for card {request.cardId} at gate {request.gateId}"
    else:
        decision = "ALLOW"
        reason_code = "VALID"
        # Kiểm tra các điều kiện cảnh báo (ví dụ: quota gần hết)
        if quota_result["remaining"] <= 1:
            has_warning = True
            warning_message = f"Quota almost exhausted for card {request.cardId}, remaining: {quota_result['remaining']}"
    
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
        gate_id=request.gateId,
        card_id=request.cardId,
        decision=decision,
        reason_code=reason_code,
        latency_ms=int((time.time() - start_time) * 1000),
        correlation_id=corr_id_str
    )
    
    # ============================================================
    # 📤 Gửi decision sang Analytics (B5)
    # ============================================================
    await analytics_client.send_decision(
        correlation_id=str(request.correlationId),
        decision=decision,
        reason=reason_code or "NONE",
        latency_ms=int((time.time() - start_time) * 1000),
        quota_before=quota_result["before"],
        quota_after=quota_result["remaining"],
        rules_triggered=policy_result.get("rules_triggered", [])
    )
    
    # ============================================================
    # 🔔 Gửi Alert sang B7 (Notification) nếu có lỗi hoặc cảnh báo
    # ============================================================
    if has_warning or decision == "DENY":
        alert = AlertEvent(
            eventId=uuid4(),
            correlationId=request.correlationId,
            traceId=uuid4(),
            severity="WARNING" if has_warning and decision == "ALLOW" else "CRITICAL",
            userId=request.cardId,
            gateId=request.gateId,
            alertDetails={
                "ruleId": "ACCESS_CHECK_RULE",
                "message": warning_message or f"Access denied for card {request.cardId}: {reason_code}",
                "decision": decision,
                "reasonCode": reason_code,
                "remainingQuota": quota_result["remaining"],
                "policyResult": policy_result
            },
            timestamp=datetime.now()
        )
        # Lưu alert
        await alert_storage.save_alert(alert)
        alerts_list.append(alert.dict())
        
        # Gửi alert sang Notification (B7)
        await notification_client.send_alert(alert)
        logger.info(f"🔔 Alert sent to B7 for access check: {request.cardId} - {decision}")
    
    elapsed_ms = (time.time() - start_time) * 1000
    rule_engine_latencies.append(elapsed_ms)
    if len(rule_engine_latencies) > 120:
        rule_engine_latencies.pop(0)
    
    return response


@app.get("/policies/access/{policyId}", tags=["Access Control"])
async def get_policy(policyId: str, token_data: dict = Depends(verify_token)):
    """Access Gate gọi để lấy policy cache"""
    policy = await policy_engine.get_policy(policyId)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.get("/decisions/{decisionId}", tags=["Audit & Policy"])
async def get_decision(decisionId: str, token_data: dict = Depends(verify_token)):
    """Tra cứu quyết định theo ID (cho B3, B5)"""
    record = await audit_logger.get_by_id(decisionId)
    if not record:
        raise HTTPException(status_code=404, detail="Decision not found or moved to cold storage")
    
    if "cardId" in record:
        card = record["cardId"]
        record["cardIdMasked"] = f"{card[:4]}****{card[-4:]}"
        del record["cardId"]
    
    return record

# Trong hàm get_connection_status, sửa lại phần B4:
@app.get("/connection-status", tags=["System Admin"])
async def get_connection_status(token_data: dict = Depends(verify_token)):
    """Lấy trạng thái kết nối đến các B khác"""
    b4_status = connection_manager.get_status("b4")
    b4_display = "🟢 Connected (REAL)" if b4_status == ConnectionStatus.REAL else "🟡 Using Fallback (Internal AI)"
    
    return {
        "b3": {
            "status": connection_manager.get_status("b3").value,
            "display": "🟢 Connected" if connection_manager.get_status("b3") == ConnectionStatus.REAL else "🟡 Using Fallback"
        },
        "b4": {
            "status": b4_status.value,
            "display": b4_display,
            "fallback_url": connection_manager.get_fallback_url("b4")
        },
        "b7": {
            "status": connection_manager.get_status("b7").value,
            "display": "🟢 Connected" if connection_manager.get_status("b7") == ConnectionStatus.REAL else "🟡 Using Fallback"
        },
        "b5": {
            "status": connection_manager.get_status("b5").value,
            "display": "🟢 Connected" if connection_manager.get_status("b5") == ConnectionStatus.REAL else "🟡 Using Fallback"
        }
    }

# ============================================================
# API Endpoints - TEST DECISION (B6 → B5)
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
    body = await request.json()
    
    correlation_id = body.get("correlationId", str(uuid4()))
    decision = body.get("decision", "ALLOW")
    reason = body.get("reason", "TEST")
    
    # Gửi decision đến B5 (có fallback)
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

# Thêm endpoint để dashboard lấy mode hiện tại
@app.get("/ai-vision-mode", tags=["System Admin"])
async def get_ai_vision_mode(token_data: dict = Depends(verify_token)):
    """Lấy mode hiện tại của AI Vision (real/fallback)"""
    mode = await ai_client.get_mode()
    return {
        "mode": mode,
        "display": "🟢 Connected to B4 (Real)" if mode == "real" else "🟡 Using Fallback (Internal)"
    }

@app.post("/cache/invalidate/{policyId}", tags=["System Admin"])
async def invalidate_cache(policyId: str, token_data: dict = Depends(verify_token)):
    """Xóa cache policy (admin)"""
    await policy_engine.invalidate_cache(policyId)
    return JSONResponse(status_code=204, content=None)


# ============================================================
# API Endpoints - CẶP 05: IoT INGESTION → B6 (Consumer - Queue Async)
# ============================================================
@app.post("/internal/evaluate-sensor", tags=["Event Evaluation"])
async def evaluate_sensor(
    event: SensorEvent,
    token_data: dict = Depends(verify_token)
):
    """
    IoT Ingestion (B1) gửi dữ liệu cảm biến
    B6 kiểm tra ngưỡng, phân loại trạng thái, phát sinh alert nếu cần
    """
    from src.core_service.services.sensor_evaluator import sensor_evaluator
    from src.core_service.services.device_registry import device_registry_service
    
    # Đánh giá dữ liệu sensor
    result = await sensor_evaluator.evaluate(event)
    
    # Log kết quả
    logger.info(f"Sensor evaluation result: device={result.device_id}, status={result.status.value}, alerts={len(result.alerts)}")
    
    # Nếu có alert, xử lý
    if result.alerts:
        for alert_data in result.alerts:
            # Tạo AlertEvent
            alert = AlertEvent(
                eventId=uuid4(),
                correlationId=event.correlationId,
                traceId=uuid4(),
                severity=alert_data.get("severity", "MEDIUM"),
                userId="SYSTEM",
                gateId=result.device_registry.get("location", "UNKNOWN") if result.device_registry else "UNKNOWN",
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
            
            # 💾 Lưu alert vào database và danh sách
            await alert_storage.save_alert(alert)
            alerts_list.append(alert.dict())
            
            # 🔔 Gửi alert sang Notification (B7)
            await notification_client.send_alert(alert)
            logger.info(f"🔔 Alert sent to B7: {alert.eventId} - {alert.severity}")
            
            # 📊 Gửi decision sang Analytics (B5)
            await analytics_client.send_decision(
                correlation_id=str(event.correlationId),
                decision=alert_data.get("severity", "ALERT_CREATED"),
                reason=f"{result.status.value}: {alert_data.get('message', '')}",
                latency_ms=0,
                quota_before=0,
                quota_after=0,
                rules_triggered=[alert_data.get("rule_id", "SENSOR_THRESHOLD_RULE")]
            )
            logger.info(f"📊 Decision sent to B5 (Analytics) for alert: {alert.eventId}")
    
    return JSONResponse(
        status_code=202,
        content={
            "message": "Event received for processing",
            "device_id": event.device_id,
            "status": result.status.value,
            "alerts_count": len(result.alerts)
        }
    )


# ============================================================
# API Endpoints - CẶP 02: B4 (AI Vision) → B6 (Provider)
# B4 gửi kết quả phân tích ảnh sang B6
# ============================================================
@app.post("/policies/evaluate-detection", tags=["Event Evaluation"])
async def evaluate_detection_from_ai(detection: AIDetectionResponse, token_data: dict = Depends(verify_token)):
    """
    AI Vision (B4) gửi kết quả phân tích ảnh sang B6
    B6 dựa vào kết quả này để ra quyết định nghiệp vụ
    """
    logger.info(f"Received detection from AI Vision: {detection.detectionId} - {detection.label} - {detection.confidence}")
    
    alert_triggered = False
    alert = None
    
    # ============================================================
    # Kiểm tra kết quả detection và tạo alert nếu cần
    # ============================================================
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
        logger.info(f"🔔 Alert created from AI detection: {alert.eventId}")
    
    # ============================================================
    # Nếu có alert, gửi đến B7 và B5
    # ============================================================
    if alert_triggered and alert:
        # 💾 Lưu alert
        await alert_storage.save_alert(alert)
        alerts_list.append(alert.dict())
        
        # 🔔 Gửi alert sang Notification (B7)
        await notification_client.send_alert(alert)
        logger.info(f"🔔 Alert sent to B7 from AI detection: {alert.eventId}")
        
        # 📊 Gửi decision sang Analytics (B5)
        await analytics_client.send_decision(
            correlation_id=str(detection.detectionId),
            decision="AI_DETECTION",
            reason=f"Person detected with confidence {detection.confidence}",
            latency_ms=0,
            quota_before=0,
            quota_after=0,
            rules_triggered=["AI_DETECTION_RULE"]
        )
        logger.info(f"📊 Decision sent to B5 (Analytics) from AI detection: {detection.detectionId}")
    
    return JSONResponse(status_code=200, content={"status": "received"})

# ============================================================
# API Endpoints - CẶP 02b: CAMERA EVENT (B2 → B6)
# B2 gửi sự kiện camera sang B6
# ============================================================
@app.post("/policies/evaluate-camera-event", response_model=CameraEventResponse, tags=["Camera Integration"])
async def evaluate_camera_event(
    event: CameraEvent,
    token_data: dict = Depends(verify_token)
):
    """
    Camera Stream (B2) gửi sự kiện camera sang B6
    B6 đánh giá và ra quyết định có cảnh báo hay không
    """
    logger.info(f"Received camera event from B2: camera={event.camera_id}, event_type={event.event_type}, motion={event.motion_detected}")
    
    # 1. Đánh giá sự kiện
    result = await camera_evaluator.evaluate(event)
    
    # 2. Nếu có alert, xử lý
    if result["alert_triggered"] and result["alerts"]:
        for alert in result["alerts"]:
            # 💾 Lưu alert vào database và danh sách
            await alert_storage.save_alert(alert)
            alerts_list.append(alert.dict())
            
            # 🔔 Gửi alert sang Notification (B7)
            await notification_client.send_alert(alert)
            logger.info(f"🔔 Camera alert sent to B7: {alert.eventId} - {alert.severity}")
            
            # 📊 Gửi decision sang Analytics (B5)
            await analytics_client.send_decision(
                correlation_id=str(event.correlationId),
                decision=alert.severity,
                reason=f"Camera event: {result['message']}",
                latency_ms=0,
                quota_before=0,
                quota_after=0,
                rules_triggered=[result["rule_id"]]
            )
            logger.info(f"📊 Camera decision sent to B5: {alert.eventId}")
    
    # 3. Trả response cho B2
    return CameraEventResponse(
        status="processed",
        alert_triggered=result["alert_triggered"],
        message=result["message"] or "Event processed successfully",
        correlation_id=event.correlationId
    )

# ============================================================
# API Endpoints - CẶP 08: B6 → ANALYTICS (Provider - B5 gọi B6)
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
# API Endpoints - B6 → AI VISION (Consumer - B6 gọi B4)
# ============================================================
@app.post("/evaluate-detection", response_model=AIDetectionResponse, tags=["Event Evaluation"])
async def evaluate_detection(request: AIDetectionRequest, token_data: dict = Depends(verify_token)):
    """
    B6 gọi AI Vision (B4) để phân tích ảnh
    """
    try:
        result = await ai_client.detect(request)
        return result
    except Exception as e:
        logger.error(f"AI Vision error: {e}")
        return AIDetectionResponse(
            detectionId=request.detectionId or uuid4(),
            matched=False,
            label="unknown",
            confidence=0.0,
            status="error",
            modelVersion="fallback",
            processedAt=datetime.now()
        )


# ============================================================
# API Endpoints - B6 → ACCESS GATE (Consumer)
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
async def get_gate_status(gateId: str, token_data: dict = Depends(verify_token)):
    """B6 gọi Access Gate (B3) để lấy status"""
    return await access_gate_client.get_gate_status(gateId)

# ============================================================
# API Endpoints - TEST ALERT (B6 → B7)
# ============================================================
@app.post("/internal/send-test-alert", tags=["System Admin"])
async def send_test_alert(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    Test endpoint để gửi alert trực tiếp đến B7
    Dùng để kiểm tra kết nối đến Notification Service
    """
    try:
        body = await request.json()
    except:
        body = {}
    
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
    
    # Gửi đến B7 (có fallback)
    sent = await notification_client.send_alert(alert)
    
    # Lưu vào danh sách alerts
    alerts_list.append(alert.dict())
    
    return JSONResponse(
        status_code=200 if sent else 202,
        content={
            "status": "sent" if sent else "queued",
            "alertId": str(alert.eventId),
            "severity": alert.severity,
            "mode": "real" if sent else "fallback",  # ← ĐÃ SỬA
            "message": "Alert sent successfully" if sent else "Alert queued (fallback mode)"
        }
    )

@app.get("/internal/fallback-decisions", tags=["System Admin"])
async def get_fallback_decisions(
    limit: int = 10,
    token_data: dict = Depends(verify_token)
):
    """Lấy danh sách decisions đã lưu fallback (dùng để kiểm tra)"""
    return await analytics_client.get_fallback_decisions(limit)

# ============================================================
# API Endpoints - SYSTEM ADMIN
# ============================================================
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