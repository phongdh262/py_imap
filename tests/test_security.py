import os
import unittest
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.security.auth import AdminSecurity, FAILED_ATTEMPTS, MAX_FAILED_ATTEMPTS, verify_admin
from src.security.crypto import SecretManager
from src.security.headers import SecurityHeadersMiddleware
from src.security.path_guard import PathSecurity


class TestSecurityFeatures(unittest.TestCase):
    def setUp(self):
        FAILED_ATTEMPTS.clear()

    def test_mask_secret(self):
        self.assertEqual(SecretManager.mask_secret(""), "")
        self.assertEqual(SecretManager.mask_secret("12345"), "***")
        self.assertEqual(SecretManager.mask_secret("supersecretpassword123"), "sup***123")

    def test_sanitize_log_dict(self):
        payload = {
            "source_user": "admin@example.com",
            "source_password": "supersecretpassword123",
            "metadata": {
                "dest_password": "targetsecretpassword456",
                "normal_field": "safe_value"
            }
        }
        sanitized = SecretManager.sanitize_log_dict(payload)
        self.assertEqual(sanitized["source_user"], "admin@example.com")
        self.assertTrue("***" in sanitized["source_password"])
        self.assertTrue("***" in sanitized["metadata"]["dest_password"])
        self.assertEqual(sanitized["metadata"]["normal_field"], "safe_value")

    def test_path_security_traversal_blocking(self):
        base_dir = Path("/tmp/safe_reports")
        base_dir.mkdir(parents=True, exist_ok=True)

        # 1. Normal valid file
        valid = PathSecurity.validate_safe_path(base_dir, "report_123.html")
        self.assertEqual(valid, (base_dir / "report_123.html").resolve())

        # 2. Block '..' traversal
        with self.assertRaises(HTTPException) as ctx:
            PathSecurity.validate_safe_path(base_dir, "../../../etc/passwd")
        self.assertEqual(ctx.exception.status_code, 400)

        # 3. Block null byte injection
        with self.assertRaises(HTTPException) as ctx:
            PathSecurity.validate_safe_path(base_dir, "report.html\0.exe")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_brute_force_lockout(self):
        client_ip = "192.168.1.100"
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            AdminSecurity.record_failure(client_ip)
            # Should not raise yet
            AdminSecurity.check_brute_force(client_ip)

        # 5th failure triggers lockout
        AdminSecurity.record_failure(client_ip)
        with self.assertRaises(HTTPException) as ctx:
            AdminSecurity.check_brute_force(client_ip)
        self.assertEqual(ctx.exception.status_code, 429)

        # Reset on success
        AdminSecurity.record_success(client_ip)
        # Should now pass without exception
        AdminSecurity.check_brute_force(client_ip)

    def test_web_auth_and_owasp_headers(self):
        os.environ["ENABLE_WEB_AUTH"] = "true"
        os.environ["ADMIN_USERNAME"] = "testadmin"
        os.environ["ADMIN_PASSWORD"] = "testpass123"

        test_app = FastAPI(dependencies=[Depends(verify_admin)])
        test_app.add_middleware(SecurityHeadersMiddleware)

        @test_app.get("/test")
        def protected_endpoint():
            return {"status": "ok"}

        client = TestClient(test_app)

        # Unauthenticated request to /test should return 401
        res = client.get("/test")
        self.assertEqual(res.status_code, 401)
        self.assertIn("WWW-Authenticate", res.headers)

        # Check OWASP security headers are present even on 401
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")

        # Authenticated request with correct credentials
        res_auth = client.get("/test", auth=("testadmin", "testpass123"))
        self.assertEqual(res_auth.status_code, 200)
        self.assertEqual(res_auth.json(), {"status": "ok"})

        # Check with wrong credentials
        res_wrong = client.get("/test", auth=("testadmin", "wrongpassword"))
        self.assertEqual(res_wrong.status_code, 401)

    def test_session_cookie_and_login_flow(self):
        from src.web.server import app

        os.environ["ENABLE_WEB_AUTH"] = "true"
        os.environ["ADMIN_USERNAME"] = "testadmin"
        os.environ["ADMIN_PASSWORD"] = "testpass123"

        client = TestClient(app, follow_redirects=False)

        # 1. Unauthenticated GET /login -> 200 OK HTML
        res_login_page = client.get("/login")
        self.assertEqual(res_login_page.status_code, 200)
        self.assertIn("Py-IMAP Control Center", res_login_page.text)

        # 2. Login with bad credentials -> 401
        res_bad = client.post("/api/login", json={"username": "testadmin", "password": "wrong"})
        self.assertEqual(res_bad.status_code, 401)

        # 3. Login with correct credentials -> 200 and set-cookie
        res_good = client.post("/api/login", json={"username": "testadmin", "password": "testpass123"})
        self.assertEqual(res_good.status_code, 200)
        self.assertIn("admin_session", res_good.cookies)

        # 4. Access protected root / with session cookie
        res_root = client.get("/", cookies=res_good.cookies)
        self.assertEqual(res_root.status_code, 200)

        # 5. Accessing /login with active session redirects to /
        res_already_logged = client.get("/login", cookies=res_good.cookies)
        self.assertEqual(res_already_logged.status_code, 303)
        self.assertEqual(res_already_logged.headers.get("Location"), "/")

        # 6. Logout clears cookie and redirects to /login
        res_logout = client.get("/logout")
        self.assertEqual(res_logout.status_code, 303)
        self.assertEqual(res_logout.headers.get("Location"), "/login")


if __name__ == "__main__":
    unittest.main()
