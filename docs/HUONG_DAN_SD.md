# 📘 HƯỚNG DẪN VẬN HÀNH B6 CORE BUSINESS SERVICE

**Phiên bản:** 1.3.0  
**Ngày cập nhật:** 2026-06-16  
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

### Bước 5.1: Health check

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
    "timestamp": "2026-06-16T12:27:15.455593"
}
```

### Bước 5.2: Test access check (B3 → B6)

```bash
curl -X POST "http://localhost:8000/access/check" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "CARD_12345",
    "gateId": "LOBBY_01",
    "direction": "IN",
    "correlationId": "ab9bca6a-9d00-421e-a0cf-5b8274b6703a",
    "timestamp": "2026-06-16T12:28:45.471Z"
  }'
```

**Kết quả mong đợi:**
```json
{
  "decision": "ALLOW",
  "reasonCode": "POLICY_VIOLATION",
  "decisionId": "e19f8df2-f67f-4eba-8397-c3487ae68729",
  "remainingQuota": 4,
  "isDuplicate": false,
  "expiresAt": null
}
```

### Bước 5.3: Test sensor evaluation (B1 → B6)

## TRẠNG THÁI VÀ ĐIỀU KIỆN KÍCH HOẠT

### NORMAL - Bình thường

| Điều kiện | Giá trị | Mô tả |
|-----------|---------|-------|
| Nhiệt độ | < 35°C | Trong ngưỡng an toàn |
| Độ ẩm | < 85% | Trong ngưỡng an toàn |
| CO2 | < 1200 ppm | Trong ngưỡng an toàn |
| Khói | < 0.5 ppm | Trong ngưỡng an toàn |
| Pin | >= 20% | Đủ pin |
| Chuyển động | - | Không bất thường |

**✅ KHÔNG TẠO ALERT**

### WARNING - Cảnh báo

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

### DANGER - Nguy hiểm

| ID | Điều kiện | Ngưỡng | Severity | Rule ID |
|----|-----------|--------|----------|---------|
| D1 | Nhiệt độ | >= 40°C | **CRITICAL** | TEMP_DANGER |
| D2 | CO2 | >= 1800 ppm | **CRITICAL** | CO2_DANGER |
| D3 | Khói | >= 1.0 ppm | **CRITICAL** | SMOKE_DANGER |

**🔔 TẠO ALERT - GỬI B7 & B5**

### SENSOR_ERROR - Lỗi cảm biến

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| E1 | temperature_c = null AND humidity_percent = null | **HIGH** | SENSOR_ERROR |

**🔔 TẠO ALERT - GỬI B7 & B5**

### INVALID_DEVICE - Thiết bị không hợp lệ

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| I1 | device_id không tồn tại trong device_registry | **CRITICAL** | INVALID_DEVICE |

```bash
CORR_ID=$(uuidgen)
curl -X POST "http://localhost:8000/internal/evaluate-sensor" \
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

### Bước 5.4: Test AI detection (B4 → B6)

**Tạo UUID mới:**
```bash
uuidgen
# Kết quả: 67a1d2e9-f261-4a2c-998f-c479eee54eb6
```

**Gửi request:**
```bash
curl -X POST "http://localhost:8000/policies/evaluate-detection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "67a1d2e9-f261-4a2c-998f-c479eee54eb6",
    "matched": true,
    "label": "person",
    "confidence": 0.95,
    "status": "matched",
    "modelVersion": "yolov8n",
    "processedAt": "2026-06-16T09:38:40.510Z"
  }'
```

**Kết quả mong đợi:**
```json
{
    "status": "received"
}
```

### Bước 5.5: Lấy danh sách alerts (B5 → B6)

```bash
curl -X GET "http://localhost:8000/alerts?limit=20" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:**
```json
[
  {
    "eventId": "e2dbca73-34fb-4cc0-8a7e-a68358b7763b",
    "correlationId": "38e42605-0c56-46e9-9a6b-ff20457f9742",
    "traceId": "52f2d7a3-6944-48d6-afa4-49bf91d2f1f0",
    "severity": "CRITICAL",
    "userId": "SYSTEM",
    "gateId": "UNKNOWN",
    "alertDetails": {
      "ruleId": "SENSOR_THRESHOLD_RULE",
      "message": "High temperature detected: 65°C from SENSOR_TEMP001",
      "deviceId": "SENSOR_TEMP001",
      "readings": {
        "temperature_c": 65,
        "motion_detected": false,
        "smoke_ppm": 0
      }
    },
    "timestamp": "2026-06-16T12:29:50.647692"
  }
]
```

### Bước 5.6: Lấy quyền truy cập

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
    {
      "end": "22:00:00",
      "start": "08:00:00"
    }
  ],
  "allowedGateIds": [
    "LAB_01",
    "LAB_02",
    "LIB_01"
  ],
  "loaded_at": "2026-06-16T12:26:51.544272"
}
```

### Bước 5.7: Test camera event (B2 → B6)

> **Mục đích**: Kiểm tra endpoint nhận sự kiện từ Camera Stream (B2).

#### Test 1: Sự kiện chuyển động bình thường (không cảnh báo)

```bash
CORR_ID=$(uuidgen)
curl -X POST "http://localhost:8000/policies/evaluate-camera-event" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-lobby-01\",
    \"event_type\": \"motion_detected\",
    \"motion_detected\": true,
    \"location\": \"Lobby 01 - Main Entrance\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": false,
  "message": "Event processed successfully",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

#### Test 2: Sự kiện chuyển động tại khu vực nhạy cảm (CÓ CẢNH BÁO)

```bash
CORR_ID=$(uuidgen)
curl -X POST "http://localhost:8000/policies/evaluate-camera-event" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-server-room-01\",
    \"event_type\": \"motion_detected\",
    \"motion_detected\": true,
    \"location\": \"SERVER_ROOM - Critical Area\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected in sensitive area: SERVER_ROOM - Critical Area - Camera: cam-server-room-01",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

#### Test 3: Sự kiện camera offline (CÓ CẢNH BÁO)

```bash
CORR_ID=$(uuidgen)
curl -X POST "http://localhost:8000/policies/evaluate-camera-event" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-gate-01\",
    \"event_type\": \"camera_offline\",
    \"motion_detected\": false,
    \"location\": \"Main Gate\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera cam-gate-01 is offline at Main Gate",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

#### Test 4: Sự kiện camera bị che khuất (CÓ CẢNH BÁO)

```bash
CORR_ID=$(uuidgen)
curl -X POST "http://localhost:8000/policies/evaluate-camera-event" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-lobby-01\",
    \"event_type\": \"obstruction\",
    \"motion_detected\": false,
    \"location\": \"Lobby 01\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera cam-lobby-01 is obstructed at Lobby 01",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

#### Kiểm tra log và alert

```bash
# Kiểm tra log camera event
docker compose logs api | grep -E "camera event|Camera"

# Kiểm tra alert đã được tạo
curl -X GET "http://localhost:8000/alerts?limit=5" \
  -H "Authorization: Bearer mock-token-123" | jq '.'

# Kiểm tra log B7
docker compose logs api | grep -E "Camera alert sent to B7"
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
    "processedAt": "2026-06-16T10:30:00Z"
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

# Kết quả mong đợi:

```json
{
  "b3": {"status": "fallback", "display": "🟡 Using Fallback"},
  "b4": {"status": "fallback", "display": "🟡 Fallback (B6 internal AI mock)"},
  "b7": {"status": "fallback", "display": "🟡 Using Fallback"},
  "b5": {"status": "fallback", "display": "🟡 Using Fallback"}
}
```

## 7.1. B6 gọi B4 (AI Vision) - Phân tích ảnh

**Mục đích:** Test luồng B6 gọi AI Vision Service (B4) để phân tích ảnh và nhận kết quả nhận dạng đối tượng.

### Bước 7.1.1: Kiểm tra AI Vision Service đang chạy

```bash
curl http://localhost:9000/health
```

**Kết quả mong đợi:**

```json
{
  "status": "UP",
  "model_loaded": true,
  "timestamp": "2026-06-16T14:46:16.791322"
}
```

---

### Bước 7.1.2: Test AI Vision trực tiếp (Provider Test)

#### Test 1: Phát hiện người (Person Detection)

```bash
UUID_V4=$(uuidgen)

curl -X POST http://localhost:9000/predict \
  -H "Content-Type: application/json" \
  -d "{
    \"correlationId\": \"${UUID_V4}\",
    \"imageRef\": \"person_walking.jpg\"
  }"
```

**Kết quả mong đợi:**

```json
{
  "detectionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "matched": true,
  "label": "person",
  "confidence": 0.80,
  "status": "matched",
  "modelVersion": "yolov8n-mock-v1",
  "processedAt": "2026-06-16T..."
}
```

#### Test 2: Phát hiện cháy/khói (Fire/Smoke Detection)

```bash
UUID_V4=$(uuidgen)

curl -X POST http://localhost:9000/predict \
  -H "Content-Type: application/json" \
  -d "{
    \"correlationId\": \"${UUID_V4}\",
    \"imageRef\": \"smoke_detected.jpg\"
  }"
```

**Kết quả mong đợi:**

```json
{
  "detectionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "matched": true,
  "label": "fire",
  "confidence": 0.95,
  "status": "matched",
  "modelVersion": "yolov8n-mock-v1",
  "processedAt": "2026-06-16T..."
}
```

#### Test 3: Đối tượng không xác định (Unknown Object)

```bash
UUID_V4=$(uuidgen)

curl -X POST http://localhost:9000/predict \
  -H "Content-Type: application/json" \
  -d "{
    \"correlationId\": \"${UUID_V4}\",
    \"imageRef\": \"unknown_object.jpg\"
  }"
```

**Kết quả mong đợi:**

```json
{
  "detectionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "matched": false,
  "label": "unknown",
  "confidence": 0.26,
  "status": "not_matched",
  "modelVersion": "yolov8n-mock-v1",
  "processedAt": "2026-06-16T..."
}
```

### Bước 7.1.3: B6 gọi AI Vision qua API Gateway (Consumer Test)

**Mục đích:** Xác nhận B6 đóng vai trò Consumer và gọi sang B4 để phân tích ảnh.

```bash
CORR_ID=$(uuidgen)

curl -X POST http://localhost:8000/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"correlationId\": \"${CORR_ID}\",
    \"imageRef\": \"person.jpg\",
    \"timestamp\": \"2026-06-16T14:00:00.000Z\"
  }"
```

**Kết quả mong đợi:**

```json
{
  "detectionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "matched": true,
  "label": "person",
  "confidence": 0.85,
  "status": "matched",
  "modelVersion": "ultimate-fallback",
  "processedAt": "2026-06-16T..."
}
```

---

### Bước 7.1.4: Kiểm tra log Consumer

```bash
docker compose logs api --tail 50
```

Hoặc:

```bash
docker compose logs api | grep -i "AI"
```

**Kết quả mong đợi:**

```text
🔍 AI Vision mode: fallback
🟡 AI Vision: FALLBACK mode - calling internal AI
```

### Bước 7.2: B6 gọi B3 (Access Gate) - Lấy access logs

```bash
curl -X GET "http://localhost:8000/internal/access-logs?limit=5" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi (FALLBACK mode - khi B3 chưa kết nối):**
```json
[
    {
        "logId": "fallback_log_1",
        "cardId": "CARD_1",
        "gateId": "LAB_01",
        "direction": "IN",
        "status": "GRANTED",
        "timestamp": "2026-06-16T13:44:04.333234",
        "operatorNote": "Fallback mode - B3 not connected",
        "mock": true
    },
    {
        "logId": "fallback_log_2",
        "cardId": "CARD_2",
        "gateId": "LAB_01",
        "direction": "IN",
        "status": "GRANTED",
        "timestamp": "2026-06-16T13:44:04.333239",
        "operatorNote": "Fallback mode - B3 not connected",
        "mock": true
    },
    {
        "logId": "fallback_log_3",
        "cardId": "CARD_3",
        "gateId": "LAB_01",
        "direction": "IN",
        "status": "GRANTED",
        "timestamp": "2026-06-16T13:44:04.333240",
        "operatorNote": "Fallback mode - B3 not connected",
        "mock": true
    }
]
```

Lấy trạng thái gate:

```bash
curl -X GET "http://localhost:8000/internal/gates/LAB_01/status" \
  -H "Authorization: Bearer mock-token-123"
```
# Kết quả mong đợi (fallback):

``` json
{
    "gateId": "LAB_01",
    "isOnline": true,
    "lastHeartbeat": "2026-06-16T13:45:05.968087",
    "currentMode": "normal",
    "mock": true,
    "message": "Fallback mode - B3 not connected"
}
```

### Bước 7.3: B6 gửi alert đến B7 (Notification) - Consumer

> **Mục đích**: Test luồng B6 gửi alert đến Notification Service (B7) khi phát hiện sự cố.

#### Bước 7.3.1: Trigger Alert từ Sensor (B1 → B6 → B7)

Khi sensor nhiệt độ > 60°C, B6 tự động gửi alert đến B7.

**Gửi sensor event với nhiệt độ cao (sẽ trigger alert):**
```bash
# Tạo UUID hợp lệ
CORR_ID=$(uuidgen)
echo "Correlation ID: $CORR_ID"

curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"source_service\": \"team-iot\",
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

**Kết quả mong đợi:**
```json
{
  "message": "Event received for processing",
  "device_id": "esp32-lab-a101",
  "status": "danger",
  "alerts_count": 1
}
```

**Kiểm tra alert đã được lưu:**
```bash
curl -X GET "http://localhost:8000/alerts?limit=10" \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi:** Danh sách alerts (có alert vừa tạo)

**Kiểm tra log B7:**
```bash
docker compose logs api | grep -E "Alert sent to B7|B7_FALLBACK"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-16 09:36:56,814 - src.core_service.services.alert_storage - INFO - Alert saved: 8f0d6ff0-4a62-4195-b770-926100317248 - CRITICAL
b6-core-api  | 2026-06-16 09:36:56,815 - src.core_service.services.notification_client - INFO - 📧 [B7_FALLBACK] Alert stored locally: 8f0d6ff0-4a62-4195-b770-926100317248 - CRITICAL
```

#### Bước 7.3.2: Trigger Alert từ Access Check (B3 → B6 → B7)

Khi Access Gate có lỗi hoặc cảnh báo, B6 tự động gửi alert đến B7.

**Gửi access check với thẻ không có quyền (sẽ trigger alert):**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"cardId\": \"INVALID_CARD\",
    \"gateId\": \"RESTRICTED_AREA\",
    \"direction\": \"IN\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "decision": "DENY",
  "reasonCode": "POLICY_VIOLATION",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 5,
  "isDuplicate": false,
  "expiresAt": null
}
```

**Kiểm tra log B7 từ access check:**
```bash
docker compose logs api | grep -E "Alert sent to B7 for access check"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-16 09:40:00,xxx - src.core_service.main - INFO - 🔔 Alert sent to B7 for access check: INVALID_CARD - DENY
b6-core-api  | 2026-06-16 09:40:00,xxx - src.core_service.services.notification_client - INFO - 📧 [B7_FALLBACK] Alert stored locally: xxxxx... - CRITICAL
```

#### Bước 7.3.3: Trigger Alert từ AI Detection (B4 → B6 → B7)

Khi AI phát hiện người với độ tin cậy cao, B6 tự động gửi alert đến B7.

**Gửi kết quả detection từ AI:**
```bash
DETECTION_ID=$(uuidgen)
curl -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"detectionId\": \"${DETECTION_ID}\",
    \"matched\": true,
    \"label\": \"person\",
    \"confidence\": 0.95,
    \"status\": \"matched\",
    \"modelVersion\": \"yolov8n\",
    \"processedAt\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "received"
}
```

**Kiểm tra log B7 từ AI detection:**
```bash
docker compose logs api | grep -E "Alert sent to B7 from AI detection"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-16 09:42:00,xxx - src.core_service.main - INFO - 🔔 Alert created from AI detection: xxxxx...
b6-core-api  | 2026-06-16 09:42:00,xxx - src.core_service.main - INFO - 🔔 Alert sent to B7 from AI detection: xxxxx...
b6-core-api  | 2026-06-16 09:42:00,xxx - src.core_service.services.notification_client - INFO - 📧 [B7_FALLBACK] Alert stored locally: xxxxx... - HIGH
```

#### Bước 7.3.4: Gửi Alert thủ công (Test Endpoint)

**Gửi alert thủ công đến B7:**
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

#### Bước 7.3.5: Trigger Alert từ Camera Event (B2 → B6 → B7)

Khi Camera Stream (B2) gửi sự kiện bất thường, B6 tự động gửi alert đến B7.

**Test 1: Camera offline (CÓ CẢNH BÁO)**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-gate-01\",
    \"event_type\": \"camera_offline\",
    \"motion_detected\": false,
    \"location\": \"Main Gate\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera cam-gate-01 is offline at Main Gate",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Test 2: Camera bị che khuất (CÓ CẢNH BÁO)**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-lobby-01\",
    \"event_type\": \"obstruction\",
    \"motion_detected\": false,
    \"location\": \"Lobby 01\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera cam-lobby-01 is obstructed at Lobby 01",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Test 3: Chuyển động tại khu vực nhạy cảm (CÓ CẢNH BÁO)**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-server-room-01\",
    \"event_type\": \"motion_detected\",
    \"motion_detected\": true,
    \"location\": \"SERVER_ROOM - Critical Area\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected in sensitive area: SERVER_ROOM - Critical Area - Camera: cam-server-room-01",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Test 4: Chuyển động trong giờ cấm (CÓ CẢNH BÁO)**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-lobby-01\",
    \"event_type\": \"motion_detected\",
    \"motion_detected\": true,
    \"location\": \"Lobby 01\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT23:30:00.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected during restricted hours (23:30) at Lobby 01 - Camera: cam-lobby-01",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Kiểm tra log B7 từ camera event:**
```bash
docker compose logs api | grep -E "Camera alert sent to B7"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-17 16:50:00,xxx - src.core_service.main - INFO - 🔔 Camera alert sent to B7: xxxxx... - CRITICAL
b6-core-api  | 2026-06-17 16:50:00,xxx - src.core_service.services.notification_client - INFO - 📧 [B7_FALLBACK] Alert stored locally: xxxxx... - CRITICAL
```

#### Bước 7.3.6: Tóm tắt các trigger gửi B7

| Trigger | Endpoint | Điều kiện | Severity |
|---------|----------|-----------|----------|
| **Sensor vượt ngưỡng** | `POST /internal/evaluate-sensor` | temp > 60°C | CRITICAL |
| **Sensor vượt ngưỡng** | `POST /internal/evaluate-sensor` | temp > 45°C | HIGH |
| **Sensor vượt ngưỡng** | `POST /internal/evaluate-sensor` | smoke > 1000ppm | CRITICAL |
| **Sensor vượt ngưỡng** | `POST /internal/evaluate-sensor` | smoke > 500ppm | HIGH |
| **Access Check lỗi** | `POST /access/check` | decision = DENY | CRITICAL |
| **Access Check cảnh báo** | `POST /access/check` | quota <= 1 | WARNING |
| **AI Detection** | `POST /policies/evaluate-detection` | person + confidence > 0.7 | HIGH |
| **Camera - Offline** | `POST /policies/evaluate-camera-event` | event_type = camera_offline | CRITICAL |
| **Camera - Obstruction** | `POST /policies/evaluate-camera-event` | event_type = obstruction | HIGH |
| **Camera - Motion Sensitive** | `POST /policies/evaluate-camera-event` | motion_detected = true & location ∈ sensitive | CRITICAL |
| **Camera - Motion Restricted Hours** | `POST /policies/evaluate-camera-event` | motion_detected = true & 22:00-06:00 | HIGH |

### Bước 7.4: B6 gửi decision đến B5 (Analytics) - Consumer

> **Mục đích**: Test luồng B6 gửi decision đến Analytics Service (B5) để phân tích và thống kê.

#### Bước 7.4.1: Trigger Decision từ Access Check (B3 → B6 → B5)

Mỗi request `/access/check` đều tự động gửi decision đến B5.

**Tạo UUID hợp lệ:**
```bash
CORR_ID=$(uuidgen)
echo "Correlation ID: $CORR_ID"
```

**Gửi access check (trigger decision → B5):**
```bash
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

**Kết quả mong đợi:**
```json
{
  "decision": "ALLOW",
  "reasonCode": "VALID",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 4,
  "isDuplicate": false,
  "expiresAt": null
}
```

**Kiểm tra log (FALLBACK mode):**
```bash
docker compose logs api --tail 30 | grep -E "ANALYTICS_FALLBACK|ANALYTICS_STORAGE"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-16 14:17:16,473 - WARNING - 📊 [ANALYTICS_FALLBACK] B5 not available: [Errno -2] Name or service not known, using fallback storage
b6-core-api  | 2026-06-16 14:17:16,473 - DEBUG - 📊 [ANALYTICS_STORAGE] Fallback storage size: 1
```

✅ **THÀNH CÔNG**: Decision đã được lưu vào fallback storage

#### Bước 7.4.2: Trigger Decision từ Sensor Alert (B1 → B6 → B5)

Khi sensor tạo alert (status = warning hoặc danger), B6 tự động gửi decision đến B5.

**Gửi sensor event để trigger alert và gửi B5:**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"source_service\": \"team-iot\",
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

**Kiểm tra log B5 từ sensor:**
```bash
docker compose logs api | grep -E "Decision sent to B5.*alert"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-16 09:36:56,816 - src.core_service.main - INFO - 📊 Decision sent to B5 (Analytics) for alert: xxxxx...
b6-core-api  | 2026-06-16 09:36:56,817 - WARNING - 📊 [ANALYTICS_FALLBACK] B5 not available, using fallback storage
```

#### Bước 7.4.3: Trigger Decision từ AI Detection (B4 → B6 → B5)

Khi AI phát hiện người, B6 tự động gửi decision đến B5.

**Gửi kết quả detection từ AI:**
```bash
DETECTION_ID=$(uuidgen)
curl -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"detectionId\": \"${DETECTION_ID}\",
    \"matched\": true,
    \"label\": \"person\",
    \"confidence\": 0.95,
    \"status\": \"matched\",
    \"modelVersion\": \"yolov8n\",
    \"processedAt\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\"
  }"
```

**Kiểm tra log B5 từ AI detection:**
```bash
docker compose logs api | grep -E "Decision sent to B5.*AI detection"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-16 09:42:00,xxx - src.core_service.main - INFO - 📊 Decision sent to B5 (Analytics) from AI detection: xxxxx...
b6-core-api  | 2026-06-16 09:42:00,xxx - WARNING - 📊 [ANALYTICS_FALLBACK] B5 not available, using fallback storage
```

#### Bước 7.4.4: Xem danh sách Fallback Decisions

**Lấy danh sách decisions đã lưu trong fallback storage:**
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
    "timestamp": "2026-06-16T14:17:16.473000",
    "mode": "fallback"
  },
  {
    "correlationId": "38e42605-0c56-46e9-9a6b-ff20457f9742",
    "decision": "ALERT_CREATED",
    "reason": "CRITICAL",
    "latencyMs": 0,
    "quotaBefore": 0,
    "quotaAfter": 0,
    "rulesTriggered": ["SENSOR_THRESHOLD_RULE"],
    "timestamp": "2026-06-16T14:18:20.123000",
    "mode": "fallback"
  }
]
```

#### Bước 7.4.5: Gửi Decision thủ công (Test Endpoint)

**Gửi decision test đến B5:**
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

#### Bước 7.4.6: Trigger Decision từ Camera Event (B2 → B6 → B5)

Khi Camera Stream gửi sự kiện bất thường, B6 tự động gửi decision đến B5.

**Gửi camera event để trigger decision đến B5:**
```bash
CORR_ID=$(uuidgen)
curl -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"camera_id\": \"cam-server-room-01\",
    \"event_type\": \"motion_detected\",
    \"motion_detected\": true,
    \"location\": \"SERVER_ROOM - Critical Area\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")\",
    \"correlationId\": \"${CORR_ID}\"
  }"
```

**Kết quả mong đợi:**
```json
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected in sensitive area: SERVER_ROOM - Critical Area - Camera: cam-server-room-01",
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Kiểm tra log B5 từ camera event:**
```bash
docker compose logs api | grep -E "Camera decision sent to B5"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-17 16:55:00,xxx - src.core_service.main - INFO - 📊 Camera decision sent to B5: xxxxx...
b6-core-api  | 2026-06-17 16:55:00,xxx - src.core_service.services.analytics_client - INFO - 📊 [ANALYTICS_FALLBACK] Decision stored locally: xxxxx... - CRITICAL
```

**Kiểm tra fallback decisions:**
```bash
curl -X GET "http://localhost:8000/internal/fallback-decisions?limit=10" \
  -H "Authorization: Bearer mock-token-123" | jq '.[] | select(.reason | contains("Camera"))'
```

**Kết quả mong đợi:**
```json
{
  "correlationId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "decision": "CRITICAL",
  "reason": "Camera event: Motion detected in sensitive area: SERVER_ROOM - Critical Area - Camera: cam-server-room-01",
  "latencyMs": 0,
  "quotaBefore": 0,
  "quotaAfter": 0,
  "rulesTriggered": ["MOTION_SENSITIVE_AREA"],
  "timestamp": "2026-06-17T16:55:00.000000",
  "mode": "fallback"
}
```

#### Bước 7.4.7: Tóm tắt các trigger gửi B5

| Trigger | Endpoint | Decision | Reason |
|---------|----------|----------|--------|
| **Access Check** | `POST /access/check` | ALLOW / DENY | VALID / POLICY_VIOLATION / QUOTA_EXCEEDED |
| **Sensor Alert** | `POST /internal/evaluate-sensor` | ALERT_CREATED | CRITICAL / HIGH / MEDIUM |
| **AI Detection** | `POST /policies/evaluate-detection` | AI_DETECTION | Person detected with confidence X |
| **Test Manual** | `POST /internal/send-test-decision` | ALLOW / DENY | TEST / CUSTOM |
| **Camera - Offline** | `POST /policies/evaluate-camera-event` | event_type = camera_offline | CRITICAL |
| **Camera - Obstruction** | `POST /policies/evaluate-camera-event` | event_type = obstruction | HIGH |
| **Camera - Motion Sensitive** | `POST /policies/evaluate-camera-event` | motion_detected = true & location ∈ sensitive | CRITICAL |
| **Camera - Motion Restricted Hours** | `POST /policies/evaluate-camera-event` | motion_detected = true & 22:00-06:00 | HIGH |

#### Bước 7.4.7: Kiểm tra tổng hợp Fallback Storage

**Xem số lượng decisions đang được lưu:**
```bash
docker compose exec api python -c "
from src.core_service.services.analytics_client import analytics_client
print(f'📊 Fallback storage size: {len(analytics_client.fallback_storage)}')
"
```

**Kết quả mong đợi:**
```
📊 Fallback storage size: 3
```

**Xem toàn bộ log B5:**
```bash
docker compose logs api | grep -E "ANALYTICS|B5"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-16 14:10:35,719 - src.core_service.main - INFO - B5 connection status: offline
b6-core-api  | 2026-06-16 14:17:16,473 - WARNING - 📊 [ANALYTICS_FALLBACK] B5 not available, using fallback storage
b6-core-api  | 2026-06-16 14:17:16,473 - DEBUG - 📊 [ANALYTICS_STORAGE] Fallback storage size: 1
b6-core-api  | 2026-06-16 14:18:20,123 - WARNING - 📊 [ANALYTICS_FALLBACK] B5 not available, using fallback storage
b6-core-api  | 2026-06-16 14:18:20,123 - DEBUG - 📊 [ANALYTICS_STORAGE] Fallback storage size: 2
```

#### Bước 7.4.8: So sánh REAL vs FALLBACK mode

| Tiêu chí | REAL mode (B5 online) | FALLBACK mode (B5 offline) |
|----------|----------------------|---------------------------|
| **Trạng thái kết nối** | `connection-status` hiển thị `real` | `connection-status` hiển thị `fallback` |
| **Log pattern** | `📊 [ANALYTICS_REAL] Decision sent to B5` | `📊 [ANALYTICS_FALLBACK] Decision stored locally` |
| **Dữ liệu** | Gửi trực tiếp đến B5 | Lưu vào `fallback_storage` |
| **Response** | `"status": "sent"` | `"status": "queued"` |
| **Khôi phục** | Không cần | Có thể sync sau khi B5 online |

**Chuyển sang REAL mode (khi có B5):**
```bash
# Cập nhật .env
echo "ANALYTICS_MOCK=false" >> .env
docker compose restart api
```

**Kiểm tra REAL mode:**
```bash
curl -X GET http://localhost:8000/connection-status \
  -H "Authorization: Bearer mock-token-123"
```

**Kết quả mong đợi (REAL mode):**
```json
{
  "b5": {
    "status": "real",
    "display": "🟢 Connected"
  }
}
```

**Log khi REAL mode:**
```bash
docker compose logs api | grep "ANALYTICS_REAL"
```

**Kết quả mong đợi:**
```
b6-core-api  | 2026-06-16 14:20:00,xxx - INFO - 📊 [ANALYTICS_REAL] Decision sent to B5: bd65071b... - ALLOW
```

---

## 8. MỞ GIAO DIỆN DASHBOARD

> **Mục đích**: Sử dụng giao diện web để test nhanh tất cả API mà không cần dùng curl.

### Bước 8.1: Lưu file dashboard

**Tạo file `dashboard.html` trong thư mục BTL:**
```bash
nano dashboard.html
```

**Copy toàn bộ nội dung dashboard HTML (đã cung cấp ở trên) vào file và lưu.**

### Bước 8.2: Mở dashboard

**Cách 1: Mở trực tiếp bằng trình duyệt**
```bash
# Trên Windows
start dashboard.html

# Trên Linux/WSL
xdg-open dashboard.html
```

**Cách 2: Dùng Python HTTP server (khuyến nghị)**
```bash
# Chạy server
python3 -m http.server 8080

# Mở trình duyệt
http://localhost:8080/dashboard.html
```

### Bước 8.3: Sử dụng Dashboard

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

### Bước 8.4: Chọn môi trường test

| Chế độ | Chọn | Mục đích |
|--------|------|----------|
| **Local** | `🏠 Local (localhost:8000)` | Test nội bộ trên máy B6 |
| **Docker** | `🐳 Docker (b6-core-api:8000)` | Test trong Docker network |
| **IP LAN** | `🌐 Custom IP` → nhập `192.168.0.102:8000` | Test như B khác gọi |

### Bước 8.5: Theo dõi trạng thái kết nối

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
  -d '{"correlationId":"mqtt-test","eventType":"sensor.telemetry","deviceId":"SENSOR_TEMP001","readings":{"temperature_c":75}}'
```

**Kết quả mong đợi trong MQTT subscriber:**
```json
{
  "eventId": "...",
  "severity": "CRITICAL",
  "message": "High temperature detected: 75°C from SENSOR_TEMP001"
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

### Lỗi: 422 Unprocessable Entity (UUID error)

**Nguyên nhân:** `detectionId` không đúng định dạng UUID

**Fix:** Tạo UUID bằng `uuidgen` trước khi gửi request

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