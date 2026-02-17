"""
Correlation Monitor
Detects BTC-ALT divergence by comparing rolling return correlation.

High positive correlation → altcoin follows BTC (normal regime)
Low/negative correlation  → altcoin is diverging (potential edge)
"""

import logging
from typing import List, Optional

import numpy as np
import config

logger = logging.getLogger(__name__)


def _pct_returns(closes: np.ndarray) -> np.ndarray:
    """Percentage returns array."""
    if len(closes) < 2:
        return np.array([])
    return np.diff(closes) / closes[:-1]


def rolling_correlation(
    btc_ohlcv: List[List[float]],
    alt_ohlcv: List[List[float]],
    window: int = None,
) -> Optional[float]:
    """
    Pearson correlation of BTC vs ALT returns over `window` bars.
    Returns None if insufficient data.
    """
    if window is None:
        window = config.CORRELATION_LOOKBACK

    if not btc_ohlcv or not alt_ohlcv:
        return None

    btc_arr = np.array(btc_ohlcv, dtype=float)[:, 4]   # close prices
    alt_arr = np.array(alt_ohlcv, dtype=float)[:, 4]

    # align lengths
    min_len = min(len(btc_arr), len(alt_arr))
    btc_arr = btc_arr[-min_len:]
    alt_arr = alt_arr[-min_len:]

    if min_len < window + 1:
        return None

    btc_ret = _pct_returns(btc_arr[-window - 1:])
    alt_ret = _pct_returns(alt_arr[-window - 1:])

    if len(btc_ret) < 5 or len(alt_ret) < 5:
        return None

    try:
        corr_matrix = np.corrcoef(btc_ret, alt_ret)
        corr        = float(corr_matrix[0, 1])
        if np.isnan(corr):
            return None
        return corr
    except Exception as exc:
        logger.debug("Correlation error: %s", exc)
        return None


def is_diverging(
    btc_ohlcv: List[List[float]],
    alt_ohlcv: List[List[float]],
) -> bool:
    """
    Returns True when altcoin is diverging from BTC
    (correlation below CORR_DIVERGENCE_THRESHOLD).
    This is often an early signal of independent altcoin momentum.
    """
    corr = rolling_correlation(btc_ohlcv, alt_ohlcv)
    if corr is None:
        return False   # unknown → no filter bonus
    result = abs(corr) < config.CORR_DIVERGENCE_THRESHOLD
    logger.debug("Correlation=%.3f  diverging=%s", corr, result)
    return result


def btc_direction(btc_ohlcv: List[List[float]]) -> str:
    """
    Returns 'UP', 'DOWN', or 'FLAT' based on recent BTC EMA trend.
    Used to confirm or conflict with altcoin signals.
    """
    if not btc_ohlcv or len(btc_ohlcv) < 22:
        return "FLAT"
    closes = np.array(btc_ohlcv, dtype=float)[:, 4]
    ema9  = float(np.mean(closes[-9:]))
    ema21 = float(np.mean(closes[-21:]))
    if ema9 > ema21 * 1.001:
        return "UP"
    elif ema9 < ema21 * 0.999:
        return "DOWN"
    return "FLAT"