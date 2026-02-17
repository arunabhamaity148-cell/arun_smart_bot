"""
Smart Signal Engine — ARUNABHA SMART v10.0

SIMPLE CORE RULES (fixed, never retrained):
  LONG  → RSI < 35  AND EMA9 > EMA21 AND Volume > 1.2× avg
  SHORT → RSI > 65  AND EMA9 < EMA21 AND Volume > 1.2× avg

SMART MONEY CONCEPT (SMC) LAYER:
  • Market Structure (BOS/CHOCH detection)
  • Order Block identification (last bearish candle before bullish surge)
  • Fair Value Gap (FVG/imbalance zones)
  • Premium / Discount zones (Fibonacci 50% level)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

import config
from .timeframe_selector import select_timeframe
from .smart_filters      import all_filters_pass
from .smart_sizing       import calculate_position_size

logger = logging.getLogger(__name__)


# ─── SMC Data helpers ────────────────────────────────────────────────────────

def _detect_market_structure(highs: np.ndarray, lows: np.ndarray) -> str:
    """
    Detects recent market structure:
    BULLISH = Higher Highs + Higher Lows (BOS up)
    BEARISH = Lower Highs + Lower Lows (BOS down)
    NEUTRAL = No clear structure
    """
    if len(highs) < 10:
        return "NEUTRAL"
    # Use last 10 swing pivots
    h = highs[-10:]
    l = lows[-10:]
    hh = h[-1] > h[-5]   # recent high > prior high
    hl = l[-1] > l[-5]   # recent low  > prior low
    lh = h[-1] < h[-5]   # recent high < prior high
    ll = l[-1] < l[-5]   # recent low  < prior low

    if hh and hl:
        return "BULLISH"
    elif lh and ll:
        return "BEARISH"
    return "NEUTRAL"


def _find_order_block(
    opens: np.ndarray, closes: np.ndarray,
    highs: np.ndarray, lows: np.ndarray,
    direction: str,
    lookback: int = 20,
) -> Optional[Tuple[float, float]]:
    """
    Order Block = last opposing candle before a strong impulse move.
    LONG  OB = last bearish (red) candle before bullish impulse
    SHORT OB = last bullish (green) candle before bearish impulse

    Returns (ob_low, ob_high) or None.
    """
    if len(closes) < lookback + 3:
        return None

    arr_o = opens[-lookback:]
    arr_c = closes[-lookback:]
    arr_h = highs[-lookback:]
    arr_l = lows[-lookback:]

    if direction == "LONG":
        # Find last bearish candle followed by 2+ consecutive bullish candles
        for i in range(len(arr_c) - 3, 1, -1):
            if arr_c[i] < arr_o[i]:   # bearish candle
                if arr_c[i+1] > arr_o[i+1] and arr_c[i+2] > arr_o[i+2]:  # 2 bull follow
                    return (float(arr_l[i]), float(arr_h[i]))
    else:
        # Find last bullish candle followed by 2+ consecutive bearish candles
        for i in range(len(arr_c) - 3, 1, -1):
            if arr_c[i] > arr_o[i]:   # bullish candle
                if arr_c[i+1] < arr_o[i+1] and arr_c[i+2] < arr_o[i+2]:  # 2 bear follow
                    return (float(arr_l[i]), float(arr_h[i]))
    return None


def _find_fvg(
    highs: np.ndarray, lows: np.ndarray, direction: str, lookback: int = 15
) -> Optional[Tuple[float, float]]:
    """
    Fair Value Gap (FVG) = 3-candle imbalance zone.
    Bullish FVG: candle[i+2].low > candle[i].high  (gap between them)
    Bearish FVG: candle[i+2].high < candle[i].low
    Returns (gap_low, gap_high) of the most recent FVG.
    """
    if len(highs) < lookback + 3:
        return None

    h = highs[-lookback:]
    l = lows[-lookback:]

    if direction == "LONG":
        for i in range(len(h) - 3, 0, -1):
            if l[i+2] > h[i]:   # bullish FVG
                return (float(h[i]), float(l[i+2]))
    else:
        for i in range(len(h) - 3, 0, -1):
            if h[i+2] < l[i]:   # bearish FVG
                return (float(h[i+2]), float(l[i]))
    return None


def _premium_discount_zone(highs: np.ndarray, lows: np.ndarray) -> Dict[str, float]:
    """
    Fibonacci 50% equilibrium of the current swing range.
    DISCOUNT zone = below 50% (good for LONG entries)
    PREMIUM zone  = above 50% (good for SHORT entries)
    """
    if len(highs) < 20:
        return {"equilibrium": 0.0, "premium_start": 0.0, "discount_end": 0.0}
    swing_high = float(np.max(highs[-20:]))
    swing_low  = float(np.min(lows[-20:]))
    equil = (swing_high + swing_low) / 2
    return {
        "equilibrium":    equil,
        "premium_start":  equil,     # above = premium
        "discount_end":   equil,     # below = discount
        "swing_high":     swing_high,
        "swing_low":      swing_low,
    }


def _smc_confluence(
    direction: str,
    entry: float,
    opens: np.ndarray,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
) -> Dict[str, Any]:
    """
    Full SMC analysis. Returns confluence dict with boolean flags
    and key price levels.
    """
    structure   = _detect_market_structure(highs, lows)
    order_block = _find_order_block(opens, closes, highs, lows, direction)
    fvg         = _find_fvg(highs, lows, direction)
    pd_zone     = _premium_discount_zone(highs, lows)
    equil       = pd_zone["equilibrium"]

    # Structure alignment
    if direction == "LONG":
        structure_ok = structure == "BULLISH"
        in_discount  = entry < equil and equil > 0
    else:
        structure_ok = structure == "BEARISH"
        in_discount  = entry > equil and equil > 0

    # Near Order Block?
    near_ob = False
    if order_block:
        ob_low, ob_high = order_block
        near_ob = ob_low <= entry <= ob_high * 1.005 if direction == "LONG" \
             else ob_low * 0.995 <= entry <= ob_high

    # Inside FVG?
    in_fvg = False
    if fvg:
        fvg_low, fvg_high = fvg
        in_fvg = fvg_low <= entry <= fvg_high

    smc_score = sum([structure_ok, in_discount, near_ob, in_fvg])

    result = {
        "structure":     structure,
        "structure_ok":  structure_ok,
        "in_discount":   in_discount,
        "near_ob":       near_ob,
        "in_fvg":        in_fvg,
        "smc_score":     smc_score,        # 0-4
        "order_block":   order_block,
        "fvg":           fvg,
        "equilibrium":   equil,
        "swing_high":    pd_zone.get("swing_high", 0),
        "swing_low":     pd_zone.get("swing_low", 0),
    }
    logger.debug(
        "SMC [%s] structure=%s discount=%s ob=%s fvg=%s score=%d",
        direction, structure, in_discount, near_ob, in_fvg, smc_score,
    )
    return result


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class SignalResult:
    symbol:         str
    direction:      str
    timeframe:      str
    entry:          float
    stop_loss:      float
    take_profit:    float
    rr_ratio:       float
    rsi:            float
    ema_fast:       float
    ema_slow:       float
    volume_ratio:   float
    filters_passed: int
    filters_total:  int
    filter_detail:  Dict[str, bool]  = field(default_factory=dict)
    sizing:         Dict[str, Any]   = field(default_factory=dict)
    smc:            Dict[str, Any]   = field(default_factory=dict)
    quality:        str = "B"
    skip_reason:    str = ""


# ─── Indicator helpers ────────────────────────────────────────────────────────

def _ema(values: np.ndarray, period: int) -> float:
    if len(values) < period:
        return float(np.mean(values))
    k   = 2.0 / (period + 1)
    ema = float(values[0])
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas   = np.diff(closes)
    gains    = np.where(deltas > 0, deltas, 0.0)
    losses   = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i])  / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def _atr(highs, lows, closes, period=14):
    n   = len(closes)
    if n < 2:
        return 0.0
    trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
           for i in range(1, n)]
    trs = np.array(trs)
    if len(trs) < period:
        return float(np.mean(trs))
    atr = float(np.mean(trs[:period]))
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


# ─── Main signal generator ───────────────────────────────────────────────────

def generate_signal(
    symbol:           str,
    ohlcv:            List[List[float]],
    orderbook:        Dict[str, Any],
    btc_ohlcv:        List[List[float]],
    account_size_usd: float = None,
) -> Optional[SignalResult]:
    """
    Full signal pipeline:
    1. Core rules  (RSI + EMA + Volume)
    2. RR check    (min 1.5:1)
    3. SMC layer   (Market Structure + OB + FVG + PD Zone)
    4. Smart Filters (6 context filters, 4 must pass)
    5. Position sizing

    Returns SignalResult or None. All skip reasons logged at INFO level.
    """
    if account_size_usd is None:
        account_size_usd = config.ACCOUNT_SIZE_USD

    min_candles = config.CANDLE_LOOKBACK // 2
    if not ohlcv or len(ohlcv) < min_candles:
        logger.info("⏭ SKIP %s — only %d candles (need %d)",
                    symbol, len(ohlcv) if ohlcv else 0, min_candles)
        return None

    timeframe = select_timeframe(ohlcv)

    arr     = np.array(ohlcv, dtype=float)
    opens   = arr[:, 1]
    highs   = arr[:, 2]
    lows    = arr[:, 3]
    closes  = arr[:, 4]
    volumes = arr[:, 5]

    # ── Indicators ──────────────────────────────────────────────────────────
    rsi      = _rsi(closes, config.RSI_PERIOD)
    ema_fast = _ema(closes, config.EMA_FAST)
    ema_slow = _ema(closes, config.EMA_SLOW)
    atr      = _atr(highs, lows, closes, config.ATR_PERIOD)

    window     = min(config.VOLUME_LOOKBACK, len(volumes) - 1)
    avg_volume = float(np.mean(volumes[-window-1:-1])) if window > 0 else 1.0
    last_vol   = float(volumes[-1])
    vol_ratio  = last_vol / avg_volume if avg_volume > 0 else 0.0
    entry      = float(closes[-1])

    # ── CORE RULES ──────────────────────────────────────────────────────────
    long_core  = rsi < config.RSI_OVERSOLD   and ema_fast > ema_slow and vol_ratio >= config.VOLUME_MULTIPLIER
    short_core = rsi > config.RSI_OVERBOUGHT and ema_fast < ema_slow and vol_ratio >= config.VOLUME_MULTIPLIER

    if not long_core and not short_core:
        logger.info(
            "⏭ SKIP %s [%s] — Core rules failed | "
            "RSI=%.1f (need <%.0f/>%.0f) | "
            "EMA9=%.2f %s EMA21=%.2f | "
            "VolRatio=%.2f (need >%.1f)",
            symbol, timeframe,
            rsi, config.RSI_OVERSOLD, config.RSI_OVERBOUGHT,
            ema_fast, ">" if ema_fast > ema_slow else "<", ema_slow,
            vol_ratio, config.VOLUME_MULTIPLIER,
        )
        return None

    direction = "LONG" if long_core else "SHORT"

    # ── SL / TP ──────────────────────────────────────────────────────────────
    if direction == "LONG":
        stop_loss   = entry - atr * config.ATR_SL_MULT
        take_profit = entry + atr * config.ATR_TP_MULT
    else:
        stop_loss   = entry + atr * config.ATR_SL_MULT
        take_profit = entry - atr * config.ATR_TP_MULT

    sl_dist  = abs(entry - stop_loss)
    tp_dist  = abs(entry - take_profit)
    rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0.0

    if rr_ratio < config.MIN_RR_RATIO:
        logger.info(
            "⏭ SKIP %s [%s] %s — RR too low %.2f (need ≥%.1f) | ATR=%.4f",
            symbol, timeframe, direction, rr_ratio, config.MIN_RR_RATIO, atr,
        )
        return None

    # ── SMC Layer ────────────────────────────────────────────────────────────
    smc = _smc_confluence(direction, entry, opens, closes, highs, lows)

    # SMC gate: at least 1/4 SMC factor must align (soft filter, not hard gate)
    # Log SMC details always
    logger.info(
        "📐 SMC %s [%s] %s | Structure=%s Discount=%s OB=%s FVG=%s Score=%d/4",
        symbol, timeframe, direction,
        smc["structure"], smc["in_discount"], smc["near_ob"], smc["in_fvg"],
        smc["smc_score"],
    )

    # ── Smart Filters ────────────────────────────────────────────────────────
    passed, filter_detail = all_filters_pass(
        direction=direction, entry_price=entry, ohlcv=ohlcv,
        orderbook=orderbook, btc_ohlcv=btc_ohlcv, alt_ohlcv=ohlcv,
    )

    filters_passed = sum(1 for v in filter_detail.values() if v)
    filters_total  = len(filter_detail)

    filter_str = " | ".join(
        f"{k}={'✓' if v else '✗'}" for k, v in filter_detail.items()
    )
    logger.info(
        "🔍 FILTERS %s [%s] %s — %d/%d passed | %s",
        symbol, timeframe, direction,
        filters_passed, filters_total, filter_str,
    )

    if not passed:
        logger.info(
            "⏭ SKIP %s [%s] %s — Only %d/%d filters passed (need %d)",
            symbol, timeframe, direction,
            filters_passed, filters_total, config.MIN_FILTERS_PASS,
        )
        return None

    # ── Quality Grade ────────────────────────────────────────────────────────
    # Combine filters + SMC score for final grade
    total_score = filters_passed + smc["smc_score"]
    if total_score >= 9:        # 6 filters + 3+ SMC
        quality = "A+"
    elif total_score >= 8:
        quality = "A"
    elif total_score >= 6:
        quality = "B"
    else:
        quality = "C"

    # ── Position Sizing ──────────────────────────────────────────────────────
    sizing = calculate_position_size(account_size_usd, entry, stop_loss, ohlcv)

    logger.info(
        "✅ SIGNAL %s [%s] %s | Entry=%.4f SL=%.4f TP=%.4f | "
        "RR=%.2f | RSI=%.1f | Vol=%.2f× | "
        "SMC=%d/4 | Filters=%d/%d | Grade=%s",
        symbol, timeframe, direction,
        entry, stop_loss, take_profit,
        rr_ratio, rsi, vol_ratio,
        smc["smc_score"], filters_passed, filters_total, quality,
    )

    return SignalResult(
        symbol=symbol, direction=direction, timeframe=timeframe,
        entry=round(entry,6), stop_loss=round(stop_loss,6), take_profit=round(take_profit,6),
        rr_ratio=round(rr_ratio,2), rsi=rsi,
        ema_fast=round(ema_fast,6), ema_slow=round(ema_slow,6),
        volume_ratio=round(vol_ratio,2),
        filters_passed=filters_passed, filters_total=filters_total,
        filter_detail=filter_detail, sizing=sizing, smc=smc, quality=quality,
    )
