# Py-IMAP Email Migration Engine & Monitoring Stack

Bộ công cụ di chuyển dữ liệu email đa nền tảng (Gmail, Yandex, Outlook / Office 365, cPanel/Dovecot) được thiết kế cho **Ubuntu 24.04 LTS**, tích hợp sẵn hệ thống quan sát thời gian thực bằng **Prometheus + Grafana + Loki**.

---

## 🚀 Tính năng Hạ tầng Giám sát

1. **Prometheus Metrics (Port 9090 / App 8000)**:
   - Đo lường số lượng email thành công / thất bại theo từng account và folder (`email_migration_messages_migrated_total`, `email_migration_messages_failed_total`).
   - Tốc độ di chuyển thời gian thực: Messages/giây và Băng thông mạng MB/giây.
   - Dung lượng hộp thư nguồn trước khi migrate (`email_migration_source_mailbox_size_bytes`).
   - Tiến độ % từng tài khoản (`email_migration_account_progress_percent`).
   - Số lượng worker đang chạy đồng thời (`email_migration_active_workers`).

2. **Grafana Loki + Promtail (Port 3100 & 3000)**:
   - Thu thập log có cấu trúc dạng JSON (`/var/log/email_migrator/*.log`).
   - Bóc tách nhãn tự động: `level`, `source_account`, `folder`, `error_code`.
   - Xem chi tiết từng bức thư bị lỗi: UID, Message-ID, nguyên nhân thất bại (vượt quá dung lượng, rớt socket, sai MIME).

3. **Grafana Dashboard Tự Động (Auto-Provisioned)**:
   - Truy cập ngay không cần tạo thủ công: mở `http://localhost:3000` (hoặc IP máy chủ Ubuntu).
   - Tự động nạp sẵn Dashboard **"Email Migration Control Center"**.

---

## 🛠️ Hướng dẫn Khởi chạy trên Ubuntu 24.04

### 1. Yêu cầu tiên quyết
Cài đặt Docker và Docker Compose trên Ubuntu 24:
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
```

### 2. Khởi chạy Ứng Dụng với Giao Diện Menu Lựa Chọn (Interactive Menu)

Chỉ cần chạy:
```bash
python3 -m src.main
```
Hệ thống sẽ hiển thị menu tương tác trực quan:
```text
╭────────────────────────────────────────────────────────╮
│ PY-IMAP EMAIL MIGRATION TOOL (Ubuntu 24.04 LTS)        │
│ Multi-provider support: Gmail, Yandex, Outlook, cPanel │
│ Prometheus Metrics: http://0.0.0.0:8000/metrics        │
╰────────────────────────────────────────────────────────╯

VUI LÒNG CHỌN TÍNH NĂNG:
[1]  🔍 Quét dung lượng & thư mục máy chủ nguồn (Pre-flight Inspection)
[2]  🔑 Kiểm tra Mật khẩu ứng dụng 1 hoặc nhiều tài khoản (App Password Checker)
[3]  🚀 Di chuyển 1 tài khoản trực tiếp (Migrate 1 Account)
[4]  📂 Di chuyển hàng loạt nhiều tài khoản từ file CSV (Batch Migrate)
[5]  🔁 Thử lại các email bị lỗi từ phiên trước (Retry Failed Messages)
[6]  ⚡ Kiểm tra kết nối IMAP & SSL (Connection Health Check)
[7]  📈 Chạy chế độ Mô phỏng để kiểm tra Grafana Dashboard (Live Simulation)
[0]  ❌ Thoát chương trình (Exit)
```

---

## 🛡️ Các Tính Năng Doanh Nghiệp Cốt Lõi

### 1. Cơ Chế Xử Lý Thư Mục Tiếng Việt Có Dấu (Yandex / cPanel)
- Tự động sửa lỗi mã hóa **Modified UTF-7 (RFC 2152)** và hiện tượng **Mojibake** (UTF-8 bị đọc nhầm thành Latin-1 như `ThÆ° Ä‘Ã£ gá»­i`).
- **Tùy chọn Khử Dấu Tiếng Việt**: Tự động chuyển đổi tên thư mục thành không dấu (`Thư đã gửi` ➔ `Thu da gui`) khi di chuyển về các server cPanel/Dovecot đời cũ không hỗ trợ Unicode Maildir.

### 2. Điều Tiết Băng Thông & Chống Block IP (Anti-ban Throttling)
- Tùy chỉnh độ trễ giữa các batch (mặc định 50ms - 200ms) để không bị nhà mạng hay Google/Microsoft đánh dấu là spam request.
- **Tự động Exponential Backoff**: Khi gặp cảnh báo quá tải (`[ALERT] Too many simultaneous connections`, `Maximum bandwidth exceeded`), hệ thống tự động dừng nghỉ 5s, 10s, 20s và thử lại một cách êm dịu thay vì làm gián đoạn toàn bộ tiến trình.

### 3. Công Cụ Retry Thư Lỗi Riêng Biệt (Targeted Recovery)
- Lựa chọn **`[5]`** trên menu cho phép xem lại các phiên migrate cũ có email lỗi.
- Chỉ kéo và đẩy đúng những UID bị lỗi mà không cần quét lại toàn bộ hộp thư, sau đó tự động cập nhật lại báo cáo HTML/CSV.

### 4. Hệ Thống Bảo Mật Đa Tầng Doanh Nghiệp (Enterprise Security Hardening)
- **Xác thực Web Admin & Chống Brute-Force**:
  - Hỗ trợ HTTP Basic Auth bảo vệ toàn bộ dashboard Web Admin (`:8080`).
  - So sánh mật khẩu an toàn theo thời gian hằng số (`secrets.compare_digest`) chống tấn công Timing Attacks.
  - Tự động phát hiện và khóa IP (Lockout 5 phút) nếu nhập sai liên tiếp quá 5 lần (`HTTP 429 Too Many Requests`).
  - Biến môi trường: `ENABLE_WEB_AUTH` (mặc định: `true`), `ADMIN_USERNAME` (mặc định: `admin`), `ADMIN_PASSWORD` (mặc định: `admin123`).
- **OWASP Security Headers**:
  - Tự động gắn các header bảo mật: `X-Frame-Options: SAMEORIGIN` (chống Clickjacking), `X-Content-Type-Options: nosniff` (chống MIME confusion), `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`.
- **Chống Path Traversal (Lỗ hổng duyệt thư mục)**:
  - Kiểm tra và cô lập đường dẫn tải file báo cáo `/reports/{filename}` với `PathSecurity.validate_safe_path()`, chặn tuyệt đối các chuỗi `../`, null-byte `\0` và ký tự độc hại.
- **Che Dấu Mật Khẩu & Dữ Liệu Nhạy Cảm (Credential Masking)**:
  - Tự động che mật khẩu dạng `sup***123` trong logs, telemetry và các thông báo lỗi socket/IMAP để không bao giờ lộ mật khẩu ra bên ngoài.
- **Thắt Chặt Chuẩn Mã Hóa TLS 1.2+**:
  - Bắt buộc giao thức TLS 1.2 / TLS 1.3, kích hoạt SNI và kiểm tra tính hợp lệ của chứng chỉ SSL (`CERT_REQUIRED`).

---

### 3. Truy cập các dịch vụ
| Dịch vụ | URL | Mô tả |
| :--- | :--- | :--- |
| **Web Admin Control Panel** | `http://<SERVER_IP>:8080` | **Giao diện Web Quản Trị Trực Quan**: Kéo thả CSV, quét dung lượng, kiểm tra mật khẩu, di chuyển và tải báo cáo |
| **Grafana Dashboard** | `http://<SERVER_IP>:3000` | Giao diện theo dõi real-time (Tốc độ MB/s, Tiến độ %, Bảng Kiểm tra Mật khẩu ứng dụng, Bảng Log lỗi Loki) |
| **Prometheus UI** | `http://<SERVER_IP>:9090` | Xem và truy vấn thô các metric IMAP |
| **App Metrics Exporter**| `http://<SERVER_IP>:8000/metrics` | Endpoint Prometheus scrape trực tiếp từ Python |

### 4. Xem Logs thời gian thực
- Xem log trên container App:
  ```bash
  docker compose logs -f app
  ```
- Hoặc vào Grafana -> Panel **"Real-time Migration Audit & Error Logs"** bên dưới cùng của Dashboard để lọc log theo tài khoản và mã lỗi.

---

## ⚙️ Cấu trúc thư mục

```text
PY_IMAP/
├── docker-compose.yml              # Quản lý 5 services: app, prometheus, loki, promtail, grafana
├── Dockerfile                      # Image Python 3.12 tối ưu
├── requirements.txt                # Thư viện: prometheus_client, structlog, rich, imapclient
├── config/
│   ├── settings.yaml               # Cấu hình worker, batch size, timeout
│   ├── mapping_rules.yaml          # Quy tắc map & exclude folder (RFC 6154)
│   └── accounts.example.csv        # Mẫu danh sách tài khoản nguồn & đích
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml          # Scrape config
│   ├── loki/
│   │   └── loki-config.yml         # Log storage config
│   ├── promtail/
│   │   └── promtail-config.yml     # Tail json log & extract labels
│   └── grafana/
│       ├── provisioning/           # Tự động nạp datasources & dashboards
│       └── dashboards/
│           └── email_migration_overview.json # Giao diện Grafana thiết kế sẵn
└── src/
    ├── telemetry/
    │   ├── metrics.py              # Định nghĩa Prometheus Metrics
    │   └── logger.py               # Structlog dual console + json file
    └── main.py                     # Entry point & Migration simulation
```
