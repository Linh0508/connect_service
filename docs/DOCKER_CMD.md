```markdown
# 📚 TỔNG HỢP LỆNH DOCKER CHO B6 CORE BUSINESS SERVICE

**Phiên bản:** 1.3.0  
**Ngày cập nhật:** 2026-06-16  
**Mục đích:** Tổng hợp các lệnh Docker đã sử dụng trong quá trình phát triển B6

---

## 📋 MỤC LỤC

1. [Lệnh kiểm tra Docker](#1-lệnh-kiểm-tra-docker)
2. [Lệnh quản lý Docker Compose](#2-lệnh-quản-lý-docker-compose)
3. [Lệnh quản lý Container](#3-lệnh-quản-lý-container)
4. [Lệnh kiểm tra Logs](#4-lệnh-kiểm-tra-logs)
5. [Lệnh kiểm tra Network & Port](#5-lệnh-kiểm-tra-network--port)
6. [Lệnh quản lý Database](#6-lệnh-quản-lý-database)
7. [Lệnh quản lý Images & Volumes](#7-lệnh-quản-lý-images--volumes)
8. [Lệnh Debug & Kiểm tra lỗi](#8-lệnh-debug--kiểm-tra-lỗi)
9. [Lệnh mở Firewall & Port Forward](#9-lệnh-mở-firewall--port-forward)

---

## 1. LỆNH KIỂM TRA DOCKER

### Kiểm tra phiên bản Docker

```bash
docker --version
```
**Kết quả mong đợi:**
```
Docker version 24.0.7, build afdd53b
```

### Kiểm tra Docker Compose

```bash
docker compose version
```
**Kết quả mong đợi:**
```
Docker Compose version v2.23.0
```

### Kiểm tra Docker đang chạy

```bash
docker info
```
**Kết quả mong đợi:** Hiển thị thông tin hệ thống Docker

---

## 2. LỆNH QUẢN LÝ DOCKER COMPOSE

### Build images

```bash
docker compose build
```
**Kết quả mong đợi:** Build thành công tất cả images

### Build không dùng cache

```bash
docker compose build --no-cache
```
**Kết quả mong đợi:** Build lại từ đầu, không dùng cache

### Chạy stack (background)

```bash
docker compose up -d
```
**Kết quả mong đợi:**
```
✔ Container b6-postgres     Healthy
✔ Container b6-core-api     Started
```

### Chạy stack kèm logs

```bash
docker compose up -d && docker compose logs -f
```

### Dừng stack

```bash
docker compose down
```
**Kết quả mong đợi:** Tất cả containers dừng và xóa

### Dừng và xóa volumes

```bash
docker compose down -v
```
**Kết quả mong đợi:** Dừng containers và xóa luôn volumes

### Xem trạng thái containers

```bash
docker compose ps
```
**Kết quả mong đợi:**
```
NAME           IMAGE                STATUS
b6-postgres    postgres:15-alpine   healthy
b6-core-api    btl-api              healthy
```

### Restart một service

```bash
docker compose restart api
```
**Kết quả mong đợi:** Container API được khởi động lại

### Xem cấu hình compose

```bash
docker compose config
```
**Kết quả mong đợi:** Hiển thị file docker-compose.yml đã được parse

---

## 3. LỆNH QUẢN LÝ CONTAINER

### Xem tất cả container đang chạy

```bash
docker ps
```
**Kết quả mong đợi:**
```
CONTAINER ID   IMAGE                    STATUS
f66502d1e45c   postgres:15-alpine       healthy (Up 10 minutes)
ebe4edc6aa89   btl-api                  healthy (Up 12 minutes)
```

### Xem tất cả container (kể cả đã dừng)

```bash
docker ps -a
```

### Xem container đang restart

```bash
docker ps -a | grep Restarting
```

### Dừng một container

```bash
docker stop b6-core-api
```
**Kết quả mong đợi:** `b6-core-api`

### Khởi động một container

```bash
docker start b6-core-api
```

### Xóa một container

```bash
docker rm b6-core-api
```

### Vào bên trong container

```bash
docker exec -it b6-core-api /bin/bash
```
**Kết quả mong đợi:** Mở shell bên trong container

### Chạy lệnh trong container

```bash
docker exec b6-core-api env | grep DATABASE_URL
```
**Kết quả mong đợi:** Hiển thị biến môi trường DATABASE_URL

### Copy file vào container

```bash
docker cp src/core_service/main.py b6-core-api:/app/src/core_service/main.py
```

### Copy file từ container ra

```bash
docker cp b6-core-api:/app/src/core_service/main.py ./main_backup.py
```

---

## 4. LỆNH KIỂM TRA LOGS

### Xem logs realtime

```bash
docker compose logs -f api
```

### Xem 50 dòng log cuối

```bash
docker compose logs api --tail 50
```

### Xem logs kèm timestamp

```bash
docker compose logs api -t
```

### Xem logs container cụ thể

```bash
docker logs b6-core-api
```

### Lọc logs theo từ khóa

```bash
docker compose logs api | grep -E "Database|Error|Alert"
```

### Lọc logs lỗi

```bash
docker compose logs api | grep -i error
```

### Lưu logs ra file

```bash
docker compose logs api > logs.txt
```

---

## 5. LỆNH KIỂM TRA NETWORK & PORT

### Xem danh sách networks

```bash
docker network ls
```
**Kết quả mong đợi:** Có network `b6-team-network` và `class-network`

### Xem chi tiết network

```bash
docker network inspect b6-team-network
```

### Kiểm tra port đang lắng nghe (Linux/WSL)

```bash
sudo netstat -tlnp | grep 8000
```
**Kết quả mong đợi:**
```
tcp  0  0.0.0.0:8000  0.0.0.0:*  LISTEN
```

### Kiểm tra port (Windows)

```powershell
netstat -an | findstr "8000"
```
**Kết quả mong đợi:**
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
```

### Kiểm tra port forward (Windows)

```powershell
netsh interface portproxy show all
```
**Kết quả mong đợi:**
```
Listen on ipv4:             Connect to ipv4:
Address         Port        Address         Port
0.0.0.0         8000        172.27.125.120  8000
```

### Kiểm tra IP của container

```bash
docker inspect b6-core-api | grep IPAddress
```

---

## 6. LỆNH QUẢN LÝ DATABASE

### Kiểm tra database đang chạy

```bash
docker exec b6-postgres pg_isready -U b6_user
```
**Kết quả mong đợi:**
```
/var/run/postgresql:5432 - accepting connections
```

### Kết nối vào database

```bash
docker exec -it b6-postgres psql -U b6_user -d b6_core_db
```
**Kết quả mong đợi:** Mở giao diện psql

### Xem danh sách bảng

```bash
docker exec b6-postgres psql -U b6_user -d b6_core_db -c "\dt"
```
**Kết quả mong đợi:**
```
 public | audit_logs        | table | b6_user
 public | quota_records     | table | b6_user
 public | policies          | table | b6_user
 public | alerts            | table | b6_user
 public | idempotency_cache | table | b6_user
```

### Xem dữ liệu audit_logs

```bash
docker exec b6-postgres psql -U b6_user -d b6_core_db -c "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 5;"
```

### Xem dữ liệu policies

```bash
docker exec b6-postgres psql -U b6_user -d b6_core_db -c "SELECT policy_id, name, quota_per_day FROM policies;"
```
**Kết quả mong đợi:**
```
  policy_id        |                   name                    | quota_per_day
-------------------+-------------------------------------------+---------------
 POL_STUDENT_001   | Student Access Policy - Lab Hours         |             5
 POL_STAFF_001     | Staff Access Policy - Extended Hours      |            10
 POL_ADMIN_001     | Admin Access Policy - 24/7                |            20
```

### Đếm số lượng bản ghi

```bash
docker exec b6-postgres psql -U b6_user -d b6_core_db -c "SELECT COUNT(*) FROM audit_logs;"
```

---

## 7. LỆNH QUẢN LÝ IMAGES & VOLUMES

### Xem danh sách images

```bash
docker images
```
**Kết quả mong đợi:**
```
REPOSITORY          TAG       IMAGE ID       SIZE
btl-api             latest    abc123def456   500MB
postgres            15-alpine def456ghi789   200MB
```

### Xóa image

```bash
docker rmi btl-api
```

### Xóa image force

```bash
docker rmi -f btl-api
```

### Xem danh sách volumes

```bash
docker volume ls
```

### Xóa volume

```bash
docker volume rm btl_postgres_data
```

### Xóa tất cả volume không dùng

```bash
docker volume prune -f
```

### Xóa tất cả container, network, image không dùng

```bash
docker system prune -f
```

### Xóa tất cả (kể cả volume)

```bash
docker system prune -a --volumes -f
```

---

## 8. LỆNH DEBUG & KIỂM TRA LỖI

### Kiểm tra container bị restart

```bash
docker inspect b6-core-api | grep RestartCount
```

### Kiểm tra chi tiết container

```bash
docker inspect b6-core-api
```

### Kiểm tra resource usage

```bash
docker stats --no-stream
```
**Kết quả mong đợi:**
```
CONTAINER      CPU %     MEM USAGE / LIMIT
b6-core-api    15.30%    250MB / 7.8GB
b6-postgres    5.10%     80MB / 7.8GB
```

### Test kết nối database từ container API

```bash
docker exec b6-core-api python -c "
import asyncpg
import asyncio
async def test():
    conn = await asyncpg.connect('postgresql://b6_user:b6_password@postgres:5432/b6_core_db')
    print('✅ Database OK')
asyncio.run(test())
"
```

### Kiểm tra API từ bên trong container

```bash
docker exec b6-core-api curl http://localhost:8000/health
```

### Kiểm tra kết nối đến B3 từ container

```bash
docker exec b6-core-api curl -s http://b3-access-gate:8001/health
```

### Kiểm tra biến môi trường trong container

```bash
docker exec b6-core-api env | sort
```

---

## 9. LỆNH MỞ FIREWALL & PORT FORWARD (Windows)

### Mở firewall cho port 8000

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

### Kiểm tra firewall rule

```powershell
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*8000*"}
```

### Xóa firewall rule

```powershell
Remove-NetFirewallRule -DisplayName "B6 API Port 8000"
```

### Tạo port forward từ Windows vào WSL

```powershell
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=172.27.125.120
```

### Xóa port forward

```powershell
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```

### Xem tất cả port forward

```powershell
netsh interface portproxy show all
```

---

## 📋 BẢNG TÓM TẮT LỆNH NHANH

| Mục đích | Lệnh |
|----------|------|
| Build & chạy | `docker compose up -d --build` |
| Dừng | `docker compose down` |
| Xem trạng thái | `docker compose ps` |
| Xem logs | `docker compose logs -f api` |
| Restart API | `docker compose restart api` |
| Vào container | `docker exec -it b6-core-api /bin/bash` |
| Kiểm tra health | `curl http://localhost:8000/health` |
| Xem database | `docker exec b6-postgres psql -U b6_user -d b6_core_db -c "\dt"` |
| Dọn dẹp | `docker system prune -f` |

---

**© 2026 Nhóm B6 - Smart Campus Operations Platform** 🚀
```