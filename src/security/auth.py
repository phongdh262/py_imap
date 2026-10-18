import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security_basic = HTTPBasic(auto_error=False, realm="Py-IMAP Admin")

# In-memory brute force tracker: {client_ip: (failed_count, lockout_until_timestamp)}
FAILED_ATTEMPTS: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes

SESSION_SECRET = os.environ.get("SESSION_SECRET", "py_imap_secure_session_secret_2026")
COOKIE_NAME = "admin_session"
SESSION_MAX_AGE_SECONDS = 86400 * 7  # 7 days


def create_session_token(username: str) -> str:
    """Creates a cryptographically signed session token for the user."""
    timestamp = int(time.time())
    payload = f"{username}:{timestamp}"
    signature = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> Optional[str]:
    """Verifies HMAC signature and expiration of a session token."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        username, timestamp_str, sig = parts
        timestamp = int(timestamp_str)
        # Check token expiration
        if time.time() - timestamp > SESSION_MAX_AGE_SECONDS:
            return None
        expected_payload = f"{username}:{timestamp}"
        expected_sig = hmac.new(SESSION_SECRET.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()
        if secrets.compare_digest(sig, expected_sig):
            return username
    except Exception:
        return None
    return None


class AdminSecurity:
    """
    Manages Web Admin authentication and brute-force protection:
    - Constant-time password verification via secrets.compare_digest
    - IP-based rate-limiting & temporary lockout on repeated failed logins
    """

    @staticmethod
    def get_admin_credentials() -> Tuple[str, str]:
        """Loads admin credentials from environment or defaults, stripping quotes/whitespace."""
        user = os.environ.get("ADMIN_USERNAME", "admin").strip().strip('"').strip("'")
        pwd = os.environ.get("ADMIN_PASSWORD", "admin123").strip().strip('"').strip("'")
        return user, pwd

    @classmethod
    def check_brute_force(cls, client_ip: str):
        """Checks if client IP is currently locked out."""
        failed_count, lockout_until = FAILED_ATTEMPTS[client_ip]
        now = time.time()
        if now < lockout_until:
            remaining = int(lockout_until - now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Quá nhiều lần đăng nhập sai. Vui lòng thử lại sau {remaining} giây.",
            )

    @classmethod
    def record_failure(cls, client_ip: str):
        """Increments failed attempts and triggers lockout if threshold reached."""
        failed_count, _ = FAILED_ATTEMPTS[client_ip]
        failed_count += 1
        now = time.time()
        if failed_count >= MAX_FAILED_ATTEMPTS:
            FAILED_ATTEMPTS[client_ip] = (failed_count, now + LOCKOUT_DURATION_SECONDS)
        else:
            FAILED_ATTEMPTS[client_ip] = (failed_count, 0.0)

    @classmethod
    def record_success(cls, client_ip: str):
        """Resets failed count on successful login."""
        if client_ip in FAILED_ATTEMPTS:
            del FAILED_ATTEMPTS[client_ip]


def verify_admin(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(security_basic),
):
    """
    FastAPI Dependency for protecting endpoints:
    1. Public routes (/login, /api/login, /logout, /static/*) pass through.
    2. Checks signed cookie session (admin_session).
    3. Checks HTTP Basic Auth (for automated tests and CLI clients).
    4. If unauthenticated HTML request, redirects to /login.
    """
    path = request.url.path

    # Public exemptions
    if path in ("/login", "/api/login", "/logout") or path.startswith("/static"):
        return "public"

    enable_auth = os.environ.get("ENABLE_WEB_AUTH", "true").lower() in ("true", "1")
    if not enable_auth:
        return "anonymous"

    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Check Cookie Session
    session_cookie = request.cookies.get(COOKIE_NAME)
    if session_cookie:
        valid_user = verify_session_token(session_cookie)
        if valid_user:
            return valid_user

    # 2. Check HTTP Basic Auth (automated tests / scripts)
    if credentials:
        AdminSecurity.check_brute_force(client_ip)
        expected_user, expected_pwd = AdminSecurity.get_admin_credentials()

        user_correct = secrets.compare_digest(credentials.username.strip().encode("utf-8"), expected_user.encode("utf-8"))
        pwd_correct = secrets.compare_digest(credentials.password.encode("utf-8"), expected_pwd.encode("utf-8"))

        if user_correct and pwd_correct:
            AdminSecurity.record_success(client_ip)
            return credentials.username

        AdminSecurity.record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu quản trị không đúng",
            headers={"WWW-Authenticate": 'Basic realm="Py-IMAP Admin"'},
        )

    # 3. Not authenticated
    accept_header = request.headers.get("accept", "")
    # If browser requesting HTML page (and not API call), redirect to /login
    if "text/html" in accept_header and not path.startswith("/api/"):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    # API / non-HTML requests return 401
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Yêu cầu đăng nhập quản trị viên",
        headers={"WWW-Authenticate": 'Basic realm="Py-IMAP Admin"'},
    )
