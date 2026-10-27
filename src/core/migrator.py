import email
from email import policy
import time
from typing import Callable, List, Optional, Set
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

from src.core.folder_mapper import FolderMapper
from src.core.imap_client import IMAPClientWrapper
from src.core.models import FolderInfo, FolderRole
from src.storage.state_db import StateDatabase
from src.telemetry.logger import setup_logging
from src.telemetry.metrics import (
    ACCOUNT_PROGRESS_PERCENT,
    BYTES_TRANSFERRED_TOTAL,
    MESSAGES_FAILED_TOTAL,
    MESSAGES_MIGRATED_TOTAL,
)

from src.core.throttler import ProviderThrottler

logger = setup_logging()
header_parser = email.parser.BytesHeaderParser(policy=policy.default)


class EmailMigrator:
    r"""
    Executes high-performance streaming migration between source and destination IMAP accounts:
    - Auto-creates missing destination folders (with UTF-7 encoding)
    - Preserves RFC 822 original message body, FLAGS (\Seen, \Flagged), and INTERNALDATE
    - Streams in configurable batches (avoids RAM spikes)
    - Integrates Prometheus metrics & structured Loki logging for error tracking
    - Idempotency & Resume: deduplicates via Message-ID & content hash to prevent duplicates
    - Anti-ban: respects provider throttling with adaptive rate-limiting
    """

    def __init__(
        self,
        batch_size: int = 50,
        max_message_size_bytes: int = 50 * 1024 * 1024,
        state_db: Optional[StateDatabase] = None,
        throttler: Optional[ProviderThrottler] = None,
    ):
        self.batch_size = batch_size
        self.max_message_size = max_message_size_bytes
        self.state_db = state_db
        self.throttler = throttler or ProviderThrottler(batch_delay_seconds=0.05)

    @staticmethod
    def normalize_message_id(mid: Optional[object]) -> Optional[str]:
        """Normalizes Message-ID for reliable deduplication comparison across different mail servers."""
        if not mid:
            return None
        s = str(mid).strip()
        if s.startswith("<") and s.endswith(">"):
            s = s[1:-1].strip()
        return s.lower() if s else None

    def migrate_folder(
        self,
        src_client: IMAPClient,
        dst_client: IMAPClient,
        src_account: str,
        dst_account: str,
        src_folder: str,
        dst_folder: str,
        migration_id: Optional[int] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        force_remigrate: bool = False,
    ) -> tuple[int, int, int]:
        """
        Migrates all messages from src_folder to dst_folder.
        Returns: (success_count, failed_count, skipped_count)
        """
        success_count = 0
        failed_count = 0
        skipped_count = 0

        # 1. Ensure destination folder exists
        dst_folder = self._ensure_dest_folder(dst_client, dst_folder)

        # 1b. Live Destination Scan: Discover Message-IDs currently physical on destination
        existing_dest_message_ids: Set[str] = set()
        try:
            dst_client.select_folder(dst_folder, readonly=True)
            dst_uids = dst_client.search(["ALL"])
            if dst_uids:
                # Batch fetch headers (chunks of 250 UIDs to prevent buffer overflow/timeouts)
                scan_chunk_size = 250
                for chunk_idx in range(0, len(dst_uids), scan_chunk_size):
                    chunk = dst_uids[chunk_idx : chunk_idx + scan_chunk_size]
                    dst_headers = None
                    # Attempt fast BODY.PEEK, with fallback to RFC822.HEADER for strict IMAP servers
                    for fetch_cmd in (["BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)]"], ["BODY.PEEK[HEADER.FIELDS (Message-ID)]"], ["RFC822.HEADER"]):
                        try:
                            dst_headers = dst_client.fetch(chunk, fetch_cmd)
                            if dst_headers:
                                break
                        except Exception:
                            continue

                    if not dst_headers:
                        continue

                    for d_uid, d_res in dst_headers.items():
                        for k, v in d_res.items():
                            if isinstance(v, (bytes, str)):
                                raw_bytes = v if isinstance(v, bytes) else str(v).encode("latin-1", errors="ignore")
                                try:
                                    parsed_h = header_parser.parsebytes(raw_bytes, headersonly=True)
                                    d_mid = parsed_h.get("Message-ID")
                                    norm_mid = self.normalize_message_id(d_mid)
                                    if norm_mid:
                                        existing_dest_message_ids.add(norm_mid)
                                except Exception:
                                    # Fallback manual scan in case parsebytes encounters unexpected tokens
                                    v_str = raw_bytes.decode("latin-1", errors="ignore")
                                    for line in v_str.splitlines():
                                        if "message-id:" in line.lower():
                                            cand = line.split(":", 1)[1].strip()
                                            cand_norm = self.normalize_message_id(cand)
                                            if cand_norm:
                                                existing_dest_message_ids.add(cand_norm)

            logger.info(
                "Destination live verification pre-scanned",
                dest_folder=dst_folder,
                existing_count=len(existing_dest_message_ids),
            )
        except Exception as e:
            logger.warning("Could not pre-scan destination folder %s: %s", dst_folder, e)

        # 2. Select source folder readonly
        src_client.select_folder(src_folder, readonly=True)
        uids = src_client.search(["ALL"])
        total_messages = len(uids)

        if total_messages == 0:
            logger.info("Folder is empty, skipping", account=src_account, folder=src_folder)
            return 0, 0, 0

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
            self.throttler.throttle_batch()

            # Fetch with auto-retry on transient timeout/network drops
            fetch_results = None
            for fetch_attempt in range(1, 3):
                try:
                    fetch_results = src_client.fetch(chunk_uids, ["RFC822", "FLAGS", "INTERNALDATE", "RFC822.SIZE"])
                    break
                except Exception as e:
                    if fetch_attempt < 2 and any(k in str(e).lower() for k in ("timeout", "connection", "reset", "broken")):
                        logger.warning("Batch fetch attempt %d timed out/interrupted, retrying in 2s...", fetch_attempt)
                        time.sleep(2)
                        continue
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
                    break

            if not fetch_results:
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

                # Validation: empty body
                if not raw_body:
                    failed_count += 1
                    err_code = "EMPTY_BODY"
                    err_detail = "Message has no RFC822 content payload"
                    MESSAGES_FAILED_TOTAL.labels(
                        source_account=src_account, folder=src_folder, error_type=err_code
                    ).inc()
                    if self.state_db and migration_id:
                        self.state_db.record_failure(
                            migration_id, src_account, src_folder, uid, f"empty_{uid}", None, None, None, None, size, err_code, err_detail
                        )
                    continue

                # Parse header metadata for deduplication and reporting
                try:
                    headers = header_parser.parsebytes(raw_body, headersonly=True)
                    raw_message_id = headers.get("Message-ID")
                    norm_message_id = self.normalize_message_id(raw_message_id)
                    message_id = str(raw_message_id).strip() if raw_message_id else None
                    subject = headers.get("Subject", "")
                    sender = headers.get("From", "")
                    date_str = headers.get("Date", "")
                except Exception:
                    raw_message_id, norm_message_id, message_id, subject, sender, date_str = None, None, None, "", "", ""

                msg_hash = StateDatabase.compute_message_hash(message_id, date_str, subject, size)

                # Helper for human-readable size
                size_str = f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.2f} MB"
                safe_subject = (subject[:60] + "...") if len(subject) > 60 else (subject or "(No Subject)")
                safe_sender = (sender[:40] + "...") if len(sender) > 40 else (sender or "")
                safe_msg_id = message_id or f"UID-{uid}"

                # DEDUPLICATION & RECONCILIATION LOGIC:
                # 1. If message is PHYSICALLY ON DESTINATION right now:
                # Always SKIP it to guarantee 0% duplicates and keep destination intact.
                if norm_message_id and norm_message_id in existing_dest_message_ids:
                    skipped_count += 1
                    if migration_id:
                        self.state_db.record_skipped(migration_id)
                    logger.info(
                        f"msg {src_folder}/{uid} {{{size}}} skipped (already on host2) | MsgID: {safe_msg_id} | Subj: {safe_subject}",
                        action="SKIP",
                        status="SKIPPED",
                        source_account=src_account,
                        dest_account=dst_account,
                        folder=src_folder,
                        target_folder=dst_folder,
                        uid=uid,
                        message_id=message_id or "",
                        subject=subject,
                        sender=sender,
                        size_bytes=size,
                        size_str=size_str,
                    )
                    continue

                # 2. If destination check was empty/unavailable (e.g. brand new folder or server query failed),
                # fallback to checking SQLite state database if force_remigrate is False:
                if not existing_dest_message_ids and not force_remigrate:
                    if self.state_db and self.state_db.is_message_migrated(src_account, src_folder, msg_hash):
                        skipped_count += 1
                        if migration_id:
                            self.state_db.record_skipped(migration_id)
                        logger.info(
                            f"msg {src_folder}/{uid} {{{size}}} skipped (already on host2 cache) | MsgID: {safe_msg_id} | Subj: {safe_subject}",
                            action="SKIP",
                            status="SKIPPED",
                            source_account=src_account,
                            dest_account=dst_account,
                            folder=src_folder,
                            target_folder=dst_folder,
                            uid=uid,
                            message_id=message_id or "",
                            subject=subject,
                            sender=sender,
                            size_bytes=size,
                            size_str=size_str,
                        )
                        continue

                # Validation: size limit exceeded
                if size > self.max_message_size:
                    failed_count += 1
                    err_code = "OVERQUOTA" if "quota" in str(self.max_message_size).lower() else "SIZE_LIMIT_EXCEEDED"
                    err_detail = f"Message size {round(size / (1024*1024), 2)}MB exceeds limit of {round(self.max_message_size / (1024*1024), 2)}MB"
                    MESSAGES_FAILED_TOTAL.labels(
                        source_account=src_account, folder=src_folder, error_type=err_code
                    ).inc()
                    if self.state_db and migration_id:
                        self.state_db.record_failure(
                            migration_id, src_account, src_folder, uid, msg_hash, message_id, subject, sender, date_str, size, err_code, err_detail
                        )
                    logger.error(
                        f"Err {failed_count}/50: could not append msg {src_folder}/{uid} {{{size}}} ({err_code}: {err_detail})",
                        action="FAIL",
                        status="FAILED",
                        source_account=src_account,
                        dest_account=dst_account,
                        folder=src_folder,
                        target_folder=dst_folder,
                        uid=uid,
                        message_id=message_id or "",
                        subject=subject,
                        sender=sender,
                        size_bytes=size,
                        size_str=size_str,
                        error_code=err_code,
                        error_detail=err_detail,
                    )
                    continue

                # Append to destination with automatic namespace self-healing & auto-retry
                try:
                    append_flags = [f for f in flags if f.lower() not in (b"\\recent",)]
                    for append_attempt in range(1, 3):
                        try:
                            dst_client.append(dst_folder, raw_body, flags=append_flags, msg_time=internal_date)
                            break
                        except Exception as append_err:
                            err_str = str(append_err).lower()
                            if "nonexistent namespace" in err_str or "prefixed with: inbox" in err_str:
                                prefix = "INBOX." if ("." in dst_folder or "/" not in dst_folder) else "INBOX/"
                                fallback = dst_folder if dst_folder.startswith(prefix) else f"{prefix}{dst_folder}"
                                dst_folder = self._ensure_dest_folder(dst_client, fallback)
                                dst_client.append(dst_folder, raw_body, flags=append_flags, msg_time=internal_date)
                                break
                            elif append_attempt < 2 and any(k in err_str for k in ("timeout", "timed out", "connection", "reset", "broken")):
                                logger.warning("Append attempt %d timed out/interrupted, retrying in 2s...", append_attempt)
                                time.sleep(2)
                                continue
                            else:
                                raise append_err

                    success_count += 1
                    if norm_message_id:
                        existing_dest_message_ids.add(norm_message_id)
                    MESSAGES_MIGRATED_TOTAL.labels(source_account=src_account, folder=src_folder).inc()
                    BYTES_TRANSFERRED_TOTAL.labels(source_account=src_account).inc(size)

                    if self.state_db and migration_id:
                        self.state_db.record_success(
                            migration_id, src_account, src_folder, uid, msg_hash, message_id, subject, sender, date_str, size
                        )

                    logger.info(
                        f"msg {src_folder}/{uid} {{{size}}} copied to {dst_folder} | MsgID: {safe_msg_id} | Subj: {safe_subject}",
                        action="TRANSFER",
                        status="SUCCESS",
                        source_account=src_account,
                        dest_account=dst_account,
                        folder=src_folder,
                        target_folder=dst_folder,
                        uid=uid,
                        message_id=message_id or "",
                        subject=subject,
                        sender=sender,
                        size_bytes=size,
                        size_str=size_str,
                    )

                except Exception as e:
                    failed_count += 1
                    err_code = "could not append"
                    err_detail = str(e)
                    MESSAGES_FAILED_TOTAL.labels(
                        source_account=src_account, folder=src_folder, error_type="APPEND_FAILED"
                    ).inc()
                    if self.state_db and migration_id:
                        self.state_db.record_failure(
                            migration_id, src_account, src_folder, uid, msg_hash, message_id, subject, sender, date_str, size, "APPEND_FAILED", err_detail
                        )
                    logger.error(
                        f"Err {failed_count}/50: could not append msg {src_folder}/{uid} {{{size}}} ({err_detail})",
                        action="FAIL",
                        status="FAILED",
                        source_account=src_account,
                        dest_account=dst_account,
                        folder=src_folder,
                        target_folder=dst_folder,
                        uid=uid,
                        message_id=message_id or "",
                        subject=subject,
                        sender=sender,
                        size_bytes=size,
                        size_str=size_str,
                        error_code="APPEND_FAILED",
                        error_detail=err_detail,
                    )

            if on_progress:
                on_progress(success_count + failed_count + skipped_count, total_messages)

        return success_count, failed_count, skipped_count

    def _ensure_dest_folder(self, dst_client: IMAPClient, folder_name: str) -> str:
        """Creates destination folder if missing, handling Dovecot/cPanel namespace prefixing automatically."""
        if folder_name.upper() == "INBOX":
            return "INBOX"

        try:
            if not dst_client.folder_exists(folder_name):
                dst_client.create_folder(folder_name)
                logger.info("Created missing destination folder", folder=folder_name)
            return folder_name
        except Exception as e:
            err_msg = str(e).lower()
            if "nonexistent namespace" in err_msg or "prefixed with: inbox" in err_msg:
                prefix = "INBOX." if ("." in folder_name or "/" not in folder_name) else "INBOX/"
                fallback = folder_name if folder_name.startswith(prefix) else f"{prefix}{folder_name}"
                try:
                    if not dst_client.folder_exists(fallback):
                        dst_client.create_folder(fallback)
                        logger.info("Created missing destination folder with namespace prefix", folder=fallback)
                    return fallback
                except Exception as inner_e:
                    logger.debug("Fallback folder creation error", folder=fallback, error=str(inner_e))
            logger.debug("Folder existence check/creation note", folder=folder_name, error=str(e))
            return folder_name
