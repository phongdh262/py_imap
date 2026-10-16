from prometheus_client import Counter, Gauge, Histogram, start_http_server

# ==========================================
# PROMETHEUS METRICS DEFINITIONS
# ==========================================

# Counters
MESSAGES_MIGRATED_TOTAL = Counter(
    "email_migration_messages_migrated_total",
    "Total number of email messages migrated successfully",
    ["source_account", "folder"],
)

MESSAGES_FAILED_TOTAL = Counter(
    "email_migration_messages_failed_total",
    "Total number of email messages that failed migration",
    ["source_account", "folder", "error_type"],
)

BYTES_TRANSFERRED_TOTAL = Counter(
    "email_migration_bytes_transferred_total",
    "Total volume of email payload transferred in bytes",
    ["source_account"],
)

AUTH_CHECKS_TOTAL = Counter(
    "email_auth_checks_total",
    "Total credential/app-password check attempts",
    ["account", "host", "status"],
)

# Gauges
ACCOUNT_AUTH_STATUS = Gauge(
    "email_account_auth_status",
    "Authentication status of account: 1=Valid, 0=Failed",
    ["account", "host", "error_reason"],
)

ACTIVE_WORKERS = Gauge(
    "email_migration_active_workers",
    "Number of active migration workers currently running",
)

ACCOUNT_PROGRESS_PERCENT = Gauge(
    "email_migration_account_progress_percent",
    "Current progress percentage of an account migration (0 to 100)",
    ["source_account", "dest_account"],
)

SOURCE_MAILBOX_SIZE_BYTES = Gauge(
    "email_migration_source_mailbox_size_bytes",
    "Total size of source mailbox in bytes as reported by pre-flight inspection",
    ["source_account"],
)

SOURCE_MAILBOX_MESSAGES_TOTAL = Gauge(
    "email_migration_source_mailbox_messages_total",
    "Total number of messages in source mailbox across all folders",
    ["source_account"],
)

FOLDER_MIGRATION_STATUS = Gauge(
    "email_migration_folder_status",
    "Status of folder migration: 0=Pending, 1=In-Progress, 2=Completed, 3=Failed",
    ["source_account", "folder"],
)

# Histograms
MESSAGE_PROCESS_SECONDS = Histogram(
    "email_migration_message_process_seconds",
    "Time taken to stream and append a single message from source to destination",
    ["source_account"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def start_metrics_server(port: int = 8000, host: str = "0.0.0.0"):
    """Starts the Prometheus HTTP metrics exporter server."""
    start_http_server(port, addr=host)
