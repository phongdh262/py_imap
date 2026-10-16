import logging
from typing import Dict, List, Optional
from imapclient import IMAPClient

from src.core.folder_mapper import FolderMapper
from src.core.imap_client import IMAPClientWrapper
from src.core.models import FolderInfo, FolderRole, MailboxSummary

logger = logging.getLogger("email_migrator.inspector")


class MailboxInspector:
    """
    Performs pre-flight inspection of an IMAP mailbox:
    - Queries quota limits & usage via RFC 2087
    - Discovers folder hierarchy, roles, and message counts
    - Computes total size in bytes using RFC 8438 (STATUS=SIZE) or fast batch RFC822.SIZE fetch
    """

    def __init__(self, mapper: Optional[FolderMapper] = None):
        self.mapper = mapper or FolderMapper()

    def inspect(self, client_wrapper: IMAPClientWrapper) -> MailboxSummary:
        """Inspects source mailbox and builds a complete MailboxSummary."""
        client: IMAPClient = client_wrapper.client
        username = client_wrapper.creds.username
        summary = MailboxSummary(account=username)

        # 1. Quota Inspection (RFC 2087)
        if client_wrapper.supports_quota:
            try:
                quota_roots = client.get_quota_root("INBOX")
                if quota_roots and len(quota_roots) > 1:
                    quotas = quota_roots[1]
                    for resource, (used_kb, max_kb) in quotas:
                        if resource.upper() == b"STORAGE":
                            summary.quota_used_bytes = used_kb * 1024
                            summary.quota_limit_bytes = max_kb * 1024
                            break
            except Exception as e:
                logger.warning("Quota query failed for %s: %s", username, e)

        # 2. Discover all folders
        raw_folders = client.list_folders()
        total_msgs = 0
        total_size = 0

        for flags, delimiter, raw_name in raw_folders:
            delim_str = delimiter.decode("latin-1") if isinstance(delimiter, bytes) else str(delimiter)
            folder_name = self.mapper.decode_folder_name(raw_name)

            # Check if selectable (skip \Noselect folders)
            is_selectable = not any(
                (f.lower() == b"\\noselect" if isinstance(f, bytes) else str(f).lower() == "\\noselect")
                for f in flags
            )

            role = self.mapper.identify_role(folder_name, flags)
            is_excluded = self.mapper.is_excluded(folder_name, role)

            msg_count = 0
            folder_size = 0

            if is_selectable and not is_excluded:
                msg_count, folder_size = self._get_folder_stats(client, client_wrapper, raw_name)
                total_msgs += msg_count
                total_size += folder_size

            folder_info = FolderInfo(
                name=folder_name,
                delimiter=delim_str,
                flags=[f.decode("latin-1") if isinstance(f, bytes) else str(f) for f in flags],
                role=role,
                messages_count=msg_count,
                size_bytes=folder_size,
                is_selectable=is_selectable,
                is_excluded=is_excluded,
            )
            summary.folders.append(folder_info)

        summary.total_messages = total_msgs
        summary.total_size_bytes = total_size

        return summary

    def _get_folder_stats(
        self, client: IMAPClient, client_wrapper: IMAPClientWrapper, raw_name: str
    ) -> tuple[int, int]:
        """Calculates message count and size in bytes for a selectable folder."""
        try:
            # High-speed path: RFC 8438 STATUS=SIZE
            if client_wrapper.supports_status_size:
                try:
                    status = client.folder_status(raw_name, [b"MESSAGES", b"SIZE"])
                    msgs = status.get(b"MESSAGES", 0)
                    size = status.get(b"SIZE", 0)
                    return msgs, size
                except Exception:
                    pass

            # Standard path: Query message count via STATUS (MESSAGES)
            status = client.folder_status(raw_name, [b"MESSAGES"])
            msgs = status.get(b"MESSAGES", 0)
            if msgs == 0:
                return 0, 0

            # Select folder readonly and fast fetch RFC822.SIZE metadata
            client.select_folder(raw_name, readonly=True)
            uids = client.search(["ALL"])
            if not uids:
                return 0, 0

            # Batch fetch sizes (chunks of 1000 UIDs)
            total_size = 0
            chunk_size = 1000
            for i in range(0, len(uids), chunk_size):
                chunk = uids[i:i + chunk_size]
                fetch_data = client.fetch(chunk, ["RFC822.SIZE"])
                for uid, data in fetch_data.items():
                    total_size += data.get(b"RFC822.SIZE", 0)

            return len(uids), total_size

        except Exception as e:
            logger.warning("Could not calculate size for folder %s: %s", raw_name, e)
            return 0, 0
