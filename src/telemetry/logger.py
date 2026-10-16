import logging
import os
import sys
from pathlib import Path
import structlog


def setup_logging(log_dir: str = "/var/log/email_migrator", log_filename: str = "app.json.log"):
    """
    Sets up dual-target logging:
    1. Rich colored human-readable log to stderr / console.
    2. Structured JSON line logs to a file for Promtail/Loki ingestion.
    """
    # Ensure log directory exists
    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
        file_logging_available = True
    except Exception as e:
        sys.stderr.write(f"Warning: Cannot create log directory {log_dir}: {e}. Fallback to stdout only.\n")
        file_logging_available = False

    # Standard logging configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers
    root_logger.handlers = []

    # Console Handler (Human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # File Handler (JSON lines for Promtail/Loki)
    if file_logging_available:
        file_handler = logging.FileHandler(log_path / log_filename, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        # Use simple Formatter for file as structlog will format it as JSON
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(file_handler)

    def custom_dual_renderer(logger, name, event_dict):
        # We can let structlog format JSON for file handlers and pretty for console
        return event_dict

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if os.environ.get("LOG_FORMAT", "json").lower() == "json"
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("email_migrator")
