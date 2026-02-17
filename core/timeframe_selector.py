"""
Dynamic Timeframe Selector
Chooses 5m / 15m / 1h based on recent ATR-to-price volatility.

Low  vol  (ATR% < 0.3%) → 5m   (catch small moves)
Medium vol (0.3-0.8%)   → 15m  (default sweet spot)
High vol   (> 0.8%)     → 1h   (avoid noise)
"""

import logging
from typing import List

import numpy as np
import config

logger = logging.getLogger(__name__)


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Wilder's ATR from numpy arrays (last `period` bars)."""
    n = len(closes)
    if n < 2:
        return 0.0
    trs = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    trs = np.array(trs[-period:])
    return float(np.mean(trs)) if len(trs) > 0 else 0.0


def select_timeframe(ohlcv_15m: List[List[float]]) -> str:
    """
    Given recent 15m OHLCV candles, decide which timeframe to use.

    Args:
        ohlcv_15m: List of [ts, open, high, low, close, volume] candles (15m).

    Returns:
        One of '5m', '15m', '1h'.
    """
    if not ohlcv_15m or len(ohlcv_15m) < 20:
        return config.DEFAULT_TF

    arr = np.array(ohlcv_15m, dtype=float)
    highs  = arr[:, 2]
    lows   = arr[:, 3]
    closes = arr[:, 4]

    atr_val   = _atr(highs, lows, closes, period=config.ATR_PERIOD)
    last_close = closes[-1]
    if last_close <= 0:
        return config.DEFAULT_TF

    atr_pct = (atr_val / last_close) * 100.0

    if atr_pct < config.LOW_VOL_ATR_PCT:
        tf = "5m"
    elif atr_pct < config.MED_VOL_ATR_PCT:
        tf = "15m"
    else:
        tf = "1h"

    logger.debug("ATR%%=%.3f → timeframe=%s", atr_pct, tf)
    return tf