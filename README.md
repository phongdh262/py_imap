# Py-IMAP Email Migration Engine & Monitoring Stack

Bộ công cụ di chuyển dữ liệu email doanh nghiệp đa nền tảng (**Gmail, Yandex, Outlook / Office 365, cPanel, Dovecot, Zimbra**) tối ưu hóa cho **Ubuntu 24.04 LTS**. Hệ thống tích hợp sẵn cơ chế chống trùng lặp dữ liệu, khôi phục khi đứt mạng, bảng điều khiển trực quan **Web Admin Control Panel**, bảo mật đa tầng, và hạ tầng quan sát thời gian thực bằng **Prometheus + Grafana + Loki**.

---

## 🌟 Điểm Nổi Bật & Tính Năng Cốt Lõi

### 1. 🗄️ Chống Trùng Lặp Thư & Resume Khi Rớt Mạng (Idempotency Engine)
- **SQLite WAL State Database (`data/state.db`)**: Theo dõi trạng thái từng bức thư dựa trên `Message-ID`, `RFC822.SIZE` và `INTERNALDATE`.
- **An toàn tuyệt đối khi rớt mạng**: Nếu tiến trình bị ngắt đột ngột, khi chạy lại hệ thống sẽ tự động bỏ qua các thư đã di chuyển thành công, tiếp tục di chuyển từ vị trí bị dừng mà không sinh ra thư rác/trùng lặp.

### 2. 🇻🇳 Tự Động Xử Lý Tiếng Việt Có Dấu & Mojibake (Yandex / cPanel)
- Tự động giải mã chuẩn **Modified UTF-7 (RFC 2152)** của giao thức IMAP.
- **Tự động vá lỗi Mojibake**: Sửa các lỗi giải mã nhầm font tiếng Việt (ví dụ: `ThÆ° Ä‘Ã£ gá»­i` ➔ `Thư đã gửi`).
- **Tùy chọn Khử Dấu Tiếng Việt**: Tự động chuyển đổi tên thư mục thành tiếng Việt không dấu (`Thư đã gửi` ➔ `Thu da gui`) để tương thích tối đa với các máy chủ cPanel/Dovecot đời cũ không hỗ trợ UTF-8 Maildir.

### 3. 🛡️ Bảo Mật Đa Tầng Doanh Nghiệp (Enterprise Security Hardening)
- **Xác thực Web Admin & Chống Brute-Force**:
  - Bảo vệ Web Control Panel bằng HTTP Basic Auth.
  - So sánh mật khẩu an toàn theo thời gian hằng số (`secrets.compare_digest`) chống **Timing Attacks**.
  - **Tự động Lockout 5 phút**: Tự động khóa IP khi nhập sai liên tiếp quá 5 lần (`HTTP 429 Too Many Requests`).
- **OWASP HTTP Security Headers**:
  - `X-Frame-Options: SAMEORIGIN` (chống Clickjacking).
  - `X-Content-Type-Options: nosniff` (chống MIME-confusion).
  - `X-XSS-Protection: 1; mode=block`.
  - `Referrer-Policy: strict-origin-when-cross-origin`.
- **Chống Path Traversal (Lỗ hổng duyệt thư mục)**:
  - Kiểm tra và cô lập đường dẫn tải file báo cáo `/reports/{filename}` với `PathSecurity.validate_safe_path()`, chặn tuyệt đối các ký tự `..`, null-byte `\0`.
- **Che Dấu Mật Khẩu (Credential Masking)**:
  - Tự động che mật khẩu dạng `sup***123` trong logs, telemetry và IMAP exception để không bao giờ lộ mật khẩu trên màn hình hay hệ thống giám sát.
- **Thắt Chặt Chuẩn Mã Hóa TLS 1.2+**:
  - Bắt buộc giao thức TLS 1.2 / TLS 1.3, kích hoạt SNI và kiểm tra tính hợp lệ của chứng chỉ SSL (`CERT_REQUIRED`).

### 4. ⚡ Điều Tiết Băng Thông & Chống Block IP (Anti-ban Throttling)
- Tùy chỉnh độ trễ giữa các batch (mặc định 50ms - 200ms) để không bị nhà mạng hay Google/Microsoft gắn cờ spam request.
- **Tự động Exponential Backoff**: Khi gặp cảnh báo quá tải (`[ALERT] Too many simultaneous connections`, `Maximum bandwidth exceeded`, `[THROTTLED]`), hệ thống tự động nghỉ 5s, 10s, 20s và thử lại một cách êm dịu thay vì làm gián đoạn toàn bộ tiến trình.

### 5. 🔁 Công Cụ Retry Thư Lỗi Riêng Biệt (Targeted Recovery)
- Dành riêng cho các thư bị lỗi do sự cố mạng tức thời hoặc MIME vượt kích thước cho phép.
- Chỉ đọc và kéo đúng những UID bị lỗi từ danh sách phiên cũ, di chuyển bù vào hộp thư đích và cập nhật lại trạng thái trong database mà không phải quét lại toàn bộ tài khoản.

### 6. 📊 Tự Động Sinh Báo Cáo Kết Quả Sau Migrate
- **Báo cáo HTML Tự Chứa (Self-contained Interactive HTML)**: Thiết kế hiện đại, responsive, tích hợp biểu đồ trực quan, bảng chi tiết từng thư mục và danh sách lỗi cụ thể.
- **Báo cáo CSV Thư Lỗi**: Xuất file CSV chi tiết các bức thư thất bại kèm nguyên nhân để quản trị viên dễ dàng đối soát.

---

## 🖥️ Giao Diện Quản Trị Trực Quan (Web Admin Control Panel)

Web Control Panel (`http://<SERVER_IP>:8080`) được xây dựng sẵn với các tính năng:
- **Kéo - Thả File CSV**: Hỗ trợ nạp hàng loạt tài khoản từ file CSV mẫu.
- **Nút Kiểm Tra Nhanh**: Quét song song mật khẩu ứng dụng và kiểm tra latency kết nối của toàn bộ danh sách email.
- **Preset Nhà Cung Cấp**: 1-click điền thông số chuẩn cho Gmail, Yandex, Microsoft 365, cPanel.
- **Tùy Biến Giao Diện (Theme Switcher)**: 3 giao diện cao cấp:
  - 🌌 **Midnight Neon** (Mặc định)
  - ⬛ **OLED Obsidian** (Tối sâu tiết kiệm pin)
  - ☀️ **Clean Light** (Sáng sủa, hiện đại)
- **Live SSE Progress**: Cập nhật tiến độ % và log dạng terminal drawer theo thời gian thực mà không cần tải lại trang.

---

## 📈 Hệ Thống Quan Sát & Giám Sát (Prometheus + Grafana + Loki)

1. **Prometheus Metrics (Port 9090 / Exporter 8000)**:
   - Số lượng email thành công / thất bại: `email_migration_messages_migrated_total`, `email_migration_messages_failed_total`.
   - Tốc độ di chuyển thời gian thực: Messages/giây và Băng thông mạng MB/giây.
   - Dung lượng hộp thư trước khi migrate: `email_migration_source_mailbox_size_bytes`.
   - Tiến độ % từng tài khoản: `email_migration_account_progress_percent`.
2. **Grafana Loki + Promtail (Port 3100 & 3000)**:
   - Thu thập JSON logs từ `/var/log/email_migrator/*.log`.
   - Bóc tách nhãn tự động: `level`, `source_account`, `folder`, `error_code`.
   - Panel xem chi tiết từng bức thư bị lỗi trực tiếp trên giao diện Grafana.
3. **Grafana Dashboard Tự Động (Auto-Provisioned)**:
   - Nạp sẵn Dashboard **"Email Migration Control Center"** ngay khi khởi động Docker Compose.

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy Trên VPS (Ubuntu / Debian)

### Cách 1: Khởi chạy bằng Docker & Docker Compose (Khuyên dùng)
Tự động đóng gói và chạy toàn bộ 5 dịch vụ: **Web Control Panel, Prometheus, Grafana, Loki, Promtail**.

```bash
# 1. Cài đặt Docker & Git trên VPS (nếu chưa có)
sudo apt update && sudo apt install -y git curl docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER && newgrp docker

# 2. Clone repository về VPS
git clone https://github.com/phongdh262/py_imap.git
cd py_imap

# 3. Tạo file cấu hình môi trường (.env)
cp .env.example .env
# (Tùy chọn) Chỉnh sửa tài khoản/mật khẩu Web Admin:
# nano .env

# 4. Mở cổng Firewall (UFW) trên VPS
sudo ufw allow 8080/tcp    # Web Admin Control Panel
sudo ufw allow 3000/tcp    # Grafana Dashboard
sudo ufw reload

# 5. Build và khởi chạy ngầm tất cả dịch vụ
docker compose up -d --build

# 6. Kiểm tra trạng thái và logs
docker compose ps
docker compose logs -f app
```

Truy cập hệ thống:
- **Web Admin**: `http://<IP_VPS>:8080` (Mặc định: `admin` / `admin123` hoặc cấu hình trong `.env`)
- **Grafana Dashboard**: `http://<IP_VPS>:3000` (Mặc định: `admin` / `admin`)

---

### Cách 2: Khởi chạy trực tiếp bằng Python (Không dùng Docker)
Dành cho VPS cấu hình nhỏ (RAM 1GB) hoặc chạy thủ công:

```bash
# 1. Cài đặt Python 3, venv và Git
sudo apt update && sudo apt install -y git python3 python3-pip python3-venv

# 2. Clone repository & tạo môi trường ảo
git clone https://github.com/phongdh262/py_imap.git
cd py_imap
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Mở cổng Web Admin trên VPS
sudo ufw allow 8080/tcp && sudo ufw reload

# 4. Khởi chạy Web Admin chạy nền (Background)
nohup python3 -m src.main --web --port 8000 --web-port 8080 > app.log 2>&1 &
```

---

### 🛑 Bảng Lệnh Quản Lý Nhanh Trên VPS

| Thao tác | Docker Compose | Python Trực Tiếp |
| :--- | :--- | :--- |
| **Xem log realtime** | `docker compose logs -f app` | `tail -f app.log` |
| **Dừng hệ thống** | `docker compose down` | `pkill -f "src.main"` |
| **Khởi động lại** | `docker compose restart app` | Chạy lại lệnh `nohup ...` |
| **Cập nhật code mới** | `git pull && docker compose up -d --build` | `git pull && pip install -r requirements.txt` |

---

## 🛠️ Hướng Dẫn Khởi Chạy Local (Máy cá nhân)

### 2. Khởi chạy cục bộ (Local / Development)
Cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt
```

**Khởi chạy CLI Menu Tương Tác:**
```bash
python3 -m src.main
```
Menu hiển thị:
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

**Khởi chạy Web Admin Control Panel:**
```bash
python3 -m uvicorn src.web.server:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🌐 Danh Mục Dịch Vụ & Cổng Kết Nối

| Dịch vụ | URL | Tài khoản mặc định | Mô tả |
| :--- | :--- | :--- | :--- |
| **Web Admin Control Panel** | `http://<SERVER_IP>:8080` | `admin` / `admin123` | Giao diện điều khiển di chuyển, kéo thả CSV, cấu hình di chuyển |
| **Grafana Dashboard** | `http://<SERVER_IP>:3000` | `admin` / `Admin@Migration2026!` | Dashboard giám sát tốc độ MB/s, tiến độ %, logs Loki (Bắt buộc đăng nhập) |
| **Prometheus UI** | `http://localhost:9090` | Localhost only | Truy vấn thô metrics, biểu đồ hệ thống |
| **App Metrics Exporter** | `http://<SERVER_IP>:8000/metrics` | Không yêu cầu | Endpoint scrape của Prometheus từ Python |

---

## ⚙️ Biến Môi Trường (Environment Variables)

| Tên biến | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `ENABLE_WEB_AUTH` | `true` | Bật/tắt chế độ đăng nhập bảo vệ Web Admin |
| `ADMIN_USERNAME` | `admin` | Tài khoản đăng nhập Web Admin |
| `ADMIN_PASSWORD` | `admin123` | Mật khẩu quản trị viên Web Admin |
| `GRAFANA_ADMIN_USER` | `admin` | Tài khoản quản trị viên Grafana |
| `GRAFANA_ADMIN_PASSWORD` | `Admin@Migration2026!` | Mật khẩu quản trị viên Grafana (cần đổi sang mật khẩu mạnh) |
| `GRAFANA_URL` | `https://monitor.phongdinh.info.vn` | Địa chỉ URL của Grafana Dashboard khi người dùng click vào nút Grafana trên Web Admin |
| `ALLOWED_ORIGINS` | `*` | Danh sách CORS domain được phép truy cập API (cách nhau bởi dấu phẩy) |
| `LOG_FORMAT` | `json` | Định dạng log ghi ra file (`json` cho Loki hoặc `console`) |

---

## 🧪 Kiểm Thử Tự Động (Unit Tests)

Chạy bộ kiểm thử tự động cho hệ thống bảo mật và các module cốt lõi:
```bash
python3 -m unittest discover tests
```

---

## 📁 Cấu Trúc Mã Nguồn

```text
PY_IMAP/
├── docker-compose.yml              # Quản lý 5 services: app, prometheus, loki, promtail, grafana
├── Dockerfile                      # Image Python 3.12 tối ưu
├── requirements.txt                # Danh sách thư viện Python
├── config/
│   ├── settings.yaml               # Cấu hình worker, batch size, timeout
│   ├── mapping_rules.yaml          # Quy tắc map & exclude folder (RFC 6154)
│   └── accounts.example.csv        # File CSV mẫu tài khoản nguồn & đích
├── monitoring/
│   ├── prometheus/prometheus.yml   # Cấu hình Prometheus scrape
│   ├── loki/loki-config.yml        # Cấu hình lưu trữ log Loki
│   ├── promtail/promtail-config.yml# Promtail tailing log & gán nhãn
│   └── grafana/                    # Auto-provisioning datasource & dashboard
├── tests/
│   └── test_security.py            # Unit test xác thực, brute-force, path guard, masking
└── src/
    ├── core/                       # Core Migration Engine
    │   ├── imap_client.py          # IMAP Client TLS 1.2+ & mask mật khẩu
    │   ├── folder_mapper.py        # Mapping folder, mUTF-7 & khử dấu tiếng Việt
    │   ├── inspector.py            # Quét dung lượng hộp thư (RFC 8438 / STATUS=SIZE)
    │   ├── migrator.py             # Di chuyển batch, kiểm tra trùng lặp
    │   ├── throttler.py            # Rate limiting & Exponential backoff
    │   ├── auth_checker.py         # Kiểm tra mật khẩu ứng dụng song song
    │   ├── retry_engine.py         # Công cụ retry riêng các thư bị lỗi
    │   └── service.py              # Orchestrator điều phối
    ├── security/                   # Enterprise Security Hardening
    │   ├── auth.py                 # HTTP Basic Auth & Lockout chống Brute-Force
    │   ├── crypto.py               # Masking credential & lọc dữ liệu nhạy cảm
    │   ├── headers.py              # OWASP HTTP Security Headers Middleware
    │   └── path_guard.py           # Path Traversal Guard cho file download
    ├── storage/
    │   └── state_db.py             # SQLite WAL lưu trạng thái để resume & chống trùng
    ├── reports/
    │   └── reporter.py             # Xuất báo cáo HTML tương tác & CSV thư lỗi
    ├── web/                        # Web Admin Control Panel
    │   ├── server.py               # FastAPI backend & SSE stream
    │   ├── templates/index.html    # Giao diện Web Admin
    │   └── static/                 # CSS/JS, Dark/Light Themes
    ├── telemetry/                  # Giám sát & Logs
    │   ├── metrics.py              # Prometheus metrics collector
    │   └── logger.py               # Structlog dual console + json Loki
    ├── cli/
    │   └── menu.py                 # Giao diện dòng lệnh tương tác rich CLI
    └── main.py                     # Entry point khởi chạy
```
