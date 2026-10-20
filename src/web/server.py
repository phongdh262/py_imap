import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core.auth_checker import AuthChecker
from src.core.models import AccountCredentials, MailboxSummary
from src.core.service import MigrationService
from src.reports.reporter import MigrationReporter
from src.security.auth import (
    AdminSecurity,
    COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    verify_session_token,
    verify_admin,
)
from src.security.headers import SecurityHeadersMiddleware
from src.security.path_guard import PathSecurity
from src.storage.state_db import StateDatabase

app = FastAPI(
    title="Py-IMAP Control Center",
    version="1.0.0",
    dependencies=[Depends(verify_admin)],
)

# OWASP Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS Policy
allowed_origins_raw = os.environ.get("ALLOWED_ORIGINS", "*")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") or path in ("/", "/login"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared state
state_db = StateDatabase()
reporter = MigrationReporter(state_db)
migration_service = MigrationService()
auth_checker = AuthChecker()

# Isolated Pub/Sub for SSE Task Streaming (Supports multi-tab concurrent migrations)
TASK_SUBSCRIBERS: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
GLOBAL_SUBSCRIBERS: Set[asyncio.Queue] = set()


def broadcast_task_event(task_id: str, event_data: dict, loop: asyncio.AbstractEventLoop):
    """Safely dispatches event to both task-specific SSE subscribers and global monitors."""
    event_data["task_id"] = task_id

    def _push():
        for q in list(TASK_SUBSCRIBERS.get(task_id, set())):
            try:
                q.put_nowait(event_data)
            except Exception:
                pass
        for q in list(GLOBAL_SUBSCRIBERS):
            try:
                q.put_nowait(event_data)
            except Exception:
                pass

    if loop.is_running():
        loop.call_soon_threadsafe(_push)


class LoginRequest(BaseModel):
    username: str
    password: str


class SingleMigrateRequest(BaseModel):
    source: AccountCredentials
    dest: AccountCredentials
    sanitize_accents: bool = False
    batch_delay_ms: int = 50
    force_remigrate: bool = True


class BatchCheckRequest(BaseModel):
    source_host: Optional[str] = None
    source_port: Optional[int] = 993
    source_ssl: Optional[bool] = True
    dest_host: Optional[str] = None
    dest_port: Optional[int] = 993
    dest_ssl: Optional[bool] = True
    accounts: List[Dict[str, Any]]


class BatchMigrateRequest(BaseModel):
    source_host: Optional[str] = None
    source_port: Optional[int] = 993
    source_ssl: Optional[bool] = True
    dest_host: Optional[str] = None
    dest_port: Optional[int] = 993
    dest_ssl: Optional[bool] = True
    accounts: List[Dict[str, Any]]
    sanitize_accents: bool = False
    batch_delay_ms: int = 50
    force_remigrate: bool = True


# In-memory Task State for Background Migrations
ACTIVE_TASKS: Dict[str, Dict[str, Any]] = {}


@app.get("/login", response_class=HTMLResponse)
async def serve_login(request: Request):
    """Serves the login page. Redirects to '/' if already authenticated."""
    session_cookie = request.cookies.get(COOKIE_NAME)
    if session_cookie and verify_session_token(session_cookie):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    login_file = TEMPLATES_DIR / "login.html"
    if not login_file.exists():
        raise HTTPException(status_code=404, detail="login.html not found")
    return HTMLResponse(content=login_file.read_text(encoding="utf-8"))


@app.post("/api/login")
async def api_login(req: LoginRequest, request: Request, response: Response):
    """Authenticates admin credentials, handles brute-force protection, and sets session cookie."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    AdminSecurity.check_brute_force(client_ip)

    expected_user, expected_pwd = AdminSecurity.get_admin_credentials()
    user_match = secrets.compare_digest(req.username.strip().encode("utf-8"), expected_user.encode("utf-8"))
    pwd_match = secrets.compare_digest(req.password.encode("utf-8"), expected_pwd.encode("utf-8"))

    if not (user_match and pwd_match):
        AdminSecurity.record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên người dùng hoặc mật khẩu không chính xác",
        )

    AdminSecurity.record_success(client_ip)
    token = create_session_token(req.username.strip())

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"success": True, "redirect": "/"}


@app.get("/logout")
async def logout():
    """Logs out admin by clearing the session cookie and redirecting to /login."""
    redirect = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(key=COOKIE_NAME, path="/")
    return redirect


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serves the main Web Admin Dashboard."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    content = index_file.read_text(encoding="utf-8")
    grafana_url = os.environ.get("GRAFANA_URL", "").strip()
    if grafana_url:
        import re
        content = re.sub(
            r'href="[^"]*"\s+target="_blank"\s+class="btn btn-secondary btn-sm"\s+id="grafanaBtn"',
            f'href="{grafana_url}" target="_blank" class="btn btn-secondary btn-sm" id="grafanaBtn" data-custom-url="true"',
            content,
        )
    return HTMLResponse(content=content)


@app.post("/api/check-password")
async def check_password(creds: AccountCredentials):
    """Verifies single account credentials with latency and provider hints."""
    res = auth_checker.check_single(creds)
    return {
        "username": res.username,
        "host": res.host,
        "is_valid": res.is_valid,
        "latency_ms": res.latency_ms,
        "error_reason": res.error_reason,
        "provider_hint": res.provider_hint,
    }


@app.post("/api/check-csv")
async def check_csv_passwords(req: BatchCheckRequest):
    """Checks credentials for all accounts in CSV in parallel."""
    creds_list = []
    for row in req.accounts:
        src_host = (row.get("source_host") or req.source_host or "").strip()
        src_port = int(row.get("source_port") or req.source_port or 993)
        src_ssl_val = row.get("source_ssl")
        src_ssl = (
            str(src_ssl_val).lower() in ("true", "1")
            if src_ssl_val is not None
            else (req.source_ssl if req.source_ssl is not None else True)
        )
        src_user = (row.get("source_user") or row.get("source_email") or row.get("email") or row.get("user") or "").strip()
        src_pass = (row.get("source_password") or row.get("source_pass") or row.get("password") or row.get("pass") or "").strip()

        if src_user and src_host:
            creds_list.append(
                AccountCredentials(
                    host=src_host,
                    port=src_port,
                    ssl=src_ssl,
                    username=src_user,
                    password=src_pass,
                )
            )
    results = auth_checker.check_multiple(creds_list, max_workers=8)
    return [
        {
            "username": r.username,
            "host": r.host,
            "is_valid": r.is_valid,
            "latency_ms": r.latency_ms,
            "error_reason": r.error_reason,
            "provider_hint": r.provider_hint,
        }
        for r in results
    ]


@app.post("/api/scan/batch")
async def scan_batch_mailboxes(req: BatchCheckRequest):
    """Scans and inspects folders, size, message counts, and quota for multiple accounts in parallel."""
    def _inspect_one(row: Dict[str, Any]) -> Dict[str, Any]:
        src_host = (row.get("source_host") or req.source_host or "").strip()
        src_port = int(row.get("source_port") or req.source_port or 993)
        src_ssl_val = row.get("source_ssl")
        src_ssl = (
            str(src_ssl_val).lower() in ("true", "1")
            if src_ssl_val is not None
            else (req.source_ssl if req.source_ssl is not None else True)
        )
        src_user = (row.get("source_user") or row.get("source_email") or row.get("email") or row.get("user") or "").strip()
        src_pass = (row.get("source_password") or row.get("source_pass") or row.get("password") or row.get("pass") or "").strip()

        if not (src_user and src_host):
            return {
                "account": src_user or "Unknown",
                "host": src_host,
                "is_valid": False,
                "error_message": "Thiếu email hoặc thông tin máy chủ IMAP",
                "total_messages": 0,
                "total_size_mb": 0.0,
                "total_size_gb": 0.0,
                "total_size_bytes": 0,
                "folders_count": 0,
                "quota": None,
                "folders": [],
            }

        creds = AccountCredentials(
            host=src_host,
            port=src_port,
            ssl=src_ssl,
            username=src_user,
            password=src_pass,
        )

        try:
            summary = migration_service.inspect_source(creds)
            data = summary.model_dump()
            data["host"] = src_host
            data["is_valid"] = True
            data["error_message"] = None
            data["total_size_mb"] = summary.total_size_mb
            data["total_size_gb"] = summary.total_size_gb
            data["quota"] = summary.quota
            data["folders_count"] = len(summary.folders)
            for idx, f in enumerate(summary.folders):
                if idx < len(data.get("folders", [])):
                    data["folders"][idx]["size_mb"] = f.size_mb
                    data["folders"][idx]["destination_folder"] = f.destination_folder
                    data["folders"][idx]["messages"] = f.messages_count
                    data["folders"][idx]["messages_count"] = f.messages_count
            return data
        except Exception as e:
            return {
                "account": src_user,
                "host": src_host,
                "is_valid": False,
                "error_message": str(e),
                "total_messages": 0,
                "total_size_mb": 0.0,
                "total_size_gb": 0.0,
                "total_size_bytes": 0,
                "folders_count": 0,
                "quota": None,
                "folders": [],
            }

    loop = asyncio.get_running_loop()
    from concurrent.futures import ThreadPoolExecutor
    workers = min(max(len(req.accounts), 1), 6)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = await loop.run_in_executor(None, lambda: list(executor.map(_inspect_one, req.accounts)))

    return results


@app.post("/api/inspect")
async def inspect_mailbox(req: Dict[str, Any]):
    """Pre-flight inspection: inspects source and optionally destination to provide full reconciliation."""
    try:
        if "source" in req:
            src_creds = AccountCredentials(**req["source"])
            dst_creds = AccountCredentials(**req["dest"]) if req.get("dest") and req["dest"].get("username") and req["dest"].get("password") else None
        else:
            src_creds = AccountCredentials(**req)
            dst_creds = None

        if dst_creds:
            result = migration_service.inspect_both(src_creds, dst_creds)
            src_data = result["source"].model_dump()
            src_data["total_size_mb"] = result["source"].total_size_mb
            src_data["total_size_gb"] = result["source"].total_size_gb
            src_data["quota"] = result["source"].quota

            for idx, f in enumerate(result["source"].folders):
                if idx < len(src_data.get("folders", [])):
                    src_data["folders"][idx]["size_mb"] = f.size_mb
                    src_data["folders"][idx]["destination_folder"] = f.destination_folder
                    src_data["folders"][idx]["messages"] = f.messages_count
                    src_data["folders"][idx]["messages_count"] = f.messages_count

            dst_data = None
            if result["dest"]:
                dst_data = result["dest"].model_dump()
                dst_data["total_size_mb"] = result["dest"].total_size_mb
                dst_data["total_size_gb"] = result["dest"].total_size_gb
                dst_data["quota"] = result["dest"].quota

                for idx, f in enumerate(result["dest"].folders):
                    if idx < len(dst_data.get("folders", [])):
                        dst_data["folders"][idx]["size_mb"] = f.size_mb
                        dst_data["folders"][idx]["destination_folder"] = f.destination_folder
                        dst_data["folders"][idx]["messages"] = f.messages_count
                        dst_data["folders"][idx]["messages_count"] = f.messages_count

            return {
                "is_dual": True,
                "source": src_data,
                "dest": dst_data,
                "reconciliation": result["reconciliation"],
                "total_messages": src_data["total_messages"],
                "total_size_mb": src_data["total_size_mb"],
                "total_size_bytes": src_data["total_size_bytes"],
                "quota": src_data["quota"],
                "folders": src_data["folders"],
            }
        else:
            summary = migration_service.inspect_source(src_creds)
            data = summary.model_dump()
            data["total_size_mb"] = summary.total_size_mb
            data["total_size_gb"] = summary.total_size_gb
            data["quota"] = summary.quota
            for idx, f in enumerate(summary.folders):
                if idx < len(data.get("folders", [])):
                    data["folders"][idx]["size_mb"] = f.size_mb
                    data["folders"][idx]["destination_folder"] = f.destination_folder
                    data["folders"][idx]["messages"] = f.messages_count
                    data["folders"][idx]["messages_count"] = f.messages_count
            return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


STOP_REQUESTED_TASKS: Set[str] = set()


def run_migration_worker(task_id: str, req: SingleMigrateRequest, loop: asyncio.AbstractEventLoop):
    """Background worker executing the migration, updating ACTIVE_TASKS, and pushing SSE events."""
    service = MigrationService(
        sanitize_accents=req.sanitize_accents,
        batch_delay_seconds=req.batch_delay_ms / 1000.0,
    )

    if req.force_remigrate:
        service.state_db.clear_account_state(req.source.username)

    start_ts = time.time()
    ACTIVE_TASKS[task_id] = {
        "task_id": task_id,
        "source": req.source.username,
        "dest": req.dest.username,
        "status": "RUNNING",
        "percent": 0.0,
        "current_folder": "Đang kết nối...",
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "total_messages": 0,
        "started_at": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "start_timestamp": start_ts,
        "duration_sec": 0,
        "msg_rate": 0.0,
        "html_report": None,
        "csv_report": None,
        "error_message": None,
    }

    try:
        orig_migrate_folder = service.migrator.migrate_folder

        def custom_migrate_folder(*args, **kwargs):
            if task_id in STOP_REQUESTED_TASKS or ACTIVE_TASKS.get(task_id, {}).get("status") in ("STOPPING", "STOPPED"):
                raise Exception("TASK_STOPPED_BY_USER")

            src_folder = kwargs.get("src_folder") or args[4]
            user_cb = kwargs.get("on_progress")

            def wrapped_progress(done, total):
                if task_id in STOP_REQUESTED_TASKS or ACTIVE_TASKS.get(task_id, {}).get("status") in ("STOPPING", "STOPPED"):
                    raise Exception("TASK_STOPPED_BY_USER")

                if user_cb:
                    user_cb(done, total)
                pct = round((done / (total or 1)) * 100, 1)

                task_data = ACTIVE_TASKS.get(task_id, {})
                task_data["percent"] = pct
                task_data["current_folder"] = src_folder
                if total and total > 0:
                    task_data["total_messages"] = total
                summary = service.state_db.get_migration_summary(kwargs.get("migration_id", 0)) if kwargs.get("migration_id") else {}
                task_data["success"] = summary.get("migrated_messages", done)
                task_data["skipped"] = summary.get("skipped_messages", 0)
                task_data["failed"] = summary.get("failed_messages", 0)
                elapsed = max(time.time() - start_ts, 0.1)
                task_data["duration_sec"] = round(elapsed, 1)
                task_data["msg_rate"] = round((task_data["success"] + task_data["skipped"]) / elapsed, 1)

                broadcast_task_event(task_id, {
                    "type": "progress",
                    "task_id": task_id,
                    "source": req.source.username,
                    "percent": pct,
                    "folder": src_folder,
                    "success": task_data["success"],
                    "skipped": task_data["skipped"],
                    "failed": task_data["failed"],
                    "msg_rate": task_data["msg_rate"],
                    "duration_sec": task_data["duration_sec"],
                }, loop)

            kwargs["on_progress"] = wrapped_progress
            return orig_migrate_folder(*args, **kwargs)

        service.migrator.migrate_folder = custom_migrate_folder
        res = service.migrate_account(req.source, req.dest, force_remigrate=req.force_remigrate)

        final_duration = round(max(time.time() - start_ts, 0.1), 1)
        final_rate = round((res["success"] + res["skipped"]) / final_duration, 1)
        report_url = f"/api/reports/view/{res['migration_id']}"
        csv_name = Path(res['csv_report']).name if res.get("csv_report") else None
        final_status = "COMPLETED" if res.get("failed", 0) == 0 else "PARTIAL"

        ACTIVE_TASKS[task_id].update({
            "status": final_status,
            "percent": 100.0,
            "success": res["success"],
            "skipped": res["skipped"],
            "failed": res["failed"],
            "duration_sec": final_duration,
            "msg_rate": final_rate,
            "html_report": report_url,
            "csv_report": f"/reports/{csv_name}" if csv_name else None,
        })

        broadcast_task_event(task_id, {
            "type": "completed",
            "task_id": task_id,
            "source": req.source.username,
            "percent": 100,
            "status": final_status,
            "success": res["success"],
            "skipped": res["skipped"],
            "failed": res["failed"],
            "duration_sec": final_duration,
            "msg_rate": final_rate,
            "html_report": report_url,
            "csv_report": f"/reports/{csv_name}" if csv_name else None,
        }, loop)

    except Exception as e:
        final_duration = round(max(time.time() - start_ts, 0.1), 1)
        is_stopped = str(e) == "TASK_STOPPED_BY_USER" or task_id in STOP_REQUESTED_TASKS

        if is_stopped:
            ACTIVE_TASKS[task_id].update({
                "status": "STOPPED",
                "duration_sec": final_duration,
                "error_message": "Tiến trình đã được dừng an toàn theo yêu cầu của quản trị viên.",
            })
            broadcast_task_event(task_id, {
                "type": "stopped",
                "task_id": task_id,
                "source": req.source.username,
                "duration_sec": final_duration,
                "message": "Tiến trình đã dừng theo yêu cầu.",
            }, loop)
        else:
            ACTIVE_TASKS[task_id].update({
                "status": "FAILED",
                "duration_sec": final_duration,
                "error_message": str(e),
            })
            broadcast_task_event(task_id, {
                "type": "error",
                "task_id": task_id,
                "source": req.source.username,
                "message": str(e),
            }, loop)


def run_batch_migration_worker(batch_id: str, req: BatchMigrateRequest, loop: asyncio.AbstractEventLoop):
    """Processes CSV accounts queue in background, updating ACTIVE_TASKS for each."""
    for idx, row in enumerate(req.accounts):
        sub_task_id = f"{batch_id}_{idx + 1}"
        src_user = (row.get("source_user") or row.get("source_email") or "").strip()
        dst_user = (row.get("dest_user") or row.get("dest_email") or "").strip()
        try:
            src_host = (row.get("source_host") or req.source_host or "").strip()
            src_port = int(row.get("source_port") or req.source_port or 993)
            src_ssl_val = row.get("source_ssl")
            src_ssl = (
                str(src_ssl_val).lower() in ("true", "1")
                if src_ssl_val is not None
                else (req.source_ssl if req.source_ssl is not None else True)
            )
            src_pass = (row.get("source_password") or row.get("source_pass") or "").strip()

            dst_host = (row.get("dest_host") or req.dest_host or "").strip()
            dst_port = int(row.get("dest_port") or req.dest_port or 993)
            dst_ssl_val = row.get("dest_ssl")
            dst_ssl = (
                str(dst_ssl_val).lower() in ("true", "1")
                if dst_ssl_val is not None
                else (req.dest_ssl if req.dest_ssl is not None else True)
            )
            dst_pass = (row.get("dest_password") or row.get("dest_pass") or "").strip()

            src = AccountCredentials(
                host=src_host,
                port=src_port,
                ssl=src_ssl,
                username=src_user,
                password=src_pass,
            )
            dst = AccountCredentials(
                host=dst_host,
                port=dst_port,
                ssl=dst_ssl,
                username=dst_user,
                password=dst_pass,
            )
            single_req = SingleMigrateRequest(
                source=src,
                dest=dst,
                sanitize_accents=req.sanitize_accents,
                batch_delay_ms=req.batch_delay_ms,
                force_remigrate=req.force_remigrate,
            )
            run_migration_worker(sub_task_id, single_req, loop)
        except Exception as e:
            ACTIVE_TASKS[sub_task_id] = {
                "task_id": sub_task_id,
                "source": src_user or "Unknown",
                "dest": dst_user or "Unknown",
                "status": "FAILED",
                "percent": 0.0,
                "current_folder": "-",
                "success": 0,
                "skipped": 0,
                "failed": 0,
                "started_at": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                "html_report": None,
                "csv_report": None,
                "error_message": str(e),
            }


@app.post("/api/migrate/start")
async def start_migration_task(req: SingleMigrateRequest, background_tasks: BackgroundTasks):
    """Starts migration task in background thread and returns task ID."""
    loop = asyncio.get_running_loop()
    task_id = f"task_{int(time.time())}_{secrets.token_hex(3)}"
    background_tasks.add_task(run_migration_worker, task_id, req, loop)
    return {
        "status": "started",
        "task_id": task_id,
        "message": f"Tiến trình di chuyển cho {req.source.username} đã khởi động trong nền"
    }


@app.post("/api/migrate/batch")
async def start_batch_migration(req: BatchMigrateRequest, background_tasks: BackgroundTasks):
    """Enqueues multiple accounts for background migration."""
    loop = asyncio.get_running_loop()
    batch_id = f"batch_{int(time.time())}"
    background_tasks.add_task(run_batch_migration_worker, batch_id, req, loop)
    return {
        "status": "started",
        "batch_id": batch_id,
        "total_accounts": len(req.accounts),
        "message": f"Đã khởi động hàng đợi di chuyển cho {len(req.accounts)} tài khoản trong nền"
    }


@app.get("/api/tasks/active")
async def get_active_tasks():
    """Returns all current active and recent background tasks with dynamic duration and rate."""
    now = time.time()
    result = []
    for t in ACTIVE_TASKS.values():
        item = dict(t)
        if item.get("status") == "RUNNING" and item.get("start_timestamp"):
            elapsed = max(now - item["start_timestamp"], 0.1)
            item["duration_sec"] = round(elapsed, 1)
            item["msg_rate"] = round((item.get("success", 0) + item.get("skipped", 0)) / elapsed, 1)
        result.append(item)
    return result


@app.post("/api/tasks/stop/{task_id}")
async def stop_task(task_id: str):
    """Signals a running background task to stop gracefully."""
    STOP_REQUESTED_TASKS.add(task_id)
    if task_id in ACTIVE_TASKS:
        ACTIVE_TASKS[task_id]["status"] = "STOPPING"
        ACTIVE_TASKS[task_id]["error_message"] = "Đang dừng tiến trình..."
    return {"status": "ok", "message": f"Đã gửi tín hiệu dừng tiến trình {task_id}"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Removes a finished/failed task from active tasks list."""
    if task_id in ACTIVE_TASKS:
        del ACTIVE_TASKS[task_id]
    STOP_REQUESTED_TASKS.discard(task_id)
    return {"status": "ok", "message": f"Đã xóa tiến trình {task_id}"}


@app.post("/api/tasks/clear-completed")
async def clear_completed_tasks():
    """Cleans up completed, stopped, and failed tasks from active tasks monitor."""
    to_clear = [
        tid for tid, t in ACTIVE_TASKS.items()
        if t.get("status") in ("COMPLETED", "FAILED", "STOPPED", "PARTIAL")
    ]
    for tid in to_clear:
        del ACTIVE_TASKS[tid]
        STOP_REQUESTED_TASKS.discard(tid)
    return {"status": "ok", "cleared_count": len(to_clear)}


@app.post("/api/tasks/seed-demo")
async def seed_demo_tasks():
    """Generates realistic demo tasks for visual preview and operational testing."""
    now = time.time()
    ACTIVE_TASKS["demo_task_1"] = {
        "task_id": "task_1729302199_a1b2",
        "source": "ceo@company-old.com",
        "dest": "ceo@company-new.com",
        "status": "RUNNING",
        "percent": 68.4,
        "current_folder": "INBOX/Projects 2026",
        "success": 1420,
        "skipped": 85,
        "failed": 3,
        "total_messages": 2200,
        "started_at": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "start_timestamp": now - 145.0,
        "duration_sec": 145.2,
        "msg_rate": 10.4,
        "html_report": None,
        "csv_report": None,
        "error_message": None,
    }
    ACTIVE_TASKS["demo_task_2"] = {
        "task_id": "task_1729301100_c3d4",
        "source": "sales@oldcorp.vn",
        "dest": "sales@newcorp.vn",
        "status": "COMPLETED",
        "percent": 100.0,
        "current_folder": "Sent Items",
        "success": 3560,
        "skipped": 412,
        "failed": 0,
        "total_messages": 3972,
        "started_at": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "start_timestamp": now - 320.0,
        "duration_sec": 320.0,
        "msg_rate": 12.4,
        "html_report": "/api/reports/view/1",
        "csv_report": "report_demo.csv",
        "error_message": None,
    }
    return {"status": "ok", "seeded": 2}


@app.get("/api/migrate/stream")
async def stream_migration_events(request: Request, task_id: Optional[str] = None):
    """SSE endpoint for real-time progress updates with per-task subscriber isolation."""
    queue: asyncio.Queue = asyncio.Queue()
    if task_id:
        TASK_SUBSCRIBERS[task_id].add(queue)
    else:
        GLOBAL_SUBSCRIBERS.add(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    if task_id and data.get("type") in ("completed", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            if task_id:
                TASK_SUBSCRIBERS[task_id].discard(queue)
                if not TASK_SUBSCRIBERS[task_id]:
                    TASK_SUBSCRIBERS.pop(task_id, None)
            else:
                GLOBAL_SUBSCRIBERS.discard(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/cache/clear")
async def clear_account_cache(account: str):
    """Clears SQLite migration state cache for an account."""
    state_db.clear_account_state(account)
    return {"status": "ok", "message": f"Đã xóa bộ nhớ đệm cho tài khoản {account}"}


@app.get("/api/sessions")
async def get_all_sessions():
    """Returns all migration sessions recorded in SQLite."""
    with state_db._get_connection() as conn:
        rows = conn.execute("SELECT * FROM migrations ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


@app.delete("/api/sessions/{session_id}")
@app.post("/api/sessions/{session_id}/delete")
async def delete_session(session_id: int):
    """Deletes a specific migration session and its message states."""
    summary = state_db.get_migration_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên di chuyển này")

    # Clean up corresponding reports if they exist
    source_acc = summary.get("source_account", "")
    if source_acc:
        clean_account = source_acc.replace("@", "_at_").replace(".", "_")
        for f in REPORTS_DIR.glob(f"*{clean_account}*"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

    success = state_db.delete_migration(session_id)
    if not success:
        raise HTTPException(status_code=500, detail="Không thể xóa phiên di chuyển")
    return {"status": "ok", "message": f"Đã xóa thành công lịch sử phiên #{session_id}"}


@app.delete("/api/sessions")
@app.post("/api/sessions/clear")
async def clear_all_sessions():
    """Deletes all migration sessions and resets history."""
    running_tasks = [t for t in ACTIVE_TASKS.values() if t.get("status") == "RUNNING"]
    if running_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"Đang có {len(running_tasks)} tiến trình di chuyển đang chạy. Vui lòng dừng hoặc chờ hoàn tất trước khi xóa toàn bộ lịch sử."
        )

    count = state_db.clear_all_migrations()

    # Clean up all report files
    try:
        for f in REPORTS_DIR.glob("*.*"):
            if f.suffix in (".html", ".csv") and f.name != ".gitkeep":
                f.unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Error cleaning reports folder: {e}")

    return {"status": "ok", "message": f"Đã xóa toàn bộ {count} phiên trong lịch sử di chuyển", "deleted_count": count}


@app.get("/api/reports/view/{session_id}", response_class=HTMLResponse)
async def view_session_report(session_id: int):
    """Renders or generates the HTML audit report for a session."""
    try:
        html_file, _ = reporter.generate_reports(session_id)
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404, detail="Report file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reports/{filename}")
async def download_report_file(filename: str):
    """Downloads report files safely with path traversal protection."""
    safe_path = PathSecurity.validate_safe_path(REPORTS_DIR, filename)
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=safe_path, filename=safe_path.name)


@app.get("/config/accounts.example.csv")
async def download_example_csv():
    """Serves the template accounts.example.csv for users."""
    safe_path = PathSecurity.validate_safe_path(Path("config"), "accounts.example.csv")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="accounts.example.csv not found")
    return FileResponse(path=safe_path, filename="accounts.example.csv", media_type="text/csv")


@app.get("/config/auth_check.example.csv")
async def download_auth_check_example_csv():
    """Serves the template auth_check.example.csv for users."""
    safe_path = PathSecurity.validate_safe_path(Path("config"), "auth_check.example.csv")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="auth_check.example.csv not found")
    return FileResponse(path=safe_path, filename="auth_check.example.csv", media_type="text/csv")


class ChangePasswordRequest(BaseModel):
    new_password: str


@app.post("/api/admin/change-password")
async def change_admin_password(req: ChangePasswordRequest, request: Request):
    """Updates admin password in current environment and updates .env file."""
    if not req.new_password or len(req.new_password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 4 ký tự.")
    new_pwd = req.new_password.strip()
    os.environ["ADMIN_PASSWORD"] = new_pwd
    env_file = Path(".env")
    try:
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8")
            if "ADMIN_PASSWORD=" in content:
                import re
                content = re.sub(r'ADMIN_PASSWORD=.*', f'ADMIN_PASSWORD="{new_pwd}"', content)
            else:
                content += f'\nADMIN_PASSWORD="{new_pwd}"\n'
            env_file.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist new password to .env: {e}")
    return {"status": "ok", "message": "Đã cập nhật mật khẩu quản trị viên thành công!"}


@app.post("/api/admin/clear-cache")
async def clear_system_cache():
    """Clears system and session cache."""
    return {"status": "ok", "message": "Đã làm sạch bộ nhớ cache phiên thành công!"}


@app.post("/api/retry/{session_id}")
async def retry_session_failed_items(session_id: int):
    """Triggers retry for failed messages in a session."""
    import csv
    from src.core.retry_engine import RetryEngine

    retry_engine = RetryEngine(state_db)
    summary = state_db.get_migration_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")

    src_creds = None
    dst_creds = None
    for candidate in [Path("config/accounts.csv"), Path("config/accounts.example.csv")]:
        if candidate.exists():
            with open(candidate, mode="r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("source_user", "").strip() == summary["source_account"]:
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
                        break
        if src_creds:
            break

    if not src_creds:
        return {
            "recovered": 0,
            "still_failed": summary.get("failed_messages", 0),
            "note": "Cần lưu tài khoản vào config/accounts.csv để tự động retry trên web",
        }

    return retry_engine.retry_session(session_id, src_creds, dst_creds)


def start_web_server(host: str = "0.0.0.0", port: int = 8080):
    """Launches the Uvicorn web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")
