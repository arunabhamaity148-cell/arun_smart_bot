"""
Core modules for ARUNABHA EXTREME FEAR BOT v1.0
"""

from .extreme_fear_engine import ExtremeFearEngine
from .simple_filters import SimpleFilters
from .risk_manager import RiskManager, Trade
from .market_mood import MarketMood, get_fear_index
from .smart_signal import generate_signal, SignalResult

__all__ = [
    "ExtremeFearEngine",
    "SimpleFilters",
    "RiskManager",
    "Trade",
    "MarketMood",
    "get_fear_index",
    "generate_signal",
    "SignalResult",
]
