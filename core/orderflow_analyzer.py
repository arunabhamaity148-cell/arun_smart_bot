"""
Orderflow Analyzer
Reads the L2 orderbook (bid/ask) to detect buy vs sell pressure.

bid_pressure = bid_volume / (bid_volume + ask_volume)
> threshold → bullish pressure (supports LONG signals)
< (1-threshold) → bearish pressure (supports SHORT signals)
"""

import logging
from typing import Dict, Any, List

import config

logger = logging.getLogger(__name__)


def _total_volume(levels: List[List[float]], depth: int) -> float:
    """Sum notional value (price × size) for top `depth` levels."""
    return sum(price * qty for price, qty in levels[:depth] if len(levels[0]) >= 2)


def analyze_orderflow(orderbook: Dict[str, Any]) -> Dict[str, float]:
    """
    Args:
        orderbook: {'bids': [[price, vol], ...], 'asks': [[price, vol], ...]}

    Returns:
        {
            'bid_pressure': float 0-1,   # fraction of volume on bid side
            'ask_pressure': float 0-1,
            'imbalance':    float -1..1, # positive = more bids
        }
    """
    bids: List[List[float]] = orderbook.get("bids", [])
    asks: List[List[float]] = orderbook.get("asks", [])

    depth = config.ORDERBOOK_DEPTH

    bid_vol = _total_volume(bids, depth) if bids else 0.0
    ask_vol = _total_volume(asks, depth) if asks else 0.0
    total   = bid_vol + ask_vol

    if total <= 0:
        return {"bid_pressure": 0.5, "ask_pressure": 0.5, "imbalance": 0.0}

    bid_pressure = bid_vol / total
    ask_pressure = ask_vol / total
    imbalance    = bid_pressure - ask_pressure   # positive = bullish

    logger.debug(
        "Orderflow  bid_pressure=%.3f  ask_pressure=%.3f  imbalance=%.3f",
        bid_pressure, ask_pressure, imbalance,
    )
    return {
        "bid_pressure": bid_pressure,
        "ask_pressure": ask_pressure,
        "imbalance": imbalance,
    }


def is_bullish_pressure(orderbook: Dict[str, Any]) -> bool:
    result = analyze_orderflow(orderbook)
    return result["bid_pressure"] >= config.OB_PRESSURE_THRESHOLD


def is_bearish_pressure(orderbook: Dict[str, Any]) -> bool:
    result = analyze_orderflow(orderbook)
    return result["ask_pressure"] >= config.OB_PRESSURE_THRESHOLD