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

    def test_universal_confirm_modal_presence(self):
        """Verifies that the custom action confirmation modal is rendered in the UI."""
        from fastapi.testclient import TestClient
        from src.web.server import app
        os.environ["ENABLE_WEB_AUTH"] = "false"
        client = TestClient(app)
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn('id="universalConfirmModal"', res.text)
        self.assertIn('id="btnProceedUniversalConfirm"', res.text)
        self.assertIn('id="btnCancelUniversalConfirm"', res.text)

    def test_vietnam_timezone_synchronization(self):
        """Verifies that the timezone helper produces accurate Vietnam (GMT+7) timestamps."""
        from src.core.timezone import get_vn_now, format_vn_datetime, VN_TZ
        vn_now = get_vn_now()
        self.assertIsNotNone(vn_now.tzinfo)
        self.assertEqual(str(vn_now.tzinfo), "Asia/Ho_Chi_Minh")

        formatted = format_vn_datetime(vn_now)
        # Formatted string should match HH:MM:SS DD/MM/YYYY
        self.assertRegex(formatted, r"^\d{2}:\d{2}:\d{2} \d{2}/\d{2}/\d{4}$")

        db_ts = format_vn_datetime(vn_now, fmt="%Y-%m-%d %H:%M:%S")
        self.assertRegex(db_ts, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_message_id_normalization_and_deduplication(self):
        """Verifies that Message-ID normalization handles angle brackets, folding, whitespace and case insensitivity."""
        from src.core.migrator import EmailMigrator
        norm = EmailMigrator.normalize_message_id
        target = "db9pr01mb72769729581665005@domain.com"

        self.assertEqual(norm("<DB9PR01MB72769729581665005@domain.com>"), target)
        self.assertEqual(norm("  <db9pr01mb72769729581665005@domain.com>  "), target)
        self.assertEqual(norm("DB9PR01MB72769729581665005@domain.COM"), target)
        self.assertEqual(norm("<DB9PR01MB72769729581665005@domain.com>\r\n"), target)
        self.assertIsNone(norm(None))
        self.assertIsNone(norm(""))

    # -------------------------------------------------------------
    # 6. Microsoft 365 OAuth2 (XOAUTH2) & Entra ID Token Tests
    # -------------------------------------------------------------
    def test_m365_oauth2_client_credentials_and_caching(self):
        """Kiểm tra lấy Access Token tự động qua Entra ID Client Credentials và bộ nhớ đệm TTL."""
        from src.core.models import AccountCredentials
        from src.core.oauth2 import M365OAuth2Provider, OAuth2TokenError

        M365OAuth2Provider.clear_cache()
        creds = AccountCredentials(
            host="outlook.office365.com",
            port=993,
            username="user@tenant.onmicrosoft.com",
            auth_type="XOAUTH2",
            tenant_id="11111111-2222-3333-4444-555555555555",
            client_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            client_secret="super-secret-value",
        )
        self.assertTrue(creds.is_oauth2)
        self.assertTrue(creds.has_valid_auth())

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.mocktoken",
            "expires_in": 3599,
        }

        with patch("src.core.oauth2.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            # Lần 1: Gọi HTTP lấy token từ Entra ID
            token1 = M365OAuth2Provider.resolve_access_token(creds)
            self.assertEqual(token1, "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.mocktoken")
            self.assertEqual(mock_http.post.call_count, 1)

            # Lần 2: Trả về từ bộ nhớ đệm mà không gọi lại HTTP
            token2 = M365OAuth2Provider.resolve_access_token(creds)
            self.assertEqual(token2, token1)
            self.assertEqual(mock_http.post.call_count, 1)

            # Lần 3: force_refresh=True buộc lấy lại token mới
            token3 = M365OAuth2Provider.resolve_access_token(creds, force_refresh=True)
            self.assertEqual(token3, token1)
            self.assertEqual(mock_http.post.call_count, 2)

        # Kiểm tra xử lý lỗi Entra ID AADSTS7000215 (sai Client Secret)
        mock_err_resp = MagicMock()
        mock_err_resp.status_code = 401
        mock_err_resp.json.return_value = {
            "error": "invalid_client",
            "error_description": "AADSTS7000215: Invalid client secret provided.",
        }
        with patch("src.core.oauth2.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = mock_err_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with self.assertRaises(OAuth2TokenError) as ctx:
                M365OAuth2Provider.resolve_access_token(creds, force_refresh=True)
            self.assertIn("Client Secret", str(ctx.exception))

    def test_imap_client_wrapper_xoauth2_login_and_retry(self):
        """Kiểm tra IMAPClientWrapper gọi oauth2_login và tự động làm mới token nếu token cache hết hạn."""
        from imapclient.exceptions import LoginError
        from src.core.imap_client import IMAPClientWrapper
        from src.core.models import AccountCredentials

        creds = AccountCredentials(
            host="outlook.office365.com",
            port=993,
            username="ceo@company.com",
            auth_type="XOAUTH2",
            tenant_id="tenant-123",
            client_id="client-456",
            client_secret="secret-789",
        )

        with patch("src.core.imap_client.IMAPClient") as mock_imap_cls, patch(
            "src.core.imap_client.M365OAuth2Provider.resolve_access_token"
        ) as mock_resolve:
            mock_imap = MagicMock()
            # Giả lập lần đầu oauth2_login thất bại do token cũ, lần 2 thành công
            mock_imap.oauth2_login.side_effect = [LoginError("NO AUTHENTICATE failed"), None]
            mock_imap.capabilities.return_value = [b"IMAP4REV1", b"AUTH=XOAUTH2"]
            mock_imap.namespace.return_value = (((b"", b"/"),), (), ())
            mock_imap_cls.return_value = mock_imap
            mock_resolve.side_effect = ["cached-expired-token", "fresh-new-token"]

            wrapper = IMAPClientWrapper(creds)
            wrapper.connect()

            self.assertEqual(mock_resolve.call_count, 2)
            mock_imap.oauth2_login.assert_any_call("ceo@company.com", "cached-expired-token")
            mock_imap.oauth2_login.assert_called_with("ceo@company.com", "fresh-new-token")


if __name__ == "__main__":
    unittest.main()


