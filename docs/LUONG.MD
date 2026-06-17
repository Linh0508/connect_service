# 📘 HƯỚNG DẪN LUỒNG DỮ LIỆU B6 - TỔNG QUAN KIẾN TRÚC

**Phiên bản:** 1.3.0  
**Ngày cập nhật:** 2026-06-17  
**Dành cho:** Smart Campus Operations Platform - Plug-a-thon

---

## 1. TỔNG QUAN VỀ B6 CORE BUSINESS SERVICE

B6 Core Business Service đóng vai trò là **trung tâm xử lý quyết định** trong hệ thống Smart Campus Operations Platform. Service này nhận dữ liệu từ các thành phần khác trong hệ thống (B1, B3, B4, B5), xử lý và đánh giá theo các quy tắc nghiệp vụ, sau đó gửi kết quả đến các service liên quan (B5, B7) để phân tích và thông báo.

Về bản chất, B6 hoạt động như một **Decision Engine** - cỗ máy ra quyết định, với khả năng tự động chuyển đổi giữa chế độ REAL và FALLBACK khi các service khác không khả dụng.

---

## 2. CÁC SERVICE KẾT NỐI VỚI B6

### 2.1. Các Service gọi đến B6 (Provider)

| Service | Vai trò | Endpoint | Mục đích |
|---------|---------|----------|----------|
| **B1 - IoT** | Gửi dữ liệu cảm biến | `/internal/evaluate-sensor` | Cung cấp dữ liệu môi trường từ các thiết bị IoT |
| **B3 - Access Gate** | Kiểm tra quyền truy cập | `/access/check` | Xác thực thẻ và quyền ra vào cổng |
| **B4 - AI Vision** | Kết quả phân tích ảnh | `/policies/evaluate-detection` | Gửi kết quả nhận dạng đối tượng |
| **B5 - Analytics** | Lấy danh sách cảnh báo | `/alerts` | Truy vấn dữ liệu cảnh báo để phân tích |

### 2.2. B6 gọi đến các Service khác (Consumer)

| Service | Vai trò | Endpoint | Mục đích |
|---------|---------|----------|----------|
| **B3 - Access Gate** | Lấy logs truy cập | `/internal/access-logs` | Thu thập lịch sử truy cập |
| **B4 - AI Vision** | Phân tích ảnh | `/evaluate-detection` | Gửi ảnh để AI nhận dạng |
| **B5 - Analytics** | Gửi decision | `analytics_client.send_decision()` | Ghi nhận quyết định để phân tích |
| **B7 - Notification** | Gửi alert | `notification_client.send_alert()` | Thông báo sự cố và cảnh báo |

---

## 3. LUỒNG DỮ LIỆU CHI TIẾT

### 3.1. B1 (IoT) → B6: Xử lý dữ liệu cảm biến

Khi B1 gửi dữ liệu cảm biến lên B6, quá trình xử lý diễn ra theo các bước sau:

**Bước 1: Nhận dữ liệu**
B6 nhận request POST đến endpoint `/internal/evaluate-sensor` với dữ liệu JSON chứa thông tin thiết bị và các chỉ số môi trường như nhiệt độ, độ ẩm, CO2, khói, pin và trạng thái chuyển động.

**Bước 2: Kiểm tra thiết bị**
Hệ thống sẽ kiểm tra `device_id` trong cơ sở dữ liệu device_registry. Nếu thiết bị không tồn tại, dữ liệu sẽ bị gắn nhãn `invalid_device` và tạo cảnh báo ngay lập tức.

**Bước 3: Đánh giá dữ liệu**
Dữ liệu được đưa qua bộ đánh giá Sensor Evaluator để phân loại trạng thái. Hệ thống so sánh từng chỉ số với các ngưỡng đã được định nghĩa:
- **Bình thường**: Tất cả chỉ số trong ngưỡng an toàn
- **Cảnh báo**: Một hoặc nhiều chỉ số vượt ngưỡng cảnh báo (ví dụ nhiệt độ > 35°C, CO2 > 1200 ppm, khói > 0.5 ppm, pin < 20%)
- **Nguy hiểm**: Chỉ số vượt ngưỡng nguy hiểm (nhiệt độ >= 40°C, CO2 >= 1800 ppm, khói >= 1.0 ppm)

**Bước 4: Kiểm tra chuyển động bất thường**
Nếu phát hiện chuyển động trong khung giờ bất thường (22:00 - 06:00) hoặc tại các khu vực nhạy cảm như phòng thí nghiệm sau giờ làm việc, hệ thống sẽ tạo thêm cảnh báo.

**Bước 5: Tạo và gửi cảnh báo**
Nếu phát hiện trạng thái cảnh báo hoặc nguy hiểm, B6 sẽ tạo một AlertEvent với các thông tin chi tiết bao gồm rule_id, message, device_id, readings và timestamp.

**Bước 6: Lưu trữ và phân phối**
Alert được lưu vào cơ sở dữ liệu và danh sách bộ nhớ. Đồng thời, B6 sẽ gửi alert đến B7 để thông báo và gửi decision đến B5 để phân tích.

---

### 3.2. B3 (Access Gate) → B6: Kiểm tra quyền truy cập

Khi B3 gửi yêu cầu kiểm tra quyền truy cập, B6 thực hiện:

**Bước 1: Xác thực Gate**
Hệ thống kiểm tra xem gate_id có nằm trong danh sách gate được phép của token không. Nếu không, B6 sẽ gửi ngay một cảnh báo bảo mật về truy cập trái phép đến B7 và B5, sau đó trả về lỗi 403.

**Bước 2: Đánh giá Policy**
B6 áp dụng policy engine để kiểm tra thẻ có quyền truy cập vào gate tại thời điểm hiện tại hay không. Policy bao gồm các quy tắc về khung giờ cho phép và danh sách gate được phép.

**Bước 3: Kiểm tra Quota**
Hệ thống kiểm tra hạn ngạch sử dụng hàng ngày của thẻ. Nếu đã sử dụng hết quota, quyết định sẽ là DENY.

**Bước 4: Ra quyết định**
Dựa trên kết quả đánh giá policy và quota, B6 đưa ra quyết định ALLOW hoặc DENY cùng với mã lý do tương ứng.

**Bước 5: Gửi đến B5**
Mỗi quyết định đều được gửi đến B5 để phân tích thống kê, bất kể là ALLOW hay DENY.

**Bước 6: Gửi đến B7 khi có vấn đề**
Nếu quyết định là DENY hoặc có cảnh báo về quota sắp hết, B6 sẽ tạo alert và gửi đến B7 để thông báo.

---

### 3.3. B4 (AI Vision) → B6: Xử lý kết quả nhận dạng

Khi B4 gửi kết quả phân tích ảnh:

**Bước 1: Nhận kết quả**
B6 nhận kết quả từ B4 qua endpoint `/policies/evaluate-detection` với các thông tin: detection_id, matched, label, confidence.

**Bước 2: Đánh giá kết quả**
Nếu kết quả khớp với label "person" với độ tin cậy trên 70%, B6 sẽ tạo alert về việc phát hiện người.

**Bước 3: Phân phối**
Alert được gửi đến B7 để thông báo và decision được gửi đến B5 để phân tích.

---

### 3.4. B5 (Analytics) → B6: Lấy danh sách cảnh báo

B5 có thể gọi đến B6 để lấy danh sách cảnh báo thông qua endpoint `/alerts`. B6 sẽ trả về danh sách alert đã được lưu trong bộ nhớ, có thể lọc theo severity nếu cần. Đây là luồng Provider thuần túy, không phát sinh thêm xử lý.

---

## 4. LUỒNG B6 GỌI ĐẾN CÁC SERVICE KHÁC

### 4.1. B6 → B4 (AI Vision): Phân tích ảnh

Khi B6 cần phân tích ảnh, nó gọi B4 thông qua endpoint `/evaluate-detection`:

**Bước 1: Kiểm tra chế độ**
Hệ thống kiểm tra trạng thái kết nối với B4 thông qua Connection Manager. Nếu B4 đang online, B6 sẽ sử dụng REAL mode.

**Bước 2: Gửi request trong REAL mode**
B6 gửi request đến B4 với image reference. Nếu B4 phản hồi thành công, kết quả được trả về cho người gọi.

**Bước 3: Chuyển sang FALLBACK mode**
Nếu B4 không khả dụng hoặc phản hồi lỗi, B6 tự động chuyển sang FALLBACK mode, sử dụng AI container nội bộ của B6 (b6-ai-vision:9000) để xử lý.

**Bước 4: Ultimate Fallback**
Nếu cả B4 và AI container nội bộ đều không hoạt động, B6 sẽ trả về mock response với kết quả giả định dựa trên từ khóa trong image reference.

---

### 4.2. B6 → B3 (Access Gate): Lấy access logs

Khi B6 cần lấy lịch sử truy cập:

**Bước 1: Kiểm tra chế độ**
Connection Manager kiểm tra trạng thái của B3.

**Bước 2: REAL mode**
Nếu B3 online, B6 gọi API của B3 để lấy logs thực tế.

**Bước 3: FALLBACK mode**
Nếu B3 không khả dụng, B6 tự động trả về dữ liệu mock (giả lập) với các log mẫu, đảm bảo tính liên tục của dịch vụ.

---

### 4.3. B6 → B5 (Analytics): Gửi decision

Mỗi khi B6 ra quyết định (từ access check hoặc từ alert), nó sẽ gửi decision đến B5:

**Bước 1: Tạo payload**
B6 tạo payload với các thông tin: correlation_id, decision, reason, latency_ms, quota_before, quota_after, rules_triggered.

**Bước 2: REAL mode**
Nếu B5 online, B6 gửi POST request đến B5 và nhận phản hồi thành công.

**Bước 3: FALLBACK mode**
Nếu B5 không khả dụng, B6 lưu decision vào fallback_storage trong bộ nhớ. Điều này đảm bảo không mất dữ liệu khi B5 offline. Khi B5 hoạt động trở lại, có thể đồng bộ dữ liệu từ fallback_storage.

---

### 4.4. B6 → B7 (Notification): Gửi alert

Khi có sự cố hoặc cảnh báo, B6 gửi alert đến B7:

**Bước 1: Tạo AlertEvent**
B6 tạo đối tượng AlertEvent với các thông tin: event_id, correlation_id, trace_id, severity, user_id, gate_id, alert_details, timestamp.

**Bước 2: REAL mode**
Nếu B7 online, B6 gửi POST request đến B7 với webhook path. B7 sẽ xử lý và gửi thông báo đến người dùng cuối.

**Bước 3: FALLBACK mode**
Nếu B7 không khả dụng, B6 chỉ log lại thông tin alert và vẫn đảm bảo response thành công để không làm gián đoạn luồng chính.

---

## 5. CƠ CHẾ REAL VÀ FALLBACK

### 5.1. Nguyên lý hoạt động

B6 được trang bị cơ chế tự động phát hiện và chuyển đổi giữa REAL và FALLBACK mode. Điều này đảm bảo hệ thống luôn hoạt động ổn định ngay cả khi các service phụ thuộc không khả dụng.

**REAL mode**: B6 gọi trực tiếp đến service thật, nhận và xử lý phản hồi thực tế.

**FALLBACK mode**: B6 tự xử lý nội bộ, trả về dữ liệu giả lập hoặc lưu trữ tạm thời, đảm bảo không làm gián đoạn luồng chính.

### 5.2. Cách xác định chế độ

Connection Manager thực hiện các bước sau để xác định chế độ:

1. **Kiểm tra auto_detect flag**: Nếu auto_detect được tắt, mặc định sử dụng FALLBACK.

2. **Phân tích URL**: Nếu URL chứa các pattern nội bộ (localhost, b3-access-gate, b6-ai-vision, b5-analytics, b7-notification), tự động chuyển sang FALLBACK.

3. **Health check**: Gọi endpoint `/health` của service đích, nếu response 200 và status = "UP", chuyển sang REAL.

4. **Phân tích response**: Đối với B4, kiểm tra thêm các trường đặc trưng như `model_loaded` để xác định đây là AI service thật hay container nội bộ.

### 5.3. Fallback Storage cho B5

Khi B5 offline, B6 lưu các decision vào fallback_storage, một danh sách trong bộ nhớ. Mỗi entry chứa đầy đủ thông tin decision cùng timestamp và mode = "fallback". Dung lượng được giới hạn ở 1000 bản ghi để tránh tràn bộ nhớ.

---

## 6. CÁC TRIGGER TẠO ALERT

### 6.1. Từ Sensor (B1 → B6)

| Điều kiện | Severity | Rule ID |
|-----------|----------|---------|
| Nhiệt độ >= 40°C | CRITICAL | TEMP_DANGER |
| Nhiệt độ >= 35°C | HIGH | TEMP_WARNING |
| Độ ẩm >= 85% | MEDIUM | HUMIDITY_WARNING |
| CO2 >= 1800 ppm | CRITICAL | CO2_DANGER |
| CO2 >= 1200 ppm | HIGH | CO2_WARNING |
| Khói >= 1.0 ppm | CRITICAL | SMOKE_DANGER |
| Khói >= 0.5 ppm | HIGH | SMOKE_WARNING |
| Pin < 20% | MEDIUM | BATTERY_WARNING |
| Motion (22:00-06:00) | HIGH | MOTION_ABNORMAL_TIME |
| Motion trong Lab (18:00-07:00) | HIGH | MOTION_AFTER_HOURS_LAB |
| temp = null & humidity = null | HIGH | SENSOR_ERROR |
| Device không tồn tại | CRITICAL | INVALID_DEVICE |

### 6.2. Từ Access Check (B3 → B6)

| Điều kiện | Severity | Rule ID |
|-----------|----------|---------|
| Decision = DENY | CRITICAL | ACCESS_CHECK_RULE |
| Quota <= 1 | WARNING | ACCESS_CHECK_RULE |
| Gate không được phép | CRITICAL | SECURITY_BREACH |

### 6.3. Từ AI Detection (B4 → B6)

| Điều kiện | Severity | Rule ID |
|-----------|----------|---------|
| matched = true, label = person, confidence > 0.7 | HIGH | AI_DETECTION_RULE |

---

## 7. ĐỊNH DẠNG DỮ LIỆU JSON ĐẦU VÀO

### 7.1. Từ B1 (IoT Sensor)

```json
{
  "source_service": "team-iot",
  "timestamp": "2026-06-17T14:30:25+07:00",
  "device_id": "esp32-lab-a101",
  "location": "Lab A101",
  "temperature_c": 25.5,
  "humidity_percent": 60.2,
  "light_lux": 410,
  "co2_ppm": 450,
  "smoke_ppm": 0.01,
  "battery_percent": 77,
  "motion_detected": false,
  "correlationId": "uuid-xxx-xxx"
}
```

### 7.2. Từ B3 (Access Gate)

```json
{
  "cardId": "CARD_12345",
  "gateId": "LOBBY_01",
  "direction": "IN",
  "correlationId": "uuid-xxx-xxx",
  "timestamp": "2026-06-17T14:30:25+07:00"
}
```

### 7.3. Từ B4 (AI Vision)

```json
{
  "detectionId": "uuid-xxx-xxx",
  "matched": true,
  "label": "person",
  "confidence": 0.95,
  "status": "matched",
  "modelVersion": "yolov8n",
  "processedAt": "2026-06-17T14:30:25+07:00"
}
```

---

## 8. KẾT LUẬN

B6 Core Business Service là trung tâm xử lý quyết định của hệ thống, với các đặc điểm nổi bật:

1. **Đa luồng dữ liệu**: Nhận dữ liệu từ nhiều nguồn khác nhau (IoT, Access Gate, AI Vision) và phân phối đến các service liên quan (Analytics, Notification).

2. **Tự động phục hồi**: Cơ chế REAL/FALLBACK đảm bảo service luôn hoạt động ngay cả khi các service phụ thuộc không khả dụng.

3. **Xử lý thông minh**: Áp dụng các quy tắc nghiệp vụ để đánh giá dữ liệu, phân loại trạng thái và tạo cảnh báo phù hợp.

4. **Lưu trữ tạm thời**: Fallback storage cho B5 đảm bảo không mất dữ liệu khi service phân tích offline.

5. **Luồng alert đa dạng**: Tạo alert từ nhiều nguồn khác nhau với các mức độ severity khác nhau, đảm bảo hệ thống phản ứng kịp thời với mọi tình huống.