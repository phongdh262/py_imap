import re
import unicodedata
from typing import Any, Dict, List, Optional
from imapclient import imap_utf7

from src.core.models import FolderInfo, FolderRole
from src.core.provider_rules import ProviderRulesManager

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
        "inbox.sent", "inbox/sent", "отправленные"
    ],
    FolderRole.DRAFTS: [
        "drafts", "bản nháp", "[gmail]/drafts", "inbox.drafts", "inbox/drafts", "черновики"
    ],
    FolderRole.TRASH: [
        "trash", "deleted items", "thùng rác", "[gmail]/trash", "inbox.trash", "inbox/trash", "удаленные"
    ],
    FolderRole.JUNK: [
        "junk", "spam", "thư rác", "[gmail]/spam", "inbox.spam", "inbox/junk", "спам"
    ],
    FolderRole.ARCHIVE: [
        "archive", "lưu trữ", "[gmail]/all mail", "архив"
    ],
}


class FolderMapper:
    """
    Handles folder identification, exclusion rules, cross-server hierarchy mapping,
    and advanced Vietnamese / Yandex encoding normalization:
    - Automatically heals Modified UTF-7 (mUTF-7) and Mojibake (UTF-8 masquerading as Latin-1)
    - Integrates ProviderRulesManager for provider-aware folder exclusions (e.g. [Gmail]/All Mail)
    - Supports optional Vietnamese accent stripping ('Thư đã gửi' -> 'Thu da gui') for legacy servers
    - Delimiter conversion ('/' <-> '.')
    """

    def __init__(
        self,
        exclude_patterns: Optional[List[str]] = None,
        custom_mappings: Optional[Dict[str, str]] = None,
        sanitize_accents: bool = False,
        source_provider: str = "generic",
        dest_provider: str = "generic",
        rules_manager: Optional[ProviderRulesManager] = None,
    ):
        self.rules_manager = rules_manager or ProviderRulesManager()
        self.source_provider = source_provider
        self.dest_provider = dest_provider

        # Merge provider-specific exclusions with custom exclude patterns
        if exclude_patterns is not None:
            raw_patterns = exclude_patterns
        else:
            raw_patterns = self.rules_manager.get_provider_rules(source_provider).get(
                "exclude_by_default",
                [r".*spam.*", r".*junk.*", r".*trash.*", r".*deleted.*", r"\[gmail\]/all mail"]
            )

        self.exclude_patterns = [
            re.compile(p, re.IGNORECASE) for p in raw_patterns
        ]
        self.custom_mappings = custom_mappings or {}
        self.sanitize_accents = sanitize_accents

    @staticmethod
    def decode_folder_name(raw_name: Any) -> str:
        """
        Robust multi-layer decoder resolving Yandex & cPanel Vietnamese encoding issues:
        1. Handles raw bytes vs string
        2. Resolves Modified UTF-7 (&...-) used in IMAP RFC 2152
        3. Detects and heals Mojibake (UTF-8 decoded as Latin-1)
        """
        if isinstance(raw_name, bytes):
            try:
                s = raw_name.decode("utf-8")
            except UnicodeDecodeError:
                s = raw_name.decode("latin-1")
        else:
            s = str(raw_name)

        # 1. Resolve Modified UTF-7 (e.g., 'Th&AbA- &ARE-&AOM g&Hu0-i')
        if "&" in s and "-" in s:
            try:
                decoded = imap_utf7.decode(s.encode("latin-1"))
                if decoded:
                    return decoded
            except Exception:
                pass

        # 2. Resolve Mojibake: UTF-8 erroneously decoded as Latin-1 (e.g., 'ThÆ° Ä\x91Ã£')
        try:
            fixed = s.encode("latin-1").decode("utf-8")
            # If successfully decoded into valid UTF-8 and shortened, it was mojibake
            if fixed != s and len(fixed) < len(s):
                return fixed
        except Exception:
            pass

        return s

    @staticmethod
    def encode_folder_name(unicode_name: str) -> str:
        """Encodes Unicode string into IMAP modified UTF-7."""
        try:
            return imap_utf7.encode(unicode_name).decode("latin-1")
        except Exception:
            return unicode_name

    @staticmethod
    def remove_vietnamese_accents(text: str) -> str:
        """
        Converts Vietnamese accented string into clean ASCII:
        'Thư đã gửi' -> 'Thu da gui', 'Hợp đồng 2026' -> 'Hop dong 2026'.
        Prevents corrupted names on legacy Dovecot / Exchange servers that do not support Unicode maildirs.
        """
        # Handle 'đ' and 'Đ' which are not decomposed by NFD
        text = re.sub(r"[đ]", "d", text)
        text = re.sub(r"[Đ]", "D", text)
        normalized = unicodedata.normalize("NFD", text)
        return "".join(c for c in normalized if unicodedata.category(c) != "Mn")

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

        # 3. Check provider rules role mappings
        prov_mappings = self.rules_manager.get_role_mappings(self.source_provider)
        for pattern_name, target_role_str in prov_mappings.items():
            if lower_name == pattern_name.lower():
                try:
                    return FolderRole(target_role_str.lower())
                except Exception:
                    pass

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
        dest_canonical_map: Dict[FolderRole, str],
        dest_prefix: str = "",
    ) -> str:
        """
        Calculates destination folder name:
        1. If source folder is mapped to a canonical role (e.g., SENT), map to destination's known role folder.
        2. Clean up provider-specific namespace tags (e.g. '[Gmail]/Quan trọng' -> 'Quan trọng').
        3. Adapt hierarchy delimiter (e.g. Projects/2025 -> Projects.2025) and escape literal dots.
        4. Apply destination personal namespace prefix (e.g. 'INBOX.' on Dovecot / cPanel).
        5. Apply Vietnamese accent stripping if sanitize_accents=True.
        """
        # User custom override
        if source_folder in self.custom_mappings:
            target = self.custom_mappings[source_folder]
        elif source_role in dest_canonical_map:
            # Match by canonical role if available on destination
            return dest_canonical_map[source_role]
        elif source_role == FolderRole.INBOX:
            return "INBOX"
        else:
            # General hierarchical folder
            clean_target = source_folder
            # Strip [Gmail]/ or [Gmail]. prefixes for cleaner target structure
            if clean_target.lower().startswith("[gmail]/") or clean_target.lower().startswith("[gmail]."):
                clean_target = clean_target[8:]

            if source_delim != dest_delim:
                # If destination delimiter is '.' and source had literal '.', replace literal '.' with '_'
                if dest_delim == "." and "." in clean_target:
                    parts = clean_target.split(source_delim)
                    safe_parts = [p.replace(".", "_") for p in parts]
                    clean_target = source_delim.join(safe_parts)
                target = clean_target.replace(source_delim, dest_delim)
            else:
                target = clean_target

            # Apply destination namespace prefix (e.g., 'INBOX.' or 'INBOX/')
            if dest_prefix and not target.startswith(dest_prefix) and target.upper() != "INBOX":
                target = f"{dest_prefix}{target}"

        # Sanitize accents if requested
        if self.sanitize_accents:
            target = self.remove_vietnamese_accents(target)

        return target
