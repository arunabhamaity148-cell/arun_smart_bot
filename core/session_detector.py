"""
Session Detector
Uses real volume/volatility (not clock time) to classify the current
market session and assess whether conditions are favourable for trading.

Sessions:
  PRIME   – High volume AND high volatility (best signals)
  ACTIVE  – Either high volume OR high volatility
  QUIET   – Low on both axes (avoid trading)
"""

import logging
from typing import List, Tuple

import numpy as np
import config

logger = logging.getLogger(__name__)


SESSION_PRIME  = "PRIME"
SESSION_ACTIVE = "ACTIVE"
SESSION_QUIET  = "QUIET"


def _rolling_mean(arr: np.ndarray, window: int) -> float:
    if len(arr) < window:
        return float(np.mean(arr)) if len(arr) else 0.0
    return float(np.mean(arr[-window:]))


def detect_session(ohlcv: List[List[float]]) -> Tuple[str, float, float]:
    """
    Classify current session from recent OHLCV candles.

    Returns:
        (session_label, volume_ratio, volatility_ratio)
        volume_ratio     = last_volume / avg_volume
        volatility_ratio = last_range  / avg_range
    """
    if not ohlcv or len(ohlcv) < 10:
        return SESSION_ACTIVE, 1.0, 1.0

    arr      = np.array(ohlcv, dtype=float)
    volumes  = arr[:, 5]
    highs    = arr[:, 2]
    lows     = arr[:, 3]
    ranges   = highs - lows

    window       = min(config.VOLUME_LOOKBACK, len(arr) - 1)
    avg_volume   = _rolling_mean(volumes[:-1], window)
    avg_range    = _rolling_mean(ranges[:-1], window)

    last_volume  = float(volumes[-1])
    last_range   = float(ranges[-1])

    vol_ratio  = (last_volume / avg_volume)  if avg_volume > 0 else 1.0
    rang_ratio = (last_range  / avg_range)   if avg_range  > 0 else 1.0

    high_vol   = vol_ratio  >= config.VOLUME_MULTIPLIER
    high_rang  = rang_ratio >= 1.0   # above-average candle range

    if high_vol and high_rang:
        session = SESSION_PRIME
    elif high_vol or high_rang:
        session = SESSION_ACTIVE
    else:
        session = SESSION_QUIET

    logger.debug(
        "Session=%s vol_ratio=%.2f rang_ratio=%.2f",
        session, vol_ratio, rang_ratio,
    )
    return session, vol_ratio, rang_ratio


def is_tradeable_session(ohlcv: List[List[float]]) -> bool:
    """Returns True if session is PRIME or ACTIVE."""
    session, _, _ = detect_session(ohlcv)
    return session in (SESSION_PRIME, SESSION_ACTIVE)