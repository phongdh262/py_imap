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
[5]  ⚡ Kiểm tra kết nối IMAP & SSL (Connection Health Check)
[6]  📈 Chạy chế độ Mô phỏng để kiểm tra Grafana Dashboard (Live Simulation)
[0]  ❌ Thoát chương trình (Exit)
```

---

## 🔑 Tính năng Kiểm Tra Mật Khẩu Ứng Dụng (App Password Verification)

Tính năng này cho phép bạn kiểm thử trước độ chính xác của tài khoản và Mật khẩu ứng dụng (App Password) mà không cần chờ tới lúc migrate:
1. **Kiểm tra 1 tài khoản**: Nhập Host, Username, App Password -> Kiểm tra SSL handshake, xác thực và báo lỗi cụ thể (ví dụ: Gmail yêu cầu App Password, Yandex yêu cầu bật App Password, Microsoft 365 chặn Basic Auth).
2. **Kiểm tra hàng loạt (Batch CSV)**: Quét song song nhiều luồng từ file CSV (`config/accounts.csv`), in bảng tổng hợp xanh/đỏ và tính toán tỷ lệ thành công (%).
3. **Đẩy Metrics lên Grafana**: Tự động tăng `email_auth_checks_total` và cập nhật bảng `email_account_auth_status` trên Grafana Dashboard theo thời gian thực.

---

### 3. Truy cập các dịch vụ
| Dịch vụ | URL | Mô tả |
| :--- | :--- | :--- |
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
