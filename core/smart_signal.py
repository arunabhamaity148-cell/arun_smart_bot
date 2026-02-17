"""
Smart Signal Engine – ARUNABHA SMART v10.0
Core signal generation: simple, robust, anti-overfitted.

SIMPLE CORE RULES (fixed, never retrained):
  LONG  → RSI < 35  AND EMA9 > EMA21 AND Volume > 1.2× avg
  SHORT → RSI > 65  AND EMA9 < EMA21 AND Volume > 1.2× avg

ADAPTATION LAYER:
  • Dynamic timeframe selection
  • Session quality check
  • Orderflow confirmation
  • Liquidation map awareness
  • BTC correlation context
  • Smart position sizing

ANTI-OVERFITTING:
  - No ML, no optimisation, no retraining
  - Fixed thresholds, dynamic context only
  - Human executes (manual trading)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

import numpy as np

import config
from .timeframe_selector import select_timeframe
from .smart_filters      import all_filters_pass
from .smart_sizing       import calculate_position_size

logger = logging.getLogger(__name__)


# ─── Data classes ────────────────────────────────────────────────────────────

@dataclass
class SignalResult:
    symbol:        str
    direction:     str           # 'LONG' | 'SHORT'
    timeframe:     str
    entry:         float
    stop_loss:     float
    take_profit:   float
    rr_ratio:      float
    rsi:           float
    ema_fast:      float
    ema_slow:      float
    volume_ratio:  float
    filters_passed: int
    filters_total:  int
    filter_detail:  Dict[str, bool] = field(default_factory=dict)
    sizing:         Dict[str, Any]  = field(default_factory=dict)
    quality:        str = "A"        # A / B / C based on filters_passed


# ─── Indicator helpers ────────────────────────────────────────────────────────

def _ema(values: np.ndarray, period: int) -> float:
    """Exponential moving average – last value."""
    if len(values) < period:
        return float(np.mean(values))
    k   = 2.0 / (period + 1)
    ema = float(values[0])
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    """Wilder RSI."""
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i])  / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs  = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    n  = len(closes)
    if n < 2:
        return 0.0
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
           for i in range(1, n)]
    trs = np.array(trs)
    if len(trs) < period:
        return float(np.mean(trs))
    # Wilder smoothing
    atr = float(np.mean(trs[:period]))
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


# ─── Core signal generator ───────────────────────────────────────────────────

def generate_signal(
    symbol:    str,
    ohlcv:     List[List[float]],
    orderbook: Dict[str, Any],
    btc_ohlcv: List[List[float]],
    account_size_usd: float = None,
) -> Optional[SignalResult]:
    """
    Evaluate a symbol and return a SignalResult if all conditions met,
    else None.

    Args:
        symbol:           e.g. 'ETH/USDT'
        ohlcv:            Candles on selected timeframe [ts,o,h,l,c,v]
        orderbook:        {'bids': [...], 'asks': [...]}
        btc_ohlcv:        BTC candles for correlation analysis
        account_size_usd: Account equity for position sizing
    """
    if account_size_usd is None:
        account_size_usd = config.ACCOUNT_SIZE_USD

    if not ohlcv or len(ohlcv) < config.CANDLE_LOOKBACK // 2:
        logger.debug("%s: insufficient candles (%d)", symbol, len(ohlcv) if ohlcv else 0)
        return None

    # ── Select best timeframe ──────────────────────────────────────────────
    timeframe = select_timeframe(ohlcv)

    # ── Build numpy arrays ─────────────────────────────────────────────────
    arr     = np.array(ohlcv, dtype=float)
    opens   = arr[:, 1]
    highs   = arr[:, 2]
    lows    = arr[:, 3]
    closes  = arr[:, 4]
    volumes = arr[:, 5]

    # ── Core indicators ────────────────────────────────────────────────────
    rsi      = _rsi(closes, config.RSI_PERIOD)
    ema_fast = _ema(closes, config.EMA_FAST)
    ema_slow = _ema(closes, config.EMA_SLOW)
    atr      = _atr(highs, lows, closes, config.ATR_PERIOD)

    window     = min(config.VOLUME_LOOKBACK, len(volumes) - 1)
    avg_volume = float(np.mean(volumes[-window - 1: -1])) if window > 0 else 1.0
    last_vol   = float(volumes[-1])
    vol_ratio  = last_vol / avg_volume if avg_volume > 0 else 0.0

    entry = float(closes[-1])

    # ── SIMPLE CORE RULES ──────────────────────────────────────────────────
    long_core  = (
        rsi < config.RSI_OVERSOLD
        and ema_fast > ema_slow
        and vol_ratio >= config.VOLUME_MULTIPLIER
    )
    short_core = (
        rsi > config.RSI_OVERBOUGHT
        and ema_fast < ema_slow
        and vol_ratio >= config.VOLUME_MULTIPLIER
    )

    if not long_core and not short_core:
        logger.debug(
            "%s: core rules not met (RSI=%.1f EMA9=%.4f EMA21=%.4f vol_ratio=%.2f)",
            symbol, rsi, ema_fast, ema_slow, vol_ratio,
        )
        return None

    direction = "LONG" if long_core else "SHORT"

    # ── SL / TP calculation ────────────────────────────────────────────────
    if direction == "LONG":
        stop_loss   = entry - atr * config.ATR_SL_MULT
        take_profit = entry + atr * config.ATR_TP_MULT
    else:
        stop_loss   = entry + atr * config.ATR_SL_MULT
        take_profit = entry - atr * config.ATR_TP_MULT

    sl_dist = abs(entry - stop_loss)
    tp_dist = abs(entry - take_profit)
    rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0.0

    if rr_ratio < config.MIN_RR_RATIO:
        logger.debug("%s: RR=%.2f below minimum %.2f", symbol, rr_ratio, config.MIN_RR_RATIO)
        return None

    # ── Smart filter layer ─────────────────────────────────────────────────
    passed, filter_detail = all_filters_pass(
        direction    = direction,
        entry_price  = entry,
        ohlcv        = ohlcv,
        orderbook    = orderbook,
        btc_ohlcv    = btc_ohlcv,
        alt_ohlcv    = ohlcv,
    )

    filters_passed = sum(1 for v in filter_detail.values() if v)
    filters_total  = len(filter_detail)

    if not passed:
        logger.debug(
            "%s: filters insufficient (%d/%d)", symbol, filters_passed, filters_total
        )
        return None

    # ── Quality grade ──────────────────────────────────────────────────────
    if filters_passed == filters_total:
        quality = "A+"
    elif filters_passed >= 5:
        quality = "A"
    elif filters_passed >= 4:
        quality = "B"
    else:
        quality = "C"

    # ── Position sizing ────────────────────────────────────────────────────
    sizing = calculate_position_size(account_size_usd, entry, stop_loss, ohlcv)

    signal = SignalResult(
        symbol         = symbol,
        direction      = direction,
        timeframe      = timeframe,
        entry          = round(entry, 6),
        stop_loss      = round(stop_loss, 6),
        take_profit    = round(take_profit, 6),
        rr_ratio       = round(rr_ratio, 2),
        rsi            = rsi,
        ema_fast       = round(ema_fast, 6),
        ema_slow       = round(ema_slow, 6),
        volume_ratio   = round(vol_ratio, 2),
        filters_passed = filters_passed,
        filters_total  = filters_total,
        filter_detail  = filter_detail,
        sizing         = sizing,
        quality        = quality,
    )

    logger.info(
        "✅ SIGNAL %s %s | Entry=%.4f SL=%.4f TP=%.4f RR=%.2f Q=%s Filters=%d/%d",
        symbol, direction, entry, stop_loss, take_profit,
        rr_ratio, quality, filters_passed, filters_total,
    )
    return signal