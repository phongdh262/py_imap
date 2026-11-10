import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.imap_client import IMAPAuthenticationError, IMAPClientWrapper, IMAPConnectionError
from src.core.models import AccountCredentials, AuthType
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import ACCOUNT_AUTH_STATUS, AUTH_CHECKS_TOTAL

console = Console()
logger = setup_logging()


@dataclass
class AuthCheckResult:
    username: str
    host: str
    is_valid: bool
    latency_ms: float = 0.0
    error_reason: str = ""
    provider_hint: str = ""


class AuthChecker:
    """
    Dedicated checker for IMAP credentials & App Passwords (Mật khẩu ứng dụng):
    - Fast SSL handshake & login verification
    - Detects provider-specific error hints (Gmail App Password, Yandex App Pass, M365 Modern Auth)
    - Concurrently verifies multiple accounts in parallel
    - Updates Prometheus metrics and exports rich terminal tables
    """

    def check_single(self, creds: AccountCredentials) -> AuthCheckResult:
        """Verifies a single account's credentials and records metrics."""
        start_time = time.time()
        try:
            with IMAPClientWrapper(creds) as client:
                latency = round((time.time() - start_time) * 1000, 2)

                # Prometheus metrics
                AUTH_CHECKS_TOTAL.labels(account=creds.username, host=creds.host, status="success").inc()
                ACCOUNT_AUTH_STATUS.labels(account=creds.username, host=creds.host, error_reason="none").set(1)

                logger.info(
                    "App Password check passed",
                    account=creds.username,
                    host=creds.host,
                    latency_ms=latency,
                )
                return AuthCheckResult(
                    username=creds.username,
                    host=creds.host,
                    is_valid=True,
                    latency_ms=latency,
                )

        except (IMAPAuthenticationError, IMAPConnectionError) as e:
            latency = round((time.time() - start_time) * 1000, 2)
            err_msg = str(e)
            hint = self._detect_provider_hint(creds.host, err_msg)

            # Prometheus metrics
            AUTH_CHECKS_TOTAL.labels(account=creds.username, host=creds.host, status="failed").inc()
            ACCOUNT_AUTH_STATUS.labels(account=creds.username, host=creds.host, error_reason=hint or "auth_failed").set(0)

            logger.error(
                "App Password check failed",
                account=creds.username,
                host=creds.host,
                error_detail=err_msg,
                hint=hint,
            )
            return AuthCheckResult(
                username=creds.username,
                host=creds.host,
                is_valid=False,
                latency_ms=latency,
                error_reason=err_msg,
                provider_hint=hint,
            )
        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            AUTH_CHECKS_TOTAL.labels(account=creds.username, host=creds.host, status="failed").inc()
            ACCOUNT_AUTH_STATUS.labels(account=creds.username, host=creds.host, error_reason="unexpected_error").set(0)
            return AuthCheckResult(
                username=creds.username,
                host=creds.host,
                is_valid=False,
                latency_ms=latency,
                error_reason=str(e),
                provider_hint="Kiểm tra lại cấu hình mạng hoặc Firewall máy chủ",
            )

    def check_multiple(self, accounts: List[AccountCredentials], max_workers: int = 5) -> List[AuthCheckResult]:
        """Concurrently checks a list of accounts using thread pool."""
        results: List[AuthCheckResult] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_acc = {executor.submit(self.check_single, acc): acc for acc in accounts}
            for future in as_completed(future_to_acc):
                res = future.result()
                results.append(res)

        return results

    def check_from_csv(self, csv_path: str, check_target: str = "both") -> List[AuthCheckResult]:
        """
        Reads accounts from CSV and verifies credentials.
        check_target: 'source', 'dest', or 'both'
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {csv_path}")

        accounts_to_check: List[AccountCredentials] = []
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if check_target in ("source", "both") and row.get("source_user"):
                    src_auth_raw = (row.get("source_auth_type") or "PLAIN").strip().upper()
                    src_auth = AuthType.XOAUTH2 if src_auth_raw == "XOAUTH2" else AuthType.PLAIN
                    accounts_to_check.append(
                        AccountCredentials(
                            host=row["source_host"].strip(),
                            port=int(row.get("source_port", 993)),
                            ssl=str(row.get("source_ssl", "true")).lower() in ("true", "1"),
                            username=row["source_user"].strip(),
                            password=(row.get("source_password") or "").strip() or None,
                            auth_type=src_auth,
                            oauth2_token=(row.get("source_oauth2_token") or "").strip() or None,
                            tenant_id=(row.get("source_tenant_id") or "").strip() or None,
                            client_id=(row.get("source_client_id") or "").strip() or None,
                            client_secret=(row.get("source_client_secret") or "").strip() or None,
                        )
                    )
                if check_target in ("dest", "both") and row.get("dest_user"):
                    dst_auth_raw = (row.get("dest_auth_type") or "PLAIN").strip().upper()
                    dst_auth = AuthType.XOAUTH2 if dst_auth_raw == "XOAUTH2" else AuthType.PLAIN
                    accounts_to_check.append(
                        AccountCredentials(
                            host=row["dest_host"].strip(),
                            port=int(row.get("dest_port", 993)),
                            ssl=str(row.get("dest_ssl", "true")).lower() in ("true", "1"),
                            username=row["dest_user"].strip(),
                            password=(row.get("dest_password") or "").strip() or None,
                            auth_type=dst_auth,
                            oauth2_token=(row.get("dest_oauth2_token") or "").strip() or None,
                            tenant_id=(row.get("dest_tenant_id") or "").strip() or None,
                            client_id=(row.get("dest_client_id") or "").strip() or None,
                            client_secret=(row.get("dest_client_secret") or "").strip() or None,
                        )
                    )

        console.print(f"[bold cyan]Đang kiểm tra đồng thời {len(accounts_to_check)} tài khoản...[/bold cyan]")
        results = self.check_multiple(accounts_to_check)
        self.render_results_table(results)
        return results

    def render_results_table(self, results: List[AuthCheckResult]):
        """Renders results table in terminal."""
        table = Table(title="Kết Quả Kiểm Tra Mật Khẩu Ứng Dụng / IMAP", show_header=True, header_style="bold magenta")
        table.add_column("Tài khoản", style="cyan")
        table.add_column("Host IMAP", style="white")
        table.add_column("Trạng thái", justify="center")
        table.add_column("Độ trễ", justify="right")
        table.add_column("Ghi chú / Hướng dẫn khắc phục", style="yellow")

        valid_count = 0
        failed_count = 0

        for r in results:
            if r.is_valid:
                valid_count += 1
                status = "[bold green]✓ HỢP LỆ[/bold green]"
                note = "[green]Mật khẩu ứng dụng hoạt động tốt[/green]"
            else:
                failed_count += 1
                status = "[bold red]✗ THẤT BẠI[/bold red]"
                note = r.provider_hint or r.error_reason[:60]

            table.add_row(r.username, r.host, status, f"{r.latency_ms} ms", note)

        console.print(table)

        # Summary panel
        console.print(
            Panel(
                f"[bold]Tổng số tài khoản:[/bold] {len(results)}\n"
                f"[bold green]Hợp lệ:[/bold green] {valid_count}\n"
                f"[bold red]Thất bại / Sai mật khẩu:[/bold red] {failed_count}",
                title="Tổng kết Kiểm Tra Mật Khẩu",
                border_style="green" if failed_count == 0 else "red",
            )
        )

    @staticmethod
    def _detect_provider_hint(host: str, error_msg: str) -> str:
        """Detects specific error causes for major providers."""
        lower_err = error_msg.lower()
        lower_host = host.lower()

        if "gmail.com" in lower_host or "google" in lower_host:
            if "application-specific password" in lower_err or "web login required" in lower_err:
                return "Cần tạo 'Mật khẩu ứng dụng' (App Password) trong Google Account > Security > 2-Step Verification"
            if "invalid credentials" in lower_err:
                return "Sai email hoặc mật khẩu ứng dụng (lưu ý không dùng mật khẩu chính nếu bật 2FA)"

        if "yandex" in lower_host:
            if "authentication failed" in lower_err:
                return "Cần tạo Mật khẩu ứng dụng tại Yandex ID > Security > App Passwords"

        if "office365.com" in lower_host or "outlook" in lower_host:
            if "aadsts" in lower_err or "oauth2" in lower_err or "access token" in lower_err:
                return "Kiểm tra lại Tenant ID, Client ID, Client Secret và quyền API Office 365 Exchange Online > IMAP.AccessAsApp (Admin Consent)"
            if "authenticate failed" in lower_err:
                return "Token OAuth2 hợp lệ nhưng chưa cấp quyền Service Principal cho mailbox (Add-MailboxPermission FullAccess) hoặc chưa bật IMAP cho user trong Exchange Admin"
            if "basic auth" in lower_err or "denied" in lower_err or "login failed" in lower_err:
                return "Microsoft 365 yêu cầu xác thực OAuth2 (XOAUTH2). Hãy chuyển Phương thức xác thực sang OAuth2 (Microsoft 365 Entra ID)"

        return "Sai thông tin đăng nhập hoặc IMAP chưa được bật trên máy chủ"
