"""
ARUNABHA SMART SIGNAL v4.0 - FINAL
Conservative Elite Institutional Mode - OPTION 3
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

import config
from .extreme_fear_engine import ExtremeFearEngine, extreme_fear_engine
from .simple_filters import SimpleFilters
from .risk_manager import RiskManager, Trade, risk_manager
from .market_mood import MarketMood
from .btc_regime_detector import btc_detector, BTCRegime

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
    regime_mode: str = ""
    atr_pct: float = 0.0
    structure_strength: str = ""


_pending_confirmations: Dict[str, Dict] = {}


def generate_signal(
    symbol: str,
    ohlcv_15m: List[List[float]],
    ohlcv_5m: List[List[float]],
    ohlcv_1h: List[List[float]],
    btc_ohlcv_15m: List[List[float]],
    btc_ohlcv_1h: List[List[float]],
    btc_ohlcv_4h: List[List[float]],
    funding_rate: float,
    fear_index: int,
    account_size: float,
    risk_mgr: RiskManager,
    filters: SimpleFilters,
    engine: ExtremeFearEngine,
    mood: MarketMood
) -> Optional[SignalResult]:
    
    global _pending_confirmations
    
    logger.info("=" * 70)
    logger.info("[ELITE MODE] SCAN START: %s", symbol)
    logger.info("=" * 70)
    
    # Check pending confirmations
    if symbol in _pending_confirmations:
        return _check_confirmation(symbol, ohlcv_15m, risk_mgr, filters, fear_index, account_size, mood)
    
    # BTC data validation
    if not btc_ohlcv_15m or len(btc_ohlcv_15m) < 30:
        logger.error("❌ BLOCK: Insufficient BTC 15m data (need 30, got %s)", 
                    len(btc_ohlcv_15m) if btc_ohlcv_15m else 0)
        return None
    
    if not btc_ohlcv_1h or len(btc_ohlcv_1h) < 15:
        logger.error("❌ BLOCK: Insufficient BTC 1h data (need 15, got %s)",
                    len(btc_ohlcv_1h) if btc_ohlcv_1h else 0)
        return None
        
    if not btc_ohlcv_4h or len(btc_ohlcv_4h) < 15:
        logger.error("❌ BLOCK: Insufficient BTC 4h data (need 15, got %s)",
                    len(btc_ohlcv_4h) if btc_ohlcv_4h else 0)
        return None
    
    logger.info("[STEP 1] REGIME GATEKEEPER")
    
    regime_analysis = btc_detector.analyze(btc_ohlcv_15m, btc_ohlcv_1h, btc_ohlcv_4h)
    
    # ===== OPTION 3: CONFIDENCE-BASED ALLOW =====
    if not regime_analysis.can_trade:
        # confidence ভালো থাকলে ট্রেড করতে দেবে
        if regime_analysis.confidence >= 25:
            logger.warning("⚠️ Regime gate says BLOCK but confidence %d%% - allowing", 
                          regime_analysis.confidence)
        else:
            logger.error("❌ BLOCK: Regime gate - %s", regime_analysis.block_reason)
            return None
    
    trade_mode = regime_analysis.trade_mode
    
    logger.info("✅ REGIME: %s | Mode: %s | Conf: %d%% | Consistency: %s",
               regime_analysis.regime.value, trade_mode,
               regime_analysis.confidence, regime_analysis.consistency)
    
    logger.info("[STEP 2] VOLATILITY COMPRESSION")
    
    atr = _calculate_atr(ohlcv_15m)
    current_price = ohlcv_15m[-1][4]
    atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
    
    if atr <= 0:
        logger.error("❌ BLOCK: ATR invalid (%.4f) - insufficient data", atr)
        return None
    
    logger.info("   ATR%%: %.2f", atr_pct)
    
    if atr_pct > 4.0:
        logger.warning("   ⚠️ HIGH ATR: %.2f%% - RiskManager will evaluate", atr_pct)
    elif 2.5 <= atr_pct <= 4.0:
        logger.warning("   ⚠️ ELEVATED: ATR %.2f%% - Position may be reduced", atr_pct)
    
    if atr_pct < 0.4:
        logger.warning("   ⚠️ LOW: ATR %.2f%% - Breakout trades avoided", atr_pct)
    
    logger.info("✅ VOLATILITY: OK (ATR: %.4f)", atr)
    
    logger.info("[STEP 3] STRUCTURE CONFIRMATION")
    
    engine_result = engine.evaluate(
        ohlcv_15m=ohlcv_15m,
        ohlcv_5m=ohlcv_5m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        funding_rate=funding_rate,
        fear_index=fear_index,
        btc_trade_mode=trade_mode
    )
    
    if not engine_result["structure_passed"]:
        logger.error("❌ BLOCK: Structure not confirmed")
        return None
    
    if engine_result.get("structure_weak") and engine_result["score"] < 20:
        logger.error("❌ BLOCK: Structure weak and low score")
        return None
    
    direction = engine_result["direction"]
    
    # Direction check for trend mode
    if trade_mode == "TREND":
        if regime_analysis.regime in [BTCRegime.STRONG_BULL, BTCRegime.BULL] and direction != "LONG":
            if regime_analysis.confidence < 30:
                logger.error("❌ BLOCK: Direction mismatch - BTC bull but SHORT signal")
                return None
            else:
                logger.warning("⚠️ Direction mismatch but confidence %d%% - allowing", 
                              regime_analysis.confidence)
        if regime_analysis.regime in [BTCRegime.STRONG_BEAR, BTCRegime.BEAR] and direction != "SHORT":
            if regime_analysis.confidence < 30:
                logger.error("❌ BLOCK: Direction mismatch - BTC bear but LONG signal")
                return None
            else:
                logger.warning("⚠️ Direction mismatch but confidence %d%% - allowing",
                              regime_analysis.confidence)
    
    logger.info("✅ STRUCTURE: %s | Direction: %s", 
               engine_result.get("structure_strength", "OK"), direction)
    
    logger.info("[STEP 4] SCORE VALIDATION")
    
    score = engine_result["score"]
    grade = engine_result["grade"]
    
    logger.info("   Score: %d | Grade: %s | Mode: %s", score, grade, trade_mode)
    
    # Get market-specific thresholds from adaptive engine
    from core.adaptive_engine import adaptive_engine
    market_config = adaptive_engine.get_params()
    
    min_score = market_config.get("min_score", 20)
    
    if score < min_score:
        logger.error("❌ BLOCK: Score %d < minimum %d for %s mode", score, min_score, trade_mode)
        return None
    
    # Grade validation (OPTION 3: C grade allowed if score good)
    if grade == "C" and score < 30:
        logger.error("❌ BLOCK: Grade C with low score")
        return None
    
    logger.info("✅ SCORE: OK")
    
    logger.info("[STEP 5] RISK MANAGER")
    
    is_locked, lock_reason = risk_mgr.check_day_lock()
    if is_locked:
        logger.error("❌ BLOCK: Day locked - %s", lock_reason)
        return None
    
    if not risk_mgr.can_trade(symbol):
        logger.error("❌ BLOCK: Risk manager rejection")
        return None
    
    # Calculate SL/TP
    sl_tp = risk_mgr.calculate_sl_tp(direction, current_price, atr, trade_mode)
    
    if sl_tp["rr_ratio"] < config.MIN_RR_RATIO:
        logger.error("❌ BLOCK: R:R %.2f < %.2f", sl_tp["rr_ratio"], config.MIN_RR_RATIO)
        return None
    
    # Choppy mode TP adjustment
    if trade_mode == "CHOPPY":
        if direction == "LONG":
            sl_tp["take_profit"] = current_price + (atr * 1.2)
        else:
            sl_tp["take_profit"] = current_price - (atr * 1.2)
        sl_tp["rr_ratio"] = abs(sl_tp["take_profit"] - current_price) / abs(current_price - sl_tp["stop_loss"])
        logger.info("[ELITE] CHOPPY TP adjusted: ATR×1.2 = %.2f", sl_tp["take_profit"])
    
    position_check = risk_mgr.calculate_position(account_size, current_price, sl_tp["stop_loss"], atr_pct, fear_index)
    
    if position_check.get("blocked"):
        logger.error("❌ BLOCK: Position sizing - %s", position_check.get("reason"))
        return None
    
    logger.info("✅ RISK: Pre-check OK | RR %.2f | SL %.2f | TP %.2f",
               sl_tp["rr_ratio"], sl_tp["stop_loss"], sl_tp["take_profit"])
    
    # Apply filters
    filters_passed, filters_total, filters_details, mandatory_pass = filters.evaluate(
        direction=direction,
        ohlcv_15m=ohlcv_15m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        btc_ohlcv_1h=btc_ohlcv_1h,
        btc_ohlcv_4h=btc_ohlcv_4h,
        funding_rate=funding_rate,
        symbol=symbol,
        ema200_passed=engine_result.get("ema200_passed", False)
    )
    
    if filters_passed < market_config.get("min_filters", 2):
        logger.error("❌ BLOCK: Filters %d/%d passed, minimum %d required", 
                    filters_passed, filters_total, market_config.get("min_filters", 2))
        return None
    
    # Entry confirmation for choppy mode
    if config.ENTRY_CONFIRMATION_WAIT and trade_mode == "CHOPPY":
        logger.info("[STEP 6] ENTRY CONFIRMATION PENDING (CHOPPY MODE)")
        
        _pending_confirmations[symbol] = {
            "direction": direction,
            "entry_zone": current_price,
            "sl": sl_tp["stop_loss"],
            "tp": sl_tp["take_profit"],
            "rr": sl_tp["rr_ratio"],
            "score": score,
            "grade": grade,
            "filters_passed": filters_passed,
            "logic": engine_result["top_logic"],
            "mood": mood.get_mood(),
            "timestamp": datetime.now(),
            "candle_count": 0,
            "regime_mode": trade_mode,
            "atr_pct": atr_pct,
            "structure_strength": engine_result.get("structure_strength", "OK"),
            "fear_index": fear_index,
            "account_size": account_size,
            "mood_obj": mood,
            "atr": atr
        }
        
        return SignalResult(
            symbol=symbol,
            direction=direction,
            entry=current_price,
            stop_loss=sl_tp["stop_loss"],
            take_profit=sl_tp["take_profit"],
            rr_ratio=sl_tp["rr_ratio"],
            position_size=position_check,
            extreme_fear_score=score,
            extreme_fear_grade=grade,
            filters_passed=filters_passed,
            logic_triggered=engine_result["top_logic"],
            market_mood=mood.get_mood()["emoji"] + " " + mood.get_mood()["mood"],
            session_info=trade_mode,
            human_insight=f"⏳ PENDING: {trade_mode} mode",
            confirmation_pending=True,
            confirmation_price=current_price,
            regime_mode=trade_mode,
            atr_pct=atr_pct,
            structure_strength=engine_result.get("structure_strength", "OK")
        )
    
    if trade_mode == "TREND":
        logger.info("[STEP 6] IMMEDIATE EXECUTION (TREND MODE)")
    
    return _finalize_signal(
        symbol=symbol,
        direction=direction,
        entry=current_price,
        sl_tp=sl_tp,
        engine_result=engine_result,
        filters_passed=filters_passed,
        mood_data=mood.get_mood(),
        risk_mgr=risk_mgr,
        filters=filters,
        account_size=account_size,
        mood=mood,
        regime_mode=trade_mode,
        atr_pct=atr_pct,
        fear_index=fear_index,
        pre_validated_position=position_check
    )


def _check_confirmation(symbol: str, ohlcv: List[List[float]], 
                       risk_mgr: RiskManager, filters: SimpleFilters,
                       fear_index: int,
                       account_size: float,
                       mood: MarketMood) -> Optional[SignalResult]:
    
    global _pending_confirmations
    
    pending = _pending_confirmations.get(symbol)
    if not pending:
        return None
    
    current_price = ohlcv[-1][4]
    direction = pending["direction"]
    entry_zone = pending["entry_zone"]
    atr = pending.get("atr", _calculate_atr(ohlcv))
    
    pending["candle_count"] += 1
    
    logger.info("[CONFIRMATION] %s - Candle #%d", symbol, pending["candle_count"])
    
    confirmed = False
    
    # ATR-based confirmation
    if direction == "LONG":
        bullish_close = current_price > entry_zone + (atr * 0.2)
        higher_low = ohlcv[-1][3] > ohlcv[-2][3] if len(ohlcv) > 1 else False
        confirmed = bullish_close and higher_low
        logger.info("   Price: %.2f > Entry+%.2f | Bullish: %s | HL: %s",
                   current_price, atr * 0.2, bullish_close, higher_low)
    else:
        bearish_close = current_price < entry_zone - (atr * 0.2)
        lower_high = ohlcv[-1][2] < ohlcv[-2][2] if len(ohlcv) > 1 else False
        confirmed = bearish_close and lower_high
        logger.info("   Price: %.2f < Entry-%.2f | Bearish: %s | LH: %s",
                   current_price, atr * 0.2, bearish_close, lower_high)
    
    if confirmed:
        logger.info("✅ CONFIRMED after %d candles", pending["candle_count"])
        del _pending_confirmations[symbol]
        
        if atr <= 0:
            logger.error("❌ CONFIRMATION FAILED: ATR invalid (%.4f)", atr)
            return None
        
        sl_tp = risk_mgr.calculate_sl_tp(direction, current_price, atr, pending["regime_mode"])
        
        if pending["regime_mode"] == "CHOPPY":
            if direction == "LONG":
                sl_tp["take_profit"] = current_price + (atr * 1.2)
            else:
                sl_tp["take_profit"] = current_price - (atr * 1.2)
            sl_tp["rr_ratio"] = abs(sl_tp["take_profit"] - current_price) / abs(current_price - sl_tp["stop_loss"])
        
        return _finalize_signal(
            symbol=symbol,
            direction=direction,
            entry=current_price,
            sl_tp=sl_tp,
            engine_result={
                "score": pending["score"], 
                "grade": pending["grade"], 
                "top_logic": pending["logic"],
                "structure_strength": pending["structure_strength"]
            },
            filters_passed=pending["filters_passed"],
            mood_data=pending["mood"],
            risk_mgr=risk_mgr,
            filters=filters,
            account_size=pending["account_size"],
            mood=pending["mood_obj"],
            regime_mode=pending["regime_mode"],
            atr_pct=pending["atr_pct"],
            fear_index=pending["fear_index"],
            pre_validated_position=None
        )
    
    elif pending["candle_count"] >= 3:
        logger.warning("❌ CONFIRMATION FAILED: Max candles")
        del _pending_confirmations[symbol]
        return None
    
    else:
        logger.info("⏳ Waiting...")
        return None


def _finalize_signal(symbol, direction, entry, sl_tp, engine_result, 
                    filters_passed, mood_data, risk_mgr, filters, account_size, mood,
                    regime_mode, atr_pct, fear_index,
                    pre_validated_position: Optional[Dict] = None):
    
    if (pre_validated_position and 
        not pre_validated_position.get("blocked") and 
        abs(pre_validated_position.get("entry", entry) - entry) < 0.01):
        position = pre_validated_position
        logger.info("[RISK] Using pre-validated position sizing")
    else:
        position = risk_mgr.calculate_position(account_size, entry, sl_tp["stop_loss"], atr_pct, fear_index)
        logger.info("[RISK] Calculated fresh position sizing")
    
    if position.get("blocked"):
        logger.error("❌ BLOCK: Position sizing failed - %s", position.get("reason"))
        return None
    
    trade = Trade(
        symbol=symbol,
        direction=direction,
        entry=entry,
        stop_loss=sl_tp["stop_loss"],
        take_profit=sl_tp["take_profit"],
        size_usd=position.get("position_usd", 0),
        timestamp=datetime.now(),
        max_holding_minutes=60 if regime_mode == "CHOPPY" else 90
    )
    
    if not risk_mgr.open_trade(trade):
        return None
    
    filters.update_cooldown(symbol)
    
    insight = _build_insight(mood_data, engine_result, filters_passed, direction, regime_mode)
    
    logger.info("=" * 70)
    logger.info("✅ ELITE SIGNAL: %s %s @ %.2f | Mode: %s | Grade: %s | RR: %.2f | Size: $%.2f",
               symbol, direction, entry, regime_mode, engine_result["grade"],
               sl_tp["rr_ratio"], position.get("position_usd", 0))
    logger.info("=" * 70)
    
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
        market_mood=mood_data["emoji"] + " " + mood_data["mood"] if isinstance(mood_data, dict) else "Unknown",
        session_info=regime_mode,
        human_insight=insight,
        confirmation_pending=False,
        regime_mode=regime_mode,
        atr_pct=atr_pct,
        structure_strength=engine_result.get("structure_strength", "OK")
    )


def _build_insight(mood: Dict, engine: Dict, filters: int, direction: str, mode: str) -> str:
    lines = []
    
    if isinstance(mood, dict):
        if mood.get("mood") == "EXTREME_FEAR":
            lines.append("😱 ELITE_CAUTION")
        elif mood.get("mood") == "FEAR":
            lines.append("⚠️ SELECTIVE")
    
    lines.append(f"🎯 {mode}")
    lines.append(f"🏆 Grade: {engine.get('grade', 'A')}")
    lines.append(f"🧠 {', '.join(engine.get('top_logic', [])[:2])}")
    lines.append(f"{'🟢' if direction == 'LONG' else '🔴'} {direction}")
    
    return " | ".join(lines)


def _calculate_atr(ohlcv: List[List[float]], period: int = 14) -> float:
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