"""
Time utilities – sleep detection, IST conversion, date helpers.
"""

from datetime import datetime, timezone, timedelta


IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC)


def ist_now() -> datetime:
    return datetime.now(IST)


def is_sleep_time() -> bool:
    """
    Returns True during IST 1 AM – 7 AM (UTC 19:30 – 01:30).
    No trading signals are generated during this window.
    """
    now_ist = ist_now()
    h, m = now_ist.hour, now_ist.minute
    # 01:00 – 06:59 IST = sleep
    if 1 <= h < 7:
        return True
    return False


def today_utc_str() -> str:
    """YYYY-MM-DD string in UTC."""
    return utcnow().strftime("%Y-%m-%d")


def today_ist_str() -> str:
    """YYYY-MM-DD string in IST."""
    return ist_now().strftime("%Y-%m-%d")


def ts_label() -> str:
    """Human-readable timestamp in IST for Telegram messages."""
    return ist_now().strftime("%d %b %Y  %H:%M IST")