"""
Smart Filters — ARUNABHA SMART v10.1
══════════════════════════════════════
Context-aware filter layer. At least MIN_FILTERS_PASS must pass
before a core signal is forwarded as a trading alert.

Filters (9 total, need MIN_FILTERS_PASS=5 to fire):
  ── Original 6 ──────────────────────────────────────
  1. Session       – is it PRIME or ACTIVE?
  2. Orderflow     – bid/ask pressure aligns with direction?
  3. Liquidation   – near a key level?
  4. BTC Trend     – BTC doesn't conflict with trade?
  5. Correlation   – altcoin diverging (independent momentum)?
  6. Volatility    – ATR sufficient for TP to clear fees?
  ── New 3 ───────────────────────────────────────────
  7. MTF           – 1h structure confirms 15m entry direction?
  8. Funding Rate  – not entering a crowded/extreme-funded trade?
  9. VPOC          – entry is in a high-volume confluence zone?
"""

import logging
from typing import Dict, Any, List, Tuple, Optional

import numpy as np
import config
from .session_detector    import detect_session, SESSION_QUIET
from .orderflow_analyzer  import analyze_orderflow
from .liquidation_tracker import build_liquidation_map, near_support, near_resistance
from .correlation_monitor import is_diverging, btc_direction
from .mtf_confirmation    import mtf_confirms
from .vpoc_profile        import build_volume_profile, vpoc_confirms

logger = logging.getLogger(__name__)


def _atr_sufficient(ohlcv: List[List[float]], entry: float) -> bool:
    """ATR must be enough for TP to exceed 0.3% (covers fees at leverage)."""
    if not ohlcv or len(ohlcv) < 15 or entry <= 0:
        return True
    arr    = np.array(ohlcv, dtype=float)
    highs  = arr[:, 2]
    lows   = arr[:, 3]
    closes = arr[:, 4]
    n      = len(closes)
    trs    = [max(highs[i] - lows[i],
                  abs(highs[i] - closes[i-1]),
                  abs(lows[i] - closes[i-1]))
              for i in range(1, n)]
    atr         = float(np.mean(trs[-14:])) if trs else 0.0
    tp_dist_pct = (atr * config.ATR_TP_MULT / entry) * 100
    return tp_dist_pct >= 0.3


def evaluate_filters(
    direction:     str,
    entry_price:   float,
    ohlcv:         List[List[float]],
    orderbook:     Dict[str, Any],
    btc_ohlcv:     List[List[float]],
    alt_ohlcv:     List[List[float]],
    # New optional inputs for v10.1 filters
    ohlcv_1h:      Optional[List[List[float]]] = None,
    funding_ok:    Optional[bool]               = None,   # pre-fetched by scan_symbol
    vpoc_ok:       Optional[bool]               = None,   # pre-computed by scan_symbol
) -> Tuple[int, int, Dict[str, bool]]:
    """
    Evaluate all 9 smart filters.

    Returns:
        (passed: int, total: int, filter_results: Dict[str, bool])
    """
    results: Dict[str, bool] = {}

    # ── 1. Session ────────────────────────────────────────────────────────
    session, _, _ = detect_session(ohlcv)
    results["session"] = session != SESSION_QUIET

    # ── 2. Orderflow ──────────────────────────────────────────────────────
    of = analyze_orderflow(orderbook)
    if direction == "LONG":
        results["orderflow"] = of["bid_pressure"] >= config.OB_PRESSURE_THRESHOLD
    else:
        results["orderflow"] = of["ask_pressure"] >= config.OB_PRESSURE_THRESHOLD

    # ── 3. Liquidation ────────────────────────────────────────────────────
    liq_map = build_liquidation_map(ohlcv)
    if direction == "LONG":
        results["liquidation"] = near_support(liq_map)
    else:
        results["liquidation"] = near_resistance(liq_map)

    # ── 4. BTC Trend ──────────────────────────────────────────────────────
    btc_dir = btc_direction(btc_ohlcv)
    if direction == "LONG":
        results["btc_trend"] = btc_dir != "DOWN"
    else:
        results["btc_trend"] = btc_dir != "UP"

    # ── 5. Correlation ────────────────────────────────────────────────────
    results["correlation"] = is_diverging(btc_ohlcv, alt_ohlcv)

    # ── 6. Volatility / ATR ───────────────────────────────────────────────
    results["volatility"] = _atr_sufficient(ohlcv, entry_price)

    # ── 7. MTF Confirmation ───────────────────────────────────────────────
    # ohlcv_1h comes from WS cache; if None → neutral pass
    results["mtf_1h"] = mtf_confirms(direction, ohlcv_1h or [])

    # ── 8. Funding Rate ───────────────────────────────────────────────────
    # funding_ok is pre-fetched in scan_symbol (async); True = safe to trade
    if funding_ok is None:
        results["funding"] = True   # data unavailable → neutral
    else:
        results["funding"] = funding_ok

    # ── 9. VPOC / Volume Profile ──────────────────────────────────────────
    if vpoc_ok is None:
        # Compute inline if not pre-computed
        profile  = build_volume_profile(ohlcv)
        ok, _    = vpoc_confirms(direction, entry_price, profile)
        results["vpoc"] = ok
    else:
        results["vpoc"] = vpoc_ok

    passed = sum(1 for v in results.values() if v)
    total  = len(results)

    logger.debug(
        "Filters [%s] passed=%d/%d | %s",
        direction, passed, total,
        " ".join(f"{k}={'✓' if v else '✗'}" for k, v in results.items()),
    )
    return passed, total, results


def all_filters_pass(
    direction:     str,
    entry_price:   float,
    ohlcv:         List[List[float]],
    orderbook:     Dict[str, Any],
    btc_ohlcv:     List[List[float]],
    alt_ohlcv:     List[List[float]],
    ohlcv_1h:      Optional[List[List[float]]] = None,
    funding_ok:    Optional[bool]               = None,
    vpoc_ok:       Optional[bool]               = None,
    min_pass:      int                          = None,
) -> Tuple[bool, Dict[str, bool]]:
    """
    Returns (True, results) if >= min_pass filters pass.
    Default min_pass = config.MIN_FILTERS_PASS (now 5 for 9 filters).
    """
    if min_pass is None:
        min_pass = config.MIN_FILTERS_PASS

    passed, total, results = evaluate_filters(
        direction=direction,
        entry_price=entry_price,
        ohlcv=ohlcv,
        orderbook=orderbook,
        btc_ohlcv=btc_ohlcv,
        alt_ohlcv=alt_ohlcv,
        ohlcv_1h=ohlcv_1h,
        funding_ok=funding_ok,
        vpoc_ok=vpoc_ok,
    )
    return passed >= min_pass, results
