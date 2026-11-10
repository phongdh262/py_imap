import threading
import time
from typing import Dict, Optional, Tuple
import httpx

from src.core.models import AccountCredentials


class OAuth2TokenError(Exception):
    """Raised when acquiring or refreshing an OAuth2 access token fails."""
    pass


class M365OAuth2Provider:
    """
    Microsoft 365 / Microsoft Entra ID (Azure AD) OAuth2 Token Manager for IMAP:
    - Supports App-only Client Credentials flow (scope: https://outlook.office365.com/.default)
    - Supports Delegated Refresh Token flow (scope: https://outlook.office.com/IMAP.AccessAsUser.All)
    - Thread-safe in-memory token cache with automatic expiration buffer (120s before expiry)
    """

    _cache: Dict[Tuple[str, str, str, str], Tuple[str, float]] = {}
    _lock = threading.Lock()
    EXPIRY_BUFFER_SECONDS = 120

    @classmethod
    def resolve_access_token(cls, creds: AccountCredentials, force_refresh: bool = False) -> str:
        """
        Resolves a valid OAuth2 access token from AccountCredentials:
        1. If tenant_id + client_id + client_secret are provided -> Entra ID Client Credentials flow
        2. If client_id + refresh_token are provided -> Entra ID Refresh Token flow
        3. If oauth2_token is provided directly -> returns static/direct access token
        """
        tenant_id = (creds.tenant_id or "").strip()
        client_id = (creds.client_id or "").strip()
        client_secret = (creds.client_secret or "").strip()
        refresh_token = (creds.refresh_token or "").strip()
        direct_token = (creds.oauth2_token or "").strip()

        # Case 1: Microsoft 365 App-Only (Client Credentials)
        if tenant_id and client_id and client_secret and not refresh_token:
            return cls.fetch_client_credentials_token(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                force_refresh=force_refresh,
            )

        # Case 2: OAuth2 Refresh Token Flow (Delegated)
        if client_id and refresh_token:
            return cls.fetch_refresh_token(
                tenant_id=tenant_id or "common",
                client_id=client_id,
                refresh_token=refresh_token,
                client_secret=client_secret or None,
                force_refresh=force_refresh,
            )

        # Case 3: Direct Access Token
        if direct_token:
            return direct_token

        raise OAuth2TokenError(
            "Thiếu thông tin OAuth2: Cần cung cấp bộ (Tenant ID, Client ID, Client Secret) của Microsoft 365 hoặc Access Token trực tiếp."
        )

    @classmethod
    def fetch_client_credentials_token(
        cls,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        scope: str = "https://outlook.office365.com/.default",
        force_refresh: bool = False,
    ) -> str:
        """Acquires an App-only OAuth2 access token from Microsoft Entra ID."""
        cache_key = ("client_credentials", tenant_id, client_id, client_secret)
        now = time.time()

        if not force_refresh:
            with cls._lock:
                cached = cls._cache.get(cache_key)
                if cached and cached[1] > now:
                    return cached[0]

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
            "grant_type": "client_credentials",
        }

        try:
            with httpx.Client(timeout=20.0) as http_client:
                resp = http_client.post(
                    token_url,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.RequestError as exc:
            raise OAuth2TokenError(f"Không thể kết nối máy chủ xác thực Microsoft Entra ID: {exc}") from None

        if resp.status_code != 200:
            err_detail = cls._extract_entra_error(resp)
            raise OAuth2TokenError(f"Lấy Access Token Microsoft 365 thất bại: {err_detail}")

        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise OAuth2TokenError("Phản hồi từ Microsoft Entra ID không chứa access_token.")

        expires_in = int(data.get("expires_in", 3599))
        expires_at = now + max(60, expires_in - cls.EXPIRY_BUFFER_SECONDS)

        with cls._lock:
            cls._cache[cache_key] = (access_token, expires_at)

        return access_token

    @classmethod
    def fetch_refresh_token(
        cls,
        tenant_id: str,
        client_id: str,
        refresh_token: str,
        client_secret: Optional[str] = None,
        scope: str = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
        force_refresh: bool = False,
    ) -> str:
        """Acquires a delegated OAuth2 access token using a refresh_token."""
        cache_key = ("refresh_token", tenant_id, client_id, refresh_token)
        now = time.time()

        if not force_refresh:
            with cls._lock:
                cached = cls._cache.get(cache_key)
                if cached and cached[1] > now:
                    return cached[0]

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            "client_id": client_id,
            "refresh_token": refresh_token,
            "scope": scope,
            "grant_type": "refresh_token",
        }
        if client_secret:
            payload["client_secret"] = client_secret

        try:
            with httpx.Client(timeout=20.0) as http_client:
                resp = http_client.post(
                    token_url,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.RequestError as exc:
            raise OAuth2TokenError(f"Không thể kết nối máy chủ xác thực Microsoft Entra ID: {exc}") from None

        if resp.status_code != 200:
            err_detail = cls._extract_entra_error(resp)
            raise OAuth2TokenError(f"Làm mới Access Token Microsoft 365 thất bại: {err_detail}")

        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise OAuth2TokenError("Phản hồi từ Microsoft Entra ID không chứa access_token.")

        expires_in = int(data.get("expires_in", 3599))
        expires_at = now + max(60, expires_in - cls.EXPIRY_BUFFER_SECONDS)

        with cls._lock:
            cls._cache[cache_key] = (access_token, expires_at)

        return access_token

    @classmethod
    def clear_cache(cls):
        """Clears cached OAuth2 tokens."""
        with cls._lock:
            cls._cache.clear()

    @staticmethod
    def _extract_entra_error(resp: httpx.Response) -> str:
        try:
            body = resp.json()
            err = body.get("error", "")
            desc = body.get("error_description", "")
            if "AADSTS700016" in desc or err == "unauthorized_client":
                return "Sai Client ID (Application ID) hoặc ứng dụng chưa được đăng ký trong Tenant này (AADSTS700016)."
            if "AADSTS7000215" in desc or err == "invalid_client":
                return "Sai Client Secret (chú ý copy cột 'Value' của Secret chứ không phải 'Secret ID' - AADSTS7000215)."
            if "AADSTS90002" in desc:
                return "Sai Tenant ID (Directory ID không tồn tại trên Microsoft Entra ID - AADSTS90002)."
            if desc:
                first_line = desc.splitlines()[0].strip()
                return f"{err} - {first_line}" if err else first_line
            return err or f"HTTP {resp.status_code}"
        except Exception:
            return f"HTTP {resp.status_code}: {resp.text[:200]}"
