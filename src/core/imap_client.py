import ssl
from typing import List, Optional, Set
from imapclient import IMAPClient
from imapclient.exceptions import LoginError, ProtocolError

from src.core.models import AccountCredentials, AuthType
from src.core.oauth2 import M365OAuth2Provider, OAuth2TokenError


class IMAPConnectionError(Exception):
    """Raised when connecting or handshaking with IMAP host fails."""
    pass


class IMAPAuthenticationError(Exception):
    """Raised when authentication (Password or OAuth2) fails."""
    pass


class IMAPClientWrapper:
    """
    Robust IMAP4_SSL Client wrapper providing:
    - TLS 1.2 / TLS 1.3 with SNI support
    - Password / App-password and XOAUTH2 authentication
    - Server capability inspection (SPECIAL-USE, QUOTA, STATUS=SIZE)
    - Auto reconnect & graceful context manager termination
    """

    def __init__(self, creds: AccountCredentials):
        self.creds = creds
        self.client: Optional[IMAPClient] = None
        self._capabilities: Set[str] = set()

    def connect(self) -> "IMAPClientWrapper":
        """Establishes SSL connection and performs authentication."""
        try:
            # Build secure TLS context enforcing TLS 1.2+
            ssl_context = None
            if self.creds.ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED

            self.client = IMAPClient(
                host=self.creds.host,
                port=self.creds.port,
                ssl=self.creds.ssl,
                ssl_context=ssl_context,
                timeout=self.creds.timeout,
                use_uid=True,
            )

            # Authenticate based on auth type / OAuth2 configuration
            if self.creds.is_oauth2:
                token = M365OAuth2Provider.resolve_access_token(self.creds)
                try:
                    self.client.oauth2_login(self.creds.username, token)
                except (LoginError, ProtocolError):
                    # If dynamic OAuth2 credentials are used, force refresh once in case cached token expired
                    if (self.creds.tenant_id and self.creds.client_id and self.creds.client_secret) or (
                        self.creds.client_id and self.creds.refresh_token
                    ):
                        token = M365OAuth2Provider.resolve_access_token(self.creds, force_refresh=True)
                        self.client.oauth2_login(self.creds.username, token)
                    else:
                        raise
            else:
                if not self.creds.password:
                    raise IMAPAuthenticationError("Password/App-password is required.")
                self.client.login(self.creds.username, self.creds.password)

            # Cache capabilities (in uppercase)
            raw_caps = self.client.capabilities()
            self._capabilities = {c.decode("latin-1").upper() if isinstance(c, bytes) else str(c).upper() for c in raw_caps}

            return self

        except OAuth2TokenError as e:
            clean_err = self._mask_sensitive(str(e))
            raise IMAPAuthenticationError(f"OAuth2 failed for {self.creds.username} on {self.creds.host}: {clean_err}") from None
        except LoginError as e:
            clean_err = self._mask_sensitive(str(e))
            raise IMAPAuthenticationError(f"Login failed for {self.creds.username} on {self.creds.host}: {clean_err}") from None
        except (ProtocolError, ssl.SSLError, OSError) as e:
            clean_err = self._mask_sensitive(str(e))
            raise IMAPConnectionError(f"Cannot connect to IMAP host {self.creds.host}:{self.creds.port}: {clean_err}") from None

    def _mask_sensitive(self, message: str) -> str:
        """Masks passwords, client secrets, and tokens in error messages."""
        clean = message
        for secret in (
            self.creds.password,
            self.creds.client_secret,
            self.creds.oauth2_token,
            self.creds.refresh_token,
        ):
            if secret:
                clean = clean.replace(secret, "***")
        return clean

    def has_capability(self, capability: str) -> bool:
        """Checks if server announced a specific RFC capability."""
        return capability.upper() in self._capabilities

    @property
    def supports_special_use(self) -> bool:
        """RFC 6154: Special-Use Mailboxes."""
        return self.has_capability("SPECIAL-USE")

    @property
    def supports_quota(self) -> bool:
        """RFC 2087: IMAP4 QUOTA extension."""
        return self.has_capability("QUOTA")

    @property
    def supports_status_size(self) -> bool:
        """RFC 8438: STATUS=SIZE extension."""
        return self.has_capability("STATUS=SIZE")

    def disconnect(self):
        """Gracefully logs out and closes the IMAP socket."""
        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass
            finally:
                self.client = None

    def __enter__(self) -> "IMAPClientWrapper":
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
