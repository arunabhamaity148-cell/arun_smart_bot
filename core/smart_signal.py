"""
ARUNABHA SMART SIGNAL v1.0
Integrates Extreme Fear Engine + Simple Filters + Risk Manager
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import numpy as np

import config
from .extreme_fear_engine import ExtremeFearEngine
from .simple_filters import SimpleFilters
from .risk_manager import RiskManager, Trade
from .market_mood import MarketMood

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    position_size: Dict[str, float]
    extreme_fear_score: int
    extreme_fear_grade: str
    filters_passed: int
    logic_triggered: List[str]
    market_mood: str
    session_info: str
    human_insight: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def generate_signal(
    symbol: str,
    ohlcv_15m: List[List[float]],
    ohlcv_5m: List[List[float]],
    ohlcv_1h: List[List[float]],
    btc_ohlcv_15m: List[List[float]],
    funding_rate: float,
    fear_index: int,
    account_size: float,
    risk_manager: RiskManager,
    filters: SimpleFilters,
    engine: ExtremeFearEngine,
    mood: MarketMood
) -> Optional[SignalResult]:
    """
    Main signal generation pipeline
    """
    
    # 1. Check if we can trade
    if not risk_manager.can_trade(symbol):
        return None
    
    # 2. Check market mood
    mood_data = mood.get_mood()
    if not mood_data["should_trade"]:
        logger.info("%s: Fear index %d too high, stopping", symbol, fear_index)
        return None
    
    # 3. Run Extreme Fear Engine (your 10 logic)
    engine_result = engine.evaluate(
        ohlcv_15m=ohlcv_15m,
        ohlcv_5m=ohlcv_5m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        funding_rate=funding_rate,
        fear_index=fear_index
    )
    
    if not engine_result["can_trade"]:
        logger.info("%s: Extreme Fear Score %d too low", 
                   symbol, engine_result["score"])
        return None
    
    # 4. Run Simple Filters (6 filters, need 4)
    filters_passed, filters_total, filter_details = filters.evaluate(
        direction="LONG",  # Will determine below
        ohlcv_15m=ohlcv_15m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        funding_rate=funding_rate,
        symbol=symbol
    )
    
    if filters_passed < config.MIN_FILTERS_PASS:
        logger.info("%s: Filters %d/%d, need %d", 
                   symbol, filters_passed, filters_total, config.MIN_FILTERS_PASS)
        return None
    
    # 5. Determine direction from top logic
    direction = _determine_direction(engine_result["top_logic"], ohlcv_15m)
    
    # Re-run filters with correct direction
    filters_passed, filters_total, filter_details = filters.evaluate(
        direction=direction,
        ohlcv_15m=ohlcv_15m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        funding_rate=funding_rate,
        symbol=symbol
    )
    
    if filters_passed < config.MIN_FILTERS_PASS:
        return None
    
    # 6. Calculate SL/TP
    atr = _calculate_atr(ohlcv_15m)
    sl_tp = risk_manager.calculate_sl_tp(direction, ohlcv_15m[-1][4], atr)
    
    if sl_tp["rr_ratio"] < config.MIN_RR_RATIO:
        logger.info("%s: RR %.2f too low", symbol, sl_tp["rr_ratio"])
        return None
    
    # 7. Calculate position size
    entry = ohlcv_15m[-1][4]
    position = risk_manager.calculate_position(
        account_size, entry, sl_tp["stop_loss"]
    )
    
    # 8. Create trade object
    from datetime import datetime
    trade = Trade(
        symbol=symbol,
        direction=direction,
        entry=entry,
        stop_loss=sl_tp["stop_loss"],
        take_profit=sl_tp["take_profit"],
        size_usd=position.get("position_usd", 0),
        timestamp=datetime.now(),
        max_holding_minutes=90 if mood_data["mood"] == "EXTREME_FEAR" else 120
    )
    
    # 9. Register trade
    risk_manager.open_trade(trade)
    filters.update_cooldown(symbol)
    
    # 10. Build human insight
    insight = _build_insight(
        mood_data, engine_result, filters_passed, direction
    )
    
    logger.info(
        "✅ SIGNAL %s %s | Score: %d/%d | Grade: %s | RR: %.2f | Filters: %d/6",
        symbol, direction, engine_result["score"], 100,
        engine_result["grade"], sl_tp["rr_ratio"], filters_passed
    )
    
    return SignalResult(
        symbol=symbol,
        direction=direction,
        entry=entry,
        stop_loss=sl_tp["stop_loss"],
        take_profit=sl_tp["take_profit"],
        rr_ratio=sl_tp["rr_ratio"],
        position_size=position,
        extreme_fear_score=engine_result["score"],
        extreme_fear_grade=engine_result["grade"],
        filters_passed=filters_passed,
        logic_triggered=engine_result["top_logic"],
        market_mood=mood_data["emoji"] + " " + mood_data["mood"],
        session_info=", ".join(mood.is_session_active()["active_sessions"]),
        human_insight=insight
    )


def _determine_direction(top_logic: List[str], ohlcv: List[List[float]]) -> str:
    """Determine direction from triggered logic"""
    # Most extreme fear logic are bullish reversal
    bullish_logic = [
        "Liquidity Sweep", "RSI Capitulation", "Bear Trap",
        "Funding Extreme", "Demand OB", "EMA200 Reclaim",
        "MTF Divergence", "Session Reversal"
    ]
    
    bearish_logic = ["BTC Calm + Alt Strong"]  # Can be either
    
    bullish_count = sum(1 for l in top_logic if l in bullish_logic)
    
    # Default to LONG in extreme fear (mean reversion)
    return "LONG" if bullish_count > 0 else "SHORT"


def _build_insight(mood: Dict, engine: Dict, filters: int, direction: str) -> str:
    """Build human-readable insight"""
    lines = []
    
    # Mood context
    if mood["mood"] == "EXTREME_FEAR":
        lines.append("😱 EXTREME FEAR: Choto profit, quick exit")
    elif mood["mood"] == "FEAR":
        lines.append("⚠️ FEAR: Cautious, reduce size")
    
    # Logic summary
    lines.append(f"🧠 Logic: {', '.join(engine['top_logic'][:3])}")
    
    # Filter summary
    lines.append(f"🔍 Filters: {filters}/6 passed")
    
    # Direction insight
    if direction == "LONG":
        lines.append("🟢 LONG: Panic reversal, mean reversion")
    else:
        lines.append("🔴 SHORT: Weakness continuation")
    
    return " | ".join(lines)


def _calculate_atr(ohlcv: List[List[float]], period: int = 14) -> float:
    """Calculate ATR"""
    if len(ohlcv) < period + 1:
        return 0.0
        
    trs = []
    for i in range(1, len(ohlcv)):
        high = ohlcv[i][2]
        low = ohlcv[i][3]
        prev_close = ohlcv[i-1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    
    return sum(trs[-period:]) / period


from datetime import datetime 
