import os
import secrets
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security_basic = HTTPBasic()

# In-memory brute force tracker: {client_ip: (failed_count, lockout_until_timestamp)}
FAILED_ATTEMPTS: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes


class AdminSecurity:
    """
    Manages Web Admin authentication and brute-force protection:
    - Constant-time password verification via secrets.compare_digest
    - IP-based rate-limiting & temporary lockout on repeated failed logins
    """

    @staticmethod
    def get_admin_credentials() -> Tuple[str, str]:
        """Loads admin credentials from environment or defaults."""
        user = os.environ.get("ADMIN_USERNAME", "admin")
        pwd = os.environ.get("ADMIN_PASSWORD", "admin123")
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


def verify_admin(request: Request, credentials: Optional[HTTPBasicCredentials] = Depends(HTTPBasic(auto_error=False))):
    """FastAPI Dependency for protecting endpoints with HTTP Basic Authentication."""
    enable_auth = os.environ.get("ENABLE_WEB_AUTH", "true").lower() in ("true", "1")
    if not enable_auth:
        return "anonymous"

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu đăng nhập quản trị viên",
            headers={"WWW-Authenticate": "Basic"},
        )

    client_ip = request.client.host if request.client else "127.0.0.1"
    AdminSecurity.check_brute_force(client_ip)

    expected_user, expected_pwd = AdminSecurity.get_admin_credentials()

    user_correct = secrets.compare_digest(credentials.username.encode("utf-8"), expected_user.encode("utf-8"))
    pwd_correct = secrets.compare_digest(credentials.password.encode("utf-8"), expected_pwd.encode("utf-8"))

    if not (user_correct and pwd_correct):
        AdminSecurity.record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu quản trị không đúng",
            headers={"WWW-Authenticate": "Basic"},
        )

    AdminSecurity.record_success(client_ip)
    return credentials.username
