import time
from typing import Callable, List, Optional
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

from src.core.folder_mapper import FolderMapper
from src.core.imap_client import IMAPClientWrapper
from src.core.models import FolderInfo, FolderRole
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import (
    ACCOUNT_PROGRESS_PERCENT,
    BYTES_TRANSFERRED_TOTAL,
    MESSAGES_FAILED_TOTAL,
    MESSAGES_MIGRATED_TOTAL,
)

logger = setup_logging()


class EmailMigrator:
    r"""
    Executes high-performance streaming migration between source and destination IMAP accounts:
    - Auto-creates missing destination folders (with UTF-7 encoding)
    - Preserves RFC 822 original message body, FLAGS (\Seen, \Flagged), and INTERNALDATE
    - Streams in configurable batches (avoids RAM spikes)
    - Integrates Prometheus metrics & structured Loki logging for error tracking
    """

    def __init__(self, batch_size: int = 50, max_message_size_bytes: int = 50 * 1024 * 1024):
        self.batch_size = batch_size
        self.max_message_size = max_message_size_bytes

    def migrate_folder(
        self,
        src_client: IMAPClient,
        dst_client: IMAPClient,
        src_account: str,
        dst_account: str,
        src_folder: str,
        dst_folder: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> tuple[int, int]:
        """
        Migrates all messages from src_folder to dst_folder.
        Returns: (success_count, failed_count)
        """
        success_count = 0
        failed_count = 0

        # 1. Ensure destination folder exists
        self._ensure_dest_folder(dst_client, dst_folder)

        # 2. Select source folder readonly
        src_client.select_folder(src_folder, readonly=True)
        uids = src_client.search(["ALL"])
        total_messages = len(uids)

        if total_messages == 0:
            logger.info("Folder is empty, skipping", account=src_account, folder=src_folder)
            return 0, 0

        logger.info(
            "Starting folder migration",
            source_account=src_account,
            dest_account=dst_account,
            source_folder=src_folder,
            dest_folder=dst_folder,
            total_messages=total_messages,
        )

        # 3. Process in batches
        for i in range(0, total_messages, self.batch_size):
            chunk_uids = uids[i:i + self.batch_size]

            try:
                # Fetch message body, flags, and internal date
                fetch_results = src_client.fetch(chunk_uids, ["RFC822", "FLAGS", "INTERNALDATE", "RFC822.SIZE"])
            except Exception as e:
                logger.error(
                    "Failed to fetch batch from source",
                    source_account=src_account,
                    folder=src_folder,
                    error_code="BATCH_FETCH_FAILED",
                    error_detail=str(e),
                )
                failed_count += len(chunk_uids)
                MESSAGES_FAILED_TOTAL.labels(
                    source_account=src_account, folder=src_folder, error_type="FETCH_ERROR"
                ).inc(len(chunk_uids))
                continue

            # Stream each message into destination
            for uid in chunk_uids:
                msg_data = fetch_results.get(uid)
                if not msg_data:
                    failed_count += 1
                    continue

                raw_body = msg_data.get(b"RFC822")
                flags = msg_data.get(b"FLAGS", ())
                internal_date = msg_data.get(b"INTERNALDATE")
                size = msg_data.get(b"RFC822.SIZE", len(raw_body) if raw_body else 0)

                # Validation checks
                if not raw_body:
                    failed_count += 1
                    err_code = "EMPTY_BODY"
                    err_detail = "Message has no RFC822 content payload"
                    MESSAGES_FAILED_TOTAL.labels(
                        source_account=src_account, folder=src_folder, error_type=err_code
                    ).inc()
                    logger.error(
                        "Message migration failed",
                        source_account=src_account,
                        dest_account=dst_account,
                        folder=src_folder,
                        uid=uid,
                        error_code=err_code,
                        error_detail=err_detail,
                    )
                    continue

                if size > self.max_message_size:
                    failed_count += 1
                    err_code = "SIZE_LIMIT_EXCEEDED"
                    err_detail = f"Message size {round(size / (1024*1024), 2)}MB exceeds limit of {round(self.max_message_size / (1024*1024), 2)}MB"
                    MESSAGES_FAILED_TOTAL.labels(
                        source_account=src_account, folder=src_folder, error_type=err_code
                    ).inc()
                    logger.error(
                        "Message migration failed",
                        source_account=src_account,
                        dest_account=dst_account,
                        folder=src_folder,
                        uid=uid,
                        error_code=err_code,
                        error_detail=err_detail,
                    )
                    continue

                # Append to destination
                try:
                    # Clean flags: filter out system internal flags that cannot be set on APPEND
                    append_flags = [f for f in flags if f.lower() not in (b"\\recent",)]
                    dst_client.append(dst_folder, raw_body, flags=append_flags, msg_time=internal_date)

                    success_count += 1
                    MESSAGES_MIGRATED_TOTAL.labels(source_account=src_account, folder=src_folder).inc()
                    BYTES_TRANSFERRED_TOTAL.labels(source_account=src_account).inc(size)

                except Exception as e:
                    failed_count += 1
                    err_code = "APPEND_FAILED"
                    err_detail = str(e)
                    MESSAGES_FAILED_TOTAL.labels(
                        source_account=src_account, folder=src_folder, error_type=err_code
                    ).inc()
                    logger.error(
                        "Message append failed",
                        source_account=src_account,
                        dest_account=dst_account,
                        folder=src_folder,
                        dest_folder=dst_folder,
                        uid=uid,
                        error_code=err_code,
                        error_detail=err_detail,
                    )

            if on_progress:
                on_progress(success_count + failed_count, total_messages)

        return success_count, failed_count

    def _ensure_dest_folder(self, dst_client: IMAPClient, folder_name: str):
        """Creates the destination folder if it does not exist yet."""
        if folder_name.upper() == "INBOX":
            return

        try:
            # Check if exists
            exists = dst_client.folder_exists(folder_name)
            if not exists:
                dst_client.create_folder(folder_name)
                logger.info("Created missing destination folder", folder=folder_name)
        except Exception as e:
            # Some servers raise error if folder already exists
            logger.debug("Folder existence check/creation note", folder=folder_name, error=str(e))
