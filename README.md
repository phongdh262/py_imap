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

### 2. Khởi chạy toàn bộ hạ tầng (App + Prometheus + Grafana + Loki + Promtail)
Chạy lệnh duy nhất tại thư mục dự án:
```bash
docker compose up -d --build
```

Kiểm tra trạng thái các container:
```bash
docker compose ps
```

### 3. Truy cập các dịch vụ
| Dịch vụ | URL | Mô tả |
| :--- | :--- | :--- |
| **Grafana Dashboard** | `http://<SERVER_IP>:3000` | Giao diện theo dõi real-time (User: `admin` / Pass: `admin` hoặc Auto-login) |
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
