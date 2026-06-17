# Hướng dẫn sinh viên chuẩn bị Buổi 6 — Thực hành tích hợp dịch vụ

**Học phần:** FIT4110 — Dịch vụ kết nối và Công nghệ nền tảng
**Case study:** Smart Campus Operations Platform
**Nội dung buổi 6:** Các nhóm chạy service của mình và kiểm tra khả năng tích hợp với nhóm khác trên cùng một mạng nội bộ.

> Các nhóm đọc kỹ tài liệu này trước khi đến lớp. Buổi 6 là buổi thực hành tích hợp, thời gian sửa lỗi trên lớp rất ít. Nhóm nào chuẩn bị tốt ở nhà thì đến lớp chỉ cần bật hotspot, lấy IP, cập nhật `.env` và chạy kiểm tra.

---

## 1. Mục tiêu Buổi 6

Buổi 6 không tập trung vào slide trình bày. Trọng tâm là kiểm tra xem service của từng nhóm có thật sự chạy được và **tích hợp được với nhóm khác theo contract đã thống nhất từ trước** hay không.

Một nhóm được xem là chuẩn bị tốt khi chứng minh được các điểm sau:

- Service của nhóm chạy ổn định trên một máy demo bằng Docker Compose.
- Endpoint `/health` trả về kết quả thành công.
- Nhóm tích hợp đúng contract đã chốt với (các) nhóm đối tác — bất kể contract là REST, MQTT, hay kết hợp cả hai.
- Có minh chứng: log, screenshot, request/response mẫu hoặc payload MQTT mẫu.
- Khi nhóm đối tác lỗi hoặc timeout, service của nhóm mình không treo vô hạn.

Nói ngắn gọn: **Buổi 6 kiểm tra khả năng bắt tay thật giữa các service theo đúng contract liên nhóm.**

Contract cụ thể (REST endpoint, MQTT topic, payload schema, tần suất) là **do từng cặp nhóm tự thống nhất** trước Buổi 6. Tài liệu này chỉ hướng dẫn phần hạ tầng để các nhóm có thể bắt tay được trên cùng mạng.

---

## 2. Ba loại mạng cần phân biệt

Trong Buổi 6 sẽ có ba loại mạng làm việc song song. Sinh viên cần phân biệt rõ để không nhầm lẫn khi cấu hình.

### 2.1. Mạng Docker nội bộ trong một máy

Trên máy demo của từng nhóm, các container trong cùng một `docker-compose.yml` gọi nhau bằng **tên service**.

Ví dụ trong stack của nhóm IoT:

```text
api gọi db bằng db:5432
api gọi redis bằng redis:6379
worker gọi rabbitmq bằng rabbitmq:5672
```

Cách gọi này chỉ có tác dụng **trong cùng một Docker host**, tức là trong cùng một laptop demo.

### 2.2. Mạng LAN qua hotspot

Khi nhóm A muốn gọi service của nhóm B, hai nhóm đang ở hai máy khác nhau. Lúc này **không dùng tên service Docker** để gọi sang máy khác. Phải gọi qua IP của máy đối tác trong cùng hotspot:

```bash
curl http://172.20.10.5:8000/health
```

### 2.3. Mạng Internet qua HiveMQ (nếu contract dùng MQTT)

Nếu contract liên nhóm có dùng HiveMQ làm broker, các nhóm publish/subscribe topic qua **Internet ra HiveMQ cloud**, không qua LAN hotspot. Hotspot vẫn cần Internet để các máy đi ra HiveMQ.

### 2.4. Tổng hợp

| Trường hợp | Cách gọi | Ví dụ |
|---|---|---|
| Container trong cùng máy | Tên service Docker | `http://api:8000` |
| Máy nhóm A → máy nhóm B (REST) | IP máy đối tác | `http://172.20.10.5:8000` |
| Nhóm A ↔ nhóm B qua MQTT broker | Topic + broker URL | `mqtts://....hivemq.cloud:8883/smart-campus/events/...` |

Lưu ý: Docker network như `team-internal` hoặc `class-net` chỉ hoạt động trong phạm vi một Docker host. Khi các nhóm chạy trên nhiều laptop, Docker service name **không dùng được** để gọi chéo.

---

## 3. Mô hình mạng dùng trong Buổi 6

Mỗi Product dùng **một iPhone phát hotspot riêng**. Các nhóm trong cùng Product kết nối vào cùng một hotspot.

```text
Product A:  iPhone-A → 7 máy demo cùng kết nối
Product B:  iPhone-B → 7 máy demo cùng kết nối
```

Hai Product không cần gọi nhau nên dùng hai hotspot riêng là đúng.

### 3.1. Setup iPhone làm hotspot

**Bước 1**: Bật Cellular Data (Mobile Data). Một số iPhone yêu cầu phải bật Cellular Data thì Personal Hotspot mới hoạt động (kể cả khi các máy chỉ gọi nhau qua LAN, không cần Internet).

**Bước 2**: Vào `Settings → Personal Hotspot → Allow Others to Join` (bật ON).

**Bước 3**: Quan trọng — bật toggle **`Maximize Compatibility`** (Tối đa hóa khả năng tương thích).

```text
Khi BẬT toggle này:
- iPhone phát Wi-Fi ở băng tần 2.4GHz.
- Tương thích tốt hơn với máy Windows, laptop cũ.
- Tốc độ chậm hơn nhưng đủ cho demo.

Khi TẮT toggle này:
- iPhone phát 5GHz, một số laptop Windows không thấy hotspot
  hoặc kết nối được nhưng không bắt được nhau.
```

Với Buổi 6, **bắt buộc bật `Maximize Compatibility`**.

**Bước 4**: Đặt mật khẩu hotspot ở cùng menu (`Wi-Fi Password`). Mật khẩu tối thiểu 8 ký tự.

**Bước 5**: Cắm sạc iPhone liên tục. Hotspot iPhone tiêu pin rất nhanh, không cắm sạc sẽ sập giữa buổi học.

### 3.2. Giới hạn số thiết bị của iPhone hotspot

iPhone hotspot có giới hạn số thiết bị kết nối đồng thời:

```text
iPhone đời cũ (trước iPhone 12):  tối đa 5 thiết bị
iPhone 12 trở lên:                tối đa 5 thiết bị
```

Mỗi Product cần ~7 máy demo (7 nhóm). Vậy iPhone hotspot **không đủ** nếu chạy 1 iPhone cho cả Product.

Giải pháp:

```text
A. Dùng 2 iPhone, mỗi iPhone gánh ~4 máy (chia subnet riêng) — phức tạp,
   không khuyến khích vì 2 mạng khác nhau sẽ không gọi được nhau.

B. Mỗi Product giảm số máy demo: chỉ chạy 1 máy/nhóm × 7 nhóm.
   Nếu vẫn quá 5 thiết bị, gộp 2 nhóm cùng máy (chia port khác nhau).

C. Dùng router mini hoặc TP-Link M7 thay cho iPhone — khuyến khích
   nếu nhóm có sẵn thiết bị.
```

Trước Buổi 6, mỗi Product cần test trước số thiết bị tối đa hotspot chấp nhận được. Nếu không đủ, chọn giải pháp C.

### 3.3. Dải IP của iPhone hotspot

iPhone hotspot luôn cấp IP trong dải:

```text
172.20.10.0/28
Cụ thể: 172.20.10.1 (iPhone) đến 172.20.10.14 (thiết bị)
```

Khác với hotspot Android (thường 192.168.43.x). Khi sinh viên thấy IP máy mình ở dải `172.20.10.x` nghĩa là đang kết nối đúng iPhone hotspot.

---

## 4. Mỗi nhóm cử một máy demo đại diện

Một nhóm có thể có nhiều laptop, nhưng khi demo **chỉ chạy stack trên một máy duy nhất**.

Lý do: các container của nhóm cần nằm trên cùng một Docker host để gọi nhau bằng Docker service name. Nếu tách `api` ở máy này, `db` ở máy khác thì Compose network không còn đúng.

### Tiêu chí chọn máy demo

| Tiêu chí | Yêu cầu gợi ý | Lý do |
|---|---|---|
| RAM | Tối thiểu 8GB, ưu tiên 16GB | Chạy nhiều container cùng lúc |
| Ổ trống | Tối thiểu 30GB | Chứa image, volume, log |
| Docker | Đã cài và đã test trước | Không cài mới trên lớp |
| Wi-Fi adapter | Bắt được 2.4GHz | iPhone hotspot ở băng tần này |
| Pin/sạc | Có sạc đi kèm | Tránh sập máy giữa buổi |
| Repo | Đã clone và chạy thử | Giảm lỗi phát sinh trên lớp |

Nhóm xử lý ảnh hoặc service nặng (Camera, AI Vision) nên ưu tiên máy cấu hình tốt hơn.

---

## 5. Việc phải làm ở nhà trước Buổi 6

Người giữ máy demo cần chạy thử toàn bộ quy trình trước khi đến lớp:

```bash
git clone <repo-nhom>
cd <repo-nhom>
cp .env.example .env
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

Yêu cầu:

- Các container cần thiết phải chạy được.
- Endpoint `/health` trả về 200 hoặc JSON báo trạng thái thành công.
- Đã test contract với nhóm đối tác qua localhost hoặc qua HiveMQ (nếu dùng MQTT).
- Có ảnh chụp màn hình và log lưu vào thư mục `reports/`.

Nếu ở nhà chưa chạy được thì đến lớp gần như không kịp sửa.

---

## 6. Ba điều bắt buộc để nhóm khác gọi được service của mình (REST)

Áp dụng cho các nhóm có contract REST với nhóm khác.

### 6.1. Publish port ra host

Trong `docker-compose.yml`, service nào cần cho nhóm khác gọi thì phải map port ra host.

```yaml
services:
  api:
    ports:
      - "8000:8000"
```

Nếu thiếu phần `ports`, service chỉ chạy bên trong Docker, máy khác sẽ không gọi được.

### 6.2. Service phải bind `0.0.0.0`

Service phải lắng nghe trên mọi network interface, không chỉ trên `127.0.0.1`.

FastAPI/Uvicorn:

```python
uvicorn.run(app, host="0.0.0.0", port=8000)
```

Express/Fastify:

```javascript
app.listen({ port: 8000, host: "0.0.0.0" })
```

Nếu bind `127.0.0.1`, máy khác trong cùng hotspot sẽ không gọi được.

### 6.3. Mở firewall cho port demo

Nếu máy khác gọi bị timeout hoặc connection refused, cần kiểm tra firewall:

- Windows: mở Inbound Rule cho TCP port `8000`.
- macOS: cho phép ứng dụng nhận kết nối, hoặc tạm tắt firewall trong thời gian demo.
- Linux dùng `ufw`: `sudo ufw allow 8000/tcp`.

---

## 7. Đối với contract dùng MQTT

Nếu contract liên nhóm là MQTT (publish/subscribe qua HiveMQ), các điều ở mục 6 **không cần** vì nhóm không cần expose port. Thay vào đó:

- Nhóm phải chứng minh đang publish đúng topic theo schema đã chốt với đối tác.
- Nhóm đối tác chứng minh subscribe được topic và nhận được message đúng schema.
- Cả hai nhóm cùng kiểm tra bằng MQTT Explorer hoặc `mosquitto_sub` để verify message lưu thông.

Lệnh kiểm tra nhanh bằng `mosquitto_sub`:

```bash
mosquitto_sub -h <broker-host> -p 8883 \
  -u <username> -P <password> \
  --capath /etc/ssl/certs \
  -t "smart-campus/events/<topic-cua-nhom-doi-tac>" -v
```

---

## 8. Lấy IP máy demo và cập nhật `.env`

### 8.1. Lấy IP máy đang kết nối hotspot

Windows:

```bash
ipconfig
```

Tìm adapter Wi-Fi đang kết nối hotspot, lấy dòng `IPv4 Address`.

macOS:

```bash
ipconfig getifaddr en0
```

Linux:

```bash
hostname -I | awk '{print $1}'
```

Khi kết nối iPhone hotspot, IP của máy sẽ ở dải `172.20.10.x` (thường từ `172.20.10.2` đến `172.20.10.14`). iPhone giữ IP `172.20.10.1`.

### 8.2. Công bố IP cho các nhóm trong cùng Product

Sau khi lấy IP, mỗi nhóm ghi IP của mình vào bảng chung.

| Nhóm | Service | IP máy demo | Port REST (nếu có) |
|---|---|---|---|
| team-iot | IoT Ingestion | `26.236.133.24` | 8000 |
| team-camera | Camera Stream | `172.20.10.__` | 8000 |
| team-gate | Access Gate | `26.141.173.100` | 8000 |
| team-vision | AI Vision | `172.20.10.__` | 8000 |
| team-analytics | Analytics | `26.100.91.226` | 8000 |
| team-core | Core Business | `26.155.229.84` | 8000 |
| team-notify | Notification | `26.64.54.49` | 8000 |

Làm một bảng riêng cho từng Product.

### 8.3. Cập nhật `.env` khi gọi nhóm khác

Không hard-code IP trong source code. Đưa URL nhóm đối tác vào `.env`:

```bash
# .env
CORE_SERVICE_URL=http://172.20.10.5:8000
VISION_SERVICE_URL=http://172.20.10.7:8000
```

Trong code, đọc từ biến môi trường:

```python
import os
CORE_URL = os.getenv("CORE_SERVICE_URL")
```

Không viết cứng IP:

```python
# Sai
CORE_URL = "http://172.20.10.5:8000"
```

IP có thể thay đổi mỗi lần bật lại hotspot. Đầu Buổi 6 cần lấy IP lại và cập nhật `.env`.

---

## 9. Quy ước endpoint chung

Bất kể contract nghiệp vụ là gì, **mọi nhóm bắt buộc expose endpoint `/health`** trên port chính của service:

```text
GET /health → 200 OK
```

Endpoint này dùng để verify service đang sống. Đây là điểm chung duy nhất tài liệu này quy định. Các endpoint còn lại (REST cụ thể) và các topic MQTT đều do từng cặp nhóm tự thống nhất theo contract.

Mỗi nhóm nên expose API chính ra port `8000` (trừ khi có lý do riêng). Nếu phải dùng port khác, ghi rõ trong bảng IP chung ở mục 8.2.

---

## 10. Phiếu hẹn tích hợp trước Buổi 6

Mỗi cặp nhóm có integration điền một phiếu. Có thể dùng cho REST hoặc MQTT — chỉ điền phần phù hợp.

```text
PHIẾU HẸN TÍCH HỢP — BUỔI 6

Nhóm gọi (consumer):    _______________________________
Nhóm được gọi (provider): _____________________________

Kiểu giao tiếp:  [ ] REST sync   [ ] MQTT pub/sub   [ ] Cả hai

────────────────────────────────────────────
NẾU REST:
────────────────────────────────────────────
URL provider (ở nhà):       http://localhost:_____
URL provider (Buổi 6):      http://172.20.10.___:_____

Method:  ________
Path:    ___________________________________

Request mẫu:
{
  ____________________________________________
}

Response mong đợi:
{
  ____________________________________________
}

────────────────────────────────────────────
NẾU MQTT:
────────────────────────────────────────────
Broker:  _____________________________________
Topic provider publish:  _____________________
Topic consumer subscribe: ____________________

Payload mẫu:
{
  ____________________________________________
}

Tần suất publish:  __________________________

────────────────────────────────────────────
XỬ LÝ LỖI
────────────────────────────────────────────
Nếu provider lỗi/timeout, consumer xử lý:
________________________________________________

Đã test ở nhà:                       [ ] Rồi  [ ] Chưa
Đã test qua hotspot iPhone:          [ ] Rồi  [ ] Chưa
```

---

## 11. Test kết nối giữa hai nhóm tại lớp

### 11.1. Test REST

Từ máy nhóm A, gọi sang máy nhóm B:

```bash
curl http://172.20.10.5:8000/health
```

Nếu trả 200, kết nối mạng cơ bản đã ổn. Sau đó test endpoint tích hợp theo contract.

| Lỗi | Nguyên nhân thường gặp | Cách kiểm tra |
|---|---|---|
| Connection refused | Service chưa chạy, chưa publish port, bind sai | `docker compose ps`, `ports`, `0.0.0.0` |
| Timeout | Sai IP, khác hotspot, firewall chặn | Kiểm tra IP, hotspot, firewall |
| 404 | Gọi sai path | Kiểm tra lại endpoint trong contract |
| 500 | Service lỗi bên trong | `docker compose logs <service>` |
| Không phân giải hostname | Dùng nhầm tên service Docker để gọi máy khác | Đổi sang IP hotspot |

### 11.2. Test MQTT

Cả hai nhóm cùng mở MQTT Explorer (hoặc `mosquitto_sub`) trỏ vào HiveMQ, subscribe topic provider publish, và verify thấy message đúng schema khi provider gửi.

| Lỗi | Nguyên nhân | Cách kiểm tra |
|---|---|---|
| Không nhận được message | Sai topic, sai broker, sai credential | Verify topic name, credential trong `.env` |
| Subscribe được nhưng payload sai schema | Provider publish chưa đúng contract | So sánh payload với schema đã chốt |
| Disconnect liên tục | TLS cert lỗi, mất Internet | Kiểm tra cert, kết nối hotspot |

---

## 12. Xử lý khi nhóm đối tác lỗi

Trong demo, service nhóm khác có thể chưa chạy, sai endpoint hoặc timeout. Nhóm consumer không được để request treo vô hạn.

Cần chuẩn bị:

- Timeout hợp lý: 3–5 giây cho REST.
- Thông báo lỗi rõ ràng trong log.
- Trả mã lỗi phù hợp (REST): ví dụ 503 khi service phụ thuộc không sẵn sàng.
- Có thể retry nhẹ 1–2 lần.
- Với MQTT: auto-reconnect khi broker disconnect.

Ví dụ Python xử lý REST timeout:

```python
import httpx

try:
    response = httpx.post(
        CORE_URL + "/api/v1/...",
        json=payload,
        timeout=5.0,
    )
    response.raise_for_status()
except httpx.TimeoutException:
    return {"error": "service phụ thuộc timeout", "status": 503}
except httpx.HTTPStatusError as e:
    return {"error": "service phụ thuộc trả lỗi", "status": e.response.status_code}
except httpx.RequestError:
    return {"error": "không kết nối được service phụ thuộc", "status": 503}
```

Nếu service consumer dùng FastAPI async, đổi sang `httpx.AsyncClient` để không block event loop.

---

## 13. Timeline 60 phút đầu Buổi 6

| Thời gian | Việc cần làm |
|---|---|
| 0–10 phút | Bật iPhone hotspot từng Product, các máy demo kết nối vào đúng hotspot |
| 10–20 phút | Mỗi nhóm lấy IP máy demo (dải `172.20.10.x`), điền vào bảng IP chung |
| 20–30 phút | Cập nhật `.env` với URL nhóm đối tác |
| 30–40 phút | Chạy `git pull`, `docker compose up -d --build`, kiểm tra `docker compose ps` |
| 40–50 phút | Test `/health` nội bộ và `/health` của nhóm đối tác (REST), hoặc subscribe topic đối tác (MQTT) |
| 50–60 phút | Chốt nhóm nào đã sẵn sàng, nhóm nào còn lỗi |
| Sau 60 phút | Bắt đầu demo tích hợp theo cặp |

Nhóm nào chưa chạy thử ở nhà sẽ rất khó kịp trong 60 phút đầu.

---

## 14. Phương án dự phòng nếu hotspot lỗi

Nếu iPhone hotspot không đủ thiết bị hoặc các máy không nhìn thấy nhau, xử lý theo thứ tự:

1. Kiểm tra toggle `Maximize Compatibility` đã bật chưa.
2. Restart Personal Hotspot trên iPhone (tắt → bật lại).
3. Reboot Wi-Fi adapter trên máy không kết nối được.
4. Nếu quá 5 thiết bị, chuyển sang router mini hoặc TP-Link M7 dự phòng.
5. Cuối cùng, gộp tạm một số service mock trên cùng một máy để demo luồng chính.
6. Nếu vẫn lỗi, nhóm ghi lại minh chứng: IP, lệnh `curl` thất bại, firewall, `docker compose ps`, log service.

Không chuyển sang Wi-Fi công cộng nếu mạng đó có chế độ cách ly thiết bị (client isolation), vì các máy sẽ không gọi được nhau.

---

## 15. Checklist trước khi demo

Mỗi nhóm tự kiểm tra trước khi báo đã sẵn sàng.

- [ ] Máy demo đã kết nối đúng iPhone hotspot của Product.
- [ ] IP máy demo nằm trong dải `172.20.10.x`.
- [ ] Đã công bố IP của nhóm cho Product.
- [ ] Đã cập nhật `.env` với URL/topic nhóm đối tác.
- [ ] `docker compose ps` hiển thị các container cần thiết đang chạy.
- [ ] `GET /health` của nhóm mình trả thành công.
- [ ] (Nếu REST) Nhóm khác gọi được `GET /health` của nhóm mình.
- [ ] (Nếu MQTT) Nhóm khác subscribe được topic nhóm mình publish.
- [ ] Endpoint hoặc topic tích hợp chính đã test bằng dữ liệu mẫu.
- [ ] Có log, screenshot, request/response hoặc payload mẫu.
- [ ] Có phương án xử lý timeout hoặc lỗi từ service phụ thuộc.

---

## 16. Minh chứng cần nộp

Mỗi nhóm lưu vào thư mục `reports/`:

```text
reports/
├── docker-compose-ps.png         # các container đang chạy
├── health-local.png              # /health gọi từ localhost
├── health-partner.png            # nhóm khác gọi /health của mình (nếu REST)
├── mqtt-subscribe-evidence.png   # nếu MQTT, ảnh MQTT Explorer
├── integration-evidence.png      # request/response hoặc payload tích hợp
├── logs-compose.txt              # log Docker khi tích hợp
└── readiness-checklist.md        # checklist mục 15 đã đánh dấu
```

Nếu dùng video ngắn, đặt tên rõ:

```text
reports/demo-integration-<consumer>-to-<provider>.mp4
```

---

## 17. Rubric gợi ý Buổi 6

| Tiêu chí | Điểm |
|---|---:|
| Service chạy ổn định trên máy demo, `/health` thành công | 2.0 |
| Bắt tay được với nhóm đối tác theo contract (REST hoặc MQTT) | 2.5 |
| Payload/request đúng schema đã thống nhất trong contract | 1.5 |
| Có xử lý timeout hoặc lỗi từ service phụ thuộc | 1.5 |
| Có minh chứng: log, ảnh, payload mẫu | 1.5 |
| Trình bày demo rõ ràng, đúng luồng tích hợp | 1.0 |
| **Tổng** | **10.0** |

Điểm nhấn của Buổi 6 là khả năng tích hợp thật, không phải trình bày slide.

---

## 18. Quy trình tóm tắt đầu Buổi 6

1. Bật iPhone hotspot từng Product, bật `Maximize Compatibility`, cắm sạc.
2. Tất cả máy demo kết nối vào đúng hotspot.
3. Mỗi nhóm lấy IP máy demo (dải `172.20.10.x`).
4. Ghi IP vào bảng chung của Product.
5. Cập nhật `.env` với URL/topic nhóm đối tác.
6. Chạy `docker compose up -d --build`.
7. Kiểm tra `/health` của nhóm mình.
8. Test `/health` của nhóm đối tác (REST) hoặc subscribe topic (MQTT).
9. Chạy request/publish tích hợp mẫu theo contract.
10. Lưu minh chứng và sẵn sàng demo.

---

## 19. Nhắc cuối

Buổi 6 không phải buổi để bắt đầu cài Docker, sửa lại toàn bộ repo hoặc thiết kế lại contract API.

Trước khi đến lớp, mỗi nhóm cần chắc chắn:

- Repo chạy được trên máy demo.
- File `.env.example` rõ ràng.
- Docker Compose chạy được.
- Endpoint `/health` hoạt động.
- Đã chốt contract với nhóm đối tác (REST endpoint hoặc MQTT topic + schema).
- Đã có request/payload mẫu để test nhanh.

Khi lên lớp, nhóm chỉ cần kết nối iPhone hotspot, lấy IP, cập nhật `.env`, chạy stack và kiểm tra tích hợp theo contract.
