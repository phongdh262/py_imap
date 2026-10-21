"""
Timezone helper module for Vietnam (Asia/Ho_Chi_Minh, GMT+7).
Provides consistent timezone handling across all background tasks, logging, reports, and database records.
"""
import os
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

VN_TIMEZONE_STR = "Asia/Ho_Chi_Minh"
try:
    VN_TZ = ZoneInfo(VN_TIMEZONE_STR)
except Exception:
    import tzdata  # Ensure tzdata package is loaded
    VN_TZ = ZoneInfo(VN_TIMEZONE_STR)


def init_timezone() -> None:
    """Sets system/process environment variable TZ to Asia/Ho_Chi_Minh."""
    os.environ["TZ"] = VN_TIMEZONE_STR
    if hasattr(time, "tzset"):
        try:
            time.tzset()
        except Exception:
            pass


def get_vn_now() -> datetime:
    """Returns the current datetime in Vietnam (GMT+7) timezone."""
    return datetime.now(VN_TZ)


def format_vn_datetime(dt: Optional[datetime] = None, fmt: str = "%H:%M:%S %d/%m/%Y") -> str:
    """Formats datetime in Vietnam timezone."""
    if dt is None:
        dt = get_vn_now()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=VN_TZ)
    else:
        dt = dt.astimezone(VN_TZ)
    return dt.strftime(fmt)


def get_vn_timestamp_str() -> str:
    """Returns YYYY-MM-DD HH:MM:SS in Vietnam timezone for database records."""
    return format_vn_datetime(fmt="%Y-%m-%d %H:%M:%S")
