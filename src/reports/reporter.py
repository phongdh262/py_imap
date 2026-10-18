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
                subj = (item.get("subject") or "(Không có tiêu đề)")[:55]
                sender = (item.get("sender") or "Unknown")[:30]
                raw_err = item.get("error_detail") or ""
                
                # Simplify and humanize error message
                err_text = raw_err
                if "nonexistent namespace" in raw_err.lower() or "prefixed with: inbox" in raw_err.lower():
                    err_text = "Cần tiền tố INBOX. (Bấm 'Thử lại' để nạp tự động)"
                elif "already exists" in raw_err.lower() or "alreadyexists" in raw_err.lower():
                    err_text = "Thư hoặc thư mục đã tồn tại trên đích"
                elif len(err_text) > 110:
                    err_text = err_text[:110] + "..."

                failed_rows += f"""
                <tr>
                    <td><code>{item['folder']}</code></td>
                    <td style="font-family: 'JetBrains Mono', monospace; font-size: 11px;">{item['source_uid']}</td>
                    <td><span title="{item.get('sender') or ''}">{sender}</span></td>
                    <td>{subj}</td>
                    <td style="text-align: center;"><span class="badge badge-danger">{item.get('error_code')}</span></td>
                    <td style="color: var(--accent-danger); font-size: 11.5px;">{err_text}</td>
                </tr>
                """
        else:
            failed_rows = """<tr><td colspan="6" style="text-align: center; color: var(--accent-success); padding: 20px;">✓ Không có email nào bị lỗi. Toàn bộ thư mục đã được di chuyển thành công 100%.</td></tr>"""

        # Dynamic concise summary note
        if failed_count == 0:
            summary_note_html = f"""
            <div class="summary-note note-success">
                <span class="note-icon">✓</span>
                <span>Di chuyển hoàn tất 100% ({success_count:,} thư, {transferred_mb} MB). Tất cả thư mục và email đã được đồng bộ trọn vẹn sang hộp thư đích.</span>
            </div>
            """
        else:
            failed_folders = list(dict.fromkeys(item['folder'] for item in failed_items))
            folders_preview = ", ".join(f"<code>{f}</code>" for f in failed_folders[:2])
            if len(failed_folders) > 2:
                folders_preview += f" và {len(failed_folders) - 2} thư mục khác"

            summary_note_html = f"""
            <div class="summary-note note-warning">
                <span class="note-icon">ℹ</span>
                <div>
                    Đã chuyển an toàn <strong>{transferred_mb} MB</strong> ({success_count:,} thư). Có <strong>{failed_count:,}</strong> thư chưa nạp được tại {folders_preview}. 
                    Bạn có thể sử dụng nút <strong>"Thử lại"</strong> trên Control Center để tự động đồng bộ tiếp các thư này.
                </div>
            </div>
            """

        status_text = summary.get('status') or 'UNKNOWN'
        status_badge_class = 'badge-success' if failed_count == 0 and status_text == 'COMPLETED' else 'badge-warning' if failed_count > 0 else 'badge-neutral'

        failed_section_html = ""
        if failed_items:
            failed_section_html = f"""
            <div class="section-title">
                <h2>Chi Tiết Thư Chưa Nạp ({len(failed_items):,} Thư)</h2>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 140px;">Thư mục</th>
                            <th style="width: 70px;">UID</th>
                            <th style="width: 180px;">Người gửi</th>
                            <th>Tiêu đề</th>
                            <th style="width: 90px; text-align: center;">Mã lỗi</th>
                            <th style="width: 220px;">Nguyên nhân</th>
                        </tr>
                    </thead>
                    <tbody>
                        {failed_rows}
                    </tbody>
                </table>
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo Cáo Di Chuyển Email - {summary['source_account']}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #09090b;
            --surface: #111114;
            --surface-elevated: #18181c;
            --border: #222226;
            --border-subtle: #1c1c20;
            --text-primary: #f4f4f5;
            --text-secondary: #a1a1aa;
            --text-dim: #71717a;
            --accent-success: #22c55e;
            --accent-danger: #f87171;
            --accent-warning: #fbbf24;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text-primary);
            line-height: 1.5;
            padding: 32px 16px;
            font-size: 13px;
        }}
        .container {{
            max-width: 980px;
            margin: 0 auto;
        }}
        .header {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
        }}
        .header-title-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .header h1 {{
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.01em;
            color: var(--text-primary);
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
        }}
        .badge-success {{
            background: rgba(34, 197, 94, 0.1);
            color: #4ade80;
            border: 1px solid rgba(34, 197, 94, 0.25);
        }}
        .badge-warning {{
            background: rgba(251, 191, 36, 0.1);
            color: #fbbf24;
            border: 1px solid rgba(251, 191, 36, 0.25);
        }}
        .badge-danger {{
            background: rgba(248, 113, 113, 0.1);
            color: #f87171;
            border: 1px solid rgba(248, 113, 113, 0.25);
        }}
        .badge-neutral {{
            background: var(--surface-elevated);
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 8px;
            font-size: 12px;
            color: var(--text-secondary);
        }}
        .meta-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .meta-lbl {{
            color: var(--text-dim);
            font-size: 11px;
            font-weight: 600;
        }}
        code {{
            font-family: 'JetBrains Mono', monospace;
            background: var(--surface-elevated);
            padding: 1px 5px;
            border-radius: 3px;
            border: 1px solid var(--border);
            color: var(--text-primary);
            font-size: 11.5px;
        }}
        .summary-note {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 12px 16px;
            border-radius: 6px;
            font-size: 12.5px;
            margin-bottom: 16px;
            line-height: 1.5;
        }}
        .note-icon {{
            font-size: 13px;
            font-weight: bold;
            line-height: 1;
            margin-top: 2px;
        }}
        .note-success {{
            background: rgba(34, 197, 94, 0.06);
            border: 1px solid rgba(34, 197, 94, 0.2);
            color: #86efac;
        }}
        .note-warning {{
            background: rgba(251, 191, 36, 0.06);
            border: 1px solid rgba(251, 191, 36, 0.2);
            color: #fde68a;
        }}
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }}
        .kpi-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px 16px;
        }}
        .kpi-label {{
            font-size: 10.5px;
            font-weight: 600;
            color: var(--text-dim);
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .kpi-value {{
            font-size: 20px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-primary);
        }}
        .kpi-value small {{
            font-size: 11px;
            font-weight: 500;
            color: var(--text-dim);
        }}
        .text-success {{ color: #4ade80; }}
        .text-danger {{ color: #f87171; }}
        .text-muted {{ color: var(--text-dim); }}

        .section-title {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 20px 0 10px 0;
        }}
        .section-title h2 {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            letter-spacing: -0.01em;
        }}
        .table-wrap {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow-x: auto;
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12.5px;
        }}
        th, td {{
            padding: 8px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border-subtle);
        }}
        th {{
            background: var(--surface-elevated);
            color: var(--text-dim);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            border-bottom: 1px solid var(--border);
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        tr:hover td {{
            background: rgba(255, 255, 255, 0.015);
        }}
        .footer {{
            text-align: center;
            color: var(--text-dim);
            font-size: 11.5px;
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid var(--border-subtle);
        }}
        @media (max-width: 768px) {{
            .kpi-row {{ grid-template-columns: repeat(2, 1fr); }}
            .meta-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                <div class="header-title-group">
                    <h1>Báo Cáo Di Chuyển Email</h1>
                    <span class="badge {status_badge_class}">{status_text}</span>
                </div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: var(--text-dim);">
                    Phiên #{summary.get('id', 0)}
                </div>
            </div>
            <div class="meta-grid">
                <div class="meta-item">
                    <span class="meta-lbl">TÀI KHOẢN:</span>
                    <code>{summary['source_account']}</code> ➔ <code>{summary['dest_account']}</code>
                </div>
                <div class="meta-item" style="text-align: right;">
                    <span class="meta-lbl">THỜI GIAN:</span>
                    <span>{summary.get('started_at')} ➔ {summary.get('completed_at') or 'Đang xử lý'}</span>
                </div>
            </div>
        </div>

        {summary_note_html}

        <div class="kpi-row">
            <div class="kpi-card">
                <div class="kpi-label">Thành Công</div>
                <div class="kpi-value text-success">{success_count:,}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Bỏ Qua (Trùng)</div>
                <div class="kpi-value text-muted">{skipped_count:,}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Chưa Nạp Được</div>
                <div class="kpi-value {'text-danger' if failed_count > 0 else 'text-muted'}">{failed_count:,}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Dung Lượng</div>
                <div class="kpi-value">{transferred_mb} <small>MB</small></div>
            </div>
        </div>

        <div class="section-title">
            <h2>Thống Kê Theo Thư Mục</h2>
        </div>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Thư Mục</th>
                        <th style="text-align: right; width: 100px;">Tổng Số Thư</th>
                        <th style="text-align: right; width: 110px;">Thành Công</th>
                        <th style="text-align: right; width: 100px;">Chưa Nạp</th>
                        <th style="text-align: right; width: 120px;">Dung Lượng</th>
                    </tr>
                </thead>
                <tbody>
                    {folder_rows}
                </tbody>
            </table>
        </div>

        {failed_section_html}

        <div class="footer">
            Py-IMAP Migration Engine | Minimalist Monochrome Edition
        </div>
    </div>
</body>
</html>
"""

