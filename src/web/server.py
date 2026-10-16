import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core.auth_checker import AuthChecker
from src.core.models import AccountCredentials, MailboxSummary
from src.core.service import MigrationService
from src.reports.reporter import MigrationReporter
from src.storage.state_db import StateDatabase

app = FastAPI(title="Py-IMAP Control Center", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


class SingleMigrateRequest(BaseModel):
    source: AccountCredentials
    dest: AccountCredentials
    sanitize_accents: bool = False
    batch_delay_ms: int = 50


class BatchCheckRequest(BaseModel):
    accounts: List[Dict[str, Any]]


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
        return summary.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def run_migration_worker(req: SingleMigrateRequest, loop: asyncio.AbstractEventLoop):
    """Background worker executing the migration and pushing progress events."""
    service = MigrationService(
        sanitize_accents=req.sanitize_accents,
        batch_delay_seconds=req.batch_delay_ms / 1000.0,
    )

    try:
        # Patch on_progress callback to push SSE
        orig_migrate_folder = service.migrator.migrate_folder

        def custom_migrate_folder(*args, **kwargs):
            src_folder = kwargs.get("src_folder") or args[4]
            user_cb = kwargs.get("on_progress")

            def wrapped_progress(done, total):
                if user_cb:
                    user_cb(done, total)
                pct = round((done / (total or 1)) * 100, 1)
                asyncio.run_coroutine_threadsafe(
                    progress_event_queue.put({
                        "type": "progress",
                        "percent": pct,
                        "folder": src_folder,
                        "success": service.state_db.get_migration_summary(kwargs.get("migration_id", 0)).get("migrated_messages", 0) if kwargs.get("migration_id") else done,
                        "skipped": 0,
                        "failed": 0,
                    }),
                    loop,
                )

            kwargs["on_progress"] = wrapped_progress
            return orig_migrate_folder(*args, **kwargs)

        service.migrator.migrate_folder = custom_migrate_folder

        res = service.migrate_account(req.source, req.dest)

        asyncio.run_coroutine_threadsafe(
            progress_event_queue.put({
                "type": "completed",
                "percent": 100,
                "success": res["success"],
                "skipped": res["skipped"],
                "failed": res["failed"],
                "html_report": f"/api/reports/view/{res['migration_id']}",
                "csv_report": f"/reports/{Path(res['csv_report']).name}" if res.get("csv_report") else None,
            }),
            loop,
        )

    except Exception as e:
        asyncio.run_coroutine_threadsafe(
            progress_event_queue.put({
                "type": "error",
                "message": str(e),
            }),
            loop,
        )


@app.post("/api/migrate/start")
async def start_migration_task(req: SingleMigrateRequest, background_tasks: BackgroundTasks):
    """Starts migration task in background thread."""
    loop = asyncio.get_running_loop()
    background_tasks.add_task(run_migration_worker, req, loop)
    return {"status": "started", "message": "Migration initiated"}


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
    """Downloads report files."""
    file_path = REPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename)


@app.get("/config/accounts.example.csv")
async def download_example_csv():
    """Serves the template accounts.example.csv for users."""
    csv_file = Path("config/accounts.example.csv")
    if not csv_file.exists():
        raise HTTPException(status_code=404, detail="accounts.example.csv not found")
    return FileResponse(path=csv_file, filename="accounts.example.csv", media_type="text/csv")


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
