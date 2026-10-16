import re
from typing import Dict, List, Optional, Set
from imapclient import imap_utf7

from src.core.models import FolderInfo, FolderRole

# Standard RFC 6154 attributes mapped to our canonical roles
SPECIAL_USE_FLAGS = {
    b"\\sent": FolderRole.SENT,
    b"\\drafts": FolderRole.DRAFTS,
    b"\\trash": FolderRole.TRASH,
    b"\\junk": FolderRole.JUNK,
    b"\\archive": FolderRole.ARCHIVE,
    b"\\all": FolderRole.ARCHIVE,
}

# Fallback alias lists (case-insensitive) for servers lacking RFC 6154
CANONICAL_ALIASES: Dict[FolderRole, List[str]] = {
    FolderRole.INBOX: ["inbox"],
    FolderRole.SENT: [
        "sent", "sent items", "sent messages", "thư đã gửi", "[gmail]/sent mail",
        "inbox.sent", "inbox/sent"
    ],
    FolderRole.DRAFTS: [
        "drafts", "bản nháp", "[gmail]/drafts", "inbox.drafts", "inbox/drafts"
    ],
    FolderRole.TRASH: [
        "trash", "deleted items", "thùng rác", "[gmail]/trash", "inbox.trash", "inbox/trash"
    ],
    FolderRole.JUNK: [
        "junk", "spam", "thư rác", "[gmail]/spam", "inbox.spam", "inbox/junk"
    ],
    FolderRole.ARCHIVE: [
        "archive", "lưu trữ", "[gmail]/all mail"
    ],
}


class FolderMapper:
    """
    Handles folder identification, exclusion rules, and cross-server hierarchy mapping:
    - Identifies canonical roles via RFC 6154 SPECIAL-USE attributes & regex fallbacks
    - Converts delimiters between source and target hosts (e.g., '/' <-> '.')
    - Handles UTF-7 encoded folder names (Vietnamese / Unicode)
    """

    def __init__(self, exclude_patterns: Optional[List[str]] = None, custom_mappings: Optional[Dict[str, str]] = None):
        self.exclude_patterns = [
            re.compile(p, re.IGNORECASE) for p in (exclude_patterns or [
                r".*spam.*", r".*junk.*", r".*trash.*", r".*deleted.*", r"\[gmail\]/all mail"
            ])
        ]
        self.custom_mappings = custom_mappings or {}

    @staticmethod
    def decode_folder_name(raw_name: str) -> str:
        """Decodes modified UTF-7 IMAP folder names to readable Unicode."""
        try:
            return imap_utf7.decode(raw_name.encode("latin-1"))
        except Exception:
            return raw_name

    @staticmethod
    def encode_folder_name(unicode_name: str) -> str:
        """Encodes Unicode string into IMAP modified UTF-7."""
        try:
            return imap_utf7.encode(unicode_name).decode("latin-1")
        except Exception:
            return unicode_name

    def identify_role(self, folder_name: str, raw_flags: List) -> FolderRole:
        """Determines the canonical role using flags first, then names."""
        clean_name = folder_name.strip()
        lower_name = clean_name.lower()

        if lower_name == "inbox":
            return FolderRole.INBOX

        # 1. Check RFC 6154 Flags
        for flag in raw_flags:
            flag_bytes = flag.lower() if isinstance(flag, bytes) else str(flag).lower().encode()
            if flag_bytes in SPECIAL_USE_FLAGS:
                return SPECIAL_USE_FLAGS[flag_bytes]

        # 2. Check canonical aliases fallback
        for role, aliases in CANONICAL_ALIASES.items():
            if lower_name in aliases:
                return role

        return FolderRole.CUSTOM

    def is_excluded(self, folder_name: str, role: FolderRole) -> bool:
        """Checks if folder should be skipped based on exclusion rules or role."""
        if role in (FolderRole.TRASH, FolderRole.JUNK):
            return True

        for pattern in self.exclude_patterns:
            if pattern.search(folder_name):
                return True

        return False

    def map_folder_name(
        self,
        source_folder: str,
        source_role: FolderRole,
        source_delim: str,
        dest_delim: str,
        dest_canonical_map: Dict[FolderRole, str]
    ) -> str:
        """
        Calculates destination folder name:
        1. If source folder is mapped to a canonical role (e.g., SENT) and destination has a known role folder, map directly.
        2. Otherwise, adapt hierarchy delimiter (e.g. Projects/2025 -> Projects.2025)
        """
        # User custom override
        if source_folder in self.custom_mappings:
            return self.custom_mappings[source_folder]

        # Match by canonical role if available on destination
        if source_role in dest_canonical_map:
            return dest_canonical_map[source_role]

        # If it's INBOX itself
        if source_role == FolderRole.INBOX:
            return "INBOX"

        # General hierarchical folder: translate delimiter
        if source_delim != dest_delim:
            return source_folder.replace(source_delim, dest_delim)

        return source_folder
