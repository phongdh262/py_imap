from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, computed_field


class AuthType(str, Enum):
    PLAIN = "PLAIN"
    LOGIN = "LOGIN"
    XOAUTH2 = "XOAUTH2"


class AccountCredentials(BaseModel):
    host: str
    port: int = 993
    ssl: bool = True
    username: str
    password: Optional[str] = None
    auth_type: AuthType = AuthType.PLAIN
    oauth2_token: Optional[str] = None
    timeout: int = 60


class FolderRole(str, Enum):
    INBOX = "INBOX"
    SENT = "SENT"
    DRAFTS = "DRAFTS"
    TRASH = "TRASH"
    JUNK = "JUNK"
    ARCHIVE = "ARCHIVE"
    CUSTOM = "CUSTOM"


class FolderInfo(BaseModel):
    name: str
    delimiter: str = "/"
    flags: List[str] = Field(default_factory=list)
    role: FolderRole = FolderRole.CUSTOM
    messages_count: int = 0
    size_bytes: int = 0
    is_selectable: bool = True
    is_excluded: bool = False
    mapped_target: Optional[str] = None

    @computed_field
    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)

    @computed_field
    @property
    def destination_folder(self) -> str:
        if self.is_excluded:
            return "(Loại trừ)"
        return self.mapped_target or (self.role.value if self.role != FolderRole.CUSTOM else self.name)


class MailboxSummary(BaseModel):
    account: str
    total_messages: int = 0
    total_size_bytes: int = 0
    quota_limit_bytes: Optional[int] = None
    quota_used_bytes: Optional[int] = None
    folders: List[FolderInfo] = Field(default_factory=list)

    @computed_field
    @property
    def total_size_mb(self) -> float:
        return round(self.total_size_bytes / (1024 * 1024), 2)

    @computed_field
    @property
    def total_size_gb(self) -> float:
        return round(self.total_size_bytes / (1024 * 1024 * 1024), 3)

    @computed_field
    @property
    def quota(self) -> Optional[Dict[str, Any]]:
        if self.quota_limit_bytes and self.quota_limit_bytes > 0:
            usage_mb = round((self.quota_used_bytes or 0) / (1024 * 1024), 1)
            limit_mb = round(self.quota_limit_bytes / (1024 * 1024), 1)
            pct = round((usage_mb / limit_mb) * 100, 1)
            return {
                "percent": pct,
                "usage_mb": usage_mb,
                "limit_mb": limit_mb,
            }
        return None
