import csv
import getpass
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from src.core.imap_client import IMAPAuthenticationError, IMAPClientWrapper, IMAPConnectionError
from src.core.models import AccountCredentials
from src.core.service import MigrationService

console = Console()


def show_banner(metrics_port: int = 8000):
    """Displays the stylish Rich banner."""
    console.print(
        Panel.fit(
            "[bold cyan]PY-IMAP EMAIL MIGRATION TOOL (Ubuntu 24.04 LTS)[/bold cyan]\n"
            "[green]Multi-provider support: Gmail, Yandex, Outlook / M365, cPanel, Dovecot[/green]\n"
            f"[yellow]Prometheus Metrics Server listening at:[/yellow] [bold white]http://0.0.0.0:{metrics_port}/metrics[/bold white]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def prompt_account_credentials(title: str = "Account Credentials", default_host: str = "imap.gmail.com") -> AccountCredentials:
    """Interactively prompts user for IMAP credentials with password masking."""
    console.print(f"\n[bold yellow]─── {title} ───[/bold yellow]")
    host = Prompt.ask("Host IMAP (ví dụ: imap.gmail.com, imap.yandex.com, outlook.office365.com)", default=default_host)
    port = IntPrompt.ask("Port IMAP", default=993)
    use_ssl = Confirm.ask("Sử dụng SSL/TLS?", default=True)
    username = Prompt.ask("Email / Tên đăng nhập")
    password = Prompt.ask("Mật khẩu / App Password", password=True)

    return AccountCredentials(
        host=host.strip(),
        port=port,
        ssl=use_ssl,
        username=username.strip(),
        password=password.strip(),
    )


def handle_inspect_mailbox(service: MigrationService):
    """Option 1: Inspect mailbox size and folders."""
    creds = prompt_account_credentials("Nhập thông tin Hộp thư Nguồn cần kiểm tra")
    try:
        with console.status("[bold green]Đang kết nối và tính toán dung lượng...[/bold green]"):
            service.inspect_source(creds)
    except (IMAPAuthenticationError, IMAPConnectionError) as e:
        console.print(f"[bold red]Lỗi kết nối / xác thực:[/bold red] {e}")
    except Exception as e:
        console.print(f"[bold red]Lỗi ngoài dự kiến:[/bold red] {e}")


def handle_migrate_single(service: MigrationService):
    """Option 2: Migrate 1 single account."""
    console.print("[bold cyan]>>> Bước 1: Nhập tài khoản NGUỒN (Source)[/bold cyan]")
    src_creds = prompt_account_credentials("Hộp thư Nguồn (Source)", default_host="imap.gmail.com")

    console.print("\n[bold magenta]>>> Bước 2: Nhập tài khoản ĐÍCH (Destination)[/bold magenta]")
    dst_creds = prompt_account_credentials("Hộp thư Đích (Destination)", default_host="mail.cpanel-domain.com")

    console.print("\n" + "=" * 60)
    console.print(f"[bold]Xác nhận di chuyển:[/bold] [cyan]{src_creds.username}[/cyan] ➔ [green]{dst_creds.username}[/green]")
    if not Confirm.ask("Bắt đầu di chuyển ngay bây giờ?", default=True):
        console.print("[yellow]Đã hủy thao tác.[/yellow]")
        return

    try:
        service.migrate_account(src_creds, dst_creds)
    except Exception as e:
        console.print(f"[bold red]Quá trình di chuyển thất bại:[/bold red] {e}")


def handle_migrate_csv(service: MigrationService):
    """Option 3: Migrate multiple accounts from CSV."""
    default_csv = "config/accounts.example.csv" if not Path("config/accounts.csv").exists() else "config/accounts.csv"
    csv_file = Prompt.ask("Đường dẫn file CSV chứa danh sách tài khoản", default=default_csv)
    path = Path(csv_file)

    if not path.exists():
        console.print(f"[bold red]Lỗi: Không tìm thấy file tại '{csv_file}'[/bold red]")
        return

    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        accounts = list(reader)

    console.print(f"\n[bold green]Đã nạp {len(accounts)} tài khoản từ file CSV.[/bold green]")
    if not Confirm.ask("Bắt đầu di chuyển toàn bộ danh sách?", default=True):
        console.print("[yellow]Đã hủy thao tác.[/yellow]")
        return

    for idx, row in enumerate(accounts, 1):
        console.print(f"\n[bold yellow]══════ Đang xử lý Tài khoản [{idx}/{len(accounts)}] ══════[/bold yellow]")
        src_creds = AccountCredentials(
            host=row["source_host"].strip(),
            port=int(row.get("source_port", 993)),
            ssl=str(row.get("source_ssl", "true")).lower() in ("true", "1"),
            username=row["source_user"].strip(),
            password=row["source_password"].strip(),
        )
        dst_creds = AccountCredentials(
            host=row["dest_host"].strip(),
            port=int(row.get("dest_port", 993)),
            ssl=str(row.get("dest_ssl", "true")).lower() in ("true", "1"),
            username=row["dest_user"].strip(),
            password=row["dest_password"].strip(),
        )
        try:
            service.migrate_account(src_creds, dst_creds)
        except Exception as e:
            console.print(f"[bold red]Lỗi khi di chuyển {src_creds.username}:[/bold red] {e}")


def handle_test_connection():
    """Option 4: Quick IMAP & SSL connection check."""
    creds = prompt_account_credentials("Kiểm tra kết nối IMAP")
    start_time = time.time()
    try:
        with console.status("[bold green]Đang bắt tay SSL và xác thực...[/bold green]"):
            with IMAPClientWrapper(creds) as client:
                latency = round((time.time() - start_time) * 1000, 2)
                caps = client._capabilities

        console.print(
            Panel(
                f"[bold green]✓ Kết nối & Đăng nhập THÀNH CÔNG![/bold green]\n"
                f"[cyan]Độ trễ phản hồi (Latency):[/cyan] {latency} ms\n"
                f"[magenta]Hỗ trợ RFC 6154 (SPECIAL-USE):[/magenta] {'Có' if 'SPECIAL-USE' in caps else 'Không'}\n"
                f"[magenta]Hỗ trợ RFC 2087 (QUOTA):[/magenta] {'Có' if 'QUOTA' in caps else 'Không'}\n"
                f"[magenta]Hỗ trợ RFC 8438 (STATUS=SIZE):[/magenta] {'Có' if 'STATUS=SIZE' in caps else 'Không'}",
                title="Kết Quả Kiểm Tra",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[bold red]✗ Kết nối THẤT BẠI:[/bold red] {e}")


def run_interactive_menu(service: MigrationService, logger):
    """Main interactive menu loop."""
    while True:
        console.print("\n[bold cyan]VUI LÒNG CHỌN TÍNH NĂNG:[/bold cyan]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold yellow")
        table.add_column("Description", style="white")

        table.add_row("[1]", "🔍 Quét dung lượng & thư mục máy chủ nguồn (Pre-flight Inspection)")
        table.add_row("[2]", "🚀 Di chuyển 1 tài khoản trực tiếp (Migrate 1 Account)")
        table.add_row("[3]", "📂 Di chuyển hàng loạt nhiều tài khoản từ file CSV (Batch Migrate)")
        table.add_row("[4]", "⚡ Kiểm tra kết nối IMAP & SSL (Connection Health Check)")
        table.add_row("[5]", "📈 Chạy chế độ Mô phỏng để kiểm tra Grafana Dashboard (Live Simulation)")
        table.add_row("[0]", "❌ Thoát chương trình (Exit)")

        console.print(table)
        choice = Prompt.ask("[bold yellow]Nhập lựa chọn của bạn[/bold yellow]", choices=["1", "2", "3", "4", "5", "0"], default="1")

        if choice == "1":
            handle_inspect_mailbox(service)
        elif choice == "2":
            handle_migrate_single(service)
        elif choice == "3":
            handle_migrate_csv(service)
        elif choice == "4":
            handle_test_connection()
        elif choice == "5":
            from src.main_simulation import run_simulation_loop
            console.print("[green]Đang khởi chạy luồng mô phỏng. Mở Grafana tại http://localhost:3000 để xem dữ liệu...[/green]")
            run_simulation_loop(logger)
        elif choice == "0":
            console.print("[bold yellow]Cảm ơn bạn đã sử dụng Py-IMAP Migrator. Hẹn gặp lại![/bold yellow]")
            sys.exit(0)
