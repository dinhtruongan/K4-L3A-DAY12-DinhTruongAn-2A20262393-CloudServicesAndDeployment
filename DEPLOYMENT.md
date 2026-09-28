# Thông tin triển khai — Checkpoint 5

## Thông tin học viên

| Mục | Nội dung |
|---|---|
| Họ và tên | Dinh Truong An |
| Mã học viên | 2A20262393 |
| Repository | https://github.com/dinhtruongan/K4-L3A-DAY12-DinhTruongAn-2A20262393-CloudServicesAndDeployment |

## Service

| Mục | Nội dung |
|---|---|
| Public URL | https://day12-agent-7l68.onrender.com |
| Platform | Render Blueprint |
| Ngày deploy đầu tiên | 2026-09-28 |
| Web service | `day12-agent` — Docker, Free, Oregon |
| Redis-compatible store | `day12-redis` — Key Value, Free, Oregon |
| Commit deploy đầu tiên | `e8fd6b4b88f71f2db21255dcbd846825fdbf4dc0` |

## Cấu hình trên Render

| Biến | Nguồn |
|---|---|
| `PORT` | Render cấp tự động |
| `AGENT_API_KEY` | Render tạo secret ngẫu nhiên từ Blueprint; không được lưu trong Git |
| `REDIS_URL` | Connection string nội bộ của Key Value `day12-redis` |
| `RATE_LIMIT_PER_MINUTE` | `10`, cấu hình trong Blueprint |
| `MONTHLY_BUDGET_USD` | `10.0`, cấu hình trong Blueprint |
| `LOG_LEVEL` | `INFO`, cấu hình trong Blueprint |

Blueprint đặt `autoDeployTrigger: off`; workflow gọi deploy hook sau khi test và build thành công, kèm SHA đã kiểm tra. Key Value Free chỉ lưu trong bộ nhớ, nên dữ liệu có thể mất khi Render khởi động lại datastore.

## Kiểm tra dịch vụ

```bash
curl -i https://day12-agent-7l68.onrender.com/health
curl -i https://day12-agent-7l68.onrender.com/ready
curl -i -X POST https://day12-agent-7l68.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```

Kết quả quan sát trong lần kiểm tra gần nhất:

```text
GET /health -> 200 {"status":"ok","service":"day12-agent","version":"1.0.0"}
GET /ready  -> 200 {"status":"ready","redis":true}
POST /ask không có API key -> 401
```

CP5 chạy thật: **8 passed, 5 skipped**. Test HTTPS, health, Redis readiness, endpoint auth bắt buộc và tài liệu đều đạt. Test gọi `/ask` bằng khóa hợp lệ được bỏ qua trong lần chạy này vì khóa được Render tự sinh và chưa được đưa vào môi trường test cục bộ; không có khóa nào được ghi vào bằng chứng. Local smoke và JUnit nằm trong `evidence/render-smoke.txt`, `evidence/cp5-render.txt` và `evidence/cp5-render.xml`.

Để chạy kiểm tra CP5 có xác thực, đặt secret của service vào biến môi trường cục bộ `DEPLOY_API_KEY` (giá trị này không được ghi vào file này hoặc commit), rồi chạy:

```bash
python -m pytest tests/test_cp5.py -v
```

Test có xác thực tự bỏ qua nếu `DEPLOY_API_KEY` chưa được cấp cục bộ. Endpoint mock LLM không gọi nhà cung cấp AI bên ngoài.

## Ảnh chụp màn hình

Ảnh dashboard và kết quả HTTP sẽ được lưu dưới `screenshots/` sau khi hoàn tất kiểm tra.
