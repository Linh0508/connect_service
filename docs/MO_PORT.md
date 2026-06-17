```markdown
# Hướng dẫn mở port 8000 trên Windows để các máy khác gọi B6

## 1. Tìm IP của máy Windows

**Lệnh:**
```cmd
ipconfig
```

**Kết quả mong đợi:**
```
Wireless LAN adapter Wi-Fi:
   IPv4 Address. . . . . . . . . . . : 192.168.0.102
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.0.1
```
👉 **IP của bạn:** `192.168.0.102` (ghi lại để dùng ở bước 6)

---

## 2. Mở firewall cho port 8000

**Lệnh (PowerShell - Administrator):**
```powershell
New-NetFirewallRule -DisplayName "B6 API Port 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

**Kết quả mong đợi:**
```
Name                          : {70437cb7-d15f-44a9-bb9c-ef7efc921f66}
DisplayName                   : B6 API Port 8000
Enabled                       : True
Direction                     : Inbound
Action                        : Allow
```

✅ **Firewall đã mở thành công**

---

## 3. Kiểm tra firewall đã tạo

**Lệnh:**
```powershell
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*8000*"}
```

**Kết quả mong đợi:**
```
Name                          : {70437cb7-d15f-44a9-bb9c-ef7efc921f66}
DisplayName                   : B6 API Port 8000
Enabled                       : True
Action                        : Allow
```

✅ **Rule tồn tại trong firewall**

---

## 4. Tìm IP của WSL (nếu chạy Docker trong WSL)

**Lệnh (trong WSL):**
```bash
ip addr show eth0 | grep inet
```

**Kết quả mong đợi:**
```
inet 172.27.125.120/20 brd 172.27.127.255 scope global eth0
```
👉 **IP WSL:** `172.27.125.120`

---

## 5. Kiểm tra port đang lắng nghe trước khi forward

**Lệnh:**
```powershell
netstat -an | findstr "8000"
```

**Kết quả mong đợi:**
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
TCP    [::]:8000              [::]:0                 LISTENING
```

✅ **B6 API đang lắng nghe trên port 8000**

---

## 6. Tạo port forward từ Windows vào WSL

**Lệnh (PowerShell - Administrator):**
```powershell
# Xóa rule cũ (nếu có)
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0

# Tạo rule mới (thay IP_WSL bằng IP của bạn)
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=172.27.125.120

# Kiểm tra rule đã tạo
netsh interface portproxy show all
```

**Kết quả mong đợi:**
```
Listen on ipv4:             Connect to ipv4:

Address         Port        Address         Port
--------------- ----------  --------------- ----------
0.0.0.0         8000        172.27.125.120  8000
```

✅ **Port forward đã được cấu hình thành công**

---

## 7. Kiểm tra lại port sau khi forward

**Lệnh:**
```powershell
netstat -an | findstr "8000"
```

**Kết quả mong đợi:**
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
TCP    [::]:8000              [::]:0                 LISTENING
```
(có thể xuất hiện 2 dòng `0.0.0.0:8000` - bình thường)

✅ **Port forward đang hoạt động**

---

## 8. Test từ chính máy Windows

**Lệnh:**
```powershell
# Test localhost
curl http://localhost:8000/health

# Test bằng IP Windows
curl http://192.168.0.102:8000/health
```

**Kết quả mong đợi:**
```json
{"status":"UP","components":{"database":"UP","cache":"UP","rule_engine":{"status":"UP","avg_latency_ms":0},"ai_vision":{"status":"UP","url":"http://b4-ai-vision:9000"}}}
```

✅ **API hoạt động bình thường qua IP Windows**

---

## 9. Cung cấp cho các B khác

**Base URL để các B khác gọi:**
```
http://192.168.0.102:8000
```

---

## 10. Test từ máy khác trong cùng mạng

**Lệnh (trên máy khác - cùng WiFi 192.168.0.x):**
```bash
curl http://192.168.0.102:8000/health
```

**Kết quả mong đợi:**
```json
{"status":"UP","components":{"database":"UP","cache":"UP","rule_engine":{"status":"UP","avg_latency_ms":0},"ai_vision":{"status":"UP","url":"http://b4-ai-vision:9000"}}}
```

✅ **Máy khác đã gọi được B6 thành công!**

---

## 11. Test access check từ máy khác (giả lập B3)

**Lệnh (trên máy khác):**
```bash
curl -X POST http://192.168.0.102:8000/access/check \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-token-123" \
  -d '{
    "cardId": "CARD_REMOTE",
    "gateId": "LOBBY_01",
    "correlationId": "remote-test-001",
    "direction": "IN"
  }'
```

**Kết quả mong đợi:**
```json
{
  "decision": "ALLOW",
  "decisionId": "550e8400-e29b-41d4-a716-446655440000",
  "remainingQuota": 4,
  "isDuplicate": false,
  "expiresAt": "2026-06-17T15:04:27.327351"
}
```

✅ **Access check hoạt động bình thường từ máy khác!**

---

## 📋 Yêu cầu để thành công

| Yêu cầu | Trạng thái |
|---------|------------|
| Các máy cùng mạng LAN (cùng WiFi) | ⬜ Cần đảm bảo |
| Firewall đã mở port 8000 | ✅ |
| Port forward đã tạo | ✅ |
| B6 API đang chạy (docker compose up -d) | ✅ |
| Có token `mock-token-123` trong header | ✅ |

---

## ⚠️ Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|-----|-------------|----------|
| `Connection refused` | B6 chưa chạy hoặc port sai | `docker compose up -d` |
| `Connection timed out` | Firewall chưa mở hoặc sai IP | Kiểm lại IP, chạy lại bước 2 |
| `curl: (7) Failed to connect` | Không cùng mạng hoặc IP sai | Ping thử `ping 192.168.0.102` |
| `401 Unauthorized` | Thiếu token | Thêm `-H "Authorization: Bearer mock-token-123"` |

---

## 🎯 Kết luận

Sau khi hoàn thành các bước trên:

- ✅ Các máy khác trong cùng mạng LAN có thể gọi B6 qua IP `192.168.0.102:8000`
- ✅ B6 hoạt động bình thường như một dịch vụ kết nối trong hệ thống Smart Campus
- ✅ Sẵn sàng cho B3, B4, B5, B7 gọi đến

```