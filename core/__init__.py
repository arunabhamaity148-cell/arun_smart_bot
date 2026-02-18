"""
Core modules for ARUNABHA EXTREME FEAR BOT v3.0
"""

from .extreme_fear_engine import ExtremeFearEngine, extreme_fear_engine
from .simple_filters import SimpleFilters
from .risk_manager import RiskManager, Trade, risk_manager  # 🆕 Export instance too
from .market_mood import MarketMood, get_fear_index
from .smart_signal import generate_signal, SignalResult
from .btc_regime_detector import BTCRegimeDetector, BTCRegime, btc_detector

__all__ = [
    "ExtremeFearEngine",
    "extreme_fear_engine",
    "SimpleFilters",
    "RiskManager",
    "Trade",
    "risk_manager",  # 🆕 Instance
    "MarketMood",
    "get_fear_index",
    "generate_signal",
    "SignalResult",
    "BTCRegimeDetector",
    "BTCRegime",
    "btc_detector",
]
