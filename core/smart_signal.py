"""
ARUNABHA SMART SIGNAL v3.0
Surgical execution with strict order priority
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
    # 🆕 Enhanced tracking
    regime_mode: str = ""
    atr_pct: float = 0.0
    structure_strength: str = ""


# Global pending confirmations
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
    """
    🆕 ISSUE VI: STRICT EXECUTION ORDER PRIORITY
    
    1. Regime Check (Gatekeeper)
    2. Volatility Check  
    3. Structure Confirmation
    4. Score Validation
    5. Risk Manager Approval
    6. Order Placement
    """
    
    global _pending_confirmations
    
    logger.info("=" * 70)
    logger.info("[SURGICAL] SCAN START: %s", symbol)
    logger.info("=" * 70)
    
    # 🆕 GUARD: Check pending confirmations first
    if symbol in _pending_confirmations:
        return _check_confirmation(symbol, ohlcv_15m, risk_mgr, filters)
    
    # 🆕 GUARD: Validate BTC data availability (minimum 50 candles for basic analysis)
    if not btc_ohlcv_15m or len(btc_ohlcv_15m) < 50:
        logger.error("❌ BLOCK: Insufficient BTC 15m data (need 50, got %s)", 
                    len(btc_ohlcv_15m) if btc_ohlcv_15m else 0)
        return None
    
    if not btc_ohlcv_1h or len(btc_ohlcv_1h) < 20:
        logger.error("❌ BLOCK: Insufficient BTC 1h data (need 20, got %s)",
                    len(btc_ohlcv_1h) if btc_ohlcv_1h else 0)
        return None
        
    if not btc_ohlcv_4h or len(btc_ohlcv_4h) < 20:
        logger.error("❌ BLOCK: Insufficient BTC 4h data (need 20, got %s)",
                    len(btc_ohlcv_4h) if btc_ohlcv_4h else 0)
        return None
    
    # ═════════════════════════════════════════════════════════════════
    # STEP 1: REGIME CHECK (Issue I - Non-negotiable gatekeeper)
    # ═════════════════════════════════════════════════════════════════
    logger.info("[STEP 1] REGIME GATEKEEPER")
    
    # Analyze BTC regime
    regime_analysis = btc_detector.analyze(btc_ohlcv_15m, btc_ohlcv_1h, btc_ohlcv_4h)
    
    # Hard block if regime says no
    if not regime_analysis.can_trade:
        logger.error("❌ BLOCK: Regime gate - %s", regime_analysis.block_reason)
        return None
    
    trade_mode = regime_analysis.trade_mode  # "TREND" or "RANGE"
    
    logger.info("✅ REGIME: %s | Mode: %s | Conf: %d%% | Consistency: %s",
               regime_analysis.regime.value, trade_mode,
               regime_analysis.confidence, regime_analysis.consistency)
    
    # ═════════════════════════════════════════════════════════════════
    # STEP 2: VOLATILITY CHECK (Issue IV - Before structure)
    # ═════════════════════════════════════════════════════════════════
    logger.info("[STEP 2] VOLATILITY COMPRESSION")
    
    atr = _calculate_atr(ohlcv_15m)
    current_price = ohlcv_15m[-1][4]
    atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
    
    logger.info("   ATR%%: %.2f", atr_pct)
    
    # Hard block if ATR > 3%
    if atr_pct > 3.0:
        logger.error("❌ BLOCK: ATR %.2f%% > 3%% (extreme volatility)", atr_pct)
        return None
    
    # Warning for elevated
    if 2.0 <= atr_pct <= 3.0:
        logger.warning("   ⚠️ ELEVATED: ATR %.2f%% - Position will be reduced 50%%", atr_pct)
    
    # Warning for low
    if atr_pct < 0.4:
        logger.warning("   ⚠️ LOW: ATR %.2f%% - Breakout trades avoided", atr_pct)
    
    logger.info("✅ VOLATILITY: OK")
    
    # ═════════════════════════════════════════════════════════════════
    # STEP 3: STRUCTURE CONFIRMATION (Issue II - Mandatory)
    # ═════════════════════════════════════════════════════════════════
    logger.info("[STEP 3] STRUCTURE CONFIRMATION")
    
    # Get structure from engine
    engine_result = engine.evaluate(
        ohlcv_15m=ohlcv_15m,
        ohlcv_5m=ohlcv_5m,
        ohlcv_1h=ohlcv_1h,
        btc_ohlcv_15m=btc_ohlcv_15m,
        funding_rate=funding_rate,
        fear_index=fear_index,
        btc_trade_mode=trade_mode
    )
    
    # Check structure first (before score)
    if not engine_result["structure_passed"]:
        logger.error("❌ BLOCK: Structure not confirmed")
        return None
    
    if engine_result.get("structure_weak"):
        logger.error("❌ BLOCK: Structure weak - no BOS/CHoCH")
        return None
    
    direction = engine_result["direction"]
    
    # Validate direction matches regime
    if trade_mode == "TREND":
        if regime_analysis.regime in [BTCRegime.STRONG_BULL, BTCRegime.BULL] and direction != "LONG":
            logger.error("❌ BLOCK: Direction mismatch - BTC bull but SHORT signal")
            return None
        if regime_analysis.regime in [BTCRegime.STRONG_BEAR, BTCRegime.BEAR] and direction != "SHORT":
            logger.error("❌ BLOCK: Direction mismatch - BTC bear but LONG signal")
            return None
    
    logger.info("✅ STRUCTURE: %s | Direction: %s", 
               engine_result.get("structure_strength", "OK"), direction)
    
    # ═════════════════════════════════════════════════════════════════
    # STEP 4: SCORE VALIDATION (Issue III - Strict discipline)
    # ═════════════════════════════════════════════════════════════════
    logger.info("[STEP 4] SCORE VALIDATION")
    
    score = engine_result["score"]
    grade = engine_result["grade"]
    
    logger.info("   Score: %d | Grade: %s | Mode: %s", score, grade, trade_mode)
    
    # Mode-specific minimums
    if trade_mode == "CHOPPY":
        min_score = 60  # Higher bar for choppy
        allowed_grades = ["A", "A+"]
    else:
        min_score = 50
        allowed_grades = ["A", "A+", "B"]  # B allowed but warned
    
    if score < min_score:
        logger.error("❌ BLOCK: Score %d < minimum %d for %s mode", score, min_score, trade_mode)
        return None
    
    if grade not in allowed_grades:
        logger.error("❌ BLOCK: Grade %s not in allowed %s", grade, allowed_grades)
        return None
    
    if grade == "B":
        logger.warning("   ⚠️ Grade B - Marginal trade in trend mode")
    
    logger.info("✅ SCORE: OK")
    
    # ═════════════════════════════════════════════════════════════════
    # STEP 5: RISK MANAGER APPROVAL (Issue V - Capital protection)
    # ═════════════════════════════════════════════════════════════════
    logger.info("[STEP 5] RISK MANAGER")
    
    # Check day lock
    is_locked, lock_reason = risk_mgr.check_day_lock()
    if is_locked:
        logger.error("❌ BLOCK: Day locked - %s", lock_reason)
        return None
    
    if not risk_mgr.can_trade(symbol):
        logger.error("❌ BLOCK: Risk manager rejection")
        return None
    
    # Calculate SL/TP with mode adjustment
    sl_tp = risk_mgr.calculate_sl_tp(direction, current_price, atr, trade_mode)
    
    # Check RR
    if sl_tp["rr_ratio"] < config.MIN_RR_RATIO:
        logger.error("❌ BLOCK: R:R %.2f < %.2f", sl_tp["rr_ratio"], config.MIN_RR_RATIO)
        return None
    
    # Calculate position with volatility adjustment
    position = risk_mgr.calculate_position(account_size, current_price, sl_tp["stop_loss"], atr_pct)
    
    if position.get("blocked"):
        logger.error("❌ BLOCK: Position sizing - %s", position.get("reason"))
        return None
    
    logger.info("✅ RISK: Position $%.2f | RR %.2f | SL %.2f | TP %.2f",
               position.get("position_usd", 0), sl_tp["rr_ratio"],
               sl_tp["stop_loss"], sl_tp["take_profit"])
    
    # ═════════════════════════════════════════════════════════════════
    # STEP 6: ENTRY CONFIRMATION (If enabled)
    # ═════════════════════════════════════════════════════════════════
    if config.ENTRY_CONFIRMATION_WAIT:
        logger.info("[STEP 6] ENTRY CONFIRMATION PENDING")
        
        _pending_confirmations[symbol] = {
            "direction": direction,
            "entry_zone": current_price,
            "sl": sl_tp["stop_loss"],
            "tp": sl_tp["take_profit"],
            "rr": sl_tp["rr_ratio"],
            "score": score,
            "grade": grade,
            "filters_passed": 0,  # Will check after confirmation
            "logic": engine_result["top_logic"],
            "mood": mood.get_mood(),
            "timestamp": datetime.now(),
            "candle_count": 0,
            "regime_mode": trade_mode,
            "atr_pct": atr_pct,
            "structure_strength": engine_result.get("structure_strength", "OK")
        }
        
        return SignalResult(
            symbol=symbol,
            direction=direction,
            entry=current_price,
            stop_loss=sl_tp["stop_loss"],
            take_profit=sl_tp["take_profit"],
            rr_ratio=sl_tp["rr_ratio"],
            position_size=position,
            extreme_fear_score=score,
            extreme_fear_grade=grade,
            filters_passed=6,  # Passed regime, vol, structure, score, risk
            logic_triggered=engine_result["top_logic"],
            market_mood=mood.get_mood()["emoji"] + " " + mood.get_mood()["mood"],
            session_info=trade_mode,
            human_insight=f"⏳ PENDING: {trade_mode} mode | Structure: {engine_result.get('structure_strength', 'OK')}",
            confirmation_pending=True,
            confirmation_price=current_price,
            regime_mode=trade_mode,
            atr_pct=atr_pct,
            structure_strength=engine_result.get("structure_strength", "OK")
        )
    
    # Immediate execution (no confirmation wait)
    return _finalize_signal(
        symbol, direction, current_price, sl_tp, engine_result,
        6, mood.get_mood(), risk_mgr, filters, account_size, mood,
        trade_mode, atr_pct
    )


def _check_confirmation(symbol: str, ohlcv: List[List[float]], 
                       risk_mgr: RiskManager, filters: SimpleFilters) -> Optional[SignalResult]:
    """Check entry confirmation criteria."""
    global _pending_confirmations
    
    pending = _pending_confirmations.get(symbol)
    if not pending:
        return None
    
    current_price = ohlcv[-1][4]
    direction = pending["direction"]
    entry_zone = pending["entry_zone"]
    
    pending["candle_count"] += 1
    
    logger.info("[CONFIRMATION] %s - Candle #%d", symbol, pending["candle_count"])
    
    confirmed = False
    
    if direction == "LONG":
        bullish_close = current_price > entry_zone * 1.001
        higher_low = ohlcv[-1][3] > ohlcv[-2][3] if len(ohlcv) > 1 else False
        confirmed = bullish_close and higher_low
        logger.info("   Price: %.2f > Entry: %.2f | Bullish: %s | HL: %s",
                   current_price, entry_zone, bullish_close, higher_low)
    else:
        bearish_close = current_price < entry_zone * 0.999
        lower_high = ohlcv[-1][2] < ohlcv[-2][2] if len(ohlcv) > 1 else False
        confirmed = bearish_close and lower_high
        logger.info("   Price: %.2f < Entry: %.2f | Bearish: %s | LH: %s",
                   current_price, entry_zone, bearish_close, lower_high)
    
    if confirmed:
        logger.info("✅ CONFIRMED after %d candles", pending["candle_count"])
        del _pending_confirmations[symbol]
        
        # Recalculate with new price
        atr = _calculate_atr(ohlcv)
        sl_tp = risk_mgr.calculate_sl_tp(direction, current_price, atr, pending["regime_mode"])
        
        return _finalize_signal(
            symbol, direction, current_price, sl_tp,
            {"score": pending["score"], "grade": pending["grade"], "top_logic": pending["logic"]},
            6, pending["mood"], risk_mgr, filters, 1000, None,
            pending["regime_mode"], pending["atr_pct"]
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
                    regime_mode, atr_pct):
    """Finalize signal with all protections."""
    
    position = risk_mgr.calculate_position(account_size, entry, sl_tp["stop_loss"], atr_pct)
    
    trade = Trade(
        symbol=symbol,
        direction=direction,
        entry=entry,
        stop_loss=sl_tp["stop_loss"],
        take_profit=sl_tp["take_profit"],
        size_usd=position.get("position_usd", 0),
        timestamp=datetime.now(),
        max_holding_minutes=60 if regime_mode == "CHOPPY" else 90  # Shorter in choppy
    )
    
    if not risk_mgr.open_trade(trade):
        return None
    
    filters.update_cooldown(symbol)
    
    insight = _build_insight(mood_data, engine_result, filters_passed, direction, regime_mode)
    
    logger.info("=" * 70)
    logger.info("✅ SIGNAL: %s %s @ %.2f | Mode: %s | Score: %d | RR: %.2f",
               symbol, direction, entry, regime_mode, 
               engine_result["score"], sl_tp["rr_ratio"])
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
    """Build insight string."""
    lines = []
    
    if isinstance(mood, dict):
        if mood.get("mood") == "EXTREME_FEAR":
            lines.append("😱 EXTREME FEAR")
        elif mood.get("mood") == "FEAR":
            lines.append("⚠️ FEAR")
    
    lines.append(f"🎯 Mode: {mode}")
    lines.append(f"🧠 {', '.join(engine.get('top_logic', [])[:2])}")
    lines.append(f"{'🟢' if direction == 'LONG' else '🔴'} {direction}")
    
    return " | ".join(lines)


def _calculate_atr(ohlcv: List[List[float]], period: int = 14) -> float:
    """Calculate ATR."""
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
