import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any, Dict, List, Optional

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

# Global Event Queue for SSE Streaming
progress_event_queue: asyncio.Queue = asyncio.Queue()


class LoginRequest(BaseModel):
    username: str
    password: str


class SingleMigrateRequest(BaseModel):
    source: AccountCredentials
    dest: AccountCredentials
    sanitize_accents: bool = False
    batch_delay_ms: int = 50


class BatchCheckRequest(BaseModel):
    accounts: List[Dict[str, Any]]


class BatchMigrateRequest(BaseModel):
    accounts: List[Dict[str, Any]]
    sanitize_accents: bool = False
    batch_delay_ms: int = 50


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
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


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
        creds_list.append(
            AccountCredentials(
                host=row.get("source_host", "").strip(),
                port=int(row.get("source_port", 993)),
                ssl=str(row.get("source_ssl", "true")).lower() in ("true", "1"),
                username=row.get("source_user", "").strip(),
                password=row.get("source_password", "").strip(),
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


@app.post("/api/inspect")
async def inspect_source_mailbox(creds: AccountCredentials):
    """Pre-flight inspection: returns mailbox size in MB/GB, quota, and folders."""
    try:
        summary: MailboxSummary = migration_service.inspect_source(creds)
        data = summary.model_dump()
        # Guarantee calculated fields are present
        data["total_size_mb"] = summary.total_size_mb
        data["total_size_gb"] = summary.total_size_gb
        data["quota"] = summary.quota
        for idx, f in enumerate(summary.folders):
            if idx < len(data.get("folders", [])):
                data["folders"][idx]["size_mb"] = f.size_mb
                data["folders"][idx]["destination_folder"] = f.destination_folder
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def run_migration_worker(task_id: str, req: SingleMigrateRequest, loop: asyncio.AbstractEventLoop):
    """Background worker executing the migration, updating ACTIVE_TASKS, and pushing SSE events."""
    service = MigrationService(
        sanitize_accents=req.sanitize_accents,
        batch_delay_seconds=req.batch_delay_ms / 1000.0,
    )

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
        "started_at": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "html_report": None,
        "csv_report": None,
        "error_message": None,
    }

    try:
        orig_migrate_folder = service.migrator.migrate_folder

        def custom_migrate_folder(*args, **kwargs):
            src_folder = kwargs.get("src_folder") or args[4]
            user_cb = kwargs.get("on_progress")

            def wrapped_progress(done, total):
                if user_cb:
                    user_cb(done, total)
                pct = round((done / (total or 1)) * 100, 1)

                task_data = ACTIVE_TASKS.get(task_id, {})
                task_data["percent"] = pct
                task_data["current_folder"] = src_folder
                summary = service.state_db.get_migration_summary(kwargs.get("migration_id", 0)) if kwargs.get("migration_id") else {}
                task_data["success"] = summary.get("migrated_messages", done)
                task_data["skipped"] = summary.get("skipped_messages", 0)
                task_data["failed"] = summary.get("failed_messages", 0)

                asyncio.run_coroutine_threadsafe(
                    progress_event_queue.put({
                        "type": "progress",
                        "task_id": task_id,
                        "source": req.source.username,
                        "percent": pct,
                        "folder": src_folder,
                        "success": task_data["success"],
                        "skipped": task_data["skipped"],
                        "failed": task_data["failed"],
                    }),
                    loop,
                )

            kwargs["on_progress"] = wrapped_progress
            return orig_migrate_folder(*args, **kwargs)

        service.migrator.migrate_folder = custom_migrate_folder
        res = service.migrate_account(req.source, req.dest)

        report_url = f"/api/reports/view/{res['migration_id']}"
        csv_name = Path(res['csv_report']).name if res.get("csv_report") else None

        ACTIVE_TASKS[task_id].update({
            "status": "COMPLETED",
            "percent": 100.0,
            "success": res["success"],
            "skipped": res["skipped"],
            "failed": res["failed"],
            "html_report": report_url,
            "csv_report": f"/reports/{csv_name}" if csv_name else None,
        })

        asyncio.run_coroutine_threadsafe(
            progress_event_queue.put({
                "type": "completed",
                "task_id": task_id,
                "source": req.source.username,
                "percent": 100,
                "success": res["success"],
                "skipped": res["skipped"],
                "failed": res["failed"],
                "html_report": report_url,
                "csv_report": f"/reports/{csv_name}" if csv_name else None,
            }),
            loop,
        )

    except Exception as e:
        ACTIVE_TASKS[task_id].update({
            "status": "FAILED",
            "error_message": str(e),
        })
        asyncio.run_coroutine_threadsafe(
            progress_event_queue.put({
                "type": "error",
                "task_id": task_id,
                "source": req.source.username,
                "message": str(e),
            }),
            loop,
        )


def run_batch_migration_worker(batch_id: str, req: BatchMigrateRequest, loop: asyncio.AbstractEventLoop):
    """Processes CSV accounts queue in background, updating ACTIVE_TASKS for each."""
    for idx, row in enumerate(req.accounts):
        sub_task_id = f"{batch_id}_{idx + 1}"
        try:
            src = AccountCredentials(
                host=row.get("source_host", "").strip(),
                port=int(row.get("source_port", 993)),
                ssl=str(row.get("source_ssl", "true")).lower() in ("true", "1"),
                username=row.get("source_user", "").strip(),
                password=row.get("source_password", "").strip(),
            )
            dst = AccountCredentials(
                host=row.get("dest_host", "").strip(),
                port=int(row.get("dest_port", 993)),
                ssl=str(row.get("dest_ssl", "true")).lower() in ("true", "1"),
                username=row.get("dest_user", "").strip(),
                password=row.get("dest_password", "").strip(),
            )
            single_req = SingleMigrateRequest(
                source=src,
                dest=dst,
                sanitize_accents=req.sanitize_accents,
                batch_delay_ms=req.batch_delay_ms,
            )
            run_migration_worker(sub_task_id, single_req, loop)
        except Exception as e:
            ACTIVE_TASKS[sub_task_id] = {
                "task_id": sub_task_id,
                "source": row.get("source_user", "Unknown"),
                "dest": row.get("dest_user", "Unknown"),
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
    """Returns all current active and recent background tasks."""
    return list(ACTIVE_TASKS.values())


@app.get("/api/migrate/stream")
async def stream_migration_events():
    """SSE endpoint for real-time progress updates."""
    async def event_generator():
        while True:
            data = await progress_event_queue.get()
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("type") in ("completed", "error"):
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/sessions")
async def get_all_sessions():
    """Returns all migration sessions recorded in SQLite."""
    with state_db._get_connection() as conn:
        rows = conn.execute("SELECT * FROM migrations ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


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
