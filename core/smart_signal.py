"""
Smart Signal Engine — ARUNABHA SMART v10.2

ADAPTIVE STRATEGY — Market Regime-aware:
  ① TRENDING      → RSI 35/65, SL 1.5×ATR, TP 2.5×ATR, Full size
  ② RANGING       → RSI 30/70, SL 1.2×ATR, TP 1.8×ATR, 0.7× size
  ③ EXTREME_FEAR  → RSI 25/75, SL 2.0×ATR, TP 3.5×ATR, 0.5× size

SMART MONEY CONCEPT (SMC) LAYER:
  • Market Structure (BOS/CHOCH)
  • Order Block
  • Fair Value Gap (FVG)
  • Premium / Discount zones

v10.1 LAYERS:
  • MTF Confirmation (1h bias)
  • Funding Rate Filter
  • VPOC / Volume Profile
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

import config
from .timeframe_selector import select_timeframe
from .smart_filters      import all_filters_pass
from .smart_sizing       import calculate_position_size
from .vpoc_profile       import build_volume_profile, vpoc_confirms, vpoc_label
from .mtf_confirmation   import mtf_confirms, mtf_bias_label
from .market_regime      import detect_regime, RegimeParams, regime_label, REGIME_RANGING

logger = logging.getLogger(__name__)


# ─── SMC helpers ─────────────────────────────────────────────────────────────

def _detect_market_structure(highs: np.ndarray, lows: np.ndarray) -> str:
    if len(highs) < 10:
        return "NEUTRAL"
    h  = highs[-10:]
    l  = lows[-10:]
    hh = h[-1] > h[-5]
    hl = l[-1] > l[-5]
    lh = h[-1] < h[-5]
    ll = l[-1] < l[-5]
    if hh and hl:
        return "BULLISH"
    elif lh and ll:
        return "BEARISH"
    return "NEUTRAL"


def _find_order_block(
    opens: np.ndarray, closes: np.ndarray,
    highs: np.ndarray, lows: np.ndarray,
    direction: str, lookback: int = 20,
) -> Optional[Tuple[float, float]]:
    if len(closes) < lookback + 3:
        return None
    arr_o = opens[-lookback:]
    arr_c = closes[-lookback:]
    arr_h = highs[-lookback:]
    arr_l = lows[-lookback:]
    if direction == "LONG":
        for i in range(len(arr_c) - 3, 1, -1):
            if arr_c[i] < arr_o[i]:
                if arr_c[i+1] > arr_o[i+1] and arr_c[i+2] > arr_o[i+2]:
                    return (float(arr_l[i]), float(arr_h[i]))
    else:
        for i in range(len(arr_c) - 3, 1, -1):
            if arr_c[i] > arr_o[i]:
                if arr_c[i+1] < arr_o[i+1] and arr_c[i+2] < arr_o[i+2]:
                    return (float(arr_l[i]), float(arr_h[i]))
    return None


def _find_fvg(
    highs: np.ndarray, lows: np.ndarray,
    direction: str, lookback: int = 15,
) -> Optional[Tuple[float, float]]:
    if len(highs) < lookback + 3:
        return None
    h = highs[-lookback:]
    l = lows[-lookback:]
    if direction == "LONG":
        for i in range(len(h) - 3, 0, -1):
            if l[i+2] > h[i]:
                return (float(h[i]), float(l[i+2]))
    else:
        for i in range(len(h) - 3, 0, -1):
            if h[i+2] < l[i]:
                return (float(h[i+2]), float(l[i]))
    return None


def _premium_discount_zone(highs: np.ndarray, lows: np.ndarray) -> Dict[str, float]:
    if len(highs) < 20:
        return {"equilibrium": 0.0, "premium_start": 0.0, "discount_end": 0.0}
    swing_high = float(np.max(highs[-20:]))
    swing_low  = float(np.min(lows[-20:]))
    equil = (swing_high + swing_low) / 2
    return {
        "equilibrium":   equil,
        "premium_start": equil,
        "discount_end":  equil,
        "swing_high":    swing_high,
        "swing_low":     swing_low,
    }


def _smc_confluence(
    direction: str, entry: float,
    opens: np.ndarray, closes: np.ndarray,
    highs: np.ndarray, lows: np.ndarray,
) -> Dict[str, Any]:
    structure   = _detect_market_structure(highs, lows)
    order_block = _find_order_block(opens, closes, highs, lows, direction)
    fvg         = _find_fvg(highs, lows, direction)
    pd_zone     = _premium_discount_zone(highs, lows)
    equil       = pd_zone["equilibrium"]

    if direction == "LONG":
        structure_ok = structure == "BULLISH"
        in_discount  = entry < equil and equil > 0
    else:
        structure_ok = structure == "BEARISH"
        in_discount  = entry > equil and equil > 0

    near_ob = False
    if order_block:
        ob_low, ob_high = order_block
        near_ob = ob_low <= entry <= ob_high * 1.005 if direction == "LONG" \
             else ob_low * 0.995 <= entry <= ob_high

    in_fvg = False
    if fvg:
        fvg_low, fvg_high = fvg
        in_fvg = fvg_low <= entry <= fvg_high

    smc_score = sum([structure_ok, in_discount, near_ob, in_fvg])
    return {
        "structure":    structure,
        "structure_ok": structure_ok,
        "in_discount":  in_discount,
        "near_ob":      near_ob,
        "in_fvg":       in_fvg,
        "smc_score":    smc_score,
        "order_block":  order_block,
        "fvg":          fvg,
        "equilibrium":  equil,
        "swing_high":   pd_zone.get("swing_high", 0),
        "swing_low":    pd_zone.get("swing_low", 0),
    }


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
    n = len(closes)
    if n < 2:
        return 0.0
    trs = [max(highs[i] - lows[i],
               abs(highs[i] - closes[i-1]),
               abs(lows[i] - closes[i-1]))
           for i in range(1, n)]
    trs = np.array(trs)
    if len(trs) < period:
        return float(np.mean(trs))
    atr = float(np.mean(trs[:period]))
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


# ─── Signal Result ────────────────────────────────────────────────────────────

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
    filter_detail:  Dict[str, bool] = field(default_factory=dict)
    sizing:         Dict[str, Any]  = field(default_factory=dict)
    smc:            Dict[str, Any]  = field(default_factory=dict)
    quality:        str = "B"
    skip_reason:    str = ""
    # v10.1
    mtf_label:      str = ""
    vpoc_label:     str = ""
    funding_label:  str = ""
    # v10.2
    regime:         str = ""
    regime_label:   str = ""


# ─── Main signal generator ───────────────────────────────────────────────────

def generate_signal(
    symbol:            str,
    ohlcv:             List[List[float]],
    orderbook:         Dict[str, Any],
    btc_ohlcv:         List[List[float]],
    account_size_usd:  float = None,
    # v10.1
    ohlcv_1h:          Optional[List[List[float]]] = None,
    funding_long_ok:   Optional[bool]               = None,
    funding_short_ok:  Optional[bool]               = None,
    funding_long_lbl:  str                          = "",
    funding_short_lbl: str                          = "",
    # v10.2
    btc_funding_rate:  float                        = 0.0,
    btc_ohlcv_1h:      Optional[List[List[float]]] = None,
) -> Optional[SignalResult]:
    """
    Adaptive signal pipeline:
    1. Regime detection  (TRENDING / RANGING / EXTREME_FEAR)
    2. Core rules        (RSI + EMA + Volume — thresholds from regime)
    3. RR check
    4. SMC layer
    5. Smart Filters v2  (9 filters)
    6. Position sizing   (scaled by regime size_multiplier)
    """
    if account_size_usd is None:
        account_size_usd = config.ACCOUNT_SIZE_USD

    min_candles = config.CANDLE_LOOKBACK // 2
    if not ohlcv or len(ohlcv) < min_candles:
        logger.info("⏭ SKIP %s — only %d candles (need %d)",
                    symbol, len(ohlcv) if ohlcv else 0, min_candles)
        return None

    # ── Regime Detection (BTC 1h preferred, fallback to 15m) ─────────────────
    regime_ohlcv = btc_ohlcv_1h if btc_ohlcv_1h else btc_ohlcv
    regime_name, regime_params, regime_debug = detect_regime(
        btc_ohlcv    = regime_ohlcv,
        funding_rate = btc_funding_rate,
    )
    regime_lbl = regime_label(regime_name, regime_params)

    timeframe = select_timeframe(ohlcv)

    arr     = np.array(ohlcv, dtype=float)
    opens   = arr[:, 1]
    highs   = arr[:, 2]
    lows    = arr[:, 3]
    closes  = arr[:, 4]
    volumes = arr[:, 5]

    # ── Indicators ───────────────────────────────────────────────────────────
    rsi      = _rsi(closes, config.RSI_PERIOD)
    ema_fast = _ema(closes, config.EMA_FAST)
    ema_slow = _ema(closes, config.EMA_SLOW)
    atr      = _atr(highs, lows, closes, config.ATR_PERIOD)

    window     = min(config.VOLUME_LOOKBACK, len(volumes) - 1)
    avg_volume = float(np.mean(volumes[-window-1:-1])) if window > 0 else 1.0
    last_vol   = float(volumes[-1])
    vol_ratio  = last_vol / avg_volume if avg_volume > 0 else 0.0
    entry      = float(closes[-1])

    # ── CORE RULES — thresholds from regime ──────────────────────────────────
    rsi_ob  = regime_params.rsi_oversold
    rsi_os  = regime_params.rsi_overbought
    vol_min = regime_params.volume_multiplier

    long_core  = rsi < rsi_ob  and ema_fast > ema_slow and vol_ratio >= vol_min
    short_core = rsi > rsi_os  and ema_fast < ema_slow and vol_ratio >= vol_min

    if not long_core and not short_core:
        logger.info(
            "⏭ SKIP %s [%s] [%s] — Core rules failed | "
            "RSI=%.1f (need <%.0f/>%.0f) | "
            "EMA9=%.2f %s EMA21=%.2f | "
            "VolRatio=%.2f (need >%.1f)",
            symbol, timeframe, regime_name,
            rsi, rsi_ob, rsi_os,
            ema_fast, ">" if ema_fast > ema_slow else "<", ema_slow,
            vol_ratio, vol_min,
        )
        return None

    direction = "LONG" if long_core else "SHORT"

    # ── SL / TP — multipliers from regime ────────────────────────────────────
    sl_mult = regime_params.atr_sl_mult
    tp_mult = regime_params.atr_tp_mult

    if direction == "LONG":
        stop_loss   = entry - atr * sl_mult
        take_profit = entry + atr * tp_mult
    else:
        stop_loss   = entry + atr * sl_mult
        take_profit = entry - atr * tp_mult

    sl_dist  = abs(entry - stop_loss)
    tp_dist  = abs(entry - take_profit)
    rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0.0

    if rr_ratio < config.MIN_RR_RATIO:
        logger.info(
            "⏭ SKIP %s [%s] %s [%s] — RR too low %.2f | ATR=%.4f",
            symbol, timeframe, direction, regime_name, rr_ratio, atr,
        )
        return None

    # ── Direction-specific funding ────────────────────────────────────────────
    funding_ok  = funding_long_ok  if direction == "LONG" else funding_short_ok
    funding_lbl = funding_long_lbl if direction == "LONG" else funding_short_lbl

    # ── SMC ───────────────────────────────────────────────────────────────────
    smc = _smc_confluence(direction, entry, opens, closes, highs, lows)
    logger.info(
        "📐 SMC %s [%s] %s | Structure=%s Discount=%s OB=%s FVG=%s Score=%d/4",
        symbol, timeframe, direction,
        smc["structure"], smc["in_discount"], smc["near_ob"], smc["in_fvg"],
        smc["smc_score"],
    )

    # ── VPOC ──────────────────────────────────────────────────────────────────
    profile    = build_volume_profile(ohlcv)
    vpoc_ok, _ = vpoc_confirms(direction, entry, profile)
    vpoc_lbl   = vpoc_label(profile, entry)

    # ── MTF ───────────────────────────────────────────────────────────────────
    mtf_lbl = mtf_bias_label(ohlcv_1h or [])

    # ── Smart Filters (9, min from regime) ────────────────────────────────────
    passed, filter_detail = all_filters_pass(
        direction    = direction,
        entry_price  = entry,
        ohlcv        = ohlcv,
        orderbook    = orderbook,
        btc_ohlcv    = btc_ohlcv,
        alt_ohlcv    = ohlcv,
        ohlcv_1h     = ohlcv_1h,
        funding_ok   = funding_ok,
        vpoc_ok      = vpoc_ok,
        min_pass     = regime_params.min_filters_pass,
    )

    filters_passed = sum(1 for v in filter_detail.values() if v)
    filters_total  = len(filter_detail)

    filter_str = " | ".join(
        f"{k}={'✓' if v else '✗'}" for k, v in filter_detail.items()
    )
    logger.info(
        "🔍 FILTERS %s [%s] %s [%s] — %d/%d passed | %s",
        symbol, timeframe, direction, regime_name,
        filters_passed, filters_total, filter_str,
    )

    if not passed:
        logger.info(
            "⏭ SKIP %s [%s] %s [%s] — %d/%d filters (need %d)",
            symbol, timeframe, direction, regime_name,
            filters_passed, filters_total, regime_params.min_filters_pass,
        )
        return None

    # ── Quality Grade ─────────────────────────────────────────────────────────
    total_score = filters_passed + smc["smc_score"]
    if total_score >= 11:
        quality = "A+"
    elif total_score >= 9:
        quality = "A"
    elif total_score >= 7:
        quality = "B"
    else:
        quality = "C"

    # ── Position Sizing (regime size_multiplier applied) ──────────────────────
    adjusted_account = account_size_usd * regime_params.size_multiplier
    sizing = calculate_position_size(adjusted_account, entry, stop_loss, ohlcv)

    logger.info(
        "✅ SIGNAL %s [%s] %s [%s] | Entry=%.4f SL=%.4f TP=%.4f | "
        "RR=%.2f | RSI=%.1f | Vol=%.2f× | SMC=%d/4 | "
        "Filters=%d/%d | Grade=%s | Size=%.0f%%",
        symbol, timeframe, direction, regime_name,
        entry, stop_loss, take_profit,
        rr_ratio, rsi, vol_ratio, smc["smc_score"],
        filters_passed, filters_total, quality,
        regime_params.size_multiplier * 100,
    )

    return SignalResult(
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
        smc            = smc,
        quality        = quality,
        mtf_label      = mtf_lbl,
        vpoc_label     = vpoc_lbl,
        funding_label  = funding_lbl,
        regime         = regime_name,
        regime_label   = regime_lbl,
    )
