"""
Liquidation Tracker
Estimates liquidation clusters from historical highs/lows + volume spikes.

Real liquidation data is exchange-specific and not publicly available via CCXT.
We proxy it using price levels where:
  - High volume AND large wick appeared (trapped traders)
  - Local swing highs/lows (stop-hunt magnets)

These levels act as dynamic support/resistance for the signal filter.
"""

import logging
from typing import List, Dict, Any, Tuple

import numpy as np
import config

logger = logging.getLogger(__name__)


def _swing_highs(closes: np.ndarray, highs: np.ndarray, window: int = 5) -> List[float]:
    """Local maxima over rolling window."""
    levels = []
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i - window: i + window + 1]):
            levels.append(float(highs[i]))
    return levels


def _swing_lows(closes: np.ndarray, lows: np.ndarray, window: int = 5) -> List[float]:
    """Local minima over rolling window."""
    levels = []
    for i in range(window, len(lows) - window):
        if lows[i] == min(lows[i - window: i + window + 1]):
            levels.append(float(lows[i]))
    return levels


def _volume_spike_levels(
    ohlcv: np.ndarray, threshold: float = 2.0
) -> List[float]:
    """Price levels where volume was ≥ threshold × average."""
    volumes = ohlcv[:, 5]
    closes  = ohlcv[:, 4]
    avg_vol = float(np.mean(volumes))
    if avg_vol <= 0:
        return []
    spikes = np.where(volumes >= threshold * avg_vol)[0]
    return [float(closes[i]) for i in spikes]


def build_liquidation_map(ohlcv: List[List[float]]) -> Dict[str, Any]:
    """
    Build a map of probable liquidation clusters.

    Returns:
        {
            'resistance': [price, ...],   # levels ABOVE current price
            'support':    [price, ...],   # levels BELOW current price
            'current':    float,
        }
    """
    if not ohlcv or len(ohlcv) < 20:
        return {"resistance": [], "support": [], "current": 0.0}

    arr     = np.array(ohlcv[-config.LIQ_LOOKBACK:], dtype=float)
    highs   = arr[:, 2]
    lows    = arr[:, 3]
    closes  = arr[:, 4]
    current = float(closes[-1])

    s_highs  = _swing_highs(closes, highs)
    s_lows   = _swing_lows(closes, lows)
    spikes   = _volume_spike_levels(arr)

    all_levels = s_highs + s_lows + spikes
    resistance = sorted([lvl for lvl in all_levels if lvl > current])
    support    = sorted([lvl for lvl in all_levels if lvl < current], reverse=True)

    logger.debug(
        "Liq map: %d resistance / %d support levels around %.4f",
        len(resistance), len(support), current,
    )
    return {"resistance": resistance, "support": support, "current": current}


def near_resistance(liq_map: Dict[str, Any], zone_pct: float = None) -> bool:
    """True if price is within zone_pct% of nearest resistance."""
    if zone_pct is None:
        zone_pct = config.LIQ_ZONE_PCT
    current    = liq_map.get("current", 0.0)
    resistance = liq_map.get("resistance", [])
    if not resistance or current <= 0:
        return False
    nearest = resistance[0]
    return abs(nearest - current) / current * 100 <= zone_pct


def near_support(liq_map: Dict[str, Any], zone_pct: float = None) -> bool:
    """True if price is within zone_pct% of nearest support."""
    if zone_pct is None:
        zone_pct = config.LIQ_ZONE_PCT
    current = liq_map.get("current", 0.0)
    support = liq_map.get("support", [])
    if not support or current <= 0:
        return False
    nearest = support[0]
    return abs(current - nearest) / current * 100 <= zone_pct