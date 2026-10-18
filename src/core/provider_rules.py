import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional


class ProviderRulesManager:
    """
    Manages provider-specific rules, mappings, throttling, and deduplication policies:
    - Gmail / Google Workspace (Virtual labels, all mail exclusion, rate limit)
    - Microsoft 365 / Outlook (Sent Items, Exchange IMAP throttling)
    - cPanel / Dovecot (INBOX. hierarchy, dot delimiter, maildir constraints)
    - Yandex (Modified UTF-7, Cyrillic folders)
    - Generic RFC 3501 fallback
    """

    DEFAULT_RULES_PATH = Path("config/provider_rules.json")

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_RULES_PATH
        self.rules: Dict[str, Any] = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        """Loads JSON provider rules from disk or uses safe fallback."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"providers": {}}

    def detect_provider(self, host: str, username: str = "") -> str:
        """Identifies provider from host hostname or email domain."""
        host_lower = (host or "").lower().strip()
        user_lower = (username or "").lower().strip()

        if "gmail.com" in host_lower or "googlemail.com" in host_lower or user_lower.endswith("@gmail.com"):
            return "gmail"
        if "office365.com" in host_lower or "outlook.com" in host_lower or "live.com" in host_lower or user_lower.endswith("@outlook.com"):
            return "outlook"
        if "yandex." in host_lower or user_lower.endswith("@yandex.com") or user_lower.endswith("@yandex.ru"):
            return "yandex"
        if "zimbra" in host_lower:
            return "zimbra"
        if host_lower.startswith("mail."):
            return "cpanel"

        return "generic"

    def get_provider_rules(self, provider_id: str) -> Dict[str, Any]:
        """Returns the specific rule dictionary for a provider."""
        providers = self.rules.get("providers", {})
        return providers.get(provider_id) or providers.get("generic", {})

    def get_exclusion_patterns(self, provider_id: str) -> List[re.Pattern]:
        """Returns compiled regex patterns for folders that should be skipped by default."""
        rule = self.get_provider_rules(provider_id)
        raw_patterns = rule.get("exclude_by_default", [r"(?i).*spam.*", r"(?i).*junk.*", r"(?i).*trash.*"])
        return [re.compile(p, re.IGNORECASE) for p in raw_patterns]

    def get_role_mappings(self, provider_id: str) -> Dict[str, str]:
        """Returns folder role mappings (e.g. '[Gmail]/Thư đã gửi' -> 'SENT')."""
        rule = self.get_provider_rules(provider_id)
        return rule.get("role_mappings", {})

    def get_recommended_throttling(self, provider_id: str) -> Dict[str, int]:
        """Returns recommended batch_size and delay_ms."""
        rule = self.get_provider_rules(provider_id)
        return rule.get("rate_limit", {"batch_size": 50, "batch_delay_ms": 30})
