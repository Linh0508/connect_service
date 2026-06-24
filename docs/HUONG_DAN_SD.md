# 📘 HƯỚNG DẪN VẬN HÀNH B6 CORE BUSINESS SERVICE

**Phiên bản:** 1.5.0  
**Ngày cập nhật:** 2026-06-24  
**Dành cho:** Smart Campus Operations Platform - Plug-a-thon

---

## 📋 MỤC LỤC

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cài đặt ban đầu](#2-cài-đặt-ban-đầu)
3. [Cấu hình kết nối mạng LAN (Mức 2)](#3-cấu-hình-kết-nối-mạng-lan-mức-2)
4. [Chạy Docker Compose](#4-chạy-docker-compose)
5. [TEST LOCAL: Tự test các endpoint của B6](#5-test-local-tự-test-các-endpoint-của-b6)
6. [TEST PROVIDER: Dùng IP máy B6 cho bên khác test vào](#6-test-provider-dùng-ip-máy-b6-cho-bên-khác-test-vào)
7. [TEST CONSUMER: B6 gọi giả lập các B khác](#7-test-consumer-b6-gọi-giả-lập-các-b-khác)
8. [Mở giao diện Dashboard](#8-mở-giao-diện-dashboard)
9. [Tích hợp MQTT (HiveMQ Cloud) - Mức 3](#9-tích-hợp-mqtt-hivemq-cloud---mức-3)
10. [Xử lý sự cố](#10-xử-lý-sự-cố)
11. [Lệnh nhanh](#11-lệnh-nhanh)

---

## 1. YÊU CẦU HỆ THỐNG

| Thành phần | Phiên bản | Kiểm tra |
|------------|-----------|----------|
| **Docker Engine** | 20.10.0+ | `docker --version` |
| **Docker Compose** | 2.0.0+ | `docker compose version` |
| **RAM** | 4GB (khuyến nghị 8GB) | - |
| **Port trống** | 8000, 5432, 9000 | B6 API, DB, AI Vision |

---

## 2. CÀI ĐẶT BAN ĐẦU

### Bước 2.1: Clone repository

```bash
git clone <repository-url>
cd BTL
```

### Bước 2.2: Tạo file cấu hình

```bash
cp .env.example .env
```

### Bước 2.3: Cấu hình cơ bản trong `.env`

```bash
# Đảm bảo các dòng sau được cấu hình đúng
DEBUG=false
DATABASE_DISABLED=false
```

---

## 3. CẤU HÌNH KẾT NỐI MẠNG LAN (MỨC 2)

### Bước 3.1: Tìm IP của máy bạn

**Windows (CMD):**
```cmd
ipconfig
```
**Kết quả mong đợi:**
```
Wireless LAN adapter Wi-Fi:
   IPv4 Address. . . . . . . . . . . : 192.168.0.102
```
👉 **IP của bạn:** `192.168.0.102`

**Linux/WSL:**
```bash
ip addr show eth0 | grep inet
```
**Kết quả mong đợi:**
```
inet 172.27.125.120/20 ...
```

### Bước 3.2: Mở Firewall trên Windows

**PowerShell (Administrator):**
```powershell
New-NetFirewallRule -DisplayName "B6 API Port 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```
**Kết quả mong đợi:**
```
DisplayName                   : B6 API Port 8000
Enabled                       : True
Action                        : Allow
```

### Bước 3.3: Tạo Port Forward (nếu dùng WSL)

**PowerShell (Administrator):**
```powershell
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=172.27.125.120
netsh interface portproxy show all
```
**Kết quả mong đợi:**
```
Listen on ipv4:             Connect to ipv4:
Address         Port        Address         Port
0.0.0.0         8000        172.27.125.120  8000
```

### Bước 3.4: Kiểm tra port đang lắng nghe

```powershell
netstat -an | findstr "8000"
```
**Kết quả mong đợi:**
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
```

---

## 4. CHẠY DOCKER COMPOSE

```bash
# Build images
docker compose build --no-cache

# Chạy stack
docker compose up -d

# Kiểm tra trạng thái
docker compose ps
```

**Kết quả mong đợi:**
```
NAME           IMAGE                STATUS
b6-postgres    postgres:15-alpine   healthy
b6-ai-vision   btl-ai-vision        healthy
b6-core-api    btl-api              healthy
```

---

## 5. TEST LOCAL: TỰ TEST CÁC ENDPOINT CỦA B6

> **Mục đích**: Kiểm tra tất cả API của B6 hoạt động đúng trên localhost trước khi mở cho bên khác.

---

### 5.1. HEALTH CHECK

**Mục đích:** Kiểm tra trạng thái tổng thể của service.

```bash
curl http://localhost:8000/health
```

**Kết quả mong đợi:**
```json
{
    "status": "UP",
    "components": {
        "database": "UP",
        "cache": "UP",
        "rule_engine": {
            "status": "UP",
            "avg_latency_ms": 0
        },
        "ai_vision": {
            "status": "UP",
            "url": "http://b6-ai-vision:9000"
        },
        "access_gate": {
            "url": "http://b3-access-gate:8001"
        }
    },
    "timestamp": "2026-06-24T12:27:15.455593"
}
```

---

### 5.2. CONNECTION STATUS

**Mục đích:** Kiểm tra trạng thái kết nối đến các service khác (B3, B4, B5, B7).

```bash
curl -X GET http://localhost:8000/connection-status \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:**
```json
{
  "b3": {"status": "fallback", "display": "🟡 Fallback", "auto_detect": false, "retry_interval": 60},
  "b4": {"status": "fallback", "display": "🟡 Fallback", "fallback_url": "http://b6-ai-vision:9000", "auto_detect": false, "retry_interval": 60},
  "b5": {"status": "fallback", "display": "🟡 Fallback", "auto_detect": false, "retry_interval": 60},
  "b7": {"status": "fallback", "display": "🟡 Fallback", "auto_detect": false, "retry_interval": 60},
  "rabbitmq": {"status": "disabled", "display": "⚪ Disabled", "host": "localhost"},
  "retry_enabled": false
}
```

---

### 5.3. B1 → B6: SENSOR EVALUATION

**Mục đích:** Kiểm tra endpoint nhận dữ liệu từ IoT Sensor (B1).

#### TRẠNG THÁI VÀ ĐIỀU KIỆN KÍCH HOẠT

##### NORMAL - Bình thường

| Điều kiện | Giá trị | Mô tả |
|-----------|---------|-------|
| Nhiệt độ | < 35°C | Trong ngưỡng an toàn |
| Độ ẩm | < 85% | Trong ngưỡng an toàn |
| CO2 | < 1200 ppm | Trong ngưỡng an toàn |
| Khói | < 0.5 ppm | Trong ngưỡng an toàn |
| Pin | >= 20% | Đủ pin |

**✅ KHÔNG TẠO ALERT**

##### WARNING - Cảnh báo

| ID | Điều kiện | Ngưỡng | Severity | Rule ID |
|----|-----------|--------|----------|---------|
| W1 | Nhiệt độ | >= 35°C | **HIGH** | TEMP_WARNING |
| W2 | Độ ẩm | >= 85% | **MEDIUM** | HUMIDITY_WARNING |
| W3 | CO2 | >= 1200 ppm | **HIGH** | CO2_WARNING |
| W4 | Khói | >= 0.5 ppm | **HIGH** | SMOKE_WARNING |
| W5 | Pin | < 20% | **MEDIUM** | BATTERY_WARNING |
| W6 | Chuyển động | True (22:00-06:00) | **HIGH** | MOTION_ABNORMAL_TIME |
| W7 | Chuyển động | True (Lab sau 18:00) | **HIGH** | MOTION_AFTER_HOURS_LAB |

**🔔 TẠO ALERT - GỬI B7 & B5**

##### DANGER - Nguy hiểm

| ID | Điều kiện | Ngưỡng | Severity | Rule ID |
|----|-----------|--------|----------|---------|
| D1 | Nhiệt độ | >= 40°C | **CRITICAL** | TEMP_DANGER |
| D2 | CO2 | >= 1800 ppm | **CRITICAL** | CO2_DANGER |
| D3 | Khói | >= 1.0 ppm | **CRITICAL** | SMOKE_DANGER |

**🔔 TẠO ALERT - GỬI B7 & B5**

#### Test 1: Sensor dữ liệu bình thường (NORMAL)

```bash
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "sensor_01",
    "location": "LAB_01",
    "temperature_c": 25.5,
    "humidity_percent": 60.2,
    "light_lux": 410,
    "co2_ppm": 450,
    "smoke_ppm": 0.01,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440001"
  }'
```

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "sensor_01",
  "status": "normal",
  "alerts_count": 0
}
```

#### Test 2: Nhiệt độ cao (WARNING)

```bash
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "sensor_02",
    "location": "SERVER_ROOM",
    "temperature_c": 37.5,
    "humidity_percent": 45.0,
    "co2_ppm": 600,
    "smoke_ppm": 0.02,
    "motion_detected": true,
    "correlationId": "550e8400-e29b-41d4-a716-446655440002"
  }'
```

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "sensor_02",
  "status": "warning",
  "alerts_count": 3
}
```

**Các alert được tạo:**
- TEMP_WARNING (HIGH): Nhiệt độ 37.5°C vượt ngưỡng 35°C
- MOTION_ABNORMAL_TIME (HIGH): Phát hiện chuyển động lúc 05:43 (giờ cấm)
- MOTION_AFTER_HOURS_LAB (HIGH): Phát hiện chuyển động trong Lab sau giờ

#### Test 3: CO2 cao (DANGER)

```bash
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "sensor_03",
    "location": "CONFERENCE_ROOM",
    "temperature_c": 28.0,
    "humidity_percent": 55.0,
    "co2_ppm": 1900,
    "smoke_ppm": 0.01,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440003"
  }'
```

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "sensor_03",
  "status": "danger",
  "alerts_count": 1
}
```

**Alert được tạo:**
- CO2_DANGER (CRITICAL): CO2 1900ppm vượt ngưỡng 1800ppm

#### Test 4: Khói cao (DANGER)

```bash
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "sensor_04",
    "location": "KITCHEN",
    "temperature_c": 45.0,
    "humidity_percent": 30.0,
    "co2_ppm": 800,
    "smoke_ppm": 1.5,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440004"
  }'
```

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "sensor_04",
  "status": "danger",
  "alerts_count": 2
}
```

**Các alert được tạo:**
- TEMP_DANGER (CRITICAL): Nhiệt độ 45°C vượt ngưỡng 40°C
- SMOKE_DANGER (CRITICAL): Khói 1.5ppm vượt ngưỡng 1.0ppm

#### Test 5: Pin yếu (WARNING)

```bash
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "sensor_05",
    "location": "GARDEN",
    "temperature_c": 30.0,
    "humidity_percent": 80.0,
    "battery_percent": 15.0,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440005"
  }'
```

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "sensor_05",
  "status": "warning",
  "alerts_count": 1
}
```

**Alert được tạo:**
- BATTERY_WARNING (MEDIUM): Pin 15% dưới ngưỡng 20%

#### Test 6: Motion sau giờ (WARNING)

```bash
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "sensor_06",
    "location": "LAB_CRITICAL",
    "temperature_c": 22.0,
    "humidity_percent": 50.0,
    "motion_detected": true,
    "timestamp": "2026-06-24T23:30:00",
    "correlationId": "550e8400-e29b-41d4-a716-446655440006"
  }'
```

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "sensor_06",
  "status": "warning",
  "alerts_count": 1
}
```

**Alert được tạo:**
- MOTION_ABNORMAL_TIME (HIGH): Phát hiện chuyển động lúc 23:30 (giờ cấm)

---

### 5.4. B2 → B6: CAMERA EVENT EVALUATION

**Mục đích:** Kiểm tra endpoint nhận sự kiện từ Camera Stream (B2).

#### Test 1: Phát hiện chuyển động (trigger alert nếu trong giờ cấm)

```bash
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "CAM_LOBBY_01",
    "event_type": "motion_detected",
    "motion_detected": true,
    "location": "LOBBY",
    "frame_url": "http://storage/frames/frame_001.jpg"
  }'
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected during restricted hours (05:51) at LOBBY - Camera: CAM_LOBBY_01",
  "correlation_id": "d8ae3c7a-b8f0-4d68-a1a1-5d1cc8c90dff"
}
```

#### Test 2: Camera offline (CRITICAL alert)

```bash
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "CAM_SERVER_01",
    "event_type": "camera_offline",
    "motion_detected": false,
    "location": "SERVER_ROOM"
  }'
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera CAM_SERVER_01 is offline at SERVER_ROOM",
  "correlation_id": "5c62243c-778c-4b52-ac44-7b33e47a03c2"
}
```

#### Test 3: Camera bị che khuất (HIGH alert)

```bash
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "CAM_PARKING_01",
    "event_type": "obstruction",
    "motion_detected": false,
    "location": "PARKING_LOT"
  }'
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera CAM_PARKING_01 is obstructed at PARKING_LOT",
  "correlation_id": "c0946655-ca81-4380-9dae-0b32163f6db3"
}
```

#### Test 4: Motion ở khu vực nhạy cảm (CRITICAL alert)

```bash
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "CAM_VAULT_01",
    "event_type": "motion_detected",
    "motion_detected": true,
    "location": "VAULT",
    "frame_url": "http://storage/frames/frame_002.jpg"
  }'
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected in sensitive area: VAULT - Camera: CAM_VAULT_01",
  "correlation_id": "855bc390-1b2f-46e2-8c21-e3d9b46b679c"
}
```

#### Test 5: Motion vào ban đêm (HIGH alert)

```bash
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "CAM_OFFICE_01",
    "event_type": "motion_detected",
    "motion_detected": true,
    "location": "OFFICE",
    "timestamp": "2026-06-24T02:30:00"
  }'
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected during restricted hours (02:30) at OFFICE - Camera: CAM_OFFICE_01",
  "correlation_id": "f6bb9496-b7c3-42dc-8923-f0e6b62d7b93"
}
```

---

### 5.5. B3 → B6: ACCESS CHECK

**Mục đích:** Kiểm tra endpoint nhận request từ Access Gate (B3).

#### Test 1: Truy cập hợp lệ (ALLOW)

```bash
curl -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "LAB_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440001",
    "direction": "IN"
  }'
```

**Kết quả mong đợi:**
```json
{
  "decision": "DENY",
  "reasonCode": "POLICY_VIOLATION",
  "decisionId": "a6ff647c-7090-4849-be0a-a19340bee8c2",
  "remainingQuota": 4,
  "isDuplicate": false,
  "expiresAt": null
}
```

> **Lưu ý:** Nếu test trong giờ 08:00-22:00, kết quả sẽ là `ALLOW`. Nếu ngoài giờ, kết quả là `DENY` với `POLICY_VIOLATION`.

#### Test 2: Hết quota (DENY)

```bash
# Gọi 6 lần để hết quota (quota mặc định là 5)
for i in {1..6}; do
  echo "Attempt $i:"
  curl -X POST http://localhost:8000/access/check \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer mock-token-123" \
    -d "{
      \"cardId\": \"STU002\",
      \"gateId\": \"LAB_01\",
      \"correlationId\": \"550e8400-e29b-41d4-a716-44665544001$i\",
      \"direction\": \"IN\"
    }"
  echo ""
done
```

**Kết quả mong đợi (lần thứ 6):**
```json
{
  "decision": "DENY",
  "reasonCode": "QUOTA_EXCEEDED",
  "decisionId": "...",
  "remainingQuota": 0,
  "isDuplicate": false,
  "expiresAt": null
}
```

#### Test 3: Không có quyền vào cổng (403 Forbidden)

```bash
curl -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "OFFICE_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440007",
    "direction": "IN"
  }'
```

**Kết quả mong đợi:**
```json
{
  "title": "Gate not authorized",
  "status": 403,
  "detail": "Gate not authorized"
}
```

#### Test 4: Ngoài giờ cho phép (DENY)

```bash
curl -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "LAB_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440008",
    "direction": "IN",
    "timestamp": "2026-06-24T23:30:00"
  }'
```

**Kết quả mong đợi:**
```json
{
  "decision": "DENY",
  "reasonCode": "POLICY_VIOLATION",
  "decisionId": "8b43ff0b-8f14-4dfe-ac4c-b21392898e9a",
  "remainingQuota": 4,
  "isDuplicate": false,
  "expiresAt": null
}
```

#### Test 5: Staff truy cập (ALLOW)

```bash
curl -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STAFF001",
    "gateId": "OFFICE_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440009",
    "direction": "IN"
  }'
```

**Kết quả mong đợi:**
```json
{
  "decision": "ALLOW",
  "reasonCode": "VALID",
  "decisionId": "...",
  "remainingQuota": 9,
  "isDuplicate": false,
  "expiresAt": "2026-06-25T...Z"
}
```

> **Lưu ý:** Staff có quota 10 và được phép vào OFFICE_01.

---

### 5.6. B4 → B6: AI DETECTION RESULT

**Mục đích:** Kiểm tra endpoint nhận kết quả từ AI Vision (B4).

#### Test 1: Phát hiện người với độ tin cậy cao (tạo alert)

```bash
curl -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440010",
    "matched": true,
    "label": "person",
    "confidence": 0.95,
    "status": "matched",
    "modelVersion": "v2.0.1",
    "processedAt": "2026-06-24T10:30:00Z"
  }'
```

**Kết quả mong đợi:**
```json
{"status": "received"}
```

#### Test 2: Phát hiện vật thể (không tạo alert)

```bash
curl -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440011",
    "matched": true,
    "label": "car",
    "confidence": 0.88,
    "status": "matched",
    "modelVersion": "v2.0.1",
    "processedAt": "2026-06-24T10:30:00Z"
  }'
```

**Kết quả mong đợi:**
```json
{"status": "received"}
```

#### Test 3: Không khớp (không tạo alert)

```bash
curl -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440012",
    "matched": false,
    "label": "unknown",
    "confidence": 0.35,
    "status": "not_matched",
    "modelVersion": "v2.0.1",
    "processedAt": "2026-06-24T10:30:00Z"
  }'
```

**Kết quả mong đợi:**
```json
{"status": "received"}
```

#### Test 4: Phát hiện người với độ tin cậy thấp (không tạo alert)

```bash
curl -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440013",
    "matched": true,
    "label": "person",
    "confidence": 0.65,
    "status": "low_confidence",
    "modelVersion": "v2.0.1",
    "processedAt": "2026-06-24T10:30:00Z"
  }'
```

**Kết quả mong đợi:**
```json
{"status": "received"}
```

---

### 5.7. B5 → B6: GET ALERTS

**Mục đích:** Kiểm tra endpoint lấy danh sách cảnh báo cho Analytics (B5).

#### Test 1: Lấy tất cả alerts

```bash
curl -X GET "http://localhost:8000/alerts" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:** Danh sách 18 alerts (sau khi chạy tất cả các test trên)

#### Test 2: Lọc theo severity CRITICAL

```bash
curl -X GET "http://localhost:8000/alerts?severity=CRITICAL" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:** 9 alerts với severity CRITICAL

#### Test 3: Lọc theo severity HIGH

```bash
curl -X GET "http://localhost:8000/alerts?severity=HIGH" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:** 8 alerts với severity HIGH

#### Test 4: Lọc theo severity WARNING

```bash
curl -X GET "http://localhost:8000/alerts?severity=WARNING" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:** [] (không có WARNING alerts)

#### Test 5: Giới hạn số lượng

```bash
curl -X GET "http://localhost:8000/alerts?limit=5" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:** 5 alerts mới nhất

#### Test 6: Đếm số lượng alerts

```bash
curl -X GET "http://localhost:8000/alerts" \
  -H "Authorization: Bearer mock-token-123" | jq 'length'
```

**Kết quả mong đợi:** `18`

---

### 5.8. LẤY POLICY (B3 → B6)

**Mục đích:** Kiểm tra endpoint lấy policy cho Access Gate (B3).

```bash
curl -X GET "http://localhost:8000/policies/access/POL_STUDENT_001" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:**
```json
{
  "policyId": "POL_STUDENT_001",
  "name": "Student Access Policy - Lab Hours",
  "quotaPerDay": 5,
  "allowedTimeWindows": [
    {"start": "08:00:00", "end": "22:00:00"}
  ],
  "allowedGateIds": ["LAB_01", "LAB_02", "LIB_01", "LOBBY_01"],
  "loaded_at": "2026-06-24T..."
}
```

---

### 5.9. AI VISION MODE

**Mục đích:** Kiểm tra mode hiện tại của AI Vision (real/fallback).

```bash
curl -X GET http://localhost:8000/ai-vision-mode \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:**
```json
{
  "mode": "fallback",
  "display": "🟡 Using Fallback (Internal)"
}
```

---

### 5.10. REQUEST LOGS

**Mục đích:** Xem lịch sử các request đã gửi đến B6.

```bash
curl -X GET "http://localhost:8000/internal/request-logs?limit=10" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:** Danh sách 10 request log gần nhất

**Lọc theo service:**
```bash
# Lọc request từ B1 (IoT Sensor)
curl -X GET "http://localhost:8000/internal/request-logs?service=B1&limit=5" \
  -H "Authorization: Bearer mock-token-123"

# Lọc request từ B3 (Access Gate)
curl -X GET "http://localhost:8000/internal/request-logs?service=B3&limit=5" \
  -H "Authorization: Bearer mock-token-123"
```

---

## 6. TEST PROVIDER: DÙNG IP MÁY B6 CHO BÊN KHÁC TEST VÀO

> **Mục đích**: Đưa IP của máy B6 cho các nhóm khác (B1, B3, B4, B5) gọi vào để test.

### Bước 6.1: Lấy IP của máy B6

**Trên máy B6, chạy:**
```bash
# Windows
ipconfig | findstr IPv4

# Linux/WSL
ip addr show | grep inet
```

**Ghi lại IP**, ví dụ: `192.168.0.102`

### Bước 6.2: Cung cấp thông tin cho các B khác

| Bên gọi | Endpoint | Full URL |
|---------|----------|----------|
| B3 (Access Gate) | `POST /access/check` | `http://192.168.0.102:8000/access/check` |
| B1 (IoT Sensor) | `POST /internal/evaluate-sensor` | `http://192.168.0.102:8000/internal/evaluate-sensor` |
| B4 (AI Vision) | `POST /policies/evaluate-detection` | `http://192.168.0.102:8000/policies/evaluate-detection` |
| B5 (Analytics) | `GET /alerts` | `http://192.168.0.102:8000/alerts` |
| B7 (Notification) | `GET /alerts` | `http://192.168.0.102:8000/alerts` |
| Tất cả | `GET /health` | `http://192.168.0.102:8000/health` |

### Bước 6.3: Hướng dẫn B3 test gọi B6

**Trên máy B3 (cùng mạng LAN), chạy:**
```bash
curl -X POST http://192.168.0.102:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "CARD_FROM_B3",
    "gateId": "LOBBY_01",
    "correlationId": "b3-test-001",
    "direction": "IN"
  }'
```

**Kết quả mong đợi:**
```json
{
  "decision": "ALLOW",
  "decisionId": "...",
  "remainingQuota": 4
}
```

### Bước 6.4: Hướng dẫn B1 test gọi B6

**Trên máy B1, chạy:**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://192.168.0.102:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"source_service\": \"team-iot\",
    \"device_id\": \"esp32-lab-a101\",
    \"location\": \"Lab A101\",
    \"temperature_c\": 25.5,
    \"humidity_percent\": 60.2,
    \"light_lux\": 410,
    \"co2_ppm\": 450,
    \"smoke_ppm\": 0.01,
    \"battery_percent\": 77,
    \"motion_detected\": false,
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "esp32-lab-a101",
  "status": "normal",
  "alerts_count": 0
}
```

### Bước 6.5: Hướng dẫn B4 test gửi kết quả AI về B6

**Trên máy B4, tạo UUID:**
```bash
uuidgen
# Kết quả: 67a1d2e9-f261-4a2c-998f-c479eee54eb6
```

**Gửi request:**
```bash
curl -X POST http://192.168.0.102:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "67a1d2e9-f261-4a2c-998f-c479eee54eb6",
    "matched": true,
    "label": "person",
    "confidence": 0.92,
    "status": "matched",
    "modelVersion": "yolov8n",
    "processedAt": "2026-06-24T10:30:00Z"
  }'
```

**Kết quả mong đợi:**
```json
{"status": "received"}
```

### Bước 6.6: Kiểm tra kết nối từ máy khác

**Trên máy khác (B1, B3, B4, B5), chạy:**
```bash
# Ping trước
ping 192.168.0.102
# Kết quả mong đợi: Reply from 192.168.0.102

# Test health
curl http://192.168.0.102:8000/health
# Kết quả mong đợi: {"status":"UP",...}
```

---

## 7. TEST CONSUMER: B6 GỌI GIẢ LẬP CÁC B KHÁC

> **Mục đích**: Test các endpoint mà B6 gọi sang các service khác (B3, B4, B5, B7) với cơ chế fallback khi chưa kết nối thật.

Trước tiên, kiểm tra trạng thái kết nối đến các B:

```bash
curl -X GET http://localhost:8000/connection-status \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:**
```json
{
  "b3": {"status": "fallback", "display": "🟡 Fallback"},
  "b4": {"status": "fallback", "display": "🟡 Fallback"},
  "b5": {"status": "fallback", "display": "🟡 Fallback"},
  "b7": {"status": "fallback", "display": "🟡 Fallback"},
  "rabbitmq": {"status": "disabled", "display": "⚪ Disabled"},
  "retry_enabled": false
}
```

---

### 7.1. B6 gọi B3 (Access Gate) - Lấy access logs

```bash
curl -X GET "http://localhost:8000/internal/access-logs?limit=5" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi (FALLBACK mode):**
```json
[
    {
        "logId": "fallback_log_1",
        "cardId": "CARD_1",
        "gateId": "LAB_01",
        "direction": "IN",
        "status": "GRANTED",
        "timestamp": "2026-06-24T...",
        "operatorNote": "Fallback mode - B3 not connected",
        "mock": true
    },
    {
        "logId": "fallback_log_2",
        "cardId": "CARD_2",
        "gateId": "LAB_01",
        "direction": "IN",
        "status": "GRANTED",
        "timestamp": "2026-06-24T...",
        "operatorNote": "Fallback mode - B3 not connected",
        "mock": true
    },
    {
        "logId": "fallback_log_3",
        "cardId": "CARD_3",
        "gateId": "LAB_01",
        "direction": "IN",
        "status": "GRANTED",
        "timestamp": "2026-06-24T...",
        "operatorNote": "Fallback mode - B3 not connected",
        "mock": true
    }
]
```

**Lấy trạng thái gate:**
```bash
curl -X GET "http://localhost:8000/internal/gates/LAB_01/status" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi (FALLBACK mode):**
```json
{
    "gateId": "LAB_01",
    "isOnline": true,
    "lastHeartbeat": "2026-06-24T...",
    "currentMode": "normal",
    "mock": true,
    "message": "Fallback mode - B3 not connected"
}
```

---

### 7.2. B6 gọi B4 (AI Vision) - Phân tích ảnh

**Mục đích:** Test luồng B6 gọi AI Vision Service (B4) để phân tích ảnh.

#### Bước 7.2.1: Kiểm tra AI Vision Service đang chạy

```bash
curl http://localhost:9000/health
```

**Kết quả mong đợi:**
```json
{
  "status": "UP",
  "model_loaded": true,
  "timestamp": "2026-06-24T..."
}
```

#### Bước 7.2.2: B6 gọi AI Vision qua API Gateway (Consumer Test)

```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"correlationId\": \"${CORR_ID}\",
    \"imageRef\": \"person.jpg\"
  }"
```

**Kết quả mong đợi (FALLBACK mode):**
```json
{
  "detectionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "matched": true,
  "label": "person",
  "confidence": 0.85,
  "status": "matched",
  "modelVersion": "ultimate-fallback",
  "processedAt": "2026-06-24T..."
}
```

#### Bước 7.2.3: Kiểm tra log Consumer

```bash
docker compose logs api | grep -i "AI"
```

**Kết quả mong đợi:**
```
🔍 AI Vision mode: fallback
🟡 AI Vision: FALLBACK mode - calling internal AI at http://b6-ai-vision:9000
✅ AI Vision: FALLBACK mode - internal AI returned result
```

---

### 7.3. B6 gửi decision đến B5 (Analytics) - Consumer

#### 7.3.1: Trigger Decision từ Access Check

Mỗi request `/access/check` đều tự động gửi decision đến B5.

```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"cardId\": \"CARD_12345\",
    \"gateId\": \"LOBBY_01\",
    \"direction\": \"IN\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kiểm tra log (FALLBACK mode):**
```bash
docker compose logs api --tail 30 | grep -E "ANALYTICS_FALLBACK|ANALYTICS_STORAGE"
```

**Kết quả mong đợi:**
```
📊 [ANALYTICS_FALLBACK] Decision stored locally: xxxxx... - ALLOW
📊 [ANALYTICS_STORAGE] Fallback storage size: 1
```

#### 7.3.2: Xem danh sách Fallback Decisions

```bash
curl -X GET "http://localhost:8000/internal/fallback-decisions?limit=10" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:**
```json
[
  {
    "correlationId": "bd65071b-0a21-4b65-8de5-dc1e4b49c2ff",
    "decision": "ALLOW",
    "reason": "VALID",
    "latencyMs": 45,
    "quotaBefore": 5,
    "quotaAfter": 4,
    "rulesTriggered": [],
    "timestamp": "2026-06-24T...",
    "mode": "fallback"
  }
]
```

#### 7.3.3: Gửi Decision thủ công (Test Endpoint)

```bash
curl -X POST http://localhost:8000/internal/send-test-decision \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "decision": "ALLOW",
    "reason": "TEST_MANUAL"
  }'
```

**Kết quả mong đợi:**
```json
{
  "status": "sent",
  "correlationId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "decision": "ALLOW",
  "mode": "fallback",
  "message": "Decision sent successfully"
}
```

---

### 7.4. B6 gửi alert đến B7 (Notification) - Consumer

#### 7.4.1: Trigger Alert từ Sensor

**Gửi sensor event với nhiệt độ cao (trigger alert):**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"device_id\": \"esp32-lab-a101\",
    \"location\": \"Lab A101\",
    \"temperature_c\": 42.5,
    \"humidity_percent\": 45.2,
    \"co2_ppm\": 800,
    \"smoke_ppm\": 0.01,
    \"battery_percent\": 77,
    \"motion_detected\": false,
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "esp32-lab-a101",
  "status": "danger",
  "alerts_count": 1
}
```

**Kiểm tra log B7:**
```bash
docker compose logs api | grep -E "Alert sent to B7|B7_FALLBACK"
```

**Kết quả mong đợi:**
```
Alert saved: xxxxx... - CRITICAL
📧 [B7_FALLBACK] Alert stored locally: xxxxx... - CRITICAL
```

#### 7.4.2: Gửi Alert thủ công (Test Endpoint)

```bash
curl -X POST http://localhost:8000/internal/send-test-alert \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "severity": "CRITICAL",
    "message": "Test alert from B6 dashboard"
  }'
```

**Kết quả mong đợi:**
```json
{
  "status": "sent",
  "alertId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "severity": "CRITICAL",
  "mode": "fallback",
  "message": "Alert sent successfully"
}
```

#### 7.4.3: Tóm tắt các trigger gửi B7

| Trigger | Endpoint | Điều kiện | Severity |
|---------|----------|-----------|----------|
| **Sensor - Nhiệt độ** | `POST /internal/evaluate-sensor` | temp >= 40°C | CRITICAL |
| **Sensor - Nhiệt độ** | `POST /internal/evaluate-sensor` | temp >= 35°C | HIGH |
| **Sensor - Khói** | `POST /internal/evaluate-sensor` | smoke >= 1.0ppm | CRITICAL |
| **Sensor - Khói** | `POST /internal/evaluate-sensor` | smoke >= 0.5ppm | HIGH |
| **Sensor - CO2** | `POST /internal/evaluate-sensor` | co2 >= 1800ppm | CRITICAL |
| **Sensor - Pin** | `POST /internal/evaluate-sensor` | battery < 20% | MEDIUM |
| **Access Check - DENY** | `POST /access/check` | decision = DENY | CRITICAL |
| **Access Check - Warning** | `POST /access/check` | quota <= 1 | WARNING |
| **AI Detection** | `POST /policies/evaluate-detection` | person + confidence > 0.7 | HIGH |
| **Camera - Offline** | `POST /policies/evaluate-camera-event` | event_type = camera_offline | CRITICAL |
| **Camera - Obstruction** | `POST /policies/evaluate-camera-event` | event_type = obstruction | HIGH |
| **Camera - Motion Sensitive** | `POST /policies/evaluate-camera-event` | motion + location ∈ sensitive | CRITICAL |
| **Camera - Motion Restricted** | `POST /policies/evaluate-camera-event` | motion + 22:00-06:00 | HIGH |

---

## 8. MỞ GIAO DIỆN DASHBOARD

> **Mục đích**: Sử dụng giao diện web để test nhanh tất cả API mà không cần dùng curl.

### Bước 8.1: Mở dashboard

**Cách 1: Dùng Python HTTP server (khuyến nghị)**
```bash
# Chạy server
python3 -m http.server 8080

# Mở trình duyệt
http://localhost:8080/dashboard.html
```

**Cách 2: Mở trực tiếp bằng trình duyệt**
```bash
# Trên Windows
start dashboard.html

# Trên Linux/WSL
xdg-open dashboard.html
```

### Bước 8.2: Sử dụng Dashboard

#### Tab 1: Provider (API cung cấp)
- **🎯 B6 Provider APIs**: Test các endpoint mà B1, B3, B4, B5 gọi vào B6
  - `🔐 Access Control (B3 → B6)`: POST /access/check
  - `🌡️ Sensor Evaluation (B1 → B6)`: POST /internal/evaluate-sensor
  - `👁️ AI Detection Result (B4 → B6)`: POST /policies/evaluate-detection
  - `📋 Policy & Audit (B3, B5 → B6)`: GET /policies/access/..., GET /alerts

#### Tab 2: Consumer (B6 gọi sang B khác)
- **🔗 B6 Consumer APIs**: Test các endpoint B6 gọi sang các service khác
  - `👁️ Call AI Vision (B4)`: POST /evaluate-detection → B4
  - `🚪 Call Access Gate (B3)`: GET /internal/access-logs → B3
  - `📤 Send to Notification (B7)`: Send Alert → B7
  - `📊 Send to Analytics (B5)`: Send Sample Decision → B5
- **📊 Service Status**: Hiển thị trạng thái kết nối real/fallback cho từng service

#### Tab 3: Health Check
- **🏥 System Health Dashboard**: Xem trạng thái toàn bộ hệ thống
- **📋 Connection Logs**: Theo dõi lịch sử các request

### Bước 8.3: Chọn môi trường test

| Chế độ | Chọn | Mục đích |
|--------|------|----------|
| **Local** | `🏠 Local (localhost:8000)` | Test nội bộ trên máy B6 |
| **Docker** | `🐳 Docker (b6-core-api:8000)` | Test trong Docker network |
| **IP LAN** | `🌐 Custom IP` → nhập `192.168.0.102:8000` | Test như B khác gọi |

### Bước 8.4: Theo dõi trạng thái kết nối

Dashboard sẽ hiển thị trạng thái kết nối đến các B khác:
- 🟢 **Real** - Đã kết nối, gọi thật
- 🟡 **Fallback** - Chưa kết nối, B6 tự xử lý nội bộ
- 🔴 **Offline** - Mất kết nối

---

## 9. TÍCH HỢP MQTT (HIVE MQ CLOUD) - MỨC 3

### Bước 9.1: Tạo tài khoản HiveMQ Cloud

1. Truy cập [https://www.hivemq.com/cloud/](https://www.hivemq.com/cloud/)
2. Đăng ký tài khoản (miễn phí)
3. Tạo Cluster mới
4. Lấy thông tin connection

### Bước 9.2: Cập nhật `.env`

```bash
cat >> .env << 'EOF'

# MQTT Configuration
MQTT_ENABLED=true
MQTT_BROKER=xxxxxx.s1.eu.hivemq.cloud
MQTT_PORT=8883
MQTT_USERNAME=your-username
MQTT_PASSWORD=your-password
MQTT_TOPIC_PREFIX=smart-campus/events
EOF
```

### Bước 9.3: Thêm thư viện MQTT

```bash
echo "paho-mqtt==1.6.1" >> requirements.txt
docker compose build api
docker compose up -d
```

### Bước 9.4: Kiểm tra kết nối MQTT

```bash
docker compose logs api | grep MQTT
```

**Kết quả mong đợi:**
```
MQTT client connected to xxxxxx.s1.eu.hivemq.cloud:8883
MQTT connected successfully
```

### Bước 9.5: Subscribe để kiểm tra message

```bash
mosquitto_sub -h xxxxxx.s1.eu.hivemq.cloud -p 8883 \
  -u your-username -P your-password \
  -t "smart-campus/events/#" \
  --cafile /etc/ssl/certs/ca-certificates.crt
```

### Bước 9.6: Test publish MQTT từ B6

Khi có alert, B6 sẽ publish lên topic `smart-campus/events/alert/created`

**Trigger alert:**
```bash
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "sensor_high_temp",
    "location": "SERVER_ROOM",
    "temperature_c": 45.0,
    "correlationId": "mqtt-test-001"
  }'
```

**Kết quả mong đợi trong MQTT subscriber:**
```json
{
  "eventId": "...",
  "severity": "CRITICAL",
  "message": "Temperature 45.0°C exceeds danger threshold (40.0°C)"
}
```

---

## 10. XỬ LÝ SỰ CỐ

### Lỗi: Local test thành công, máy khác không gọi được

| Nguyên nhân | Cách fix |
|-------------|----------|
| Firewall chặn | Mở port 8000 (bước 3.2) |
| WSL chưa forward port | Tạo port proxy (bước 3.3) |
| Khác mạng LAN | Kiểm tra cùng WiFi |

**Kiểm tra:**
```bash
# Trên máy khác
ping 192.168.0.102
curl http://192.168.0.102:8000/health
```

### Lỗi: 401 Unauthorized

**Nguyên nhân:** Thiếu token

**Fix:** Thêm header `Authorization: Bearer mock-token-123`

### Lỗi: Container không khởi động

```bash
docker compose logs api
docker compose logs ai-vision
docker compose logs postgres
docker compose restart api
```

### Lỗi: Database connection failed

```bash
# Kiểm tra database
docker exec b6-postgres pg_isready -U b6_user

# Kiểm tra DATABASE_URL trong container
docker exec b6-core-api env | grep DATABASE_URL
```

### Lỗi: AI Vision không hoạt động

```bash
# Kiểm tra AI Vision health
curl http://localhost:9000/health

# Xem logs AI Vision
docker compose logs ai-vision
```

---

## 11. LỆNH NHANH

### Khởi động và kiểm tra

```bash
# Khởi động
docker compose up -d

# Kiểm tra trạng thái
docker compose ps

# Kiểm tra health
curl http://localhost:8000/health

# Xem logs
docker compose logs -f api

# Dừng
docker compose down
```

### Test Provider (B3 gọi B6)

```bash
# Từ máy B3
curl -X POST http://192.168.0.102:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{"cardId":"CARD_TEST","gateId":"LOBBY_01","correlationId":"test"}'
```

### Test Consumer (B6 gọi B4)

```bash
curl -X POST http://localhost:8000/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{"correlationId":"test","imageRef":"person.jpg"}'
```

### Mở Dashboard

```bash
# Cách 1: Mở trực tiếp
start dashboard.html  # Windows
xdg-open dashboard.html  # Linux

# Cách 2: Dùng Python server
python3 -m http.server 8080
# Mở trình duyệt: http://localhost:8080/dashboard.html
```

### MQTT

```bash
# Kiểm tra kết nối
docker compose logs api | grep MQTT

# Subscribe
mosquitto_sub -h <broker> -p 8883 -u <user> -P <pass> -t "smart-campus/events/#"
```

---

## ✅ TÓM TẮT KẾT QUẢ CẦN ĐẠT

| Test case | Kết quả mong đợi |
|-----------|------------------|
| B6 health | `200 OK` + `{"status":"UP"}` |
| B3 → B6 access check | `200 OK` + `{"decision":"ALLOW"}` |
| B1 → B6 sensor | `202 Accepted` + `{"message":"Event received"}` |
| B4 → B6 AI detection | `200 OK` + `{"status":"received"}` |
| B6 → B4 AI detection | `200 OK` + `{"matched":true,"label":"person"}` |
| B5 → B6 alerts | `200 OK` + Danh sách alerts |
| Máy khác ping | `Reply from 192.168.0.102` |
| Máy khác gọi health | `200 OK` + `{"status":"UP"}` |
| MQTT connect | `MQTT connected successfully` |
| MQTT publish | Subscriber nhận được message |
| Dashboard | Hiển thị đầy đủ 3 tabs |

---

**© 2026 Nhóm B6 - Smart Campus Operations Platform** 🚀