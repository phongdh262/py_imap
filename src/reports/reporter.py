import csv
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from src.core.timezone import format_vn_datetime
from src.storage.state_db import StateDatabase


class MigrationReporter:
    """
    Generates professional, responsive HTML and CSV audit reports:
    - Executive summary card with timeline and accounts routing
    - KPI metric cards (Success, Skipped, Failed, Transferred Size)
    - Multi-color progress track and safety guarantee notice
    - Folder breakdown table with inline progress and grand total footer
    - Failed messages drill-down table with human-readable error reasons
    - CSV failure export
    - Standalone responsive design with Dark/Light mode and Print/PDF support
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
        timestamp = format_vn_datetime(fmt="%Y%m%d_%H%M%S")

        # 1. Generate CSV if there are failed items
        csv_file = None
        csv_filename = None
        if failed_items:
            csv_filename = f"failures_{clean_account}_{timestamp}.csv"
            csv_file = self.output_dir / csv_filename
            self._build_csv(csv_file, failed_items)

        # 2. Generate HTML Report
        html_file = self.output_dir / f"report_{clean_account}_{timestamp}.html"
        html_content = self._build_html(summary, folder_stats, failed_items, csv_filename=csv_filename)
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_file, csv_file

    @staticmethod
    def _mask_sensitive(text: Optional[str]) -> str:
        """
        Masks IP addresses and references to internal Py control / servers
        to ensure report anonymity and confidentiality.
        """
        if not text:
            return ""

        # 1. Mask IPv4 addresses (with optional port)
        text = re.sub(
            r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b",
            "***.***.***.***",
            text,
        )

        # 2. Mask IPv6 addresses
        text = re.sub(
            r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}(?::\d+)?\b",
            "****:****:****",
            text,
        )

        # 3. Mask internal system / Py control references if any
        text = re.sub(r"py[-_]?imap(?:\s+control(?:\s+center)?)?", "EmailMigrator", text, flags=re.IGNORECASE)
        text = re.sub(r"py[-_]?control", "ControlServer", text, flags=re.IGNORECASE)

        return text

    def _build_csv(self, file_path: Path, failed_items: List[Dict[str, Any]]):
        """Writes failed items to a CSV file with sensitive data masked."""
        fieldnames = [
            "folder",
            "source_uid",
            "message_id",
            "sender",
            "subject",
            "date_str",
            "size_bytes",
            "error_code",
            "error_detail",
        ]
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in failed_items:
                row = dict(item)
                row["error_detail"] = self._mask_sensitive(row.get("error_detail") or "")
                if row.get("sender"):
                    row["sender"] = self._mask_sensitive(row["sender"])
                writer.writerow(row)

    @staticmethod
    def _format_duration(started_at: Optional[str], completed_at: Optional[str]) -> str:
        """Calculates human-readable duration between start and completion."""
        if not started_at or not completed_at:
            return "Đang xử lý..."
        try:
            s = started_at.replace("T", " ").split(".")[0]
            c = completed_at.replace("T", " ").split(".")[0]
            dt_start = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(c, "%Y-%m-%d %H:%M:%S")
            sec = max(0, int((dt_end - dt_start).total_seconds()))
            if sec < 60:
                return f"{sec} giây"
            mins = sec // 60
            rem_sec = sec % 60
            if mins < 60:
                return f"{mins} phút {rem_sec:02d} giây"
            hrs = mins // 60
            rem_mins = mins % 60
            return f"{hrs} giờ {rem_mins} phút"
        except Exception:
            return "-"

    def _build_html(
        self,
        summary: Dict[str, Any],
        folder_stats: List[Dict[str, Any]],
        failed_items: List[Dict[str, Any]],
        csv_filename: Optional[str] = None,
    ) -> str:
        """Constructs an enterprise-grade, responsive HTML audit report."""
        transferred_bytes = summary.get("transferred_bytes", 0) or 0
        transferred_mb = round(transferred_bytes / (1024 * 1024), 2)
        transferred_gb = round(transferred_mb / 1024, 2)
        size_display = f"{transferred_gb} GB" if transferred_mb >= 1024 else f"{transferred_mb} MB"

        src_account = self._mask_sensitive(summary.get("source_account", ""))
        dst_account = self._mask_sensitive(summary.get("dest_account", ""))

        success_count = summary.get("migrated_messages", 0) or 0
        failed_count = summary.get("failed_messages", 0) or 0
        skipped_count = summary.get("skipped_messages", 0) or 0
        total_accounted = success_count + failed_count + skipped_count
        total_raw = summary.get("total_messages", 0) or 0
        total_count = max(total_accounted, total_raw)

        # Percentages for progress
        success_pct = round((success_count / total_count * 100), 1) if total_count > 0 else 0
        skipped_pct = round((skipped_count / total_count * 100), 1) if total_count > 0 else 0
        failed_pct = round((failed_count / total_count * 100), 1) if total_count > 0 else 0
        effective_safe_pct = round(((success_count + skipped_count) / max(1, total_count) * 100), 1)

        duration_str = self._format_duration(summary.get("started_at"), summary.get("completed_at"))

        # Folder table rows & totals
        folder_rows = ""
        total_folder_msgs = 0
        total_folder_success = 0
        total_folder_failed = 0
        total_folder_size = 0

        for fs in folder_stats:
            f_total = fs.get("total", 0) or 0
            f_success = fs.get("success", 0) or 0
            f_failed = fs.get("failed", 0) or 0
            f_size_bytes = fs.get("total_size", 0) or 0
            f_size_mb = round(f_size_bytes / (1024 * 1024), 2)

            total_folder_msgs += f_total
            total_folder_success += f_success
            total_folder_failed += f_failed
            total_folder_size += f_size_bytes

            f_pct = round((f_success / f_total * 100), 1) if f_total > 0 else 100.0

            folder_rows += f"""
            <tr>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: #818cf8; flex-shrink: 0;">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                        <strong>{fs['folder']}</strong>
                    </div>
                </td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace;">{f_total:,}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: #10b981; font-weight: 600;">{f_success:,}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: {'#f43f5e' if f_failed > 0 else 'var(--text-dim)'}; font-weight: {'600' if f_failed > 0 else 'normal'};">{f_failed:,}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace;">{f_size_mb} MB</td>
                <td style="text-align: center;">
                    <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
                        <div class="mini-progress-track">
                            <div class="mini-progress-fill {'fill-warn' if f_failed > 0 else ''}" style="width: {f_pct}%;"></div>
                        </div>
                        <span style="font-size: 11.5px; font-family: 'JetBrains Mono', monospace; width: 42px; text-align: right;">{f_pct}%</span>
                    </div>
                </td>
            </tr>
            """

        total_folder_size_mb = round(total_folder_size / (1024 * 1024), 2)

        # Failed items rows
        failed_rows = ""
        if failed_items:
            for item in failed_items:
                subj = (item.get("subject") or "(Không có tiêu đề)").strip()
                if len(subj) > 65:
                    subj = subj[:65] + "..."
                sender = self._mask_sensitive((item.get("sender") or "Không rõ").strip())
                if len(sender) > 30:
                    sender = sender[:30] + "..."
                raw_err = self._mask_sensitive(item.get("error_detail") or "")

                err_text = raw_err
                if "nonexistent namespace" in raw_err.lower() or "prefixed with: inbox" in raw_err.lower():
                    err_text = "Cần tiền tố INBOX"
                elif "already exists" in raw_err.lower() or "alreadyexists" in raw_err.lower():
                    err_text = "Thư hoặc thư mục đã tồn tại trên đích"
                elif len(err_text) > 100:
                    err_text = err_text[:100] + "..."

                failed_rows += f"""
                <tr>
                    <td><code>{item['folder']}</code></td>
                    <td style="font-family: 'JetBrains Mono', monospace; font-size: 11px; text-align: center;">{item['source_uid']}</td>
                    <td><span title="{sender}">{sender}</span></td>
                    <td title="{subj}">{subj}</td>
                    <td style="text-align: center;"><span class="badge badge-danger">{item.get('error_code') or 'ERR'}</span></td>
                    <td style="color: #f43f5e; font-size: 12px;">{err_text}</td>
                </tr>
                """

        # Status text & color
        status_raw = summary.get("status") or "COMPLETED"
        if failed_count == 0 and status_raw == "COMPLETED":
            status_text = "HOÀN TẤT"
            status_badge_class = "badge-success"
            status_dot_color = "#10b981"
        elif status_raw == "IN_PROGRESS" or status_raw == "RUNNING":
            status_text = "ĐANG CHẠY"
            status_badge_class = "badge-warning"
            status_dot_color = "#f59e0b"
        else:
            status_text = "CÓ LỖI" if failed_count > 0 else status_raw
            status_badge_class = "badge-danger" if failed_count > 0 else "badge-neutral"
            status_dot_color = "#f43f5e"

        # Summary note box
        if failed_count == 0:
            summary_banner_html = f"""
            <div class="summary-banner banner-success">
                <div class="banner-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                    </svg>
                </div>
                <div>
                    <strong style="display:block; font-size: 13.5px; margin-bottom: 2px;">Đồng bộ hoàn tất 100%</strong>
                    <span>Đã nạp <strong>{success_count:,}</strong> thư ({size_display}). Tự động bảo toàn <strong>{skipped_count:,}</strong> thư hiện hữu trên đích.</span>
                </div>
            </div>
            """
        else:
            failed_folders = list(dict.fromkeys(item["folder"] for item in failed_items))
            folders_preview = ", ".join(f"<code>{f}</code>" for f in failed_folders[:2])
            if len(failed_folders) > 2:
                folders_preview += f" và {len(failed_folders) - 2} thư mục khác"

            csv_download_btn = (
                f"""<a href="/reports/{csv_filename}" download class="btn btn-secondary btn-sm" style="margin-left:auto;">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
                    <span>Tải CSV Lỗi</span>
                </a>"""
                if csv_filename
                else ""
            )

            summary_banner_html = f"""
            <div class="summary-banner banner-warning">
                <div class="banner-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                </div>
                <div style="flex: 1;">
                    <strong style="display:block; font-size: 13.5px; margin-bottom: 2px;">Có {failed_count:,} thư lỗi</strong>
                    <span>Đã nạp <strong>{success_count:,}</strong> thư ({size_display}). Thư chưa nạp nằm tại {folders_preview}. Có thể thực hiện đồng bộ lại cho các thư này.</span>
                </div>
                {csv_download_btn}
            </div>
            """

        # Failed section HTML
        if failed_items:
            failed_section_html = f"""
            <div class="card" style="margin-top: 24px; border-color: rgba(244, 63, 94, 0.3);">
                <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="status-dot" style="background: #f43f5e; box-shadow: 0 0 8px #f43f5e;"></span>
                        <h2 style="font-size: 15px; margin: 0;">Danh Sách Thư Lỗi ({len(failed_items):,})</h2>
                    </div>
                    {f'<a href="/reports/{csv_filename}" download class="btn btn-secondary btn-sm no-print">Xuất CSV</a>' if csv_filename else ''}
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 150px;">Thư Mục</th>
                                <th style="width: 70px; text-align: center;">UID</th>
                                <th style="width: 180px;">Người Gửi</th>
                                <th>Tiêu Đề</th>
                                <th style="width: 90px; text-align: center;">Mã Lỗi</th>
                                <th style="width: 220px;">Nguyên Nhân</th>
                            </tr>
                        </thead>
                        <tbody>
                            {failed_rows}
                        </tbody>
                    </table>
                </div>
            </div>
            """
        else:
            failed_section_html = ""

        started_display = (
            summary.get("started_at", "").replace("T", " ").split(".")[0] if summary.get("started_at") else "-"
        )
        completed_display = (
            summary.get("completed_at", "").replace("T", " ").split(".")[0]
            if summary.get("completed_at")
            else "Đang xử lý"
        )

        return f"""<!DOCTYPE html>
<html lang="vi" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo Cáo Di Chuyển Email | Phiên #{summary.get('id', 0)} - {src_account}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root, [data-theme="dark"] {{
            --bg-dark: #090d16;
            --bg-surface: #0e1424;
            --bg-card: rgba(17, 24, 39, 0.85);
            --bg-card-subtle: rgba(15, 23, 42, 0.65);
            --border: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(99, 102, 241, 0.4);
            --text-primary: #f8fafc;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
            --primary: #4f46e5;
            --primary-gradient: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            --success: #10b981;
            --danger: #f43f5e;
            --warning: #f59e0b;
            --info: #06b6d4;
            --card-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
            --glass-blur: blur(14px);
        }}

        [data-theme="light"] {{
            --bg-dark: #f1f5f9;
            --bg-surface: #ffffff;
            --bg-card: #ffffff;
            --bg-card-subtle: #f8fafc;
            --border: #e2e8f0;
            --border-hover: #cbd5e1;
            --text-primary: #0f172a;
            --text-muted: #475569;
            --text-dim: #64748b;
            --primary: #4f46e5;
            --primary-gradient: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            --success: #059669;
            --danger: #e11d48;
            --warning: #d97706;
            --info: #0284c7;
            --card-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
            --glass-blur: none;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.55;
            padding: 24px 16px 60px 16px;
            font-size: 13.5px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1120px;
            margin: 0 auto;
        }}

        /* Top Action Bar */
        .top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .brand-crumb {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .brand-logo-icon {{
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #6366f1 0%, #3b82f6 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            box-shadow: 0 0 14px rgba(99, 102, 241, 0.35);
        }}

        .brand-name {{
            font-size: 14px;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .brand-sep {{
            color: var(--text-dim);
            font-size: 13px;
        }}

        .top-actions {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 7px 14px;
            font-size: 12.5px;
            font-weight: 600;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.15s ease;
            border: 1px solid var(--border);
        }}

        .btn-secondary {{
            background: var(--bg-surface);
            color: var(--text-primary);
        }}

        .btn-secondary:hover {{
            border-color: var(--border-hover);
            transform: translateY(-1px);
        }}

        .btn-primary {{
            background: var(--primary-gradient);
            color: #ffffff;
            border-color: rgba(99, 102, 241, 0.4);
            box-shadow: 0 2px 10px rgba(99, 102, 241, 0.25);
        }}

        .btn-primary:hover {{
            filter: brightness(1.1);
            transform: translateY(-1px);
        }}

        .btn-sm {{
            padding: 6px 12px;
            font-size: 12px;
        }}

        /* Theme Switcher */
        .theme-switcher {{
            display: inline-flex;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 2px;
        }}

        .theme-btn {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 4px 10px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            transition: all 0.15s ease;
        }}

        .theme-btn.active {{
            background: rgba(99, 102, 241, 0.18);
            color: #818cf8;
            font-weight: 600;
        }}

        /* Main Cards */
        .card {{
            background: var(--bg-card);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid var(--border);
            border-radius: 14px;
            box-shadow: var(--card-shadow);
            overflow: hidden;
            margin-bottom: 20px;
        }}

        .card-header {{
            padding: 18px 22px;
            border-bottom: 1px solid var(--border);
        }}

        .card-body {{
            padding: 22px;
        }}

        /* Executive Master Banner */
        .master-banner {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
            flex-wrap: wrap;
            margin-bottom: 18px;
        }}

        .master-title-group h1 {{
            font-size: 20px;
            font-weight: 800;
            color: var(--text-primary);
            letter-spacing: -0.02em;
            margin-bottom: 4px;
        }}

        .master-sub {{
            font-size: 12.5px;
            color: var(--text-muted);
        }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 11.5px;
            font-weight: 700;
            letter-spacing: 0.04em;
        }}

        .status-dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 8px var(--success);
        }}

        .badge-success {{
            background: rgba(16, 185, 129, 0.12);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .badge-warning {{
            background: rgba(245, 158, 11, 0.12);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .badge-danger {{
            background: rgba(244, 63, 94, 0.12);
            color: #fb7185;
            border: 1px solid rgba(244, 63, 94, 0.3);
        }}

        .badge-neutral {{
            background: var(--bg-card-subtle);
            color: var(--text-muted);
            border: 1px solid var(--border);
        }}

        /* Account Route Strip */
        .route-strip {{
            background: var(--bg-card-subtle);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }}

        .account-box {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .account-pill {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            font-weight: 600;
            padding: 4px 10px;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-primary);
        }}

        .route-arrow {{
            color: #818cf8;
            font-size: 16px;
            font-weight: bold;
        }}

        .timeline-info {{
            display: flex;
            gap: 18px;
            font-size: 12px;
            color: var(--text-muted);
            flex-wrap: wrap;
        }}

        .timeline-item strong {{
            color: var(--text-primary);
        }}

        /* Summary Banner */
        .summary-banner {{
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 14px 18px;
            border-radius: 10px;
            font-size: 13px;
            margin-bottom: 22px;
            line-height: 1.5;
        }}

        .banner-success {{
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.25);
            color: var(--text-primary);
        }}

        .banner-warning {{
            background: rgba(245, 158, 11, 0.08);
            border: 1px solid rgba(245, 158, 11, 0.25);
            color: var(--text-primary);
        }}

        .banner-icon {{
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        /* Multi-segment Progress Bar */
        .progress-section {{
            margin-bottom: 22px;
        }}

        .progress-header {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}

        .multi-bar-track {{
            width: 100%;
            height: 10px;
            background: rgba(255, 255, 255, 0.06);
            border-radius: 999px;
            overflow: hidden;
            display: flex;
        }}

        .multi-bar-segment {{
            height: 100%;
            transition: width 0.3s ease;
        }}

        .seg-success {{ background: #10b981; }}
        .seg-skipped {{ background: #f59e0b; }}
        .seg-failed  {{ background: #f43f5e; }}

        /* KPI Metric Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-bottom: 24px;
        }}

        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            box-shadow: var(--card-shadow);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--border-hover);
        }}

        .kpi-label {{
            font-size: 11px;
            font-weight: 700;
            color: var(--text-dim);
            letter-spacing: 0.05em;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .kpi-value {{
            font-size: 24px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-primary);
        }}

        .kpi-sub {{
            font-size: 11.5px;
            color: var(--text-dim);
        }}

        /* Tables */
        .table-wrap {{
            width: 100%;
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}

        th {{
            background: var(--bg-surface);
            color: var(--text-dim);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}

        tbody tr:hover {{
            background: rgba(99, 102, 241, 0.04);
        }}

        tfoot td {{
            font-weight: 700;
            background: var(--bg-surface);
            border-top: 2px solid var(--border);
            border-bottom: none;
        }}

        code {{
            font-family: 'JetBrains Mono', monospace;
            background: rgba(255, 255, 255, 0.06);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
            border: 1px solid var(--border);
        }}

        /* Mini progress track */
        .mini-progress-track {{
            width: 60px;
            height: 6px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 999px;
            overflow: hidden;
        }}

        .mini-progress-fill {{
            height: 100%;
            background: #10b981;
            border-radius: 999px;
        }}

        .mini-progress-fill.fill-warn {{
            background: #f59e0b;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            color: var(--text-dim);
            font-size: 12px;
            margin-top: 36px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }}

        /* Print / PDF Mode */
        @media print {{
            body {{
                background: #ffffff !important;
                color: #000000 !important;
                padding: 0 !important;
                font-size: 12px !important;
            }}
            .no-print {{
                display: none !important;
            }}
            .card {{
                box-shadow: none !important;
                border: 1px solid #cbd5e1 !important;
                background: #ffffff !important;
                page-break-inside: avoid;
            }}
            th {{
                background: #f1f5f9 !important;
                color: #334155 !important;
            }}
            td {{
                color: #0f172a !important;
                border-bottom: 1px solid #e2e8f0 !important;
            }}
            .badge {{
                border: 1px solid #94a3b8 !important;
                color: #0f172a !important;
            }}
            .status-dot {{
                display: none !important;
            }}
            .kpi-card {{
                border: 1px solid #cbd5e1 !important;
                box-shadow: none !important;
            }}
        }}

        /* Responsive */
        @media (max-width: 900px) {{
            .kpi-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .route-strip {{
                flex-direction: column;
                align-items: flex-start;
            }}
        }}

        @media (max-width: 600px) {{
            .kpi-grid {{
                grid-template-columns: 1fr;
            }}
            .master-banner {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Top Action Bar -->
        <div class="top-bar no-print">
            <div class="brand-crumb">
                <div class="brand-logo-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <rect width="20" height="16" x="2" y="4" rx="3"/>
                        <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                    </svg>
                </div>
                <span class="brand-name">Báo Cáo Di Chuyển Email</span>
            </div>

            <div class="top-actions">
                <div class="theme-switcher">
                    <button type="button" class="theme-btn active" id="btnThemeDark" onclick="setTheme('dark')">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
                        <span>Tối</span>
                    </button>
                    <button type="button" class="theme-btn" id="btnThemeLight" onclick="setTheme('light')">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
                        <span>Sáng</span>
                    </button>
                </div>

                <button type="button" class="btn btn-secondary btn-sm" onclick="window.print()" title="In hoặc xuất PDF">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect width="12" height="8" x="6" y="14"/></svg>
                    <span>In / PDF</span>
                </button>

                <a href="/" class="btn btn-primary btn-sm" title="Quay lại">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
                    <span>Quay Lại</span>
                </a>
            </div>
        </div>

        <!-- Master Session Card -->
        <div class="card">
            <div class="card-body">
                <div class="master-banner">
                    <div class="master-title-group">
                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                            <span class="badge badge-neutral" style="font-family: 'JetBrains Mono', monospace;">PHIÊN #{summary.get('id', 0)}</span>
                            <span class="status-badge {status_badge_class}">
                                <span class="status-dot" style="background: {status_dot_color}; box-shadow: 0 0 8px {status_dot_color};"></span>
                                {status_text}
                            </span>
                        </div>
                        <h1>Báo Cáo Di Chuyển Email</h1>
                        <p class="master-sub">Đối chiếu kết quả đồng bộ dữ liệu giữa hai hộp thư</p>
                    </div>

                    <div style="text-align: right;" class="no-print">
                        <div style="font-size: 11.5px; color: var(--text-dim); text-transform: uppercase; font-weight: 700;">Tỷ Lệ Hoàn Tất</div>
                        <div style="font-size: 28px; font-weight: 800; font-family: 'JetBrains Mono', monospace; color: #10b981;">
                            {effective_safe_pct}%
                        </div>
                    </div>
                </div>

                <!-- Account Route Strip -->
                <div class="route-strip">
                    <div class="account-box">
                        <span style="font-size: 11px; font-weight: 700; color: var(--text-dim); text-transform: uppercase;">Nguồn:</span>
                        <span class="account-pill">{src_account}</span>
                        <span class="route-arrow">➔</span>
                        <span style="font-size: 11px; font-weight: 700; color: var(--text-dim); text-transform: uppercase;">Đích:</span>
                        <span class="account-pill">{dst_account}</span>
                    </div>

                    <div class="timeline-info">
                        <div class="timeline-item">
                            Bắt đầu: <strong>{started_display}</strong>
                        </div>
                        <div class="timeline-item">
                            Hoàn tất: <strong>{completed_display}</strong>
                        </div>
                        <div class="timeline-item">
                            Thời gian: <strong>{duration_str}</strong>
                        </div>
                    </div>
                </div>

                <!-- Multi-segment visual progress -->
                <div class="progress-section">
                    <div class="progress-header">
                        <span>Kết quả đồng bộ ({total_count:,} thư)</span>
                        <span>Thành công: {success_count:,} &bull; Bỏ qua: {skipped_count:,} &bull; Lỗi: {failed_count:,}</span>
                    </div>
                    <div class="multi-bar-track">
                        <div class="multi-bar-segment seg-success" style="width: {success_pct}%;" title="Thành công: {success_count} ({success_pct}%)"></div>
                        <div class="multi-bar-segment seg-skipped" style="width: {skipped_pct}%;" title="Bỏ qua: {skipped_count} ({skipped_pct}%)"></div>
                        <div class="multi-bar-segment seg-failed" style="width: {failed_pct}%;" title="Lỗi: {failed_count} ({failed_pct}%)"></div>
                    </div>
                </div>

                {summary_banner_html}
            </div>
        </div>

        <!-- 4 KPI Stat Cards -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">
                    <span>Thành Công</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <div class="kpi-value" style="color: #10b981;">{success_count:,}</div>
                <div class="kpi-sub">{success_pct}% tổng thư</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-label">
                    <span>Bỏ Qua</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                </div>
                <div class="kpi-value" style="color: #f59e0b;">{skipped_count:,}</div>
                <div class="kpi-sub">Đã có sẵn trên đích</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-label">
                    <span>Lỗi</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{'#f43f5e' if failed_count > 0 else 'var(--text-dim)'}" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                </div>
                <div class="kpi-value" style="color: {'#f43f5e' if failed_count > 0 else 'var(--text-dim)'};">{failed_count:,}</div>
                <div class="kpi-sub">{'Cần đồng bộ lại' if failed_count > 0 else '0 thư lỗi'}</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-label">
                    <span>Dung Lượng</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2.2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
                </div>
                <div class="kpi-value" style="color: #06b6d4;">{transferred_mb} <span style="font-size: 13px; font-weight:600; color:var(--text-dim);">MB</span></div>
                <div class="kpi-sub">{size_display} hoàn tất</div>
            </div>
        </div>

        <!-- Folder Breakdown Table Card -->
        <div class="card">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                <h2 style="font-size: 15px; font-weight: 700; margin: 0; color: var(--text-primary);">Thống Kê Thư Mục ({len(folder_stats)})</h2>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Thư Mục</th>
                            <th style="text-align: right; width: 110px;">Tổng Thư</th>
                            <th style="text-align: right; width: 110px;">Thành Công</th>
                            <th style="text-align: right; width: 110px;">Lỗi</th>
                            <th style="text-align: right; width: 130px;">Dung Lượng</th>
                            <th style="text-align: center; width: 130px;">Tỷ Lệ</th>
                        </tr>
                    </thead>
                    <tbody>
                        {folder_rows}
                    </tbody>
                    <tfoot>
                        <tr>
                            <td>Tổng cộng ({len(folder_stats)} thư mục)</td>
                            <td style="text-align: right; font-family: 'JetBrains Mono', monospace;">{total_folder_msgs:,}</td>
                            <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: #10b981;">{total_folder_success:,}</td>
                            <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: {'#f43f5e' if total_folder_failed > 0 else 'inherit'};">{total_folder_failed:,}</td>
                            <td style="text-align: right; font-family: 'JetBrains Mono', monospace;">{total_folder_size_mb} MB</td>
                            <td style="text-align: center; font-family: 'JetBrains Mono', monospace;">
                                {round((total_folder_success / max(1, total_folder_msgs) * 100), 1)}%
                            </td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>

        <!-- Failed Items Drill-Down (If any) -->
        {failed_section_html}

        <!-- Footer -->
        <div class="footer">
            <div>
                <strong>Báo Cáo Đối Chiếu Dữ Liệu Email</strong>
            </div>
            <div style="color: var(--text-dim); font-size: 11.5px;">
                Thời gian tạo: {format_vn_datetime(fmt='%d/%m/%Y %H:%M')}
            </div>
        </div>
    </div>

    <script>
        function setTheme(theme) {{
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('email_report_theme', theme);
            const btnDark = document.getElementById('btnThemeDark');
            const btnLight = document.getElementById('btnThemeLight');
            if (btnDark && btnLight) {{
                if (theme === 'dark') {{
                    btnDark.classList.add('active');
                    btnLight.classList.remove('active');
                }} else {{
                    btnLight.classList.add('active');
                    btnDark.classList.remove('active');
                }}
            }}
        }}

        // Initialize theme from localStorage or default dark
        (function() {{
            const saved = localStorage.getItem('email_report_theme') || 'dark';
            setTheme(saved);
        }})();
    </script>
</body>
</html>
"""
