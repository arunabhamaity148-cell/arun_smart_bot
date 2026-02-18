"""
ARUNABHA SMART SIGNAL v2.1
With BTC multi-timeframe data
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

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
    confirmation_pending: bool = False
    confirmation_price: float = 0.0


# Global pending signals for entry confirmation
_pending_confirmations: Dict[str, Dict] = {}


def generate_signal(
    symbol: str,
    ohlcv_15m: List[List[float]],
    ohlcv_5m: List[List[float]],
    ohlcv_1h: List[List[float]],
    btc_ohlcv_15m: List[List[float]],
    btc_ohlcv_1h: List[List[float]],      # 🆕 New
    btc_ohlcv_4h: List[List[float]],      # 🆕 New
    funding_rate: float,
    fear_index: int,
    account_size: float,
    risk_manager: RiskManager,
    filters: SimpleFilters,
    engine: ExtremeFearEngine,
    mood: MarketMood
) -> Optional[SignalResult]:
    """
    Full signal pipeline with entry confirmation
    """
    
    global _pending_confirmations
    
    logger.info("=" * 60)
    logger.info("🔍 SCAN START: %s", symbol)
    logger.info("=" * 60)
    
    # Check for pending confirmation
    if symbol in _pending_confirmations:
        return _check_confirmation(
            symbol, ohlcv_15m, risk_manager, filters
        )
    
    # ─── STEP 1: Risk Manager Check ─────────────────────────
    logger.info("[STEP 1] Risk Manager Check...")
    if not risk_manager.can_trade(symbol):
        stats = risk_manager.get_stats()
        logger.warning("❌ BLOCK: %s | Daily limit %d/%d or max concurrent %d/%d",
                      symbol, 
                      stats.get('total', 0), config.MAX_SIGNALS_DAY,
                      stats.get('active_trades', 0), config.MAX_CONCURRENT)
        return None
    logger.info("✅ PASS: Can trade")
    
    # ─── STEP 2: Market Mood Check ──────────────────────────
    logger.info("[STEP 2] Market Mood Check...")
    mood_data = mood.get_mood()
    logger.info("   Fear Index: %d/100 (%s)", fear_index, mood_data["mood"])
    
    if not mood_data["should_trade"]:
        logger.warning("❌ BLOCK: Fear index %d > stop threshold %d",
                      fear_index, config.FEAR_INDEX_STOP)
        return None
    logger.info("✅ PASS: Market mood OK")
    
    # ─── STEP 3: Extreme Fear Engine ────────────────────────
    logger.info("[STEP 3] Extreme Fear Engine (Strict)...")
    engine_result = engine.evaluate(
        ohlcv_15m=ohlcv_15m,
        ohlcv_5m=ohlcv_5m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        funding_rate=funding_rate,
        fear_index=fear_index
    )
    
    logger.info("   Score: %d/100 (min: %d) | Grade: %s", 
               engine_result["score"], config.MIN_SCORE_TO_TRADE, engine_result["grade"])
    logger.info("   EMA200: %s | Structure: %s", 
               engine_result["ema200_passed"], engine_result["structure_passed"])
    
    if not engine_result["ema200_passed"]:
        logger.warning("❌ BLOCK: EMA200 not confirmed (MANDATORY)")
        return None
        
    if not engine_result["structure_passed"]:
        logger.warning("❌ BLOCK: Structure shift not confirmed (MANDATORY)")
        logger.info("   💡 TIP: Wait for BOS (Break of Structure) or CHoCH")
        return None
    
    if not engine_result["can_trade"]:
        logger.warning("❌ BLOCK: Score %d < minimum %d",
                      engine_result["score"], config.MIN_SCORE_TO_TRADE)
        return None
    logger.info("✅ PASS: All mandatory checks OK")
    
    # ─── STEP 4: Determine Direction ────────────────────────
    logger.info("[STEP 4] Determine Direction...")
    direction = engine_result["direction"]
    logger.info("   Direction: %s (from structure)", direction)
    
    # ─── STEP 5: Simple Filters (8 filters) ─────────────────
    logger.info("[STEP 5] Simple Filters Check (need %d/8)...", config.MIN_FILTERS_PASS)
    filters_passed, filters_total, filter_details, mandatory_pass = filters.evaluate(
        direction=direction,
        ohlcv_15m=ohlcv_15m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        btc_ohlcv_1h=btc_ohlcv_1h,      # 🆕 Pass new data
        btc_ohlcv_4h=btc_ohlcv_4h,      # 🆕 Pass new data
        funding_rate=funding_rate,
        symbol=symbol,
        ema200_passed=engine_result["ema200_passed"],
        structure_passed=engine_result["structure_passed"]
    )
    
    if not mandatory_pass:
        logger.warning("❌ BLOCK: Mandatory filters failed (Session/BTC/EMA200/Structure)")
        return None
    
    for name, detail in filter_details.items():
        status = "✅" if detail["pass"] else "❌"
        logger.info("   %s %s: %s", status, name, detail["msg"])
    
    logger.info("   Total: %d/%d passed", filters_passed, filters_total)
    
    if filters_passed < config.MIN_FILTERS_PASS:
        failed = [n for n, d in filter_details.items() if not d["pass"]]
        logger.warning("❌ BLOCK: Filters %d/%d, need %d | Failed: %s",
                      filters_passed, filters_total, 
                      config.MIN_FILTERS_PASS, ", ".join(failed))
        return None
    logger.info("✅ PASS: All filters OK")
    
    # ─── STEP 6: Calculate SL/TP ────────────────────────────
    logger.info("[STEP 6] Calculate SL/TP...")
    atr = _calculate_atr(ohlcv_15m)
    current_price = ohlcv_15m[-1][4]
    
    sl_tp = risk_manager.calculate_sl_tp(direction, current_price, atr)
    logger.info("   ATR: %.2f | Entry: %.2f | SL: %.2f | TP: %.2f | R:R: %.2f:1",
               atr, current_price, sl_tp["stop_loss"], sl_tp["take_profit"], sl_tp["rr_ratio"])
    
    if sl_tp["rr_ratio"] < config.MIN_RR_RATIO:
        logger.warning("❌ BLOCK: RR %.2f < minimum %.2f",
                      sl_tp["rr_ratio"], config.MIN_RR_RATIO)
        return None
    logger.info("✅ PASS: RR OK")
    
    # ─── STEP 7: Entry Confirmation Delay ────────────────────
    if config.ENTRY_CONFIRMATION_WAIT:
        logger.info("[STEP 7] ⏳ ENTRY CONFIRMATION PENDING...")
        logger.info("   Waiting for next candle close above entry zone")
        
        _pending_confirmations[symbol] = {
            "direction": direction,
            "entry_zone": current_price,
            "sl": sl_tp["stop_loss"],
            "tp": sl_tp["take_profit"],
            "rr": sl_tp["rr_ratio"],
            "score": engine_result["score"],
            "grade": engine_result["grade"],
            "filters_passed": filters_passed,
            "logic": engine_result["top_logic"],
            "mood": mood_data,
            "timestamp": datetime.now(),
            "candle_count": 0
        }
        
        return SignalResult(
            symbol=symbol,
            direction=direction,
            entry=current_price,
            stop_loss=sl_tp["stop_loss"],
            take_profit=sl_tp["take_profit"],
            rr_ratio=sl_tp["rr_ratio"],
            position_size={},
            extreme_fear_score=engine_result["score"],
            extreme_fear_grade=engine_result["grade"],
            filters_passed=filters_passed,
            logic_triggered=engine_result["top_logic"],
            market_mood=mood_data["emoji"] + " " + mood_data["mood"],
            session_info=", ".join(mood.is_session_active()["active_sessions"]),
            human_insight="⏳ PENDING: Waiting for entry confirmation (next candle close)",
            confirmation_pending=True,
            confirmation_price=current_price
        )
    
    return _finalize_signal(
        symbol, direction, current_price, sl_tp, engine_result, 
        filters_passed, mood_data, risk_manager, filters, account_size, mood
    )


def _check_confirmation(symbol: str, ohlcv: List[List[float]], 
                       risk_manager: RiskManager, filters: SimpleFilters) -> Optional[SignalResult]:
    """Check if entry confirmation criteria met"""
    global _pending_confirmations
    
    pending = _pending_confirmations.get(symbol)
    if not pending:
        return None
    
    current_price = ohlcv[-1][4]
    direction = pending["direction"]
    entry_zone = pending["entry_zone"]
    
    pending["candle_count"] += 1
    
    logger.info("[CONFIRMATION CHECK] %s - Candle #%d", symbol, pending["candle_count"])
    
    confirmed = False
    
    if direction == "LONG":
        bullish_close = current_price > entry_zone * 1.001
        higher_low = ohlcv[-1][3] > ohlcv[-2][3] if len(ohlcv) > 1 else False
        confirmed = bullish_close and higher_low
        
        logger.info("   Price: %.2f vs Entry: %.2f | Bullish: %s | Higher Low: %s",
                   current_price, entry_zone, bullish_close, higher_low)
    else:
        bearish_close = current_price < entry_zone * 0.999
        lower_high = ohlcv[-1][2] < ohlcv[-2][2] if len(ohlcv) > 1 else False
        confirmed = bearish_close and lower_high
        
        logger.info("   Price: %.2f vs Entry: %.2f | Bearish: %s | Lower High: %s",
                   current_price, entry_zone, bearish_close, lower_high)
    
    if confirmed:
        logger.info("✅ CONFIRMED: Entry criteria met after %d candles", pending["candle_count"])
        del _pending_confirmations[symbol]
        
        atr = _calculate_atr(ohlcv)
        sl_tp = risk_manager.calculate_sl_tp(direction, current_price, atr)
        
        return _finalize_signal(
            symbol, direction, current_price, sl_tp,
            {"score": pending["score"], "grade": pending["grade"], "top_logic": pending["logic"]},
            pending["filters_passed"], pending["mood"], risk_manager, filters, 1000, None
        )
    elif pending["candle_count"] >= 3:
        logger.warning("❌ CONFIRMATION FAILED: Max candles reached, cancelling signal")
        del _pending_confirmations[symbol]
        return None
    else:
        logger.info("⏳ Still waiting for confirmation...")
        return None


def _finalize_signal(symbol, direction, entry, sl_tp, engine_result, 
                    filters_passed, mood_data, risk_manager, filters, account_size, mood):
    """Finalize and create signal"""
    
    position = risk_manager.calculate_position(
        account_size, entry, sl_tp["stop_loss"]
    )
    
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
    
    risk_manager.open_trade(trade)
    filters.update_cooldown(symbol)
    
    insight = _build_insight(mood_data, engine_result, filters_passed, direction)
    
    logger.info("=" * 60)
    logger.info("✅ SIGNAL GENERATED: %s %s @ %.2f", symbol, direction, entry)
    logger.info("   Score: %d | Grade: %s | RR: %.2f", 
               engine_result["score"], engine_result["grade"], sl_tp["rr_ratio"])
    logger.info("=" * 60)
    
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
        session_info=", ".join(mood.is_session_active()["active_sessions"]) if mood else "",
        human_insight=insight,
        confirmation_pending=False
    )


def _build_insight(mood: Dict, engine: Dict, filters: int, direction: str) -> str:
    """Build human-readable insight"""
    lines = []
    
    if mood["mood"] == "EXTREME_FEAR":
        lines.append("😱 EXTREME FEAR: Quick profit target")
    elif mood["mood"] == "FEAR":
        lines.append("⚠️ FEAR: Reduced size, cautious")
    
    lines.append(f"🧠 Logic: {', '.join(engine['top_logic'][:3])}")
    lines.append(f"🔍 Filters: {filters}/8 passed")
    
    if direction == "LONG":
        lines.append("🟢 LONG: EMA200 + Structure + BTC Bull confirmed")
    else:
        lines.append("🔴 SHORT: EMA200 + Structure + BTC Bear confirmed")
    
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
