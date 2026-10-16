import argparse
import random
import time
from rich.console import Console
from rich.panel import Panel

from src.telemetry.logger import setup_logging
from src.telemetry.metrics import (
    ACCOUNT_PROGRESS_PERCENT,
    ACTIVE_WORKERS,
    BYTES_TRANSFERRED_TOTAL,
    FOLDER_MIGRATION_STATUS,
    MESSAGE_PROCESS_SECONDS,
    MESSAGES_FAILED_TOTAL,
    MESSAGES_MIGRATED_TOTAL,
    SOURCE_MAILBOX_MESSAGES_TOTAL,
    SOURCE_MAILBOX_SIZE_BYTES,
    start_metrics_server,
)

console = Console()


def run_simulation(logger):
    """
    Simulates real-world multi-account migration:
    - Pre-flight quota/size inspection
    - Folder discovery & mapping
    - Streaming message migration with metrics
    - Realistic error occurrences to test Grafana alerting & error drill-down
    """
    logger.info("Starting simulation mode for Prometheus & Grafana verification")

    accounts = [
        {"src": "ceo@source-company.com", "dst": "ceo@dest-corp.com", "size_mb": 4200, "msgs": 1500},
        {"src": "sales@source-company.com", "dst": "sales@dest-corp.com", "size_mb": 8500, "msgs": 3200},
        {"src": "tech@source-company.com", "dst": "tech@dest-corp.com", "size_mb": 12000, "msgs": 4800},
    ]

    folders = ["INBOX", "Sent Items", "Archive", "Finance 2025"]

    for acc in accounts:
        SOURCE_MAILBOX_SIZE_BYTES.labels(source_account=acc["src"]).set(acc["size_mb"] * 1024 * 1024)
        SOURCE_MAILBOX_MESSAGES_TOTAL.labels(source_account=acc["src"]).set(acc["msgs"])
        ACCOUNT_PROGRESS_PERCENT.labels(source_account=acc["src"], dest_account=acc["dst"]).set(0)

    ACTIVE_WORKERS.set(len(accounts))

    logger.info("Pre-flight scan completed", total_accounts=len(accounts))

    # Migration simulation loop
    completed_counts = {acc["src"]: 0 for acc in accounts}

    while True:
        for acc in accounts:
            src = acc["src"]
            dst = acc["dst"]
            total_msgs = acc["msgs"]

            if completed_counts[src] >= total_msgs:
                continue

            folder = random.choice(folders)
            FOLDER_MIGRATION_STATUS.labels(source_account=src, folder=folder).set(1)  # In-Progress

            # Simulate batch of 5-15 messages
            batch_size = random.randint(5, 15)
            for _ in range(batch_size):
                if completed_counts[src] >= total_msgs:
                    break

                with MESSAGE_PROCESS_SECONDS.labels(source_account=src).time():
                    time.sleep(random.uniform(0.01, 0.05))

                # 97% success, 3% realistic failures
                if random.random() < 0.97:
                    msg_size = random.randint(15_000, 4_500_000)  # 15KB - 4.5MB
                    MESSAGES_MIGRATED_TOTAL.labels(source_account=src, folder=folder).inc()
                    BYTES_TRANSFERRED_TOTAL.labels(source_account=src).inc(msg_size)
                    completed_counts[src] += 1
                else:
                    error_types = [
                        ("ATTACHMENT_SIZE_EXCEEDED", "Payload exceeds 35MB host limit"),
                        ("MIME_PARSING_FAILED", "Corrupted boundary header in RFC822"),
                        ("IMAP_TIMEOUT", "Socket timed out after 30s during APPEND"),
                    ]
                    err_code, err_desc = random.choice(error_types)
                    MESSAGES_FAILED_TOTAL.labels(
                        source_account=src, folder=folder, error_type=err_code
                    ).inc()

                    logger.error(
                        "Failed to migrate message",
                        source_account=src,
                        dest_account=dst,
                        folder=folder,
                        uid=random.randint(1000, 99999),
                        error_code=err_code,
                        error_detail=err_desc,
                    )

            # Update progress
            progress = round((completed_counts[src] / total_msgs) * 100, 2)
            ACCOUNT_PROGRESS_PERCENT.labels(source_account=src, dest_account=dst).set(progress)

            if completed_counts[src] >= total_msgs:
                FOLDER_MIGRATION_STATUS.labels(source_account=src, folder=folder).set(2)  # Completed
                logger.info("Account migration completed", account=src, total_migrated=completed_counts[src])

        # Check if all done
        if all(completed_counts[acc["src"]] >= acc["msgs"] for acc in accounts):
            ACTIVE_WORKERS.set(0)
            logger.info("All accounts completed migration simulation!")
            time.sleep(10)
            # Reset counters for continuous dashboard demonstration
            for acc in accounts:
                completed_counts[acc["src"]] = 0
            ACTIVE_WORKERS.set(len(accounts))


def main():
    parser = argparse.ArgumentParser(description="Python IMAP Email Migration Engine")
    parser.add_argument("--simulate", action="store_true", default=True, help="Run simulation mode")
    parser.add_argument("--port", type=int, default=8000, help="Prometheus metrics port")
    args = parser.parse_args()

    logger = setup_logging()

    console.print(
        Panel.fit(
            "[bold cyan]PY-IMAP EMAIL MIGRATION ENGINE[/bold cyan]\n"
            f"[green]Prometheus Metrics Server listening on port :[/green][bold yellow]{args.port}[/bold yellow]\n"
            "[magenta]Monitoring ready for Prometheus + Grafana + Loki[/magenta]",
            border_style="cyan",
        )
    )

    # Start Prometheus exporter HTTP server
    start_metrics_server(port=args.port)
    logger.info("Prometheus metrics server started", port=args.port)

    if args.simulate:
        run_simulation(logger)
    else:
        logger.info("Production mode selected. Ready for account workers.")
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
