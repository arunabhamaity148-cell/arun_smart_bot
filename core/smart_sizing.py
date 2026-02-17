"""
Smart Sizing
Regime-adjusted position sizing between 1% and 2% risk.

Volatility regime:
  LOW  → use max risk (1.5-2.0%)  – cleaner markets, wider SL
  MED  → use mid risk (1.25%)
  HIGH → use min risk (1.0%)      – noisy, protect capital

Output is lot/position size in USD notional (leveraged).
"""

import logging
from typing import List

import numpy as np
import config

logger = logging.getLogger(__name__)


def _atr_regime(ohlcv: List[List[float]]) -> str:
    """Returns 'LOW', 'MED', or 'HIGH' volatility regime."""
    if not ohlcv or len(ohlcv) < 20:
        return "MED"
    arr    = np.array(ohlcv, dtype=float)
    highs  = arr[:, 2]
    lows   = arr[:, 3]
    closes = arr[:, 4]
    n      = len(closes)
    trs    = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
              for i in range(1, n)]
    atr    = float(np.mean(trs[-14:])) if trs else 0.0
    last_close = float(closes[-1])
    if last_close <= 0:
        return "MED"
    atr_pct = atr / last_close * 100
    if atr_pct < config.LOW_VOL_ATR_PCT:
        return "LOW"
    elif atr_pct < config.MED_VOL_ATR_PCT:
        return "MED"
    return "HIGH"


def calculate_risk_pct(ohlcv: List[List[float]]) -> float:
    """Returns risk % (1.0 – 2.0) adjusted for current volatility."""
    regime = _atr_regime(ohlcv)
    if regime == "LOW":
        risk_pct = config.RISK_PCT_MAX          # 2.0%
    elif regime == "MED":
        risk_pct = (config.RISK_PCT_MIN + config.RISK_PCT_MAX) / 2   # 1.5%
    else:
        risk_pct = config.RISK_PCT_MIN          # 1.0%
    logger.debug("Volatility regime=%s → risk_pct=%.2f%%", regime, risk_pct)
    return risk_pct


def calculate_position_size(
    account_size_usd: float,
    entry_price: float,
    stop_loss: float,
    ohlcv: List[List[float]],
) -> dict:
    """
    Calculate position size in USD and number of contracts.

    Args:
        account_size_usd: Total account equity.
        entry_price:      Planned entry price.
        stop_loss:        SL price.
        ohlcv:            Recent candles for regime detection.

    Returns:
        {
            'risk_pct':       float,
            'risk_usd':       float,
            'position_usd':   float,   # leveraged notional
            'contracts':      float,   # position_usd / entry_price
            'leverage':       int,
        }
    """
    if entry_price <= 0 or stop_loss <= 0 or account_size_usd <= 0:
        return {}

    risk_pct    = calculate_risk_pct(ohlcv)
    risk_usd    = account_size_usd * risk_pct / 100.0

    sl_distance_pct = abs(entry_price - stop_loss) / entry_price
    if sl_distance_pct <= 0:
        return {}

    # Max position we can afford given SL and risk budget (leveraged)
    position_usd = risk_usd / sl_distance_pct
    # Cap at 2× account (leverage acts naturally via exchange margin)
    max_position = account_size_usd * config.LEVERAGE
    position_usd = min(position_usd, max_position)

    contracts    = position_usd / entry_price

    result = {
        "risk_pct":     round(risk_pct, 2),
        "risk_usd":     round(risk_usd, 2),
        "position_usd": round(position_usd, 2),
        "contracts":    round(contracts, 6),
        "leverage":     config.LEVERAGE,
    }
    logger.debug("Position size: %s", result)
    return result