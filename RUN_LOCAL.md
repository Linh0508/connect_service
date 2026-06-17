# RUN_LOCAL

Hướng dẫn chạy service Core Business trong thư mục `BTL` bằng Docker.

## 1. Chuẩn bị

1. Mở terminal và chuyển tới thư mục `BTL`.
2. Đảm bảo đã cài Docker.
3. Nếu cần cài Python dependencies để chạy local, dùng:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Build Docker image

```bash
docker build -t btl-core-business:latest .
```

## 3. Chạy container bằng Docker

```bash
docker run --rm -p 4010:4010 --env-file .env.example --name btl-core-business btl-core-business:latest
```

Hoặc dùng `docker-compose`:

```bash
docker compose up --build
```

## 4. Kiểm tra endpoint `/health`

Mở terminal khác và chạy:

```bash
curl http://127.0.0.1:4010/health
```

Kết quả mong muốn:

```json
{
  "status": "UP",
  "service": "core-business",
  "version": "1.0.0"
}
```

## 5. Chạy lại Postman/Newman test

1. Cài dependencies Node nếu chưa có:

```bash
npm install
```

2. Chạy Newman test với môi trường local:

```bash
./scripts/run-newman.sh local
```

3. Kết quả report sẽ được sinh trong thư mục `reports/`.

## 6. Dừng container

Nếu chạy bằng `docker run` với `--rm`, container sẽ tự xóa khi nhấn `Ctrl+C`.

Nếu chạy bằng docker compose:

```bash
docker compose down
```
