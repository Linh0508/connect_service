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

## 📋 **5.3. B1 → B6: SENSOR EVALUATION**

**Mục đích:** Kiểm tra endpoint nhận dữ liệu từ IoT Sensor (B1) với đầy đủ logic VALIDATE, NORMALIZE, ENRICH, CLASSIFY và PRODUCE.

---

### 🔍 **QUY TRÌNH XỬ LÝ CỦA B6**

| Bước | Mô tả | Đầu ra |
|------|-------|--------|
| **1. VALIDATE** | Kiểm tra field bắt buộc, kiểu dữ liệu | Lỗi nếu thiếu field |
| **2. CHECK DEVICE** | Đối chiếu device_id với registry | Device info hoặc invalid_device |
| **3. CHECK SENSOR ERROR** | temperature_c hoặc humidity_percent = null | sensor_error |
| **4. CLASSIFY** | Phân loại theo ngưỡng | status, reason |
| **5. ASSESS** | Xác định alert_level | alert_level |
| **6. POLICY** | Áp policy quyết định alert | should_alert, severity |
| **7. PRODUCE** | Tạo alert + gửi B7/B5 + audit | Response JSON |

---

### 📊 **TRẠNG THÁI VÀ ĐIỀU KIỆN KÍCH HOẠT**

#### NORMAL - Bình thường

| Điều kiện | Giá trị | Mô tả |
|-----------|---------|-------|
| Nhiệt độ | < 35°C | Trong ngưỡng an toàn |
| Độ ẩm | < 85% | Trong ngưỡng an toàn |
| CO2 | < 1200 ppm | Trong ngưỡng an toàn |
| Khói | < 0.5 ppm | Trong ngưỡng an toàn |
| Pin | >= 20% | Đủ pin |

**✅ KHÔNG TẠO ALERT**

---

#### WARNING - Cảnh báo

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

---

#### DANGER - Nguy hiểm

| ID | Điều kiện | Ngưỡng | Severity | Rule ID |
|----|-----------|--------|----------|---------|
| D1 | Nhiệt độ | >= 40°C | **CRITICAL** | TEMP_DANGER |
| D2 | CO2 | >= 1800 ppm | **CRITICAL** | CO2_DANGER |
| D3 | Khói | >= 1.0 ppm | **CRITICAL** | SMOKE_DANGER |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

#### SENSOR_ERROR - Lỗi cảm biến

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| E1 | temperature_c = null AND humidity_percent = null | **HIGH** | SENSOR_ERROR |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

#### INVALID_DEVICE - Thiết bị không hợp lệ

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| I1 | device_id không tồn tại trong device_registry | **CRITICAL** | INVALID_DEVICE |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

### 🧪 **TEST CASES**

#### Test 1: Sensor dữ liệu bình thường (NORMAL)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-lab-a101",
    "location": "Lab A101",
    "temperature_c": 25.5,
    "humidity_percent": 60.2,
    "light_lux": 410,
    "co2_ppm": 450,
    "smoke_ppm": 0.01,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440001"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-lab-a101",
  "status": "normal",
  "alert_level": "low",
  "reason": "All values within normal range",
  "alerts_count": 0,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

---

#### Test 2: Nhiệt độ cao (WARNING)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-lab-a102",
    "location": "Lab A102",
    "temperature_c": 37.5,
    "humidity_percent": 45.0,
    "co2_ppm": 600,
    "smoke_ppm": 0.02,
    "battery_percent": 77,
    "motion_detected": true,
    "correlationId": "550e8400-e29b-41d4-a716-446655440002"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-lab-a102",
  "status": "warning",
  "alert_level": "high",
  "reason": "Temperature 37.5°C exceeds warning threshold (35.0°C); Motion detected at abnormal time ...",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440002"
}
```

**Các alert được tạo:**
- TEMP_WARNING (HIGH): Nhiệt độ 37.5°C vượt ngưỡng 35°C
- MOTION_ABNORMAL_TIME (HIGH): Phát hiện chuyển động trong giờ cấm
- MOTION_AFTER_HOURS_LAB (HIGH): Phát hiện chuyển động trong Lab sau giờ

---

#### Test 3: CO2 cao (DANGER)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-hall-b201",
    "location": "Hall B201",
    "temperature_c": 28.0,
    "humidity_percent": 55.0,
    "co2_ppm": 1900,
    "smoke_ppm": 0.01,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440003"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-hall-b201",
  "status": "danger",
  "alert_level": "high",
  "reason": "CO₂ 1900ppm exceeds danger threshold (1800ppm)",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440003"
}
```

**Alert được tạo:**
- CO2_DANGER (CRITICAL): CO2 1900ppm vượt ngưỡng 1800ppm

---

#### Test 4: Khói cao (DANGER)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-lab-b202",
    "location": "Lab B202",
    "temperature_c": 45.0,
    "humidity_percent": 30.0,
    "co2_ppm": 800,
    "smoke_ppm": 1.5,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440004"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-lab-b202",
  "status": "danger",
  "alert_level": "high",
  "reason": "Temperature 45.0°C exceeds danger threshold (40.0°C); Smoke 1.5ppm exceeds danger threshold (1.0ppm)",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440004"
}
```

**Các alert được tạo:**
- TEMP_DANGER (CRITICAL): Nhiệt độ 45°C vượt ngưỡng 40°C
- SMOKE_DANGER (CRITICAL): Khói 1.5ppm vượt ngưỡng 1.0ppm

---

#### Test 5: Pin yếu (WARNING)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-gate-a",
    "location": "Main Gate A",
    "temperature_c": 30.0,
    "humidity_percent": 80.0,
    "co2_ppm": 450,
    "smoke_ppm": 0.01,
    "battery_percent": 15,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440005"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-gate-a",
  "status": "warning",
  "alert_level": "medium",
  "reason": "Battery 15% below warning threshold (20.0%)",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440005"
}
```

**Alert được tạo:**
- BATTERY_WARNING (MEDIUM): Pin 15% dưới ngưỡng 20%

---

#### Test 6: Motion sau giờ (WARNING)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-office-01",
    "location": "Office 01",
    "temperature_c": 22.0,
    "humidity_percent": 50.0,
    "co2_ppm": 450,
    "smoke_ppm": 0.01,
    "battery_percent": 77,
    "motion_detected": true,
    "timestamp": "2026-06-24T23:30:00",
    "correlationId": "550e8400-e29b-41d4-a716-446655440006"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-office-01",
  "status": "warning",
  "alert_level": "high",
  "reason": "Motion detected at abnormal time 23:30 at Office 01",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440006"
}
```

**Alert được tạo:**
- MOTION_ABNORMAL_TIME (HIGH): Phát hiện chuyển động lúc 23:30 (giờ cấm)

---

#### Test 7: Độ ẩm cao (WARNING)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-lab-a101",
    "location": "Lab A101",
    "temperature_c": 28.0,
    "humidity_percent": 88.0,
    "co2_ppm": 450,
    "smoke_ppm": 0.01,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440007"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-lab-a101",
  "status": "warning",
  "alert_level": "medium",
  "reason": "Humidity 88.0% exceeds warning threshold (85.0%)",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440007"
}
```

**Alert được tạo:**
- HUMIDITY_WARNING (MEDIUM): Độ ẩm 88% vượt ngưỡng 85%

---

#### Test 8: Thiết bị không hợp lệ (INVALID_DEVICE)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "invalid-device-999",
    "location": "Unknown",
    "temperature_c": 25.5,
    "humidity_percent": 60.2,
    "co2_ppm": 450,
    "smoke_ppm": 0.01,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440008"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "invalid-device-999",
  "status": "invalid_device",
  "alert_level": "critical",
  "reason": "Device invalid-device-999 not found in registry",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440008"
}
```

**Alert được tạo:**
- INVALID_DEVICE (CRITICAL): Thiết bị không có trong registry

---

#### Test 9: Lỗi cảm biến (SENSOR_ERROR)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-lab-a101",
    "location": "Lab A101",
    "temperature_c": null,
    "humidity_percent": null,
    "co2_ppm": 450,
    "smoke_ppm": 0.01,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440009"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-lab-a101",
  "status": "sensor_error",
  "alert_level": "high",
  "reason": "Both temperature and humidity are null",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440009"
}
```

**Alert được tạo:**
- SENSOR_ERROR (HIGH): Cảm biến không có dữ liệu

---

#### Test 10: CO2 Warning (WARNING)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-library-01",
    "location": "Library 01",
    "temperature_c": 25.0,
    "humidity_percent": 50.0,
    "co2_ppm": 1500,
    "smoke_ppm": 0.01,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440010"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-library-01",
  "status": "warning",
  "alert_level": "high",
  "reason": "CO₂ 1500ppm exceeds warning threshold (1200ppm)",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440010"
}
```

**Alert được tạo:**
- CO2_WARNING (HIGH): CO2 1500ppm vượt ngưỡng 1200ppm

---

#### Test 11: Khói Warning (WARNING)

```bash
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "device_id": "esp32-lab-a101",
    "location": "Lab A101",
    "temperature_c": 25.0,
    "humidity_percent": 50.0,
    "co2_ppm": 450,
    "smoke_ppm": 0.8,
    "battery_percent": 77,
    "motion_detected": false,
    "correlationId": "550e8400-e29b-41d4-a716-446655440011"
  }' | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-lab-a101",
  "status": "warning",
  "alert_level": "high",
  "reason": "Smoke 0.8ppm exceeds warning threshold (0.5ppm)",
  "alerts_count": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440011"
}
```

**Alert được tạo:**
- SMOKE_WARNING (HIGH): Khói 0.8ppm vượt ngưỡng 0.5ppm

---

### 📝 **BẢNG TỔNG HỢP TEST CASES B1**

| Test | Device ID | Status | Alert Level | Alerts | Key Reason |
|------|-----------|--------|-------------|--------|------------|
| 1 | esp32-lab-a101 | normal | low | 0 | All values normal |
| 2 | esp32-lab-a102 | warning | high | 1 | Temp 37.5°C + Motion |
| 3 | esp32-hall-b201 | danger | high | 1 | CO2 1900ppm |
| 4 | esp32-lab-b202 | danger | high | 1 | Temp 45°C + Smoke 1.5ppm |
| 5 | esp32-gate-a | warning | medium | 1 | Battery 15% |
| 6 | esp32-office-01 | warning | high | 1 | Motion 23:30 |
| 7 | esp32-lab-a101 | warning | medium | 1 | Humidity 88% |
| 8 | invalid-device-999 | invalid_device | critical | 1 | Device not found |
| 9 | esp32-lab-a101 | sensor_error | high | 1 | Temp & Humidity null |
| 10 | esp32-library-01 | warning | high | 1 | CO2 1500ppm |
| 11 | esp32-lab-a101 | warning | high | 1 | Smoke 0.8ppm |

---

# 📋 **5.4. B2 → B6: CAMERA EVENT EVALUATION**

**Mục đích:** Kiểm tra endpoint nhận sự kiện từ Camera Stream (B2) và đánh giá có cần tạo cảnh báo hay không.

---

## 🔍 **QUY TRÌNH XỬ LÝ CỦA B6**

| Bước | Mô tả | Đầu ra |
|------|-------|--------|
| **1. RECEIVE** | Nhận sự kiện camera từ B2 qua REST | CameraEvent object |
| **2. VALIDATE** | Kiểm tra field bắt buộc (camera_id, event_type) | Lỗi nếu thiếu field |
| **3. CLASSIFY** | Phân loại sự kiện theo loại và ngữ cảnh | alert_triggered, severity, message |
| **4. POLICY** | Áp policy kết hợp với các nguồn khác | should_alert, severity |
| **5. PRODUCE** | Tạo alert + gửi B7/B5 + audit | Response JSON |

---

## 📊 **TRẠNG THÁI VÀ ĐIỀU KIỆN KÍCH HOẠT**

### Motion Detected - Phát hiện chuyển động

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| M1 | Motion tại khu vực nhạy cảm (SERVER_ROOM, VAULT, etc.) | **CRITICAL** | MOTION_SENSITIVE_AREA |
| M2 | Motion trong giờ cấm (22:00 - 06:00) | **HIGH** | MOTION_RESTRICTED_HOURS |
| M3 | Motion tại Lab sau 18:00 | **HIGH** | MOTION_AFTER_HOURS_LAB |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

### Camera Offline - Camera mất kết nối

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| O1 | event_type = camera_offline | **CRITICAL** | CAMERA_OFFLINE |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

### Obstruction - Camera bị che khuất

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| B1 | event_type = obstruction | **HIGH** | CAMERA_OBSTRUCTION |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

### Tamper Detected - Camera bị can thiệp

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| T1 | event_type = tamper_detected | **CRITICAL** | CAMERA_TAMPER |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

## 🧪 **TEST CASES**

### Test 1: Phát hiện chuyển động bình thường (Motion Normal)

**Mô tả:** Camera phát hiện chuyển động tại khu vực bình thường trong giờ cho phép. Không tạo alert.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "cam-lobby-01",
    "event_type": "motion_detected",
    "motion_detected": true,
    "location": "LOBBY",
    "frame_url": "http://storage/frames/frame_001.jpg",
    "correlationId": "550e8400-e29b-41d4-a716-446655440010"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "processed",
  "alert_triggered": false,
  "message": "Event processed successfully",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440010"
}
```

---

### Test 2: Camera offline (CRITICAL alert)

**Mô tả:** Camera mất kết nối → Tạo alert CRITICAL.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "cam-server-01",
    "event_type": "camera_offline",
    "motion_detected": false,
    "location": "SERVER_ROOM",
    "correlationId": "550e8400-e29b-41d4-a716-446655440011"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera cam-server-01 is offline at SERVER_ROOM",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440011"
}
```

**Alert được tạo:**
- CAMERA_OFFLINE (CRITICAL): Camera cam-server-01 offline tại SERVER_ROOM

---

### Test 3: Camera bị che khuất (HIGH alert)

**Mô tả:** Camera bị che khuất → Tạo alert HIGH.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "cam-gate-01",
    "event_type": "obstruction",
    "motion_detected": false,
    "location": "MAIN_GATE",
    "correlationId": "550e8400-e29b-41d4-a716-446655440012"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera cam-gate-01 is obstructed at MAIN_GATE",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440012"
}
```

**Alert được tạo:**
- CAMERA_OBSTRUCTION (HIGH): Camera cam-gate-01 bị che khuất tại MAIN_GATE

---

### Test 4: Motion tại khu vực nhạy cảm (CRITICAL alert)

**Mô tả:** Phát hiện chuyển động tại VAULT → Tạo alert CRITICAL.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "cam-vault-01",
    "event_type": "motion_detected",
    "motion_detected": true,
    "location": "VAULT",
    "frame_url": "http://storage/frames/frame_002.jpg",
    "correlationId": "550e8400-e29b-41d4-a716-446655440013"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected in sensitive area: VAULT - Camera: cam-vault-01",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440013"
}
```

**Alert được tạo:**
- MOTION_SENSITIVE_AREA (CRITICAL): Phát hiện chuyển động tại khu vực nhạy cảm VAULT

---

### Test 5: Motion vào ban đêm (HIGH alert)

**Mô tả:** Phát hiện chuyển động lúc 02:30 → Tạo alert HIGH (giờ cấm).

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "cam-office-01",
    "event_type": "motion_detected",
    "motion_detected": true,
    "location": "OFFICE",
    "timestamp": "2026-06-24T02:30:00",
    "correlationId": "550e8400-e29b-41d4-a716-446655440014"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected during restricted hours (02:30) at OFFICE - Camera: cam-office-01",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440014"
}
```

**Alert được tạo:**
- MOTION_RESTRICTED_HOURS (HIGH): Phát hiện chuyển động trong giờ cấm 02:30

---

### Test 6: Camera Tamper (CRITICAL alert)

**Mô tả:** Camera bị can thiệp vật lý → Tạo alert CRITICAL.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "cam-vault-01",
    "event_type": "tamper_detected",
    "motion_detected": true,
    "location": "VAULT",
    "frame_url": "http://storage/frames/frame_003.jpg",
    "correlationId": "550e8400-e29b-41d4-a716-446655440015"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Camera cam-vault-01 tamper detected at VAULT",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440015"
}
```

**Alert được tạo:**
- CAMERA_TAMPER (CRITICAL): Camera cam-vault-01 bị can thiệp tại VAULT

---

### Test 7: Motion tại Lab sau giờ (HIGH alert)

**Mô tả:** Phát hiện chuyển động trong Lab lúc 23:30 → Tạo alert HIGH.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-camera-event \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "camera_id": "cam-lab-01",
    "event_type": "motion_detected",
    "motion_detected": true,
    "location": "LAB_01",
    "timestamp": "2026-06-24T23:30:00",
    "correlationId": "550e8400-e29b-41d4-a716-446655440016"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "processed",
  "alert_triggered": true,
  "message": "Motion detected during restricted hours (23:30) at LAB_01 - Camera: cam-lab-01",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440016"
}
```

**Alert được tạo:**
- MOTION_RESTRICTED_HOURS (HIGH): Phát hiện chuyển động trong giờ cấm 23:30

---

# 📋 **5.5. B3 → B6: ACCESS CHECK**

**Mục đích:** Kiểm tra endpoint nhận request từ Access Gate (B3) để kiểm tra quyền ra vào real-time với đầy đủ logic VALIDATE, LOOKUP, DECIDE, ENRICH.

---

## 🔍 **QUY TRÌNH XỬ LÝ CỦA B6**

| Bước | Mô tả | Đầu ra |
|------|-------|--------|
| **1. RECEIVE** | Nhận request từ B3 qua REST | AccessCheckRequest |
| **2. VALIDATE** | Kiểm tra field bắt buộc (cardId, gateId, correlationId) | Lỗi nếu thiếu field |
| **3. RATE LIMIT** | Kiểm tra giới hạn request theo IP | 429 nếu quá limit |
| **4. IDEMPOTENCY** | Kiểm tra correlationId đã xử lý chưa | Cache response nếu có |
| **5. GATE AUTH** | Kiểm tra gate có trong token không | 403 nếu không |
| **6. POLICY** | Áp policy: time window, gate allowed | Policy result |
| **7. QUOTA** | Kiểm tra và giảm quota | Quota result |
| **8. DECIDE** | Quyết định ALLOW/DENY | Decision |
| **9. ENRICH** | Bổ sung thông tin (nếu có) | Enriched data |
| **10. AUDIT** | Lưu log mọi quyết định | Audit log |
| **11. PRODUCE** | Gửi decision sang B5, alert sang B7 | Response JSON |

---

## 📊 **TRẠNG THÁI VÀ ĐIỀU KIỆN KÍCH HOẠT**

### ALLOW - Cho phép

| ID | Điều kiện | Mô tả |
|----|-----------|-------|
| A1 | Trong giờ cho phép (08:00-22:00) | Student access allowed |
| A2 | Trong giờ cho phép (06:00-23:59) | Staff access allowed |
| A3 | Quota còn > 0 | Còn lượt truy cập |

**✅ KHÔNG TẠO ALERT**

---

### DENY - Từ chối

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| D1 | Ngoài giờ cho phép | **CRITICAL** | TIME_WINDOW_VIOLATION |
| D2 | Gate không được phép | **CRITICAL** | GATE_NOT_ALLOWED |
| D3 | Hết quota | **WARNING** | QUOTA_EXCEEDED |
| D4 | Gate không có trong token | **CRITICAL** | GATE_AUTHORIZATION_FAILED |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

### WARNING - Cảnh báo (vẫn ALLOW)

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| W1 | Quota còn <= 1 | **WARNING** | QUOTA_ALMOST_EXHAUSTED |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

## 🧪 **TEST CASES**

### Test 1: Student truy cập hợp lệ (ALLOW)

**Mô tả:** Sinh viên STU001 truy cập LAB_01 trong giờ cho phép (08:00-22:00). Quota còn 5/5.

```bash
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "LAB_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440020",
    "direction": "IN"
  }' | jq '.'

# Kết quả mong đợi (trong giờ 08:00-22:00):
{
  "decision": "ALLOW",
  "reasonCode": "VALID",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 4,
  "isDuplicate": false,
  "expiresAt": "2026-06-26T17:30:00Z"
}
```

---

### Test 2: Student truy cập ngoài giờ (DENY)

**Mô tả:** Sinh viên STU001 truy cập LAB_01 lúc 23:30 (ngoài giờ 08:00-22:00). Quota còn 4/5.

```bash
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "LAB_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440021",
    "direction": "IN",
    "timestamp": "2026-06-24T23:30:00"
  }' | jq '.'

# Kết quả mong đợi:
{
  "decision": "DENY",
  "reasonCode": "POLICY_VIOLATION",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 4,
  "isDuplicate": false,
  "expiresAt": null
}
```

**Alert được tạo:**
- ACCESS_ALERT (CRITICAL): Time window violation

---

### Test 3: Staff truy cập (ALLOW)

**Mô tả:** Nhân viên STAFF001 truy cập OFFICE_01 trong giờ cho phép (06:00-23:59). Quota còn 10/10.

```bash
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STAFF001",
    "gateId": "OFFICE_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440022",
    "direction": "IN"
  }' | jq '.'

# Kết quả mong đợi:
{
  "decision": "ALLOW",
  "reasonCode": "VALID",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 9,
  "isDuplicate": false,
  "expiresAt": "2026-06-26T17:30:00Z"
}
```

---

### Test 4: Student truy cập gate không được phép (DENY)

**Mô tả:** Sinh viên STU001 truy cập OFFICE_01 (không có trong allowed_gate_ids của policy student). Quota còn 4/5.

```bash
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "OFFICE_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440023",
    "direction": "IN"
  }' | jq '.'

# Kết quả mong đợi:
{
  "title": "Gate not authorized",
  "status": 403,
  "detail": "Gate not authorized"
}
```

**Alert được tạo:**
- SECURITY_BREACH (CRITICAL): Unauthorized gate access attempt

---

### Test 5: Student truy cập - Quota hết (DENY)

**Mô tả:** Sinh viên STU001 đã dùng hết quota 5/5, truy cập lần thứ 6 → Từ chối.

```bash
# Gọi 6 lần để hết quota
for i in {1..6}; do
  echo "Attempt $i:"
  curl -s -X POST http://localhost:8000/access/check \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer mock-token-123" \
    -d "{
      \"cardId\": \"STU001\",
      \"gateId\": \"LAB_01\",
      \"correlationId\": \"550e8400-e29b-41d4-a716-44665544002$i\",
      \"direction\": \"IN\"
    }" | jq '.'
  echo ""
done

# Kết quả mong đợi (lần thứ 6):
{
  "decision": "DENY",
  "reasonCode": "QUOTA_EXCEEDED",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 0,
  "isDuplicate": false,
  "expiresAt": null
}
```

**Alert được tạo:**
- ACCESS_ALERT (WARNING): Quota exceeded for card STU001

---

### Test 6: Student truy cập - Quota sắp hết (WARNING, vẫn ALLOW)

**Mô tả:** Sinh viên STU001 quota còn 1/5 → Cảnh báo nhưng vẫn cho phép.

```bash
# Giả sử quota đã dùng 4/5, lần này là lần thứ 5
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "LAB_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440027",
    "direction": "IN"
  }' | jq '.'

# Kết quả mong đợi:
{
  "decision": "ALLOW",
  "reasonCode": "VALID",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 0,
  "isDuplicate": false,
  "expiresAt": "2026-06-26T17:30:00Z"
}
```

**Alert được tạo:**
- ACCESS_ALERT (WARNING): Quota almost exhausted for card STU001

---

### Test 7: Staff truy cập - Gate không được phép (DENY)

**Mô tả:** Nhân viên STAFF001 truy cập VAULT_01 (không có trong allowed_gate_ids của staff policy).

```bash
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STAFF001",
    "gateId": "VAULT_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440028",
    "direction": "IN"
  }' | jq '.'

# Kết quả mong đợi:
{
  "title": "Gate not authorized",
  "status": 403,
  "detail": "Gate not authorized"
}
```

**Alert được tạo:**
- SECURITY_BREACH (CRITICAL): Unauthorized gate access attempt: STAFF001 -> VAULT_01

---

### Test 8: Student truy cập - Trùng correlationId (Idempotency)

**Mô tả:** Gửi cùng correlationId trong vòng 60 giây → Trả về response cache.

```bash
# Lần 1
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "LAB_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440030",
    "direction": "IN"
  }' | jq '.'

# Lần 2 (trong vòng 60 giây)
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "STU001",
    "gateId": "LAB_01",
    "correlationId": "550e8400-e29b-41d4-a716-446655440030",
    "direction": "IN"
  }' | jq '.'

# Kết quả mong đợi (lần 2):
{
  "decision": "ALLOW",
  "reasonCode": "VALID",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 4,
  "isDuplicate": true,
  "expiresAt": "2026-06-26T17:30:00Z"
}
```

---

# 📋 **5.6. B4 → B6: AI DETECTION RESULT**

**Mục đích:** Kiểm tra endpoint nhận kết quả phân tích từ AI Vision Service (B4) và đánh giá rủi ro.

---

## 🔍 **QUY TRÌNH XỬ LÝ CỦA B6**

| Bước | Mô tả | Đầu ra |
|------|-------|--------|
| **1. RECEIVE** | Nhận kết quả detection từ B4 qua REST | AIDetectionResponse |
| **2. VALIDATE** | Kiểm tra field bắt buộc (detectionId, label, confidence) | Lỗi nếu thiếu field |
| **3. CLASSIFY** | Phân loại dựa trên label và confidence | alert_triggered |
| **4. ASSESS** | Đánh giá mức độ rủi ro | risk_level |
| **5. POLICY** | Áp policy quyết định alert | should_alert, severity |
| **6. PRODUCE** | Tạo alert + gửi B7/B5 + audit | Response JSON |

---

## 📊 **TRẠNG THÁI VÀ ĐIỀU KIỆN KÍCH HOẠT**

### Person Detected - Phát hiện người

| ID | Điều kiện | Confidence | Severity | Rule ID |
|----|-----------|------------|----------|---------|
| P1 | label = "person" AND confidence > 0.7 | > 0.7 | **HIGH** | AI_DETECTION_RULE |

**🔔 TẠO ALERT - GỬI B7 & B5**

---

### Object Detected - Phát hiện vật thể

| ID | Điều kiện | Confidence | Severity | Rule ID |
|----|-----------|------------|----------|---------|
| O1 | label != "person" | Bất kỳ | **NONE** | - |

**✅ KHÔNG TẠO ALERT**

---

### Low Confidence - Độ tin cậy thấp

| ID | Điều kiện | Confidence | Severity | Rule ID |
|----|-----------|------------|----------|---------|
| L1 | confidence <= 0.7 | ≤ 0.7 | **NONE** | - |

**✅ KHÔNG TẠO ALERT**

---

### No Match - Không khớp

| ID | Điều kiện | Severity | Rule ID |
|----|-----------|----------|---------|
| N1 | matched = false | **NONE** | - |

**✅ KHÔNG TẠO ALERT**

---

## 🧪 **TEST CASES**

### Test 1: Phát hiện người với độ tin cậy cao (HIGH alert)

**Mô tả:** AI phát hiện người với confidence 0.95 → Tạo alert HIGH.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440030",
    "matched": true,
    "label": "person",
    "confidence": 0.95,
    "status": "matched",
    "modelVersion": "yolov8n",
    "processedAt": "2026-06-24T17:30:00Z"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "received"
}
```

**Alert được tạo:**
- AI_DETECTION_RULE (HIGH): Person detected with confidence 0.95

---

### Test 2: Phát hiện vật thể (không alert)

**Mô tả:** AI phát hiện car với confidence 0.88 → Không tạo alert.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440031",
    "matched": true,
    "label": "car",
    "confidence": 0.88,
    "status": "matched",
    "modelVersion": "yolov8n",
    "processedAt": "2026-06-24T17:30:00Z"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "received"
}
```

**✅ KHÔNG TẠO ALERT**

---

### Test 3: Không khớp (không alert)

**Mô tả:** AI không phát hiện đối tượng → Không tạo alert.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440032",
    "matched": false,
    "label": "unknown",
    "confidence": 0.35,
    "status": "not_matched",
    "modelVersion": "yolov8n",
    "processedAt": "2026-06-24T17:30:00Z"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "received"
}
```

**✅ KHÔNG TẠO ALERT**

---

### Test 4: Phát hiện người với độ tin cậy thấp (không alert)

**Mô tả:** AI phát hiện người nhưng confidence 0.65 (< 0.7) → Không tạo alert.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440033",
    "matched": true,
    "label": "person",
    "confidence": 0.65,
    "status": "low_confidence",
    "modelVersion": "yolov8n",
    "processedAt": "2026-06-24T17:30:00Z"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "received"
}
```

**✅ KHÔNG TẠO ALERT**

---

### Test 5: Phát hiện người lạ (HIGH alert)

**Mô tả:** AI phát hiện người lạ với confidence 0.92 → Tạo alert HIGH (unknown_person).

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440034",
    "matched": true,
    "label": "person",
    "confidence": 0.92,
    "status": "unknown_person",
    "modelVersion": "yolov8n",
    "processedAt": "2026-06-24T17:30:00Z"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "received"
}
```

**Alert được tạo:**
- AI_DETECTION_RULE (HIGH): Person detected with confidence 0.92

---

### Test 6: Phát hiện nhiều người (HIGH alert)

**Mô tả:** AI phát hiện 2 người với confidence cao → Tạo alert HIGH.

```bash
curl -s -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "detectionId": "550e8400-e29b-41d4-a716-446655440035",
    "matched": true,
    "label": "person",
    "confidence": 0.93,
    "status": "multiple_persons",
    "modelVersion": "yolov8n",
    "processedAt": "2026-06-24T17:30:00Z"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "received"
}
```

**Alert được tạo:**
- AI_DETECTION_RULE (HIGH): Person detected with confidence 0.93

---

# 📋 **5.7. B5 → B6: GET ALERTS**

**Mục đích:** Kiểm tra endpoint cung cấp danh sách cảnh báo cho Analytics Service (B5) để tổng hợp KPI và thống kê.

---

## 🔍 **QUY TRÌNH XỬ LÝ CỦA B6**

| Bước | Mô tả | Đầu ra |
|------|-------|--------|
| **1. RECEIVE** | Nhận request GET từ B5 | Request với limit, severity |
| **2. VALIDATE** | Kiểm tra tham số hợp lệ | limit (1-100), severity (LOW/MEDIUM/HIGH/CRITICAL) |
| **3. FETCH** | Lấy danh sách alerts từ memory | List alerts |
| **4. FILTER** | Lọc theo severity nếu có | Filtered list |
| **5. RESPOND** | Trả về danh sách alerts | JSON response |

---

## 📊 **CẤU TRÚC DỮ LIỆU ALERT**

```json
{
  "event_id": "alert-xxxxxxxxxxxx",
  "alert_id": "ALT-XXXXXXXX",
  "alert_type": "sensor_danger",
  "severity": "CRITICAL",
  "target": "security_team",
  "message": "CO₂ 1900ppm exceeds danger threshold (1800ppm)",
  "details": {
    "device_id": "esp32-hall-b201",
    "status": "danger",
    "alert_level": "high",
    "readings": {...},
    "location": "Hall B201"
  },
  "timestamp": "2026-06-24T17:30:00.000000"
}
```

---

## 🧪 **TEST CASES**

### Test 1: Lấy tất cả alerts

**Mô tả:** Lấy toàn bộ danh sách alerts đã được tạo từ các test trước.

```bash
curl -s -X GET "http://localhost:8000/alerts" \
  -H "Authorization: Bearer mock-token-123" | jq '.'

# Kết quả mong đợi:
[
  {
    "event_id": "alert-xxxxxxxxxxxx",
    "alert_id": "ALT-XXXXXXXX",
    "alert_type": "sensor_danger",
    "severity": "CRITICAL",
    "target": "security_team",
    "message": "CO₂ 1900ppm exceeds danger threshold (1800ppm)",
    "details": {...},
    "timestamp": "2026-06-24T17:30:00.000000"
  },
  ...
]
```

---

### Test 2: Lọc theo severity CRITICAL

**Mô tả:** Chỉ lấy các alert có severity = CRITICAL.

```bash
curl -s -X GET "http://localhost:8000/alerts?severity=CRITICAL" \
  -H "Authorization: Bearer mock-token-123" | jq '.[] | {alert_id: .alert_id, severity: .severity, message: .message}'

# Kết quả mong đợi:
{
  "alert_id": "ALT-XXXXXXXX",
  "severity": "CRITICAL",
  "message": "CO₂ 1900ppm exceeds danger threshold (1800ppm)"
}
```

---

### Test 3: Lọc theo severity HIGH

**Mô tả:** Chỉ lấy các alert có severity = HIGH.

```bash
curl -s -X GET "http://localhost:8000/alerts?severity=HIGH" \
  -H "Authorization: Bearer mock-token-123" | jq '.[] | {alert_id: .alert_id, severity: .severity, message: .message}'

# Kết quả mong đợi:
{
  "alert_id": "ALT-XXXXXXXX",
  "severity": "HIGH",
  "message": "Person detected with confidence 0.95"
}
```

---

### Test 4: Lọc theo severity MEDIUM

**Mô tả:** Chỉ lấy các alert có severity = MEDIUM.

```bash
curl -s -X GET "http://localhost:8000/alerts?severity=MEDIUM" \
  -H "Authorization: Bearer mock-token-123" | jq '.[] | {alert_id: .alert_id, severity: .severity, message: .message}'

# Kết quả mong đợi:
{
  "alert_id": "ALT-XXXXXXXX",
  "severity": "MEDIUM",
  "message": "Battery 15% below warning threshold (20.0%)"
}
```

---

### Test 5: Giới hạn số lượng alerts

**Mô tả:** Chỉ lấy 5 alert gần nhất.

```bash
curl -s -X GET "http://localhost:8000/alerts?limit=5" \
  -H "Authorization: Bearer mock-token-123" | jq 'length'

# Kết quả mong đợi:
5
```

---

### Test 6: Lấy alerts với severity không tồn tại

**Mô tả:** Lọc với severity không có trong hệ thống → Trả về danh sách rỗng.

```bash
curl -s -X GET "http://localhost:8000/alerts?severity=LOW" \
  -H "Authorization: Bearer mock-token-123" | jq '.'

# Kết quả mong đợi:
[]
```

---

### Test 7: Đếm tổng số alerts

**Mô tả:** Đếm tổng số alerts đã được tạo.

```bash
curl -s -X GET "http://localhost:8000/alerts" \
  -H "Authorization: Bearer mock-token-123" | jq 'length'

# Kết quả mong đợi:
[ số lượng alerts đã tạo ]
```

---

### Test 8: Lấy alerts với limit và severity

**Mô tả:** Kết hợp limit và severity.

```bash
curl -s -X GET "http://localhost:8000/alerts?severity=CRITICAL&limit=3" \
  -H "Authorization: Bearer mock-token-123" | jq '.[] | {alert_id: .alert_id, severity: .severity}'

# Kết quả mong đợi:
{
  "alert_id": "ALT-XXXXXXXX",
  "severity": "CRITICAL"
}
```

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

# 📋 **7. TEST CONSUMER: B6 GỌI GIẢ LẬP CÁC B KHÁC**

> **Mục đích**: Test các endpoint mà B6 gọi sang các service khác (B3, B4, B5, B7) với cơ chế fallback khi chưa kết nối thật.

---

## 🔍 **KIỂM TRA TRẠNG THÁI KẾT NỐI**

```bash
curl -s -X GET http://localhost:8000/connection-status \
  -H "Authorization: Bearer mock-token-123" | jq '.'
```

**Kết quả mong đợi:**
```json
{
  "b3": {
    "status": "fallback",
    "display": "🟡 Fallback",
    "auto_detect": false,
    "retry_interval": 60
  },
  "b4": {
    "status": "fallback",
    "display": "🟡 Fallback",
    "fallback_url": "http://b6-ai-vision:9000",
    "auto_detect": false,
    "retry_interval": 60
  },
  "b5": {
    "status": "fallback",
    "display": "🟡 Fallback",
    "auto_detect": false,
    "retry_interval": 60
  },
  "b7": {
    "status": "fallback",
    "display": "🟡 Fallback",
    "auto_detect": false,
    "retry_interval": 60
  },
  "rabbitmq": {
    "status": "disabled",
    "display": "⚪ Disabled",
    "host": "localhost"
  },
  "retry_enabled": false
}
```

---

## 7.1. B6 GỌI B3 (ACCESS GATE) - LẤY ACCESS LOGS

### 7.1.1: Lấy danh sách access logs

```bash
curl -s -X GET "http://localhost:8000/internal/access-logs?limit=5" \
  -H "Authorization: Bearer mock-token-123" | jq '.'

# Kết quả mong đợi (FALLBACK mode):
[
  {
    "logId": "fallback_log_1",
    "cardId": "CARD_1",
    "gateId": "LAB_01",
    "direction": "IN",
    "status": "GRANTED",
    "timestamp": "2026-06-24T17:30:00.000000",
    "operatorNote": "Fallback mode - B3 not connected",
    "mock": true
  },
  {
    "logId": "fallback_log_2",
    "cardId": "CARD_2",
    "gateId": "LAB_01",
    "direction": "IN",
    "status": "GRANTED",
    "timestamp": "2026-06-24T17:30:00.000000",
    "operatorNote": "Fallback mode - B3 not connected",
    "mock": true
  },
  {
    "logId": "fallback_log_3",
    "cardId": "CARD_3",
    "gateId": "LAB_01",
    "direction": "IN",
    "status": "GRANTED",
    "timestamp": "2026-06-24T17:30:00.000000",
    "operatorNote": "Fallback mode - B3 not connected",
    "mock": true
  }
]
```

### 7.1.2: Lấy trạng thái gate

```bash
curl -s -X GET "http://localhost:8000/internal/gates/LAB_01/status" \
  -H "Authorization: Bearer mock-token-123" | jq '.'

# Kết quả mong đợi (FALLBACK mode):
{
  "gateId": "LAB_01",
  "isOnline": true,
  "lastHeartbeat": "2026-06-24T17:30:00.000000",
  "currentMode": "normal",
  "mock": true,
  "message": "Fallback mode - B3 not connected"
}
```

### 7.1.3: Kiểm tra log B3

```bash
docker compose logs api | grep -E "B3|Access Gate|access-gate"
```

**Kết quả mong đợi:**
```
🚪 AccessGateClient initialized: use_real=False
🟡 [B3_FALLBACK] Using fallback access logs
```

---

## 7.2. B6 GỌI B4 (AI VISION) - PHÂN TÍCH ẢNH

### 7.2.1: Kiểm tra AI Vision Service đang chạy

```bash
curl -s http://localhost:9000/health | jq '.'

# Kết quả mong đợi:
{
  "status": "UP",
  "model_loaded": true,
  "timestamp": "2026-06-24T17:30:00.000000"
}
```

### 7.2.2: B6 gọi AI Vision qua API Gateway

```bash
CORR_ID=$(uuidgen)
curl -s -X POST http://localhost:8000/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"correlationId\": \"${CORR_ID}\",
    \"imageRef\": \"person.jpg\"
  }" | jq '.'

# Kết quả mong đợi (FALLBACK mode):
{
  "detectionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "matched": true,
  "label": "person",
  "confidence": 0.85,
  "status": "matched",
  "modelVersion": "ultimate-fallback",
  "processedAt": "2026-06-24T17:30:00.000000"
}
```

### 7.2.3: Kiểm tra log Consumer

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

## 7.3. B6 GỬI DECISION ĐẾN B5 (ANALYTICS)

### 7.3.1: Trigger Decision từ Access Check

Mỗi request `/access/check` đều tự động gửi decision đến B5.

```bash
CORR_ID=$(uuidgen)
curl -s -X POST http://localhost:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"cardId\": \"CARD_12345\",
    \"gateId\": \"LOBBY_01\",
    \"direction\": \"IN\",
    \"correlationId\": \"${CORR_ID}\"
  }" | jq '.'

# Kết quả mong đợi:
{
  "decision": "ALLOW",
  "reasonCode": "VALID",
  "decisionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "remainingQuota": 4,
  "isDuplicate": false,
  "expiresAt": "2026-06-25T17:30:00Z"
}
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

### 7.3.2: Xem danh sách Fallback Decisions

```bash
curl -s -X GET "http://localhost:8000/internal/fallback-decisions?limit=10" \
  -H "Authorization: Bearer mock-token-123" | jq '.[] | {correlationId: .correlationId, decision: .decision, reason: .reason}'

# Kết quả mong đợi:
[
  {
    "correlationId": "bd65071b-0a21-4b65-8de5-dc1e4b49c2ff",
    "decision": "ALLOW",
    "reason": "VALID"
  },
  {
    "correlationId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "decision": "DENY",
    "reason": "QUOTA_EXCEEDED"
  }
]
```

### 7.3.3: Gửi Decision thủ công (Test Endpoint)

```bash
curl -s -X POST http://localhost:8000/internal/send-test-decision \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "decision": "ALLOW",
    "reason": "TEST_MANUAL"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "sent",
  "correlationId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "decision": "ALLOW",
  "mode": "fallback",
  "message": "Decision sent successfully"
}
```

### 7.3.4: Kiểm tra log B5

```bash
docker compose logs api | grep -E "ANALYTICS|B5"
```

**Kết quả mong đợi:**
```
📊 AnalyticsClient initialized: use_real=False
📊 [ANALYTICS_FALLBACK] Decision stored locally: xxxxx... - ALLOW
📊 [ANALYTICS_STORAGE] Fallback storage size: 5
```

---

## 7.4. B6 GỬI ALERT ĐẾN B7 (NOTIFICATION)

### 7.4.1: Trigger Alert từ Sensor

**Gửi sensor event với nhiệt độ cao (trigger alert):**

```bash
CORR_ID=$(uuidgen)
curl -s -X POST http://localhost:8000/internal/evaluate-sensor \
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
  }" | jq '.'

# Kết quả mong đợi:
{
  "message": "Event received and processed",
  "device_id": "esp32-lab-a101",
  "status": "danger",
  "alert_level": "high",
  "reason": "Temperature 42.5°C exceeds danger threshold (40.0°C)",
  "alerts_count": 1,
  "correlation_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
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

### 7.4.2: Trigger Alert từ AI Detection

```bash
DETECTION_ID=$(uuidgen)
curl -s -X POST http://localhost:8000/policies/evaluate-detection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d "{
    \"detectionId\": \"${DETECTION_ID}\",
    \"matched\": true,
    \"label\": \"person\",
    \"confidence\": 0.95,
    \"status\": \"matched\",
    \"modelVersion\": \"yolov8n\",
    \"processedAt\": \"2026-06-24T17:30:00Z\"
  }" | jq '.'

# Kết quả mong đợi:
{
  "status": "received"
}
```

### 7.4.3: Gửi Alert thủ công (Test Endpoint)

```bash
curl -s -X POST http://localhost:8000/internal/send-test-alert \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "severity": "CRITICAL",
    "message": "Test alert from B6 dashboard"
  }' | jq '.'

# Kết quả mong đợi:
{
  "status": "sent",
  "alertId": "ALT-XXXXXXXX",
  "severity": "CRITICAL",
  "mode": "fallback",
  "message": "Alert sent successfully"
}
```

### 7.4.4: Kiểm tra log B7

```bash
docker compose logs api | grep -E "Notification|B7"
```

**Kết quả mong đợi:**
```
📧 NotificationClient initialized:
📧 [B7_FALLBACK] Alert stored locally: xxxxx... - CRITICAL
```

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