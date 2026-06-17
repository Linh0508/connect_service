```markdown
# Hướng dẫn chạy B6 Core Business Service với Docker Compose

**Phiên bản:** 1.3.0  
**Ngày cập nhật:** 2026-06-15  
**Dành cho:** Smart Campus Operations Platform - Plug-a-thon

---

## 📋 Mục lục

1. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
2. [Cài đặt](#cài-đặt)
3. [Cấu hình](#cấu-hình)
4. [Chạy hệ thống](#chạy-hệ-thống)
5. [Kiểm tra hoạt động](#kiểm-tra-hoạt-động)
6. [Chạy kiểm thử](#chạy-kiểm-thử)
7. [Xem logs](#xem-logs)
8. [Dừng hệ thống](#dừng-hệ-thống)
9. [Xóa toàn bộ](#xóa-toàn-bộ)
10. [Troubleshooting](#troubleshooting)
11. [API Endpoints](#api-endpoints)
12. [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)

---

## 1. Yêu cầu hệ thống

| Thành phần | Phiên bản tối thiểu |
|------------|---------------------|
| Docker Engine | 20.10.0+ |
| Docker Compose | 2.0.0+ |
| RAM | 4GB (khuyến nghị 8GB) |
| Disk space | 2GB |
| Ports trống | 8000, 5432, 9000 |

### Kiểm tra phiên bản

```bash
docker --version
docker compose version
```

---

## 2. Cài đặt

### Bước 1: Clone repository

```bash
git clone <your-repository-url>
cd BTL
```

### Bước 2: Tạo file .env từ template

```bash
cp .env.example .env
```

### Bước 3: (Optional) Chỉnh sửa file .env nếu cần

```bash
nano .env
# Hoặc
vim .env
```

---

## 3. Cấu hình

### File `.env` mặc định

```bash
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false
LOG_LEVEL=info

# Database Configuration
POSTGRES_USER=b6_user
POSTGRES_PASSWORD=b6_password
POSTGRES_DB=b6_core_db
POSTGRES_PORT=5432

# AI Vision Service
AI_PORT=9000

# API Configuration
API_TITLE="Core Business API"
API_VERSION="1.3.0"
```

### Các cổng mặc định

| Service | Cổng nội bộ | Cổng ngoài |
|---------|-------------|-------------|
| API | 8000 | 8000 |
| AI Vision | 9000 | 9000 |
| PostgreSQL | 5432 | 5432 |

---

## 4. Chạy hệ thống

### Khởi động tất cả services

```bash
docker compose up -d --build
```

**Giải thích:**
- `up` - Khởi động services
- `-d` - Chạy background (detached mode)
- `--build` - Build image trước khi chạy

### Kiểm tra trạng thái

```bash
docker compose ps
```

**Kết quả mong đợi:**

```bash
NAME           IMAGE                STATUS
b6-postgres    postgres:15-alpine   healthy
b6-ai-vision   btl-ai-vision        healthy
b6-core-api    btl-api              healthy
```

---

## 5. Kiểm tra hoạt động

### Kiểm tra Health Check API

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
    "rule_engine": {"status": "UP", "avg_latency_ms": 35},
    "ai_vision": {"status": "UP", "url": "http://ai-vision:9000"}
  },
  "timestamp": "2026-06-15T10:30:00Z"
}
```

### Kiểm tra AI Vision Service

```bash
curl http://localhost:9000/health
```

**Kết quả mong đợi:**

```json
{
  "status": "UP",
  "model_loaded": true,
  "timestamp": "2026-06-15T10:30:00Z"
}
```

### Kiểm tra Database

```bash
docker exec b6-postgres pg_isready -U b6_user
```

**Kết quả mong đợi:**

```
/var/run/postgresql:5432 - accepting connections
```

### Kiểm tra kết nối API → AI Vision

```bash
curl -X POST http://localhost:8000/evaluate-detection \
  -H "Content-Type: application/json" \
  -d '{
    "correlationId": "123e4567-e89b-12d3-a456-426614174000",
    "imageRef": "person.jpg",
    "detectionId": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

---

## 6. Chạy kiểm thử

### Chạy Newman test

```bash
bash scripts/run-newman.sh
```

### Chạy test với Docker (tự động)

```bash
docker compose --profile test up newman-tests
```

### Kết quả mong đợi

```bash
========================================
     B6 API - Newman Test Runner       
========================================
Base URL: http://localhost:8000

✓ GET /health (35.56ms)
✓ POST /access/check - ALLOW (12.33ms)
✓ POST /access/check - Idempotency (4.68ms)
✓ GET /policies/access/POL_STUDENT_001 (22.46ms)
...

========================================
✓ All tests passed!
Report saved to: reports/newman-report-local.xml
========================================
```

### Xem báo cáo test

```bash
# JUnit format
cat reports/newman-report-local.xml

# HTML report (mở trong browser)
open reports/newman-report-local.html
```

---

## 7. Xem logs

### Xem logs của tất cả services

```bash
docker compose logs -f
```

### Xem logs của một service cụ thể

```bash
# API logs
docker compose logs api -f

# AI Vision logs
docker compose logs ai-vision -f

# Database logs
docker compose logs postgres -f
```

### Lưu logs ra file

```bash
docker compose logs > logs.txt
```

---

## 8. Dừng hệ thống

### Dừng tất cả services

```bash
docker compose down
```

### Dừng và xóa volumes (mất dữ liệu)

```bash
docker compose down -v
```

---

## 9. Xóa toàn bộ

### Xóa containers, networks, images

```bash
# Dừng và xóa
docker compose down -v --rmi all

# Xóa cả images đã build
docker rmi btl-api btl-ai-vision 2>/dev/null

# Dọn dẹp system
docker system prune -f
```

---

## 10. Troubleshooting

### Lỗi: Port already in use

**Nguyên nhân:** Cổng 8000, 5432, hoặc 9000 đã được sử dụng.

**Cách fix:**

```bash
# Tìm process đang dùng cổng
lsof -i :8000
lsof -i :5432
lsof -i :9000

# Kill process hoặc đổi port trong .env
```

### Lỗi: Container không khởi động được

**Cách fix:**

```bash
# Xem logs chi tiết
docker compose logs api
docker compose logs ai-vision
docker compose logs postgres

# Restart từng service
docker compose restart api
```

### Lỗi: Database connection failed

**Cách fix:**

```bash
# Kiểm tra database đã sẵn sàng
docker exec b6-postgres pg_isready -U b6_user

# Reset database
docker compose down -v
docker compose up -d --build
```

### Lỗi: AI Vision not responding

**Cách fix:**

```bash
# Kiểm tra AI service
curl http://localhost:9000/health

# Restart AI service
docker compose restart ai-vision
```

### Lỗi: Newman test fails

**Cách fix:**

```bash
# Đảm bảo API đang chạy
curl http://localhost:8000/health

# Chạy test với verbose mode
newman run postman/collections/core-business.postman_collection.json \
  --environment postman/environments/environment_local.json \
  --verbose
```

---

## 11. API Endpoints

### Endpoints do B6 cung cấp (Provider)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/access/check` | Kiểm tra quyền ra vào |
| GET | `/policies/access/{policyId}` | Lấy chi tiết policy |
| GET | `/decisions/{decisionId}` | Tra cứu audit log |
| POST | `/cache/invalidate/{policyId}` | Xóa cache policy |
| POST | `/internal/evaluate-sensor` | IoT sensor event |
| POST | `/evaluate-detection` | AI detection |
| GET | `/internal/access-logs` | Access logs |
| GET | `/internal/gates/{gateId}/status` | Gate status |
| GET | `/health` | Health check |

### Endpoints B6 gọi sang service khác (Consumer)

| Method | URL | Service đích |
|--------|-----|--------------|
| POST | `http://ai-vision:9000/predict` | AI Vision |
| GET | `http://access-gate:8001/...` | Access Gate |
| POST | `http://notification:8002/...` | Notification |
| POST | `http://analytics:8003/...` | Analytics |

---

## 12. Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                      Docker Compose Stack                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   postgres   │  │  ai-vision   │  │     api      │          │
│  │   :5432      │  │   :9000      │  │   :8000      │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           │                                     │
│                   team-internal network                         │
│                    (b6-team-network)                            │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    External Access
                    http://localhost:8000
```

### Network nội bộ

Các service giao tiếp với nhau qua tên container:

| Từ | Đến | URL nội bộ |
|----|-----|------------|
| api | postgres | `postgres:5432` |
| api | ai-vision | `ai-vision:9000` |

---

## 📞 Hỗ trợ

Nếu gặp vấn đề, hãy liên hệ:

- **Email:** support-b6@campus.local
- **GitHub Issues:** [Create issue](<repository-url>/issues)

---

## 📝 Phiên bản

| Phiên bản | Ngày | Thay đổi |
|-----------|------|----------|
| 1.0.0 | 2026-06-10 | Initial release |
| 1.1.0 | 2026-06-12 | Thêm AI Vision service |
| 1.2.0 | 2026-06-14 | Thêm database, healthcheck |
| 1.3.0 | 2026-06-15 | Production ready, đầy đủ endpoints |

---

**© 2026 Nhóm B6 - Smart Campus Operations Platform**
```

---

## 🚀 Cách tạo file

```bash
# Copy nội dung trên vào file
cat > RUN_COMPOSE.md << 'EOF'
[PASTE NỘI DUNG TRÊN VÀO ĐÂY]
EOF

# Hoặc dùng lệnh này để tạo trực tiếp (nếu bạn có file mẫu)
# echo "..." > RUN_COMPOSE.md
```

Sau khi tạo xong, kiểm tra:

```bash
ls -la RUN_COMPOSE.md
cat RUN_COMPOSE.md | head -20
```