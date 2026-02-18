"""
ARUNABHA SMART SIGNAL v1.0
Full debug logging - kon step e block hochhe dekhabe
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
    timestamp: str = field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())


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
    Full signal pipeline with detailed logging
    """
    
    logger.info("=" * 60)
    logger.info("🔍 SCAN START: %s", symbol)
    logger.info("=" * 60)
    
    # ─── STEP 1: Risk Manager Check ─────────────────────────
    logger.info("[STEP 1] Risk Manager Check...")
    if not risk_manager.can_trade(symbol):
        stats = risk_manager.get_stats()
        logger.warning("❌ BLOCK: %s | Reason: Daily limit %d/%d or max concurrent %d/%d",
                      symbol, 
                      stats.get('total', 0), config.MAX_SIGNALS_DAY,
                      stats.get('active_trades', 0), config.MAX_CONCURRENT)
        return None
    logger.info("✅ PASS: Can trade")
    
    # ─── STEP 2: Market Mood Check ──────────────────────────
    logger.info("[STEP 2] Market Mood Check...")
    mood_data = mood.get_mood()
    logger.info("   Fear Index: %d/100 (%s)", fear_index, mood_data["mood"])
    logger.info("   Should Trade: %s", mood_data["should_trade"])
    
    if not mood_data["should_trade"]:
        logger.warning("❌ BLOCK: %s | Reason: Fear index %d > stop threshold %d",
                      symbol, fear_index, config.FEAR_INDEX_STOP)
        return None
    logger.info("✅ PASS: Market mood OK")
    
    # ─── STEP 3: Extreme Fear Engine ────────────────────────
    logger.info("[STEP 3] Extreme Fear Engine (10 Logic)...")
    engine_result = engine.evaluate(
        ohlcv_15m=ohlcv_15m,
        ohlcv_5m=ohlcv_5m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        funding_rate=funding_rate,
        fear_index=fear_index
    )
    
    logger.info("   Score: %d/100 | Grade: %s", 
               engine_result["score"], engine_result["grade"])
    logger.info("   Logic Passed: %d/9", engine_result["passed_count"])
    
    # Detailed logic breakdown
    for r in engine_result["results"]:
        status = "✅" if r.passed else "❌"
        logger.info("   %s %s: %s (+%d pts)", status, r.name, r.message, r.score if r.passed else 0)
    
    if not engine_result["can_trade"]:
        logger.warning("❌ BLOCK: %s | Reason: Score %d < minimum 40 | Need more logic triggers",
                      symbol, engine_result["score"])
        logger.info("   💡 TIP: Wait for liquidity sweep or RSI capitulation")
        return None
    logger.info("✅ PASS: Extreme Fear Score OK")
    
    # ─── STEP 4: Determine Direction ────────────────────────
    logger.info("[STEP 4] Determine Direction...")
    direction = _determine_direction(engine_result["top_logic"], ohlcv_15m)
    logger.info("   Direction: %s", direction)
    logger.info("   Top Logic: %s", ", ".join(engine_result["top_logic"][:3]))
    
    # ─── STEP 5: Simple Filters (6 filters) ─────────────────
    logger.info("[STEP 5] Simple Filters Check (need %d/6)...", config.MIN_FILTERS_PASS)
    filters_passed, filters_total, filter_details = filters.evaluate(
        direction=direction,
        ohlcv_15m=ohlcv_15m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        funding_rate=funding_rate,
        symbol=symbol
    )
    
    # Log each filter
    for name, detail in filter_details.items():
        status = "✅" if detail["pass"] else "❌"
        logger.info("   %s %s: %s (weight %d)", 
                   status, name, detail["msg"], detail["weight"])
    
    logger.info("   Total: %d/%d passed", filters_passed, filters_total)
    
    if filters_passed < config.MIN_FILTERS_PASS:
        failed = [n for n, d in filter_details.items() if not d["pass"]]
        logger.warning("❌ BLOCK: %s | Reason: Filters %d/%d, need %d | Failed: %s",
                      symbol, filters_passed, filters_total, 
                      config.MIN_FILTERS_PASS, ", ".join(failed))
        return None
    logger.info("✅ PASS: All filters OK")
    
    # ─── STEP 6: Calculate SL/TP ────────────────────────────
    logger.info("[STEP 6] Calculate SL/TP...")
    atr = _calculate_atr(ohlcv_15m)
    current_price = ohlcv_15m[-1][4]
    
    sl_tp = risk_manager.calculate_sl_tp(direction, current_price, atr)
    logger.info("   ATR: %.2f", atr)
    logger.info("   Entry: %.2f", current_price)
    logger.info("   SL: %.2f (%.2f%%)", sl_tp["stop_loss"], 
               abs(sl_tp["stop_loss"]-current_price)/current_price*100)
    logger.info("   TP: %.2f (%.2f%%)", sl_tp["take_profit"],
               abs(sl_tp["take_profit"]-current_price)/current_price*100)
    logger.info("   R:R: %.2f:1", sl_tp["rr_ratio"])
    
    if sl_tp["rr_ratio"] < config.MIN_RR_RATIO:
        logger.warning("❌ BLOCK: %s | Reason: RR %.2f < minimum %.2f",
                      symbol, sl_tp["rr_ratio"], config.MIN_RR_RATIO)
        return None
    logger.info("✅ PASS: RR OK")
    
    # ─── STEP 7: Position Sizing ────────────────────────────
    logger.info("[STEP 7] Position Sizing...")
    position = risk_manager.calculate_position(
        account_size, current_price, sl_tp["stop_loss"]
    )
    logger.info("   Risk: $%.2f (%.1f%%)", 
               position.get("risk_usd", 0), config.RISK_PCT)
    logger.info("   Position: $%.2f", position.get("position_usd", 0))
    logger.info("   Leverage: %dx", config.LEVERAGE)
    
    # ─── STEP 8: Create Trade ───────────────────────────────
    logger.info("[STEP 8] Create Trade...")
    from datetime import datetime
    trade = Trade(
        symbol=symbol,
        direction=direction,
        entry=current_price,
        stop_loss=sl_tp["stop_loss"],
        take_profit=sl_tp["take_profit"],
        size_usd=position.get("position_usd", 0),
        timestamp=datetime.now(),
        max_holding_minutes=90 if mood_data["mood"] == "EXTREME_FEAR" else 120
    )
    
    risk_manager.open_trade(trade)
    filters.update_cooldown(symbol)
    
    # ─── STEP 9: Build Insight ──────────────────────────────
    logger.info("[STEP 9] Build Human Insight...")
    insight = _build_insight(mood_data, engine_result, filters_passed, direction)
    logger.info("   Insight: %s", insight[:100] + "...")
    
    logger.info("=" * 60)
    logger.info("✅ SIGNAL GENERATED: %s %s", symbol, direction)
    logger.info("   Score: %d | Grade: %s | RR: %.2f", 
               engine_result["score"], engine_result["grade"], sl_tp["rr_ratio"])
    logger.info("=" * 60)
    
    return SignalResult(
        symbol=symbol,
        direction=direction,
        entry=current_price,
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
    
    if mood["mood"] == "EXTREME_FEAR":
        lines.append("😱 EXTREME FEAR: Choto profit, quick exit")
    elif mood["mood"] == "FEAR":
        lines.append("⚠️ FEAR: Cautious, reduce size")
    
    lines.append(f"🧠 Logic: {', '.join(engine['top_logic'][:3])}")
    lines.append(f"🔍 Filters: {filters}/6 passed")
    
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
