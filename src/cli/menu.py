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

    console.print("\n[bold yellow]>>> Tùy chọn nâng cao:[/bold yellow]")
    sanitize_accents = Confirm.ask(
        "Chuyển tên thư mục tiếng Việt thành không dấu (để chống lỗi ký tự lạ trên cPanel/Yandex)?",
        default=False
    )
    delay_ms = IntPrompt.ask("Độ trễ chống block IP giữa các batch (milliseconds)", default=50)

    console.print("\n" + "=" * 60)
    console.print(f"[bold]Xác nhận di chuyển:[/bold] [cyan]{src_creds.username}[/cyan] ➔ [green]{dst_creds.username}[/green]")
    if not Confirm.ask("Bắt đầu di chuyển ngay bây giờ?", default=True):
        console.print("[yellow]Đã hủy thao tác.[/yellow]")
        return

    # Update service options
    service.mapper.sanitize_accents = sanitize_accents
    service.throttler.batch_delay = delay_ms / 1000.0

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


from src.core.auth_checker import AuthChecker


def handle_check_app_passwords():
    """Check App Passwords for 1 or multiple accounts."""
    console.print("\n[bold cyan]KIỂM TRA MẬT KHẨU ỨNG DỤNG / IMAP:[/bold cyan]")
    console.print("  [1] Kiểm tra 1 tài khoản đơn lẻ")
    console.print("  [2] Kiểm tra hàng loạt từ file CSV")
    sub_choice = Prompt.ask("Chọn chế độ kiểm tra", choices=["1", "2"], default="1")

    checker = AuthChecker()

    if sub_choice == "1":
        creds = prompt_account_credentials("Nhập thông tin tài khoản cần kiểm tra mật khẩu ứng dụng")
        with console.status("[bold green]Đang kiểm tra mật khẩu ứng dụng...[/bold green]"):
            res = checker.check_single(creds)
        checker.render_results_table([res])
    else:
        default_csv = "config/accounts.example.csv" if not Path("config/accounts.csv").exists() else "config/accounts.csv"
        csv_file = Prompt.ask("Đường dẫn file CSV", default=default_csv)
        target = Prompt.ask("Kiểm tra cột nào trong CSV? (source=Nguồn, dest=Đích, both=Cả hai)", choices=["both", "source", "dest"], default="both")
        try:
            checker.check_from_csv(csv_file, check_target=target)
        except Exception as e:
            console.print(f"[bold red]Lỗi khi đọc file CSV:[/bold red] {e}")


def handle_test_connection():
    """Quick IMAP & SSL connection check."""
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


from src.core.retry_engine import RetryEngine


def handle_retry_failed_messages(service: MigrationService):
    """Retry failed messages from past migration sessions."""
    retry_engine = RetryEngine(service.state_db, service.throttler)
    sessions = retry_engine.list_failed_sessions()

    if not sessions:
        console.print("[bold green]Tuyệt vời! Không tìm thấy phiên di chuyển nào có thư bị lỗi.[/bold green]")
        return

    table = Table(title="Danh Sách Phiên Di Chuyển Có Thư Bị Lỗi", show_header=True, header_style="bold yellow")
    table.add_column("Mã Phiên (ID)", justify="center", style="bold cyan")
    table.add_column("Nguồn ➔ Đích", style="white")
    table.add_column("Số Thư Lỗi", justify="right", style="bold red")
    table.add_column("Thời Gian", style="dim")

    for s in sessions:
        table.add_row(
            str(s["id"]),
            f"{s['source_account']} ➔ {s['dest_account']}",
            str(s["failed_messages"]),
            str(s.get("started_at", ""))[:19]
        )
    console.print(table)

    session_id = IntPrompt.ask("Nhập Mã Phiên (ID) bạn muốn thử lại (Retry)")
    selected = next((s for s in sessions if s["id"] == session_id), None)
    if not selected:
        console.print(f"[bold red]Không tìm thấy phiên ID #{session_id}[/bold red]")
        return

    console.print(f"\n[bold yellow]Cung cấp mật khẩu xác thực cho phiên #{session_id}:[/bold yellow]")
    src_creds = prompt_account_credentials(f"Nguồn: {selected['source_account']}")
    dst_creds = prompt_account_credentials(f"Đích: {selected['dest_account']}")

    retry_engine.retry_session(session_id, src_creds, dst_creds)


def run_interactive_menu(service: MigrationService, logger):
    """Main interactive menu loop."""
    while True:
        console.print("\n[bold cyan]VUI LÒNG CHỌN TÍNH NĂNG:[/bold cyan]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold yellow")
        table.add_column("Description", style="white")

        table.add_row("[1]", "🔍 Quét dung lượng & thư mục máy chủ nguồn (Pre-flight Inspection)")
        table.add_row("[2]", "🔑 Kiểm tra Mật khẩu ứng dụng 1 hoặc nhiều tài khoản (App Password Checker)")
        table.add_row("[3]", "🚀 Di chuyển 1 tài khoản trực tiếp (Migrate 1 Account)")
        table.add_row("[4]", "📂 Di chuyển hàng loạt nhiều tài khoản từ file CSV (Batch Migrate)")
        table.add_row("[5]", "🔁 Thử lại các email bị lỗi từ phiên trước (Retry Failed Messages)")
        table.add_row("[6]", "⚡ Kiểm tra kết nối IMAP & SSL (Connection Health Check)")
        table.add_row("[7]", "📈 Chạy chế độ Mô phỏng để kiểm tra Grafana Dashboard (Live Simulation)")
        table.add_row("[8]", "🌐 Khởi chạy Giao diện Web Admin Control Panel (http://localhost:8080)")
        table.add_row("[0]", "❌ Thoát chương trình (Exit)")

        console.print(table)
        choice = Prompt.ask("[bold yellow]Nhập lựa chọn của bạn[/bold yellow]", choices=["1", "2", "3", "4", "5", "6", "7", "8", "0"], default="1")

        if choice == "1":
            handle_inspect_mailbox(service)
        elif choice == "2":
            handle_check_app_passwords()
        elif choice == "3":
            handle_migrate_single(service)
        elif choice == "4":
            handle_migrate_csv(service)
        elif choice == "5":
            handle_retry_failed_messages(service)
        elif choice == "6":
            handle_test_connection()
        elif choice == "7":
            from src.main_simulation import run_simulation_loop
            console.print("[green]Đang khởi chạy luồng mô phỏng. Mở Grafana tại http://localhost:3000 để xem dữ liệu...[/green]")
            run_simulation_loop(logger)
        elif choice == "8":
            from src.web.server import start_web_server
            console.print("[bold green]🚀 Đang khởi chạy Web Admin Panel tại http://0.0.0.0:8080 (Bấm Ctrl+C để dừng)...[/bold green]")
            start_web_server(port=8080)
        elif choice == "0":
            console.print("[bold yellow]Cảm ơn bạn đã sử dụng Py-IMAP Migrator. Hẹn gặp lại![/bold yellow]")
            sys.exit(0)
