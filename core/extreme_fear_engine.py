"""
ARUNABHA EXTREME FEAR ENGINE v2.0
Strict EMA200 + Structure Shift confirmation
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional
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
    Strict version:
    - EMA200 mandatory
    - Structure shift required
    - Min score 50
    """
    
    def __init__(self):
        self.min_score = config.MIN_SCORE_TO_TRADE  # 50
        self.max_score = 100
        
    def evaluate(self, 
                 ohlcv_15m: List[List[float]],
                 ohlcv_5m: List[List[float]],
                 ohlcv_1h: List[List[float]],
                 btc_ohlcv_15m: List[List[float]],
                 funding_rate: float = 0,
                 fear_index: int = 50) -> Dict[str, Any]:
        """
        Run all logic with strict filters
        """
        results = []
        current_price = ohlcv_15m[-1][4] if ohlcv_15m else 0
        
        # 🆕 CRITICAL: EMA200 Check (Mandatory)
        ema200_result = self._ema200_strict(ohlcv_15m, current_price)
        results.append(ema200_result)
        
        # 🆕 CRITICAL: Structure Shift (BOS/CHoCH)
        structure_result = self._structure_shift(ohlcv_15m)
        results.append(structure_result)
        
        # Logic 1: Liquidity Sweep + Reclaim
        r1 = self._liquidity_sweep(ohlcv_15m)
        results.append(r1)
        
        # Logic 2: RSI Capitulation + Volume
        r2 = self._rsi_capitulation(ohlcv_15m)
        results.append(r2)
        
        # Logic 3: Bear Trap Pattern
        r3 = self._bear_trap(ohlcv_15m)
        results.append(r3)
        
        # Logic 4: Funding Extreme Flip
        r4 = self._funding_flip(funding_rate)
        results.append(r4)
        
        # Logic 5: Demand OB Retest
        r5 = self._demand_ob(ohlcv_15m, current_price)
        results.append(r5)
        
        # Logic 6: MTF Divergence
        r6 = self._mtf_divergence(ohlcv_5m, ohlcv_15m)
        results.append(r6)
        
        # Logic 7: BTC Calm + Alt Strength
        r7 = self._btc_calm_alt(ohlcv_15m, btc_ohlcv_15m)
        results.append(r7)
        
        # Logic 8: Session Volatility Reversal
        r8 = self._session_reversal(ohlcv_5m)
        results.append(r8)
        
        # Calculate total
        total_score = sum(r.score for r in results if r.passed)
        passed_count = sum(1 for r in results if r.passed)
        
        # 🆕 STRICT: Must pass EMA200 and Structure
        can_trade = (
            total_score >= self.min_score and 
            ema200_result.passed and 
            structure_result.passed
        )
        
        # Determine grade
        if total_score >= 70:
            grade = "A+"
        elif total_score >= 55:
            grade = "A"
        elif total_score >= 40:
            grade = "B"
        else:
            grade = "C"
            
        logger.info(
            "Extreme Fear Score: %d/100 | Grade: %s | Can Trade: %s | EMA200: %s | Structure: %s",
            total_score, grade, can_trade, ema200_result.passed, structure_result.passed
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
            "direction": structure_result.details.get("direction", "LONG")
        }
    
    def _ema200_strict(self, ohlcv: List[List[float]], current_price: float) -> LogicResult:
        """🆕 MANDATORY: Price must be above EMA200 for LONG, below for SHORT consideration"""
        if len(ohlcv) < 50:
            return LogicResult("EMA200", False, 0, "Insufficient data", {})
            
        closes = [c[4] for c in ohlcv]
        ema200 = self._calculate_ema(closes, 200)
        
        # For extreme fear, we want price near or above EMA200 (reclaim)
        # Or strong rejection from below
        distance_pct = abs(current_price - ema200) / ema200 * 100
        
        # Bullish: Price above EMA200 or reclaiming
        # Bearish: Price below EMA200
        is_bullish = current_price > ema200
        is_close = distance_pct < 2.0  # Within 2%
        
        # In extreme fear, we accept price near EMA200 (potential bounce)
        passed = is_bullish or is_close
        
        return LogicResult(
            "EMA200",
            passed,
            25 if passed else 0,
            f"📈 EMA200: {ema200:.2f}, Price: {current_price:.2f} ({distance_pct:.2f}%)" if passed else f"❌ Far from EMA200: {distance_pct:.2f}%",
            {"ema200": ema200, "distance_pct": distance_pct, "bullish": is_bullish}
        )
    
    def _structure_shift(self, ohlcv: List[List[float]]) -> LogicResult:
        """🆕 MANDATORY: Market Structure Break (BOS) or Change of Character (CHoCH)"""
        if len(ohlcv) < 20:
            return LogicResult("Structure Shift", False, 0, "No data", {})
            
        highs = [c[2] for c in ohlcv[-20:]]
        lows = [c[3] for c in ohlcv[-20:]]
        closes = [c[4] for c in ohlcv[-20:]]
        
        # Find swing highs and lows
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(highs)-2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return LogicResult("Structure Shift", False, 0, "No clear swings", {})
        
        # Check for BOS (Break of Structure) - Bullish
        # Last higher high broken
        recent_highs = [h for _, h in swing_highs[-3:]]
        recent_lows = [l for _, l in swing_lows[-3:]]
        
        last_swing_high = max(recent_highs) if recent_highs else 0
        last_swing_low = min(recent_lows) if recent_lows else 0
        
        current_close = closes[-1]
        prev_close = closes[-2]
        
        # Bullish BOS: Close above last swing high
        bullish_bos = current_close > last_swing_high and prev_close <= last_swing_high
        
        # Bearish BOS: Close below last swing low  
        bearish_bos = current_close < last_swing_low and prev_close >= last_swing_low
        
        # CHoCH (Change of Character): Higher low formed after downtrend
        # Or Lower high formed after uptrend
        higher_low = recent_lows[-1] > recent_lows[-2] if len(recent_lows) >= 2 else False
        lower_high = recent_highs[-1] < recent_highs[-2] if len(recent_highs) >= 2 else False
        
        choch_bullish = higher_low and current_close > last_swing_high * 0.995
        choch_bearish = lower_high and current_close < last_swing_low * 1.005
        
        if bullish_bos or choch_bullish:
            return LogicResult(
                "Structure Shift",
                True,
                30,
                f"🔄 BULLISH BOS/CHoCH: HH {last_swing_high:.2f} broken" if bullish_bos else "🔄 CHoCH: Higher Low formed",
                {"direction": "LONG", "type": "BOS" if bullish_bos else "CHoCH", "level": last_swing_high}
            )
        elif bearish_bos or choch_bearish:
            return LogicResult(
                "Structure Shift",
                True,
                30,
                f"🔄 BEARISH BOS/CHoCH: LL {last_swing_low:.2f} broken" if bearish_bos else "🔄 CHoCH: Lower High formed",
                {"direction": "SHORT", "type": "BOS" if bearish_bos else "CHoCH", "level": last_swing_low}
            )
        
        return LogicResult(
            "Structure Shift",
            False,
            0,
            f"❌ No BOS/CHoCH | Last HH: {last_swing_high:.2f}, LL: {last_swing_low:.2f}",
            {"last_hh": last_swing_high, "last_ll": last_swing_low}
        )
    
    def _liquidity_sweep(self, ohlcv: List[List[float]]) -> LogicResult:
        """Logic: Break support + reclaim + strong close"""
        if len(ohlcv) < 10:
            return LogicResult("Liquidity Sweep", False, 0, "No data", {})
            
        lows = [c[3] for c in ohlcv[-10:]]
        closes = [c[4] for c in ohlcv[-10:]]
        highs = [c[2] for c in ohlcv[-10:]]
        
        recent_low = min(lows[-3:])
        prev_low = min(lows[-6:-3]) if len(lows) >= 6 else lows[0]
        
        sweep = recent_low < prev_low * (1 - config.LIQUIDITY_SWEEP_PCT/100)
        reclaim = closes[-1] > prev_low
        
        last_high = highs[-1]
        last_low = lows[-1]
        last_close = closes[-1]
        candle_range = last_high - last_low
        strong = (last_close - last_low) > (candle_range * 0.5) if candle_range > 0 else False
        
        passed = sweep and reclaim and strong
        
        return LogicResult(
            "Liquidity Sweep",
            passed,
            20 if passed else 0,
            "💧 Sweep + Reclaim" if passed else "No sweep",
            {"sweep": sweep, "reclaim": reclaim, "strong": strong}
        )
    
    def _rsi_capitulation(self, ohlcv: List[List[float]]) -> LogicResult:
        """Logic: RSI < 30 + volume spike + long lower wick"""
        if len(ohlcv) < 20:
            return LogicResult("RSI Capitulation", False, 0, "No data", {})
            
        closes = [c[4] for c in ohlcv[-20:]]
        volumes = [c[5] for c in ohlcv[-20:]]
        
        rsi = self._calculate_rsi(closes, 14)
        avg_vol = sum(volumes[-10:-1]) / 9
        last_vol = volumes[-1]
        vol_spike = last_vol > avg_vol * config.EXTREME_FEAR_VOLUME_MULT
        
        last = ohlcv[-1]
        open_p, high, low, close = last[1:5]
        body = abs(close - open_p)
        lower_wick = min(open_p, close) - low
        long_wick = lower_wick > body * config.BEAR_TRAP_WICK_MULT
        
        extreme_rsi = rsi < config.EXTREME_FEAR_RSI
        passed = extreme_rsi and vol_spike and long_wick
        
        return LogicResult(
            "RSI Capitulation",
            passed,
            20 if passed else 0,
            f"📉 RSI {rsi:.1f} + Vol {last_vol/avg_vol:.1f}x" if passed else f"RSI {rsi:.1f}",
            {"rsi": rsi, "vol_ratio": last_vol/avg_vol if avg_vol > 0 else 0}
        )
    
    def _bear_trap(self, ohlcv: List[List[float]]) -> LogicResult:
        """Logic: Fake breakdown + shorts trapped + reversal"""
        if len(ohlcv) < 5:
            return LogicResult("Bear Trap", False, 0, "No data", {})
            
        c1, c2, c3 = ohlcv[-3], ohlcv[-2], ohlcv[-1]
        
        c1_bearish = c1[4] < c1[1]
        c1_body = abs(c1[4] - c1[1])
        c2_body = abs(c2[4] - c2[1])
        c2_small = c2_body < c1_body * 0.5
        c3_bullish = c3[4] > c3[1]
        c3_strong = c3[4] > c1[1]
        
        passed = c1_bearish and c2_small and c3_bullish and c3_strong
        
        return LogicResult(
            "Bear Trap",
            passed,
            15 if passed else 0,
            "🪤 Bear trap" if passed else "No trap",
            {}
        )
    
    def _funding_flip(self, funding_rate: float) -> LogicResult:
        """Logic: Extreme negative funding"""
        extreme = funding_rate < config.FUNDING_EXTREME
        
        return LogicResult(
            "Funding Extreme",
            extreme,
            10 if extreme else 0,
            f"💸 Funding {funding_rate*100:.3f}%" if extreme else f"Funding {funding_rate*100:.3f}%",
            {"funding": funding_rate}
        )
    
    def _demand_ob(self, ohlcv: List[List[float]], current_price: float) -> LogicResult:
        """Logic: Strong impulse origin zone retest"""
        if len(ohlcv) < 20:
            return LogicResult("Demand OB", False, 0, "No data", {})
            
        for i in range(len(ohlcv)-5, 2, -1):
            c1, c2, c3 = ohlcv[i], ohlcv[i+1], ohlcv[i+2]
            
            if c1[4] > c1[1] and c2[4] > c2[1] and c3[4] > c3[1]:
                zone_low = min(c1[3], c2[3], c3[3])
                zone_high = max(c1[1], c2[1], c3[1])
                
                in_zone = zone_low * 0.995 <= current_price <= zone_high * 1.005
                bounced = ohlcv[-1][4] > ohlcv[-1][1]
                
                if in_zone and bounced:
                    return LogicResult(
                        "Demand OB",
                        True,
                        15,
                        f"📦 OB Retest {zone_low:.2f}-{zone_high:.2f}",
                        {"zone": [zone_low, zone_high]}
                    )
        
        return LogicResult("Demand OB", False, 0, "No OB retest", {})
    
    def _mtf_divergence(self, ohlcv_5m: List[List[float]], ohlcv_15m: List[List[float]]) -> LogicResult:
        """Logic: 5m + 15m bullish divergence"""
        if len(ohlcv_5m) < 20 or len(ohlcv_15m) < 20:
            return LogicResult("MTF Divergence", False, 0, "No data", {})
            
        closes_15m = [c[4] for c in ohlcv_15m[-20:]]
        rsi_15m = [self._calculate_rsi(closes_15m[:i+1], 14) for i in range(14, len(closes_15m))]
        
        if len(rsi_15m) < 5:
            return LogicResult("MTF Divergence", False, 0, "RSI failed", {})
        
        div_15m = closes_15m[-1] < closes_15m[-5] and rsi_15m[-1] > rsi_15m[-5]
        
        closes_5m = [c[4] for c in ohlcv_5m[-10:]]
        rsi_5m = self._calculate_rsi(closes_5m, 14)
        confirm_5m = rsi_5m > 40
        
        passed = div_15m and confirm_5m
        
        return LogicResult(
            "MTF Divergence",
            passed,
            15 if passed else 0,
            "📊 15m div + 5m confirm" if passed else "No divergence",
            {}
        )
    
    def _btc_calm_alt(self, ohlcv_alt: List[List[float]], ohlcv_btc: List[List[float]]) -> LogicResult:
        """Logic: BTC stable, alt outperforming"""
        if len(ohlcv_alt) < 10 or len(ohlcv_btc) < 10:
            return LogicResult("BTC Calm", False, 0, "No data", {})
            
        btc_atr = self._calculate_atr(ohlcv_btc[-14:])
        btc_calm = btc_atr < 0.5
        
        alt_change = (ohlcv_alt[-1][4] - ohlcv_alt[-5][4]) / ohlcv_alt[-5][4] * 100
        btc_change = (ohlcv_btc[-1][4] - ohlcv_btc[-5][4]) / ohlcv_btc[-5][4] * 100
        alt_strong = alt_change > btc_change
        
        passed = btc_calm and alt_strong
        
        return LogicResult(
            "BTC Calm + Alt Strong",
            passed,
            10 if passed else 0,
            f"💪 Alt {alt_change:.2f}% vs BTC {btc_change:.2f}%" if passed else "BTC volatile",
            {"alt_change": alt_change, "btc_change": btc_change}
        )
    
    def _session_reversal(self, ohlcv_5m: List[List[float]]) -> LogicResult:
        """Logic: London/NY open clean reversal"""
        from datetime import datetime
        import pytz
        
        now = datetime.now(pytz.UTC).astimezone(pytz.timezone('Asia/Kolkata'))
        hour = now.hour
        
        in_session = (13 <= hour <= 14) or (17 <= hour <= 18)
        
        if not in_session:
            return LogicResult("Session Reversal", False, 0, "Not session time", {})
        
        last = ohlcv_5m[-1]
        open_p, high, low, close = last[1:5]
        
        body = abs(close - open_p)
        lower_wick = min(open_p, close) - low
        upper_wick = high - max(open_p, close)
        
        if close > open_p:
            clean = lower_wick > body * 1.5
            passed = clean
            msg = "🌅 Bullish wick" if passed else "No clean wick"
        else:
            clean = upper_wick > body * 1.5
            passed = clean
            msg = "🌅 Bearish wick" if passed else "No clean wick"
        
        return LogicResult(
            "Session Reversal",
            passed,
            10 if passed else 0,
            msg,
            {}
        )
    
    # Helper methods
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
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
    
    def _calculate_ema(self, values: List[float], period: int) -> float:
        if len(values) < period:
            return sum(values) / len(values)
        
        k = 2.0 / (period + 1)
        ema = values[0]
        for v in values[1:]:
            ema = v * k + ema * (1 - k)
        return ema
    
    def _calculate_atr(self, ohlcv: List[List[float]]) -> float:
        if len(ohlcv) < 2:
            return 0.0
            
        trs = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        
        return sum(trs) / len(trs)
