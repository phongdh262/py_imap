import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.storage.state_db import StateDatabase


class MigrationReporter:
    """
    Generates professional, responsive HTML and CSV audit reports:
    - Summary stat cards (Success, Failed, Skipped, Size, Speed)
    - Folder breakdown table
    - Complete failed message drill-down table with error reasons
    - CSV export for failed messages
    """

    def __init__(self, state_db: StateDatabase, output_dir: str = "reports"):
        self.state_db = state_db
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_reports(self, migration_id: int) -> tuple[Path, Optional[Path]]:
        """
        Generates both HTML summary and CSV failure reports.
        Returns: (html_path, csv_path_if_failed_exists)
        """
        summary = self.state_db.get_migration_summary(migration_id)
        if not summary:
            raise ValueError(f"Migration ID {migration_id} not found in state database.")

        failed_items = self.state_db.get_failed_messages(migration_id)
        folder_stats = self.state_db.get_folder_statistics(migration_id)

        clean_account = summary["source_account"].replace("@", "_at_").replace(".", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. Generate HTML Report
        html_file = self.output_dir / f"report_{clean_account}_{timestamp}.html"
        html_content = self._build_html(summary, folder_stats, failed_items)
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 2. Generate CSV if there are failed items
        csv_file = None
        if failed_items:
            csv_file = self.output_dir / f"failures_{clean_account}_{timestamp}.csv"
            self._build_csv(csv_file, failed_items)

        return html_file, csv_file

    def _build_csv(self, file_path: Path, failed_items: List[Dict[str, Any]]):
        """Writes failed items to a CSV file."""
        fieldnames = ["folder", "source_uid", "message_id", "sender", "subject", "date_str", "size_bytes", "error_code", "error_detail"]
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in failed_items:
                writer.writerow(item)

    def _build_html(
        self, summary: Dict[str, Any], folder_stats: List[Dict[str, Any]], failed_items: List[Dict[str, Any]]
    ) -> str:
        """Constructs a responsive modern HTML document."""
        transferred_mb = round(summary.get("transferred_bytes", 0) / (1024 * 1024), 2)
        transferred_gb = round(transferred_mb / 1024, 3)

        success_count = summary.get("migrated_messages", 0)
        failed_count = summary.get("failed_messages", 0)
        skipped_count = summary.get("skipped_messages", 0)
        total_count = summary.get("total_messages", 0)

        # Folder table rows
        folder_rows = ""
        for fs in folder_stats:
            size_mb = round((fs.get("total_size") or 0) / (1024 * 1024), 2)
            folder_rows += f"""
            <tr>
                <td><strong>{fs['folder']}</strong></td>
                <td style="text-align: right;">{fs['total']}</td>
                <td style="text-align: right; color: #10b981;">{fs['success']}</td>
                <td style="text-align: right; color: #ef4444;">{fs['failed']}</td>
                <td style="text-align: right;">{size_mb} MB</td>
            </tr>
            """

        # Failed items rows
        failed_rows = ""
        if failed_items:
            for item in failed_items:
                subj = (item.get("subject") or "(No Subject)")[:50]
                failed_rows += f"""
                <tr>
                    <td><code>{item['folder']}</code></td>
                    <td>{item['source_uid']}</td>
                    <td>{item.get('sender') or 'Unknown'}</td>
                    <td>{subj}</td>
                    <td>{item.get('date_str') or '-'}</td>
                    <td><span class="badge badge-danger">{item.get('error_code')}</span></td>
                    <td class="text-danger-detail">{item.get('error_detail') or ''}</td>
                </tr>
                """
        else:
            failed_rows = """<tr><td colspan="7" style="text-align: center; color: #10b981; padding: 20px;">✓ Không có email nào bị lỗi! Tất cả đều di chuyển thành công.</td></tr>"""

        return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Migration Audit Report - {summary['source_account']}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
            --primary: #3b82f6;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 24px;
            color: #60a5fa;
        }}
        .header .meta {{
            color: var(--text-muted);
            font-size: 14px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
        }}
        .card .title {{
            font-size: 13px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        .card .value {{
            font-size: 28px;
            font-weight: bold;
        }}
        .text-success {{ color: var(--success); }}
        .text-danger {{ color: var(--danger); }}
        .text-warning {{ color: var(--warning); }}
        .text-primary {{ color: var(--primary); }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            background: var(--card-bg);
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }}
        th {{
            background: #243248;
            color: var(--text-muted);
            font-weight: 600;
        }}
        tr:hover {{
            background: rgba(255, 255, 255, 0.02);
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-danger {{
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }}
        .text-danger-detail {{
            color: #fca5a5;
            font-size: 12px;
        }}
        h2 {{
            font-size: 18px;
            color: #cbd5e1;
            margin-top: 32px;
            margin-bottom: 12px;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: var(--text-muted);
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Email Migration Audit & Verification Report</h1>
            <div class="meta">
                <strong>Nguồn:</strong> {summary['source_account']} ➔ <strong>Đích:</strong> {summary['dest_account']}<br>
                <strong>Bắt đầu:</strong> {summary.get('started_at')} | <strong>Hoàn thành:</strong> {summary.get('completed_at') or 'Đang xử lý'}<br>
                <strong>Trạng thái:</strong> <span class="badge badge-{'success' if failed_count == 0 else 'danger'}">{summary.get('status')}</span>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="title">Thành Công (Migrated)</div>
                <div class="value text-success">{success_count}</div>
            </div>
            <div class="card">
                <div class="title">Bỏ Qua (Đã tồn tại / Resume)</div>
                <div class="value text-primary">{skipped_count}</div>
            </div>
            <div class="card">
                <div class="title">Thất Bại (Failed)</div>
                <div class="value text-danger">{failed_count}</div>
            </div>
            <div class="card">
                <div class="title">Dung Lượng Đã Chuyển</div>
                <div class="value text-warning">{transferred_mb} <span style="font-size: 16px;">MB</span> ({transferred_gb} GB)</div>
            </div>
        </div>

        <h2>Thống Kê Chi Tiết Theo Thư Mục</h2>
        <table>
            <thead>
                <tr>
                    <th>Thư Mục</th>
                    <th style="text-align: right;">Đã Xử Lý</th>
                    <th style="text-align: right;">Thành Công</th>
                    <th style="text-align: right;">Thất Bại</th>
                    <th style="text-align: right;">Dung Lượng</th>
                </tr>
            </thead>
            <tbody>
                {folder_rows}
            </tbody>
        </table>

        <h2>Danh Sách Email Thất Bại & Nguyên Nhân ({len(failed_items)} Thư)</h2>
        <table>
            <thead>
                <tr>
                    <th>Thư mục</th>
                    <th>UID</th>
                    <th>Người gửi</th>
                    <th>Tiêu đề</th>
                    <th>Ngày</th>
                    <th>Mã lỗi</th>
                    <th>Chi tiết lỗi</th>
                </tr>
            </thead>
            <tbody>
                {failed_rows}
            </tbody>
        </table>

        <div class="footer">
            Báo cáo được sinh tự động bởi <strong>Py-IMAP Migration Engine</strong> | Ubuntu 24.04 LTS
        </div>
    </div>
</body>
</html>
"""
