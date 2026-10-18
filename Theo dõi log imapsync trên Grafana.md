# Theo dõi log imapsync trên Grafana

Oct 18, 2026 · @PhongDH

## Giới thiệu

Tài liệu này liệt kê các mục cần theo dõi trong log imapsync để dựng dashboard Grafana. Mặc định imapsync ghi log vào thư mục `LOG_imapsync/`, tên file dạng `2026_10_18_09_30_00_123_user1_user2.txt` (đổi bằng `--logdir` / `--logfile`).

Thông tin chia thành 4 nhóm: phiên chạy, tiến trình realtime, khối thống kê cuối và mã thoát. Các regex bên dưới cần kiểm tra lại với log thực tế của phiên bản imapsync đang dùng.

## 1. Thông tin phiên chạy (label / bộ lọc)

Các dòng đầu log xác định job: ai, đến đâu, đăng nhập được không.

| Mục trong log | Ví dụ dòng log | Ý nghĩa |
| --- | --- | --- |
| Phiên bản, host chạy | `Here is imapsync 2.229 on host srv01...` | Nhận diện máy chạy, version |
| PID | `PID is 12345` | Phân biệt tiến trình chạy song song |
| Server, user nguồn/đích | `Host1: IMAP server [mail.old.com] port [993] user [a@x.com]` | Label `user1`, `user2`, `host1`, `host2` |
| Đăng nhập | `Host1: success login on [...]` hoặc `failure: Error login...` | Theo dõi lỗi xác thực |
| Số thư mục | `Host1: found 25 folders.` | So sánh nguồn/đích |

## 2. Tiến trình trong lúc chạy (realtime)

Mỗi thư được copy sinh một dòng, cho biết tốc độ (msgs/s, MiB/s), ETA và số thư đã copy:

```
msg INBOX/1234 {45678} copied to INBOX/987 ... msgs/s ... MiB/s ... ETA: ...
```

Dòng lỗi có dạng `Err 3/50: ...` (số lỗi hiện tại / ngưỡng `--errorsmax`). Cần đặc biệt chú ý các chuỗi:

- `could not append` — không ghi được thư sang đích
- `could not fetch` — không đọc được thư từ nguồn
- `OVERQUOTA` — hộp thư đích hết dung lượng
- `NO [ALERT]` — server từ chối thao tác
- `Connection reset` — mất kết nối

## 3. Khối thống kê cuối (`++++ Statistics`)

Đây là phần quan trọng nhất; chỉ số cảnh báo chính là `Messages found in host1 not in host2` (thư còn thiếu).

| Trường | Dùng để |
| --- | --- |
| `Transfer started on` / `Transfer ended on` / `Transfer time` | Thời lượng sync |
| `Folders synced : 25/25 synced` | Đủ thư mục hay chưa |
| `Messages transferred` | Số thư đã chuyển |
| `Messages skipped` | Thư đã có bên đích (bình thường khi chạy lại) |
| `Messages found duplicate on host1/host2` | Thư trùng |
| `Messages found in host1 not in host2` | **Thư còn thiếu** |
| `Messages deleted on host1/host2` | Khi dùng `--delete1` / `--delete2` |
| `Total bytes transferred` / `Total bytes skipped` | Dung lượng |
| `Message rate` / `Average bandwidth rate` | Hiệu năng |
| `Reconnections to host1/host2` | Độ ổn định kết nối |
| `Memory consumption at the end`, `Biggest message` | Tài nguyên |
| `Host1 Nb messages` / `Host2 Nb messages`, `Host1 Total size` / `Host2 Total size` | So sánh tổng nguồn và đích |
| `Final difference host2 - host1` | Chênh lệch cuối, lý tưởng ≥ 0 |
| `Detected N errors` | Tổng số lỗi |

## 4. Mã thoát

Dòng cuối log cho trạng thái job, ví dụ:

```
Exiting with return value 0 (EX_OK: successful termination) 0/50 nb_errors/max_errors
```

| Mã | Ý nghĩa |
| --- | --- |
| 0 | Thành công |
| 6 | Bị dừng bởi signal |
| 10 | Lỗi kết nối |
| 12 | Lỗi TLS |
| 16 | Lỗi xác thực (sai user/pass) |
| 111 | Kết thúc có lỗi |
| 112 | Vượt ngưỡng `--errorsmax` |
| 113 | Hộp thư đích hết quota |
| 114 / 115 | Lỗi APPEND / FETCH |
| 116 / 117 | Lỗi tạo / chọn thư mục |

Danh sách mã có thể khác tùy phiên bản; kiểm tra lại bằng `imapsync --help` hoặc FAQ của imapsync.

## 5. Triển khai trên Grafana

Cách đơn giản nhất là đẩy log vào **Loki** bằng Promtail hoặc Grafana Alloy, gắn label `user1`, `user2` lấy từ tên file log.

### Truy vấn LogQL mẫu

```
# Số job thất bại (exit code khác 0)
sum(count_over_time({job="imapsync"} |~ "Exiting with return value [1-9]" [24h]))

# Thư còn thiếu theo user
{job="imapsync"} |= "Messages found in host1 not in host2"
  | regexp `not in host2\s*:\s*(?P<missing>\d+)`
  | line_format "{{.filename}}: {{.missing}}"

# Lỗi theo thời gian
sum by (filename) (count_over_time({job="imapsync"} |~ "^Err \\d+/\\d+" [5m]))

# Lỗi đăng nhập
{job="imapsync"} |~ "failure: Error login|EXIT_AUTHENTICATION_FAILURE"
```

### Regex parse khối thống kê

Dùng trong pipeline Promtail/Alloy hoặc script:

```
Messages transferred\s*:\s*(?P<transferred>\d+)
Messages skipped\s*:\s*(?P<skipped>\d+)
Messages found in host1 not in host2\s*:\s*(?P<missing>\d+)
Total bytes transferred\s*:\s*(?P<bytes>\d+)
Transfer time\s*:\s*(?P<seconds>[\d.]+) sec
Detected (?P<errors>\d+) errors
Exiting with return value (?P<exit_code>\d+)
```

Nếu cần biểu đồ số liệu đẹp hơn (bảng theo từng user, % hoàn thành), viết script parse khối Statistics sau mỗi lần chạy rồi ghi ra file cho node\_exporter textfile collector (Prometheus), hoặc vào MySQL/PostgreSQL làm datasource.

### Bố cục dashboard gợi ý

| Hàng | Panel | Nội dung |
| --- | --- | --- |
| Trên | Stat | Tổng job, thành công, thất bại, tổng thư thiếu |
| Giữa | Table | Theo từng user: transferred, skipped, missing, errors, exit code, thời gian |
| Dưới | Time series + Logs | Lỗi theo thời gian; các dòng `Err` |

### Alert nên đặt

- Exit code ≠ 0
- `Messages found in host1 not in host2` > 0
- `Detected N errors` với N > 0
