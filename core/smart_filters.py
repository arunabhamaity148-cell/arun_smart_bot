"""
Smart Filters
Context-aware filter layer. At least MIN_FILTERS_PASS (4/6) must pass
before a core signal is forwarded as a trading alert.

Filters:
  1. Session       – is it PRIME or ACTIVE?
  2. Orderflow     – bid/ask pressure aligns with signal direction?
  3. Liquidation   – near a key level (support for LONG, resistance for SHORT)?
  4. BTC Trend     – BTC direction doesn't conflict with trade?
  5. Correlation   – altcoin diverging (independent momentum)?
  6. Volatility    – ATR sufficient for meaningful TP to clear spread/fees?
"""

import logging
from typing import Dict, Any, List, Tuple

import numpy as np
import config
from .session_detector    import detect_session, SESSION_QUIET
from .orderflow_analyzer  import analyze_orderflow
from .liquidation_tracker import build_liquidation_map, near_support, near_resistance
from .correlation_monitor import is_diverging, btc_direction

logger = logging.getLogger(__name__)


def _atr_sufficient(ohlcv: List[List[float]], entry: float) -> bool:
    """ATR must be enough for TP to exceed 0.3% (covers fees at leverage)."""
    if not ohlcv or len(ohlcv) < 15 or entry <= 0:
        return True  # neutral pass if no data
    arr    = np.array(ohlcv, dtype=float)
    highs  = arr[:, 2]
    lows   = arr[:, 3]
    closes = arr[:, 4]
    n      = len(closes)
    trs    = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
              for i in range(1, n)]
    atr    = float(np.mean(trs[-14:])) if trs else 0.0
    tp_dist_pct = (atr * config.ATR_TP_MULT / entry) * 100
    return tp_dist_pct >= 0.3


def evaluate_filters(
    direction: str,            # 'LONG' or 'SHORT'
    entry_price: float,
    ohlcv: List[List[float]],
    orderbook: Dict[str, Any],
    btc_ohlcv: List[List[float]],
    alt_ohlcv: List[List[float]],
) -> Tuple[int, int, Dict[str, bool]]:
    """
    Evaluate all 6 smart filters.

    Returns:
        (passed, total, filter_results_dict)
    """
    results: Dict[str, bool] = {}

    # 1. Session filter
    session, _, _ = detect_session(ohlcv)
    results["session"] = session != SESSION_QUIET

    # 2. Orderflow filter
    of = analyze_orderflow(orderbook)
    if direction == "LONG":
        results["orderflow"] = of["bid_pressure"] >= config.OB_PRESSURE_THRESHOLD
    else:
        results["orderflow"] = of["ask_pressure"] >= config.OB_PRESSURE_THRESHOLD

    # 3. Liquidation level filter
    liq_map = build_liquidation_map(ohlcv)
    if direction == "LONG":
        results["liquidation"] = near_support(liq_map)
    else:
        results["liquidation"] = near_resistance(liq_map)

    # 4. BTC trend filter (no conflict)
    btc_dir = btc_direction(btc_ohlcv)
    if direction == "LONG":
        results["btc_trend"] = btc_dir != "DOWN"
    else:
        results["btc_trend"] = btc_dir != "UP"

    # 5. Correlation / divergence filter
    results["correlation"] = is_diverging(btc_ohlcv, alt_ohlcv)

    # 6. Volatility/ATR filter
    results["volatility"] = _atr_sufficient(ohlcv, entry_price)

    passed = sum(1 for v in results.values() if v)
    total  = len(results)

    logger.debug(
        "Filters [%s] passed=%d/%d | %s",
        direction, passed, total,
        " ".join(f"{k}={'✓' if v else '✗'}" for k, v in results.items()),
    )
    return passed, total, results


def all_filters_pass(
    direction: str,
    entry_price: float,
    ohlcv: List[List[float]],
    orderbook: Dict[str, Any],
    btc_ohlcv: List[List[float]],
    alt_ohlcv: List[List[float]],
    min_pass: int = None,
) -> Tuple[bool, Dict[str, bool]]:
    """
    Returns (True, results) if >= min_pass filters pass.
    """
    if min_pass is None:
        min_pass = config.MIN_FILTERS_PASS
    passed, total, results = evaluate_filters(
        direction, entry_price, ohlcv, orderbook, btc_ohlcv, alt_ohlcv
    )
    return passed >= min_pass, results