import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.core.folder_mapper import FolderMapper
from src.core.models import FolderRole
from src.core.retry_engine import RetryEngine
from src.core.throttler import ProviderThrottler
from src.storage.state_db import StateDatabase


class TestCoreFeatures(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_migration.sqlite")
        self.state_db = StateDatabase(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1. State Database & Deduplication (Idempotency) Test Cases
    # -------------------------------------------------------------
    def test_compute_message_hash_consistency(self):
        """Kiểm tra hàm tạo hash chữ ký duy nhất cho email để chống trùng lặp."""
        msg_id = "<CAG7N091u+Dyt_TdYTof--CiHiudT3qvQEeO3Hv1b+bUH=g_4EA@mail.gmail.com>"
        date_str = "2026-10-18 18:21:25"
        subject = "Hợp đồng dịch vụ 2026"
        size = 1048576

        hash1 = self.state_db.compute_message_hash(msg_id, date_str, subject, size)
        hash2 = self.state_db.compute_message_hash(msg_id, date_str, subject, size)
        self.assertEqual(hash1, hash2, "Cùng thông số email phải sinh ra hash giống hệt nhau")

        # Thay đổi dung lượng -> hash khác
        hash3 = self.state_db.compute_message_hash(msg_id, date_str, subject, size + 1)
        self.assertNotEqual(hash1, hash3, "Dung lượng khác nhau phải sinh ra hash khác")

        # Khi thiếu Message-ID vẫn tạo được hash từ (Date + Subject + Size)
        hash_no_msg_id = self.state_db.compute_message_hash(None, date_str, subject, size)
        self.assertTrue(len(hash_no_msg_id) == 64, "SHA-256 fallback hash phải có độ dài 64 ký tự hex")

    def test_migration_session_lifecycle_and_idempotency(self):
        """Kiểm tra vòng đời phiên di chuyển và cơ chế chống trùng lặp dữ liệu (Idempotency)."""
        src = "user_src@domain.com"
        dst = "user_dst@target.com"
        folder = "INBOX"

        # 1. Khởi tạo session
        session_id = self.state_db.start_migration(src, dst, total_messages=10)
        self.assertIsInstance(session_id, int)

        # 2. Ban đầu thư chưa được chuyển
        msg_hash = self.state_db.compute_message_hash("<msg01@domain.com>", "2026-10-19", "Hello", 2048)
        self.assertFalse(self.state_db.is_message_migrated(src, folder, msg_hash))

        # 3. Ghi nhận chuyển thành công
        self.state_db.record_success(
            migration_id=session_id,
            source_account=src,
            folder=folder,
            source_uid=101,
            msg_hash=msg_hash,
            message_id="<msg01@domain.com>",
            subject="Hello",
            sender="boss@domain.com",
            date_str="2026-10-19",
            size_bytes=2048,
        )

        # 4. Kiểm tra lại: thư đã được đánh dấu migrated -> ngăn chặn gửi trùng lặp
        self.assertTrue(
            self.state_db.is_message_migrated(src, folder, msg_hash),
            "Thư đã chuyển thành công phải được đánh dấu để bỏ qua khi chạy lại",
        )

        # 5. Ghi nhận thư bị lỗi
        fail_hash = self.state_db.compute_message_hash("<msg02@domain.com>", "2026-10-19", "Attachment Too Large", 52428800)
        self.state_db.record_failure(
            migration_id=session_id,
            source_account=src,
            folder=folder,
            source_uid=102,
            msg_hash=fail_hash,
            message_id="<msg02@domain.com>",
            subject="Attachment Too Large",
            sender="client@domain.com",
            date_str="2026-10-19",
            size_bytes=52428800,
            error_code="MESSAGE_TOO_LARGE",
            error_detail="Exceeded 35MB max allowed size on destination",
        )

        # 6. Thư lỗi không được coi là đã migrated thành công
        self.assertFalse(self.state_db.is_message_migrated(src, folder, fail_hash))

        # 7. Kiểm tra danh sách thư lỗi
        failed_messages = self.state_db.get_failed_messages(session_id)
        self.assertEqual(len(failed_messages), 1)
        self.assertEqual(failed_messages[0]["error_code"], "MESSAGE_TOO_LARGE")

        # 8. Hoàn thành phiên và kiểm tra summary
        self.state_db.complete_migration(session_id, "COMPLETED")
        summary = self.state_db.get_migration_summary(session_id)
        self.assertEqual(summary["migrated_messages"], 1)
        self.assertEqual(summary["failed_messages"], 1)
        self.assertEqual(summary["transferred_bytes"], 2048)

    # -------------------------------------------------------------
    # 2. Provider Throttling & Anti-ban Engine Test Cases
    # -------------------------------------------------------------
    def test_provider_throttling_detection(self):
        """Kiểm tra khả năng phát hiện tín hiệu giới hạn tốc độ / ban từ máy chủ email."""
        throttler = ProviderThrottler(batch_delay_seconds=0.01, base_backoff_seconds=2.0)

        # Các lỗi do nhà cung cấp bóp băng thông / chặn tạm thời
        throttled_errors = [
            "NO [UNAVAILABLE] Maximum bandwidth exceeded for this user",
            "NO [ALERT] Too many simultaneous connections",
            "A1 NO User is over quota or throttled",
            "BAD Server busy, try again later",
            "Connection reset by peer",
            "Temporary lookup failure (rate limit)",
        ]
        for err in throttled_errors:
            self.assertTrue(
                throttler.is_throttled_error(err),
                f"Phải nhận diện được lỗi throttling: '{err}'",
            )

        # Các lỗi thông thường không phải do throttling
        non_throttled_errors = [
            "NO [AUTHENTICATIONFAILED] Invalid credentials",
            "NO [NONEXISTENT] Mailbox does not exist",
            "BAD Syntax error in command",
            "NO Permission denied",
        ]
        for err in non_throttled_errors:
            self.assertFalse(
                throttler.is_throttled_error(err),
                f"Lỗi thông thường không được coi là throttling: '{err}'",
            )

    def test_throttler_exponential_backoff_timing(self):
        """Kiểm tra công thức tính exponential backoff."""
        throttler = ProviderThrottler(base_backoff_seconds=5.0)

        # Lần 1: 5 * 2^0 = 5.0s
        # Lần 2: 5 * 2^1 = 10.0s
        # Lần 3: 5 * 2^2 = 20.0s
        with patch("time.sleep") as mock_sleep:
            throttler.wait_backoff(attempt=1, account="test@gmail.com", host="imap.gmail.com", error_detail="busy")
            mock_sleep.assert_called_with(5.0)

            throttler.wait_backoff(attempt=2, account="test@gmail.com", host="imap.gmail.com", error_detail="busy")
            mock_sleep.assert_called_with(10.0)

            throttler.wait_backoff(attempt=3, account="test@gmail.com", host="imap.gmail.com", error_detail="busy")
            mock_sleep.assert_called_with(20.0)

    # -------------------------------------------------------------
    # 3. Retry Engine Recovery Test Cases
    # -------------------------------------------------------------
    def test_retry_engine_identifies_failed_sessions(self):
        """Kiểm tra Retry Engine tìm chính xác các phiên có thư lỗi để xử lý lại."""
        session_id = self.state_db.start_migration("src@domain.com", "dst@domain.com", total_messages=2)
        self.state_db.record_failure(
            migration_id=session_id,
            source_account="src@domain.com",
            folder="INBOX",
            source_uid=55,
            msg_hash="fakehash",
            message_id="<msg@domain.com>",
            subject="Invoice",
            sender="finance@domain.com",
            date_str="2026-10-18",
            size_bytes=1024,
            error_code="TIMEOUT",
            error_detail="Socket read timeout",
        )

        engine = RetryEngine(state_db=self.state_db)
        failed_sessions = engine.list_failed_sessions()
        self.assertEqual(len(failed_sessions), 1)
        self.assertEqual(failed_sessions[0]["id"], session_id)
        self.assertEqual(failed_sessions[0]["failed_messages"], 1)

    # -------------------------------------------------------------
    # 4. Folder Hierarchy & Delimiter Conversion Edge Cases
    # -------------------------------------------------------------
    def test_folder_delimiter_slash_to_dot_conversion(self):
        """Kiểm tra chuyển đổi ký tự phân cách phân cấp thư mục từ / (Gmail) sang . (Dovecot/cPanel)."""
        mapper = FolderMapper()
        dest_canonical = {FolderRole.INBOX: "INBOX"}

        # Subfolder lồng nhau 3 cấp
        result = mapper.map_folder_name(
            source_folder="Clients/2026/TechCorp",
            source_role=FolderRole.CUSTOM,
            source_delim="/",
            dest_delim=".",
            dest_canonical_map=dest_canonical,
            dest_prefix="INBOX.",
        )
        self.assertEqual(result, "INBOX.Clients.2026.TechCorp")

    # -------------------------------------------------------------
    # 5. Web API Feature Integration Tests
    # -------------------------------------------------------------
    def test_web_api_auth_check_password_validation(self):
        """Kiểm tra API kiểm tra chất lượng kết nối và xác thực mật khẩu đơn lẻ."""
        from fastapi.testclient import TestClient
        from src.web.server import app

        os.environ["ENABLE_WEB_AUTH"] = "false"
        client = TestClient(app)

        # Gửi payload thiếu trường bắt buộc
        res_bad = client.post("/api/check-password", json={"host": "imap.test.com"})
        self.assertEqual(res_bad.status_code, 422, "Thiếu tham số bắt buộc phải trả về 422 Unprocessable Entity")

    def test_web_api_active_tasks_and_cache_clear(self):
        """Kiểm tra API lấy danh sách tiến trình đang chạy và dọn dẹp bộ nhớ đệm."""
        from fastapi.testclient import TestClient
        from src.web.server import app

        os.environ["ENABLE_WEB_AUTH"] = "false"
        client = TestClient(app)

        # 1. Lấy danh sách tiến trình active
        res_active = client.get("/api/tasks/active")
        self.assertEqual(res_active.status_code, 200)
        data = res_active.json()
        self.assertIsInstance(data, list)

        # 2. Xóa cache cho tài khoản cụ thể
        res_cache = client.post("/api/cache/clear?account=test@domain.com")
        self.assertEqual(res_cache.status_code, 200)
        self.assertEqual(res_cache.json().get("status"), "ok")

        # 3. Lấy danh sách sessions
        res_sessions = client.get("/api/sessions")
        self.assertEqual(res_sessions.status_code, 200)
        self.assertIsInstance(res_sessions.json(), list)


if __name__ == "__main__":
    unittest.main()
