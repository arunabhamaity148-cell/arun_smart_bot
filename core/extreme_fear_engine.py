"""
ARUNABHA EXTREME FEAR ENGINE v3.0
Surgical execution with strict structure validation
UPDATED: OPTION 3 - Balanced approach
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

import config

logger = logging.getLogger(__name__)


@dataclass
class LogicResult:
    name: str
    passed: bool
    score: int
    message: str
    details: Dict[str, Any]


class ExtremeFearEngine:
    """
    Institutional-grade with strict structure confirmation.
    UPDATED: OPTION 3 - structure_weak হলে ব্লক না করে সতর্কতা
    """
    
    MIN_SCORE_TREND = 45      # A grade minimum
    MIN_SCORE_CHOPPY = 50     # Choppy mode needs higher score
    MIN_SCORE_WEAK = 20       # Absolute minimum (was 50)
    
    def __init__(self):
        self.max_score = 100
        self._last_regime_mode = "TREND"
    
    def evaluate(self, 
                 ohlcv_15m: List[List[float]],
                 ohlcv_5m: List[List[float]],
                 ohlcv_1h: List[List[float]],
                 btc_ohlcv_15m: List[List[float]],
                 funding_rate: float = 0,
                 fear_index: int = 50,
                 btc_trade_mode: str = "TREND") -> Dict[str, Any]:
        """
        Surgical execution with regime-aware scoring.
        """
        
        self._last_regime_mode = btc_trade_mode
        
        results = []
        current_price = ohlcv_15m[-1][4] if ohlcv_15m else 0
        
        # EMA200 Check
        ema200_result = self._ema200_strict(ohlcv_15m, current_price)
        results.append(ema200_result)
        
        # Structure Confirmation
        structure_result = self._structure_strict(ohlcv_15m)
        results.append(structure_result)
        
        # Other logic
        r1 = self._liquidity_sweep(ohlcv_15m)
        results.append(r1)
        
        r2 = self._rsi_capitulation(ohlcv_15m)
        results.append(r2)
        
        r3 = self._bear_trap(ohlcv_15m)
        results.append(r3)
        
        r4 = self._funding_flip(funding_rate)
        results.append(r4)
        
        r5 = self._demand_ob(ohlcv_15m, current_price)
        results.append(r5)
        
        r6 = self._mtf_divergence(ohlcv_5m, ohlcv_15m)
        results.append(r6)
        
        r7 = self._btc_calm_alt(ohlcv_15m, btc_ohlcv_15m)
        results.append(r7)
        
        r8 = self._session_reversal(ohlcv_5m)
        results.append(r8)
        
        # Calculate totals
        total_score = sum(r.score for r in results if r.passed)
        passed_count = sum(1 for r in results if r.passed)
        
        # Grade assignment
        grade = self._assign_grade(total_score, btc_trade_mode)
        
        # Check if structure is weak
        structure_weak = structure_result.details.get("strength") == "WEAK"
        
        # Determine if can trade based on ALL criteria
        can_trade = self._evaluate_trade_permission(
            total_score, grade, ema200_result.passed, 
            structure_result.passed, structure_weak, btc_trade_mode
        )
        
        logger.info(
            "[ENGINE] Score:%d | Grade:%s | Mode:%s | Struct:%s | Trade:%s",
            total_score, grade, btc_trade_mode,
            "WEAK" if structure_weak else "OK",
            "ALLOW" if can_trade else "BLOCK"
        )
        
        return {
            "score": total_score,
            "grade": grade,
            "passed_count": passed_count,
            "results": results,
            "can_trade": can_trade,
            "top_logic": [r.name for r in results if r.passed][:3],
            "ema200_passed": ema200_result.passed,
            "structure_passed": structure_result.passed,
            "structure_weak": structure_weak,
            "direction": structure_result.details.get("direction", "LONG"),
            "trade_mode": btc_trade_mode
        }
    
    def _assign_grade(self, score: int, mode: str) -> str:
        """Regime-aware grading - OPTION 3"""
        if mode == "CHOPPY":
            if score >= 70:
                return "A+"
            elif score >= 55:
                return "A"
            elif score >= 40:
                return "B"
            else:
                return "C"
        else:
            if score >= 65:
                return "A+"
            elif score >= 45:
                return "A"
            elif score >= 30:
                return "B"
            else:
                return "C"
    
    def _evaluate_trade_permission(self, score: int, grade: str, 
                                  ema200_ok: bool, structure_ok: bool,
                                  structure_weak: bool, mode: str) -> bool:
        """
        OPTION 3: structure_weak হলে ব্লক না করে সতর্কতা
        """
        # Hard minimums
        if score < self.MIN_SCORE_WEAK:
            return False
        
        if not ema200_ok or not structure_ok:
            return False
        
        # OPTION 3: structure_weak থাকলেও ট্রেড করতে দেবে, কিন্তু সতর্কতা দেবে
        if structure_weak and score < 20:
            # শুধু খুব খারাপ হলে ব্লক
            logger.warning("[ENGINE] Structure weak and score low - BLOCK")
            return False
        elif structure_weak:
            logger.warning("[ENGINE] Weak structure but score OK - allowing")
        
        # Mode-specific rules
        if mode == "CHOPPY":
            if score < self.MIN_SCORE_CHOPPY:
                return False
            if grade not in ["A", "A+", "B"]:
                return False
        else:  # TREND mode
            if grade == "C" and score < 25:
                return False
        
        return True
    
    def _ema200_strict(self, ohlcv: List[List[float]], current_price: float) -> LogicResult:
        """EMA200 validation."""
        if len(ohlcv) < 50:  # 200 থেকে কমিয়ে 50
            return LogicResult("EMA200", True, 10, "Limited data - allowing", {})
        
        closes = [c[4] for c in ohlcv]
        ema200 = self._calculate_ema(closes, 200)
        
        distance_pct = abs(current_price - ema200) / ema200 * 100
        is_bullish = current_price > ema200
        is_close = distance_pct < 5.0  # 2% থেকে বাড়িয়ে 5%
        
        passed = is_bullish or is_close
        
        return LogicResult(
            "EMA200",
            passed,
            15 if passed else 5,
            f"EMA200:{ema200:.2f} Dist:{distance_pct:.2f}%" if passed else f"Far from EMA200: {distance_pct:.2f}%",
            {"ema200": ema200, "distance_pct": distance_pct, "bullish": is_bullish}
        )
    
    def _calculate_ema(self, values: List[float], period: int) -> float:
        """Proper EMA."""
        if len(values) < period:
            return sum(values) / len(values)
        
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        
        for v in values[period:]:
            ema = v * k + ema * (1 - k)
        
        return ema
    
    def _structure_strict(self, ohlcv: List[List[float]]) -> LogicResult:
        """
        STRICT Structure Confirmation - OPTION 3
        """
        if len(ohlcv) < 10:  # 20 থেকে কমিয়ে 10
            return LogicResult("Structure", True, 10, "Limited data - allowing", {"strength": "OK", "direction": "LONG"})
        
        highs = [c[2] for c in ohlcv[-15:]]  # 20 থেকে কমিয়ে 15
        lows = [c[3] for c in ohlcv[-15:]]
        closes = [c[4] for c in ohlcv[-15:]]
        opens = [c[1] for c in ohlcv[-15:]]
        
        # Find swing points
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(highs)-2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))
        
        if len(swing_highs) < 1 or len(swing_lows) < 1:
            return LogicResult("Structure", True, 10, "Simple trend", {"strength": "OK", "direction": "LONG"})
        
        recent_hh = [h for _, h in swing_highs[-2:]]
        recent_ll = [l for _, l in swing_lows[-2:]]
        
        last_swing_high = max(recent_hh) if recent_hh else 0
        last_swing_low = min(recent_ll) if recent_ll else 0
        
        current_close = closes[-1]
        prev_close = closes[-2]
        current_open = opens[-1]
        
        # BOS detection
        bullish_bos = (
            current_close > last_swing_high and 
            prev_close <= last_swing_high
        )
        
        bearish_bos = (
            current_close < last_swing_low and 
            prev_close >= last_swing_low
        )
        
        # Determine strength
        if bullish_bos or bearish_bos:
            strength = "STRONG"
            passed = True
            direction = "LONG" if bullish_bos else "SHORT"
            msg = f"{'BULLISH' if bullish_bos else 'BEARISH'} BOS"
        else:
            # Check simple trend
            if closes[-1] > closes[-5]:
                strength = "WEAK"
                passed = True
                direction = "LONG"
                msg = "Weak uptrend"
            elif closes[-1] < closes[-5]:
                strength = "WEAK"
                passed = True
                direction = "SHORT"
                msg = "Weak downtrend"
            else:
                strength = "WEAK"
                passed = True  # OPTION 3: passed = True
                direction = "LONG"
                msg = "No clear structure - allowing"
        
        return LogicResult(
            "Structure",
            passed,
            15 if passed else 5,
            msg,
            {
                "direction": direction,
                "strength": strength,
                "level": last_swing_high if direction == "LONG" else last_swing_low,
                "hh": last_swing_high,
                "ll": last_swing_low
            }
        )
    
    def _liquidity_sweep(self, ohlcv: List[List[float]]) -> LogicResult:
        """Liquidity sweep detection."""
        if len(ohlcv) < 5:
            return LogicResult("Liquidity Sweep", False, 0, "No data", {})
        
        lows = [c[3] for c in ohlcv[-8:]]
        closes = [c[4] for c in ohlcv[-8:]]
        
        recent_low = min(lows[-3:])
        prev_low = min(lows[-6:-3]) if len(lows) >= 6 else lows[0]
        
        sweep = recent_low < prev_low * 0.98
        reclaim = closes[-1] > prev_low
        
        passed = sweep and reclaim
        
        return LogicResult(
            "Liquidity Sweep",
            passed,
            10 if passed else 0,
            "Sweep + Reclaim" if passed else "No sweep",
            {"sweep": sweep, "reclaim": reclaim}
        )
    
    def _rsi_capitulation(self, ohlcv: List[List[float]]) -> LogicResult:
        """RSI capitulation."""
        if len(ohlcv) < 10:
            return LogicResult("RSI Capitulation", False, 0, "No data", {})
        
        closes = [c[4] for c in ohlcv[-14:]]
        rsi = self._calculate_rsi(closes, 7)
        
        extreme_rsi = rsi < 25
        passed = extreme_rsi
        
        return LogicResult(
            "RSI Capitulation",
            passed,
            10 if passed else 0,
            f"RSI {rsi:.1f}" if passed else f"RSI {rsi:.1f}",
            {"rsi": rsi}
        )
    
    def _calculate_rsi(self, closes: List[float], period: int = 7) -> float:
        """RSI calculation."""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period-1) + gains[i]) / period
            avg_loss = (avg_loss * (period-1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100.0
        return 100 - (100 / (1 + avg_gain / avg_loss))
    
    def _bear_trap(self, ohlcv: List[List[float]]) -> LogicResult:
        """Bear trap pattern."""
        if len(ohlcv) < 3:
            return LogicResult("Bear Trap", False, 0, "No data", {})
        
        c1, c2, c3 = ohlcv[-3], ohlcv[-2], ohlcv[-1]
        
        c1_bearish = c1[4] < c1[1]
        c1_body = abs(c1[4] - c1[1])
        c2_body = abs(c2[4] - c2[1])
        c2_small = c2_body < c1_body * 0.6
        c3_bullish = c3[4] > c3[1]
        
        passed = c1_bearish and c2_small and c3_bullish
        
        return LogicResult("Bear Trap", passed, 8 if passed else 0, "Bear trap" if passed else "No trap", {})
    
    def _funding_flip(self, funding_rate: float) -> LogicResult:
        """Funding extreme."""
        extreme = funding_rate < -0.0005 or funding_rate > 0.0005
        return LogicResult("Funding Extreme", extreme, 5 if extreme else 0, f"Funding {funding_rate*100:.3f}%", {"funding": funding_rate})
    
    def _demand_ob(self, ohlcv: List[List[float]], current_price: float) -> LogicResult:
        """Demand order block."""
        if len(ohlcv) < 10:
            return LogicResult("Demand OB", False, 0, "No data", {})
        
        for i in range(len(ohlcv)-5, 2, -1):
            c1, c2, c3 = ohlcv[i], ohlcv[i+1], ohlcv[i+2]
            
            if c1[4] > c1[1] and c2[4] > c2[1]:
                zone_low = min(c1[3], c2[3])
                zone_high = max(c1[1], c2[1])
                
                in_zone = zone_low * 0.99 <= current_price <= zone_high * 1.01
                
                if in_zone:
                    return LogicResult("Demand OB", True, 8, f"OB Retest", {"zone": [zone_low, zone_high]})
        
        return LogicResult("Demand OB", False, 0, "No OB retest", {})
    
    def _mtf_divergence(self, ohlcv_5m: List[List[float]], ohlcv_15m: List[List[float]]) -> LogicResult:
        """Multi-timeframe divergence."""
        if len(ohlcv_5m) < 10 or len(ohlcv_15m) < 10:
            return LogicResult("MTF Divergence", False, 0, "No data", {})
        
        closes_15m = [c[4] for c in ohlcv_15m[-10:]]
        
        if len(closes_15m) < 5:
            return LogicResult("MTF Divergence", False, 0, "RSI failed", {})
        
        div_15m = closes_15m[-1] < closes_15m[-5] and closes_15m[-1] > closes_15m[-3]
        
        return LogicResult("MTF Divergence", div_15m, 8 if div_15m else 0, "15m div" if div_15m else "No divergence", {})
    
    def _btc_calm_alt(self, ohlcv_alt: List[List[float]], ohlcv_btc: List[List[float]]) -> LogicResult:
        """BTC calm + alt strength."""
        if len(ohlcv_alt) < 5 or len(ohlcv_btc) < 5:
            return LogicResult("BTC Calm", False, 0, "No data", {})
        
        alt_change = (ohlcv_alt[-1][4] - ohlcv_alt[-5][4]) / ohlcv_alt[-5][4] * 100
        btc_change = (ohlcv_btc[-1][4] - ohlcv_btc[-5][4]) / ohlcv_btc[-5][4] * 100
        alt_strong = alt_change > btc_change + 0.5
        
        return LogicResult("BTC Calm + Alt Strong", alt_strong, 5 if alt_strong else 0, f"Alt {alt_change:.2f}% vs BTC {btc_change:.2f}%", {"alt_change": alt_change, "btc_change": btc_change})
    
    def _session_reversal(self, ohlcv_5m: List[List[float]]) -> LogicResult:
        """Session reversal."""
        from datetime import datetime
        import pytz
        
        now = datetime.now(pytz.UTC).astimezone(pytz.timezone('Asia/Kolkata'))
        hour = now.hour
        
        in_session = (6 <= hour <= 22)  # সব সেশন
        
        if not in_session:
            return LogicResult("Session Reversal", False, 0, "Not session time", {})
        
        if len(ohlcv_5m) < 2:
            return LogicResult("Session Reversal", False, 0, "No data", {})
        
        last = ohlcv_5m[-1]
        open_p, close = last[1], last[4]
        
        body = abs(close - open_p)
        
        if close > open_p:
            passed = body > 0
            msg = "Bullish"
        else:
            passed = body > 0
            msg = "Bearish"
        
        return LogicResult("Session Reversal", passed, 5 if passed else 0, msg, {})


# Global instance
extreme_fear_engine = ExtremeFearEngine()