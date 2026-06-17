# API Contract Negotiation Log – Nhóm B6 (Hoàn chỉnh)

**Facilitator:** FIT4110 Teaching Team  
**Ngày hiệu lực:** 2026-06-14  
**Phiên bản:** 1.3.0  

---

## Cặp 10: Access Gate → Core Business (REST Sync)

**Provider:** Core Business (B6)  
**Consumer:** Access Gate  
**Negotiation Period:** 2026-05-20 to 2026-05-26  

### Issue #1: Response Latency SLA and Failure Handling

**Bối cảnh:** Provider đề xuất 200ms, Consumer yêu cầu <100ms P99 vì người dùng không thể chờ đợi tại cổng.

**Quyết định cuối cùng:**  
✓ **SLA: <100ms P99** đo đầu cuối  
✓ **Fail‑closed:** từ chối truy cập nếu B6 không phản hồi > 5 phút  
✓ Provider cam kết cache in‑memory (TTL 5 phút)  
✓ Consumer thực hiện local fallback cache  

**Sign-off:** [x] Consumer [x] Provider  

### Issue #2: Idempotency and Duplicate Request Handling

**Quyết định:** Dùng `correlationId` (UUID), cửa sổ 60 giây, trả về quyết định cũ cho duplicate, HTTP 409 nếu correlationId cũ hơn 60s.

**Sign-off:** [x] Consumer [x] Provider  

### Issue #3: Policy Update Propagation and Cache Invalidation

**Quyết định:** Cache TTL = 5 phút, endpoint `POST /cache/invalidate/{policyId}` đảm bảo hiệu lực < 5 giây, Consumer có local cache TTL 30 giây.

**Sign-off:** [x] Consumer [x] Provider  

### Issue #4: Cardholder Quota Management

**Quyết định:** Provider quản lý quota, reset theo ngày dương lịch 00:00 UTC, trả `remainingQuota`, DENY khi hết quota.

**Sign-off:** [x] Consumer [x] Provider  

### Issue #5: Authorization Scopes and Admin API Access

**Quyết định:**  
- Scopes: `access:read`, `admin:policies`, `admin:audit`  
- JWT có claim `gateIds` để giới hạn phạm vi  
- Token TTL: 24h (Consumer), 12h (Admin)  

**Sign-off:** [x] Consumer [x] Provider  

### Issue #6: API Versioning Strategy

**Quyết định:** Version trên URL (`/v1/`), hỗ trợ song song 2 version trong 6 tháng, cảnh báo trước 30 ngày khi sunset.

**Sign-off:** [x] Consumer [x] Provider  

---

## Cặp 02: B6 → AI Vision (REST Sync)

**Provider:** AI Vision  
**Consumer:** B6  

### Issue #1: Response Time & Error Handling

**Quyết định:**  
- Timeout 5 giây (B6 client)  
- AI Vision P99 ≤ 200ms  
- Lỗi 5xx hoặc timeout → B6 bỏ qua cảnh báo, retry tối đa 2 lần với backoff  

**Sign-off:** [x] B6 [x] AI Vision  

---

## Cặp 03: B6 → Access Gate (REST Sync)

**Provider:** Access Gate  
**Consumer:** B6  

### Issue #1: API Design & Rate Limiting

**Quyết định:**  
- Access Gate cung cấp `GET /v1/gates/{gateId}/status` và `GET /v1/access-logs?from=&to=&limit=`  
- Rate limit: 10 req/s  
- Timeout 3 giây, nếu lỗi B6 bỏ qua  

**Sign-off:** [x] B6 [x] Access Gate  

---

## Cặp 05: IoT Ingestion → B6 (Queue Async)

**Provider:** IoT Ingestion  
**Consumer:** B6  
**Topic:** `iot.sensors.raw`

### Issue #1: Message Schema & Error Handling

**Quyết định:**  
- Schema bắt buộc: `correlationId`, `eventType`, `deviceId`, `readings` (nhiệt độ, chuyển động, khói)  
- B6 kiểm tra ngưỡng, phát sinh alert  
- Auto‑commit offset sau xử lý thành công, lỗi → DLQ  
- IoT Ingestion đảm bảo at‑least‑once delivery  

**Sign-off:** [x] B6 [x] IoT Ingestion  

---

## Cặp 04: B6 → Notification (Queue Async)

**Provider:** Notification Service (B7)  
**Consumer:** B6  
**Topic:** `notification.alerts`

**Negotiation Period:** 2026-05-20  
**Phiên bản contract:** v1.0  

### Issue #1: Severity Field for Routing

**Raised by:** Provider  
**Bối cảnh:** Notification cần biết mức độ nghiêm trọng để quyết định kênh gửi (CRITICAL → Telegram, LOW → email)  
**Quyết định cuối cùng:**  
✓ Consumer phải thêm field `severity` vào payload `alert.created`  
✓ Enum values: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`  

**Sign-off:** [x] B6 [x] Notification  

### Issue #2: End-to-End Tracing

**Raised by:** Consumer  
**Bối cảnh:** Consumer lo ngại không thể truy vết alert nếu thiếu thông tin trace  
**Quyết định cuối cùng:**  
✓ Provider cam kết giữ nguyên `correlationId` và `traceId` trong mọi event  
✓ Không làm thay đổi hoặc mất các field này  

**Sign-off:** [x] B6 [x] Notification  

### Issue #3: Channel Routing Responsibility

**Raised by:** Provider  
**Bối cảnh:** Provider muốn tự quyết định kênh gửi dựa trên severity và user preference  
**Quyết định cuối cùng:**  
✓ Consumer **không gửi** field `channels`  
✓ Consumer gửi `userId` hoặc `userGroupId`  
✓ Provider tra cứu kênh ưu tiên của user  

**Sign-off:** [x] B6 [x] Notification  

### Issue #4: Idempotency for Duplicate Events

**Raised by:** Provider  
**Bối cảnh:** Queue at-least-once delivery có thể gây trùng lặp event  
**Quyết định cuối cùng:**  
✓ Mỗi event phải có `eventId` (UUID) do Consumer sinh ra  
✓ Provider cache `eventId` đã xử lý trong **24 giờ**  
✓ Không gửi trùng thông báo cho cùng `eventId`  

**Sign-off:** [x] B6 [x] Notification  

### Issue #5: Alert Resolution Information

**Raised by:** Provider  
**Bối cảnh:** Provider cần biết thông tin giải quyết alert để gửi thông báo và ghi log  
**Quyết định cuối cùng:**  
✓ Event `alert.resolved` phải có:  
  - `resolvedBy` (string) - tên người hoặc system xử lý  
  - `resolutionNote` (string, optional) - lý do giải quyết  

**Sign-off:** [x] B6 [x] Notification  

### Issue #6: Retry Mechanism

**Raised by:** Consumer  
**Bối cảnh:** Cần thống nhất cơ chế retry khi Provider không xử lý được  
**Quyết định cuối cùng:**  
✓ Queue retry tối đa **3 lần** với exponential backoff (1s, 2s, 4s)  
✓ Sau 3 lần thất bại → dead-letter queue (DLQ)  

**Sign-off:** [x] B6 [x] Notification  

### Tổng kết Cặp 04

| Vấn đề | Quyết định |
|--------|-------------|
| Severity enum | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| Channels | **Không gửi**, Provider tự quyết định |
| Tracing | Giữ nguyên `correlationId` + `traceId` |
| Idempotency | `eventId` (UUID), cache 24h |
| Alert resolved | `resolvedBy` + `resolutionNote` |
| Retry | 3 lần exponential (1s,2s,4s) → DLQ |

---

## Cặp 08: B6 → Analytics (Queue Async)

**Provider:** Analytics Service  
**Consumer:** B6  
**Topic:** `analytics.decisions`

### Issue #1: Data Completeness & Backpressure

**Quyết định:**  
- Schema: `correlationId`, `decision`, `reason`, `latencyMs`, `quotaBefore/After`, `rulesTriggered`  
- B6 gửi 100% quyết định và cảnh báo  
- Nếu Kafka down → local buffer (tối đa 10.000 bản ghi) và retry  

**Sign-off:** [x] B6 [x] Analytics  

---

## Các thỏa thuận bổ sung (Cross‑Cutting)

### Issue #7: Monitoring SLA and Health Check Strategy

**Bối cảnh:** Access Gate cần biết khi nào B6 chậm hoặc down để chuyển sang chế độ offline.

**Quyết định cuối cùng:**  
✓ Endpoint `GET /health` trả về trạng thái chi tiết:  
  - `status`: `UP`, `DEGRADED`, `DOWN`  
  - `components`: database, cache, rule_engine  
✓ SLA phản hồi `/health` < 500ms  
✓ B6 tự động đánh dấu `DEGRADED` nếu latency của Rule Engine vượt 150ms trong 1 phút  

**Rationale:** Phát hiện sớm suy giảm hiệu năng trước khi ảnh hưởng đến cổng.  

**Sign-off:** [x] B6 [x] Access Gate  

### Issue #8: Analytics Integration (Cặp 08 – bổ sung)

**Bối cảnh:** Analytics cần dữ liệu để thống kê lượt ra vào và cảnh báo.

**Quyết định cuối cùng:**  
✓ B6 đẩy **100%** audit log sang `analytics.decisions`  
✓ Payload bao gồm: `correlationId`, `decision`, `latencyMs`, `quotaRemaining`, `rulesTriggered`  
✓ Nếu queue down → local buffer tối đa 10.000 bản ghi, retry liên tục  

**Rationale:** Đảm bảo toàn vẹn dữ liệu báo cáo cuối ngày.  

**Sign-off:** [x] B6 [x] Analytics  

### Issue #9: Audit Logging and Data Retention

**Bối cảnh:** Quy định an ninh yêu cầu lưu trữ lịch sử ra vào để đối soát.

**Quyết định cuối cùng:**  
✓ Mỗi request quẹt thẻ sinh `decisionId` duy nhất  
✓ Audit log lưu online 30 ngày (phục vụ `GET /decisions/{id}`)  
✓ Sau 30 ngày → nén và chuyển sang cold storage (2 năm)  
✓ `cardId` phải được che mờ một phần (masking) để bảo vệ PII  

**Rationale:** Tuân thủ quy định bảo mật dữ liệu và tối ưu DB.  

**Sign-off:** [x] B6 [x] Access Gate [x] Security Team  

---

## Tổng kết các quyết định chính

| Cặp / Vấn đề | Quyết định |
|--------------|-------------|
| Cặp 10 – Latency, fail‑closed | <100ms P99, deny khi mất kết nối >5 phút |
| Cặp 10 – Idempotency | correlationId, 60s, 409 Conflict |
| Cặp 10 – Cache invalidation | TTL 5 phút + manual endpoint |
| Cặp 10 – Quota | Provider quản lý, reset UTC 00:00 |
| Cặp 10 – Auth | JWT scopes + gateIds claim |
| Cặp 10 – Versioning | URL version, 6 tháng song song |
| Cặp 02 – AI Vision | Timeout 5s, P99≤200ms, retry 2 lần |
| Cặp 03 – Access Gate (outbound) | Rate 10 req/s, timeout 3s |
| Cặp 05 – IoT schema | JSON có correlationId, deviceId, readings |
| Cặp 04 – Severity enum | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| Cặp 04 – Channels | **Không gửi**, Provider tự quyết định |
| Cặp 04 – Tracing | `correlationId` + `traceId` |
| Cặp 04 – Idempotency | `eventId` (UUID), cache 24h |
| Cặp 04 – Alert resolved | `resolvedBy` + `resolutionNote` |
| Cặp 04 – Retry | 3 lần exponential (1s,2s,4s) → DLQ |
| Cặp 08 – Analytics | Gửi 100%, local buffer nếu Kafka down |
| Issue #7 – Health check | `/health` chi tiết, SLA <500ms |
| Issue #8 – Analytics payload | Thêm quota, rulesTriggered |
| Issue #9 – Audit retention | Online 30 ngày, offline 2 năm, masking |

---

## Chốt hợp đồng v1.3.0

**Provider (B6) sign-off:** _________________  
**Consumer (Access Gate) sign-off:** _________________  
**AI Vision sign-off:** _________________  
**Notification (B7) sign-off:** _________________  
**IoT Ingestion sign-off:** _________________  
**Analytics sign-off:** _________________  
**Security Team sign-off:** _________________  

**Witness (GV/TA):** _________________  
**Date:** 2026-06-14