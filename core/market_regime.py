"""
market_regime.py — ARUNABHA SMART v10.2
══════════════════════════════════════════
Market Regime Detector + Adaptive Strategy Selector

তিনটা Regime auto-detect করে:

① TRENDING
   • EMA9 > EMA21 clearly (>0.3% gap), RSI 50-70 বা 30-50
   • ADX-style momentum দেখা
   • Strategy: Momentum follow — standard RSI 35/65 thresholds
   • Signal rate: দিনে 2-4টা

② RANGING / CHOPPY (এখনকার market)
   • EMA9 ≈ EMA21 (gap < 0.15%), RSI 40-60 range-এ আটকা
   • ATR কম, candle ranges ছোট
   • Strategy: Mean Reversion — RSI thresholds relax করে 30/70
     Range top/bottom থেকে entry, tighter SL
   • Signal rate: দিনে 1-2টা

③ EXTREME FEAR / CAPITULATION
   • Funding rate deeply negative (< -0.05%)
   • RSI < 25 বা > 75 (extreme readings)
   • Volume spike + sharp 1h candle
   • Strategy: Fade the crowd — LONG when extreme fear
     Wider SL (2x ATR), smaller position size
   • Signal rate: দিনে 0-1টা (rare but high quality)

প্রতিটা regime-এ আলাদা:
  • RSI thresholds
  • ATR multipliers (SL/TP)
  • Volume requirements
  • Min filters required
  • Position size multiplier
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ─── Regime labels ────────────────────────────────────────────────────────────
REGIME_TRENDING  = "TRENDING"
REGIME_RANGING   = "RANGING"
REGIME_FEAR      = "EXTREME_FEAR"


# ─── Per-regime parameter sets ───────────────────────────────────────────────

@dataclass
class RegimeParams:
    """All signal parameters that change per regime."""
    regime:             str

    # Core signal thresholds
    rsi_oversold:       float   # LONG  trigger
    rsi_overbought:     float   # SHORT trigger

    # ATR multipliers
    atr_sl_mult:        float   # SL = entry ± ATR × this
    atr_tp_mult:        float   # TP = entry ± ATR × this

    # Volume requirement
    volume_multiplier:  float   # last_vol / avg_vol must exceed this

    # Filter strictness
    min_filters_pass:   int     # out of 9

    # Position sizing
    size_multiplier:    float   # 1.0 = normal, 0.5 = half size

    # Human-readable description for Telegram
    label:              str
    emoji:              str


# ── Trending market params ────────────────────────────────────────────────────
PARAMS_TRENDING = RegimeParams(
    regime            = REGIME_TRENDING,
    rsi_oversold      = 35.0,    # Standard — wait for clear oversold
    rsi_overbought    = 65.0,
    atr_sl_mult       = 1.5,
    atr_tp_mult       = 2.5,
    volume_multiplier = 1.2,
    min_filters_pass  = 5,       # Strict
    size_multiplier   = 1.0,     # Full size
    label             = "Trending Market",
    emoji             = "📈",
)

# ── Ranging/Choppy params ─────────────────────────────────────────────────────
PARAMS_RANGING = RegimeParams(
    regime            = REGIME_RANGING,
    rsi_oversold      = 30.0,    # More extreme — wait for deeper oversold
    rsi_overbought    = 70.0,    # More extreme — wait for deeper overbought
    atr_sl_mult       = 1.2,     # Tighter SL (range is smaller)
    atr_tp_mult       = 1.8,     # Shorter TP (range is smaller)
    volume_multiplier = 1.5,     # Need stronger volume spike in choppy market
    min_filters_pass  = 4,       # Slightly relaxed (fewer strong signals)
    size_multiplier   = 0.7,     # Smaller position (lower confidence)
    label             = "Ranging / Choppy",
    emoji             = "↔️",
)

# ── Extreme Fear params ───────────────────────────────────────────────────────
PARAMS_FEAR = RegimeParams(
    regime            = REGIME_FEAR,
    rsi_oversold      = 25.0,    # Very extreme — only true capitulation
    rsi_overbought    = 75.0,
    atr_sl_mult       = 2.0,     # Wider SL (volatile, whipsaw risk)
    atr_tp_mult       = 3.5,     # Wider TP (big moves when fear unwinds)
    volume_multiplier = 2.0,     # Must see panic volume
    min_filters_pass  = 4,       # Relaxed (fear distorts normal filters)
    size_multiplier   = 0.5,     # Half size (high risk environment)
    label             = "Extreme Fear",
    emoji             = "😱",
)


# ─── Regime Detection Logic ───────────────────────────────────────────────────

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


def _atr_pct(ohlcv: List[List[float]]) -> float:
    """ATR as % of current price — measures volatility."""
    if not ohlcv or len(ohlcv) < 15:
        return 0.5
    arr    = np.array(ohlcv, dtype=float)
    highs  = arr[:, 2]
    lows   = arr[:, 3]
    closes = arr[:, 4]
    n      = len(closes)
    trs    = [max(highs[i] - lows[i],
                  abs(highs[i] - closes[i-1]),
                  abs(lows[i] - closes[i-1]))
              for i in range(1, n)]
    atr = float(np.mean(trs[-14:])) if len(trs) >= 14 else float(np.mean(trs))
    return (atr / closes[-1]) * 100 if closes[-1] > 0 else 0.5


def _ema_gap_pct(ohlcv: List[List[float]]) -> float:
    """EMA9-EMA21 gap as % of price — measures trend strength."""
    if not ohlcv or len(ohlcv) < 22:
        return 0.0
    closes = np.array(ohlcv, dtype=float)[:, 4]
    ema9   = _ema(closes, 9)
    ema21  = _ema(closes, 21)
    return abs(ema9 - ema21) / ema21 * 100 if ema21 > 0 else 0.0


def _rsi_volatility(ohlcv: List[List[float]], lookback: int = 20) -> float:
    """Std dev of RSI over lookback — low = choppy, high = trending."""
    if not ohlcv or len(ohlcv) < lookback + 15:
        return 10.0
    closes = np.array(ohlcv, dtype=float)[:, 4]
    rsi_series = []
    for i in range(lookback):
        idx    = -(lookback - i)
        window = closes[:idx] if idx != 0 else closes
        if len(window) >= 15:
            rsi_series.append(_rsi(window[-30:]))
    return float(np.std(rsi_series)) if rsi_series else 10.0


def detect_regime(
    btc_ohlcv:    List[List[float]],
    funding_rate: float = 0.0,
) -> Tuple[str, RegimeParams, Dict[str, Any]]:
    """
    Detects current market regime from BTC 1h OHLCV + funding rate.

    Returns:
        (regime_name, params, debug_info)

    Logic priority:
        1. Extreme Fear check (funding + RSI extreme)
        2. Ranging check (tight EMA gap + low ATR + low RSI std)
        3. Default → Trending
    """
    if not btc_ohlcv or len(btc_ohlcv) < 30:
        logger.debug("Regime: insufficient data → RANGING default")
        return REGIME_RANGING, PARAMS_RANGING, {}

    closes = np.array(btc_ohlcv, dtype=float)[:, 4]
    rsi         = _rsi(closes, 14)
    ema_gap_pct = _ema_gap_pct(btc_ohlcv)
    atr_pct     = _atr_pct(btc_ohlcv)
    rsi_std     = _rsi_volatility(btc_ohlcv, 20)

    debug = {
        "rsi":          round(rsi, 1),
        "ema_gap_pct":  round(ema_gap_pct, 3),
        "atr_pct":      round(atr_pct, 3),
        "rsi_std":      round(rsi_std, 2),
        "funding_rate": round(funding_rate * 100, 4),
    }

    # ── 1. Extreme Fear check ──────────────────────────────────────────────
    # Funding deeply negative AND RSI very low = panic capitulation
    is_panic_long  = funding_rate <= -0.0005 and rsi < 30   # panic short squeeze setup
    is_panic_short = funding_rate >=  0.0010 and rsi > 70   # extreme greed reversal

    if is_panic_long or is_panic_short:
        logger.info(
            "🔴 Regime: EXTREME_FEAR | RSI=%.1f Funding=%.4f%% EMA_gap=%.3f%%",
            rsi, funding_rate * 100, ema_gap_pct,
        )
        return REGIME_FEAR, PARAMS_FEAR, debug

    # ── 2. Ranging/Choppy check ────────────────────────────────────────────
    # Tight EMA gap + low ATR + RSI std dev low = sideways chop
    tight_ema  = ema_gap_pct < 0.20    # EMA9/EMA21 within 0.20% of each other
    low_atr    = atr_pct < 0.40        # ATR < 0.40% of price
    low_rsi_sd = rsi_std < 8.0         # RSI not moving much

    ranging_score = sum([tight_ema, low_atr, low_rsi_sd])
    if ranging_score >= 2:             # 2 out of 3 = choppy
        logger.info(
            "↔️  Regime: RANGING | RSI=%.1f EMA_gap=%.3f%% ATR=%.3f%% RSI_std=%.1f",
            rsi, ema_gap_pct, atr_pct, rsi_std,
        )
        return REGIME_RANGING, PARAMS_RANGING, debug

    # ── 3. Default: Trending ──────────────────────────────────────────────
    logger.info(
        "📈 Regime: TRENDING | RSI=%.1f EMA_gap=%.3f%% ATR=%.3f%% RSI_std=%.1f",
        rsi, ema_gap_pct, atr_pct, rsi_std,
    )
    return REGIME_TRENDING, PARAMS_TRENDING, debug


def regime_label(regime: str, params: RegimeParams) -> str:
    """Short label for Telegram alerts."""
    return f"{params.emoji} {params.label}"
