"""
ARUNABHA BTC REGIME DETECTOR v3.6 - PART 1/2
Conservative Elite Institutional Mode - UPDATED FOR LIVE MARKET
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BTCRegime(Enum):
    STRONG_BULL = "strong_bull"
    BULL = "bull"
    CHOPPY = "choppy"
    BEAR = "bear"
    STRONG_BEAR = "strong_bear"
    UNKNOWN = "unknown"


@dataclass
class RegimeAnalysis:
    regime: BTCRegime
    confidence: int
    direction: str
    strength: str
    consistency: str
    can_trade: bool
    trade_mode: str
    block_reason: Optional[str]
    tier_requirement: str
    adx_threshold: float
    details: Dict


class BTCRegimeDetector:
    """
    Conservative Elite Institutional regime detection.
    UPDATED: Lowered thresholds for live market trading
    """
    
    # FIX 1: Lowered thresholds for live market (was 20, 40)
    HARD_BLOCK_CONFIDENCE = 10        # 20 → 10 (কম কনফিডেন্সেও ট্রেড করতে দেবে)
    CHOPPY_MIN_CONFIDENCE = 20        # 30 → 20
    TREND_MIN_CONFIDENCE = 25          # 40 → 25 (bear market ট্রেড করতে দেবে)
    
    CHOPPY_ADX_MIN = 20                # 28 → 20
    TREND_ADX_MIN = 18                  # 25 → 18 (ADX কম থাকলেও ট্রেড করতে দেবে)
    
    CHOPPY_TIER_MIN = 70                # 85 → 70
    TREND_TIER_MIN = 50                  # 70 → 50
    
    ADX_HISTORY_SIZE = 5
    
    def __init__(self):
        self.regime_history: List[BTCRegime] = []
        self.max_history = 10
        self._last_analysis: Optional[RegimeAnalysis] = None
        self._skip_next_cycle = False
        self._adx_history: List[float] = []
    
    def _calculate_ema(self, values: List[float], period: int) -> float:
        if len(values) < period:
            return sum(values) / len(values)
        
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        
        for price in values[period:]:
            ema = (price * k) + (ema * (1 - k))
        
        return ema
    
    def _calculate_true_adx(self, ohlcv: List, period: int = 14) -> float:
        if len(ohlcv) < period * 3:
            # FIX 1: Increased from 15.0 to 18.0 for better ADX in low data
            return 18.0
        
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        
        tr_list = []
        for i in range(1, len(ohlcv)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        plus_dm = []
        minus_dm = []
        for i in range(1, len(ohlcv)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
        
        if len(plus_dm) < period:
            # FIX 1: Consistent low-data fallback
            return 18.0
        
        atr = sum(tr_list[:period]) / period
        plus_di_sum = sum(plus_dm[:period])
        minus_di_sum = sum(minus_dm[:period])
        
        for i in range(period, len(tr_list)):
            atr = ((atr * (period - 1)) + tr_list[i]) / period
            plus_di_sum = ((plus_di_sum * (period - 1)) + plus_dm[i]) / period
            minus_di_sum = ((minus_di_sum * (period - 1)) + minus_dm[i]) / period
        
        plus_di = (plus_di_sum / atr) * 100 if atr > 0 else 0
        minus_di = (minus_di_sum / atr) * 100 if atr > 0 else 0
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100 if (plus_di + minus_di) > 0 else 0
        
        if len(self._adx_history) < 2:
            adx = dx
        else:
            prev_adx = self._adx_history[-1]
            adx = ((prev_adx * (period - 1)) + dx) / period
        
        self._adx_history.append(adx)
        if len(self._adx_history) > self.ADX_HISTORY_SIZE:
            self._adx_history.pop(0)
        
        if len(self._adx_history) >= 3:
            final_adx = sum(self._adx_history) / len(self._adx_history)
        else:
            final_adx = adx
        
        return final_adx
    
    def _get_ema_signals(self, ohlcv: List, name: str) -> Dict:
        if len(ohlcv) < 50:  # FIX: কমিয়ে 50 করা হয়েছে (was 200)
            # ডেটা কম থাকলেও কাজ করবে
            if len(ohlcv) < 20:
                return {"valid": False, "reason": f"Need at least 20 candles, got {len(ohlcv)}"}
            
            # কম ডেটা নিয়েই কাজ চালানো
            closes = [c[4] for c in ohlcv]
            price = closes[-1]
            
            # সিম্পল EMA (ছোট পিরিয়ড)
            ema9 = self._calculate_ema(closes, min(9, len(closes)//2))
            ema21 = self._calculate_ema(closes, min(21, len(closes)//2))
            
            return {
                "valid": True,
                "ema9": ema9,
                "ema21": ema21,
                "ema200": price,  # Approximate
                "price": price,
                "bullish_stack": ema9 > ema21,
                "bearish_stack": ema9 < ema21,
                "dist_200_pct": 0,
                "alignment_score": 10 if ema9 > ema21 else -10 if ema9 < ema21 else 0
            }
        
        closes = [c[4] for c in ohlcv]
        
        ema9 = self._calculate_ema(closes, 9)
        ema21 = self._calculate_ema(closes, 21)
        ema200 = self._calculate_ema(closes, 200)
        
        price = closes[-1]
        
        bullish_stack = ema9 > ema21 > ema200
        bearish_stack = ema9 < ema21 < ema200
        
        dist_200_pct = ((price - ema200) / ema200) * 100
        
        return {
            "valid": True,
            "ema9": ema9,
            "ema21": ema21,
            "ema200": ema200,
            "price": price,
            "bullish_stack": bullish_stack,
            "bearish_stack": bearish_stack,
            "dist_200_pct": dist_200_pct,
            "alignment_score": 15 if bullish_stack else -15 if bearish_stack else 5 if ema9 > ema21 else -5 if ema9 < ema21 else 0
        }
    
    def analyze(self, ohlcv_15m: List[List[float]], 
                ohlcv_1h: List[List[float]],
                ohlcv_4h: List[List[float]]) -> RegimeAnalysis:
        
        ema_score, ema_details = self._analyze_ema_structure(ohlcv_15m, ohlcv_1h, ohlcv_4h)
        structure_score, structure_details = self._analyze_market_structure(ohlcv_4h)
        momentum_score, momentum_details = self._analyze_momentum(ohlcv_15m, ohlcv_1h)
        vol_score, vol_details = self._analyze_volatility(ohlcv_15m)
        
        adx_value = self._calculate_true_adx(ohlcv_15m)
        
        total_score = (
            ema_score * 0.4 +
            structure_score * 0.3 +
            momentum_score * 0.2 +
            vol_score * 0.1
        )
        
        regime, confidence = self._classify_regime(total_score)
        consistency = self._check_consistency()
        
        can_trade, trade_mode, block_reason, tier_req, adx_thresh = self._apply_balanced_rules(
            regime, confidence, consistency, adx_value, vol_details
        )
        
        self.regime_history.append(regime)
        if len(self.regime_history) > self.max_history:
            self.regime_history.pop(0)
        
        direction = "UP" if total_score > 5 else "DOWN" if total_score < -5 else "SIDEWAYS"  # FIX: threshold 10→5
        strength = self._calculate_strength(abs(total_score))
        
        analysis = RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            direction=direction,
            strength=strength,
            consistency=consistency,
            can_trade=can_trade,
            trade_mode=trade_mode,
            block_reason=block_reason,
            tier_requirement=tier_req,
            adx_threshold=adx_thresh,
            details={
                "total_score": round(total_score, 1),
                "adx": round(adx_value, 1),
                "ema": ema_details,
                "structure": structure_details,
                "momentum": momentum_details,
                "volatility": vol_details,
            }
        )
        
        self._last_analysis = analysis
        
        status_emoji = "✅" if can_trade else "🚫"
        logger.info(
            "[REGIME GATE] %s | Conf:%d%% | ADX:%.1f | %s | Tier:%s | %s | %s",
            regime.value,
            confidence,
            adx_value,
            consistency,
            tier_req,
            trade_mode,
            block_reason if block_reason else f"{status_emoji} ALLOW"
        )
        
        return analysis
from .btc_regime_detector_part1 import BTCRegime, BTCRegimeDetector, logger
"""
ARUNABHA BTC REGIME DETECTOR v3.6 - PART 2/2
Conservative Elite Institutional Mode - UPDATED FOR LIVE MARKET
"""

import logging
from typing import Dict, List, Tuple, Optional
from .btc_regime_detector_part1 import BTCRegime, BTCRegimeDetector, logger

# এই ফাইলটি PART 1-এর পর যুক্ত করতে হবে
# ক্লাসটি PART 1-এ শুরু হয়েছে, এখানে বাকি মেথডগুলি দেওয়া হল


    def _apply_balanced_rules(self, regime: BTCRegime, confidence: int, 
                             consistency: str, adx: float, 
                             vol_details: Dict) -> Tuple[bool, str, Optional[str], str, float]:
        
        if consistency == "CHANGING":
            if not self._skip_next_cycle:
                self._skip_next_cycle = True
                return False, "WAIT", "Regime CHANGING - skipping 1 cycle", "N/A", 0
            else:
                self._skip_next_cycle = False
        
        # FIX: Hard block confidence lowered
        if confidence < self.HARD_BLOCK_CONFIDENCE:
            return False, "BLOCK", f"Confidence {confidence}% < {self.HARD_BLOCK_CONFIDENCE}% (Hard Block)", "N/A", 0
        
        if regime == BTCRegime.UNKNOWN:
            return False, "BLOCK", "Unknown regime", "N/A", 0
        
        if regime == BTCRegime.CHOPPY:
            if confidence < self.CHOPPY_MIN_CONFIDENCE:
                return False, "BLOCK", f"CHOPPY + Low confidence {confidence}% < {self.CHOPPY_MIN_CONFIDENCE}%", "N/A", 0
            
            if adx < self.CHOPPY_ADX_MIN:
                return False, "BLOCK", f"CHOPPY + Weak ADX {adx:.1f} < {self.CHOPPY_ADX_MIN}", f"Tier1-{self.CHOPPY_TIER_MIN}+", self.CHOPPY_ADX_MIN
            
            return True, "RANGE", None, f"Tier1-{self.CHOPPY_TIER_MIN}+", self.CHOPPY_ADX_MIN
        
        if regime in [BTCRegime.BEAR, BTCRegime.BULL, BTCRegime.STRONG_BEAR, BTCRegime.STRONG_BULL]:
            # FIX: Lowered confidence requirement
            if confidence < self.TREND_MIN_CONFIDENCE:
                return False, "BLOCK", f"{regime.value} + Low confidence {confidence}% < {self.TREND_MIN_CONFIDENCE}%", "N/A", 0
            
            # FIX: Lowered ADX requirement
            if adx < self.TREND_ADX_MIN:
                return False, "BLOCK", f"{regime.value} + Weak ADX {adx:.1f} < {self.TREND_ADX_MIN}", f"Tier1-{self.TREND_TIER_MIN}+", self.TREND_ADX_MIN
            
            return True, "TREND", None, f"Tier1-{self.TREND_TIER_MIN}+", self.TREND_ADX_MIN
        
        return False, "BLOCK", f"Unhandled regime: {regime.value}", "N/A", 0
    
    def _analyze_ema_structure(self, tf15: List, tf1h: List, tf4h: List) -> Tuple[int, Dict]:
        score = 0
        details = {}
        
        tfs = {
            "15m": self._get_ema_signals(tf15, "15m"),
            "1h": self._get_ema_signals(tf1h, "1h"),
            "4h": self._get_ema_signals(tf4h, "4h")
        }
        
        valid_tfs = {k: v for k, v in tfs.items() if v.get("valid")}
        
        if not valid_tfs:
            return 5, {"error": "Limited EMA data - using default"}  # FIX: Default score
        
        weights = {"4h": 1.5, "1h": 1.0, "15m": 0.5}
        
        for tf_name, tf_data in valid_tfs.items():
            score += tf_data["alignment_score"] * weights[tf_name]
            details[tf_name] = {
                "stack": "BULL" if tf_data.get("bullish_stack") else "BEAR" if tf_data.get("bearish_stack") else "MIXED",
                "dist_200": round(tf_data.get("dist_200_pct", 0), 2)
            }
        
        # FIX: Less strict alignment requirement
        bullish_count = sum(1 for t in valid_tfs.values() if t.get("bullish_stack"))
        bearish_count = sum(1 for t in valid_tfs.values() if t.get("bearish_stack"))
        
        if bullish_count >= 2:
            score += 10
            details["alignment"] = "PARTIAL_BULL"
        elif bearish_count >= 2:
            score -= 10
            details["alignment"] = "PARTIAL_BEAR"
        elif bullish_count == 1 or bearish_count == 1:
            details["alignment"] = "WEAK"
        else:
            details["alignment"] = "MIXED"
        
        return max(-50, min(50, score)), details
    
    def _analyze_market_structure(self, ohlcv_4h: List) -> Tuple[int, Dict]:
        if len(ohlcv_4h) < 20:  # FIX: 30 থেকে কমিয়ে 20
            return 5, {"structure": "INSUFFICIENT_DATA", "default": True}  # FIX: Default positive
        
        highs = [c[2] for c in ohlcv_4h[-20:]]  # FIX: 30 থেকে কমিয়ে 20
        lows = [c[3] for c in ohlcv_4h[-20:]]
        
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(highs)-2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))
        
        if len(swing_highs) < 1 or len(swing_lows) < 1:  # FIX: 2 থেকে কমিয়ে 1
            return 5, {"structure": "SIMPLE", "default": True}
        
        recent_hh = [h for _, h in swing_highs[-2:]]  # FIX: 3 থেকে কমিয়ে 2
        recent_ll = [l for _, l in swing_lows[-2:]]
        
        hh_pattern = recent_hh[-1] > recent_hh[0] if len(recent_hh) >= 2 else False
        hl_pattern = recent_ll[-1] > recent_ll[0] if len(recent_ll) >= 2 else False
        lh_pattern = recent_hh[-1] < recent_hh[0] if len(recent_hh) >= 2 else False
        ll_pattern = recent_ll[-1] < recent_ll[0] if len(recent_ll) >= 2 else False
        
        details = {"recent_hh": recent_hh[-1] if recent_hh else 0, 
                   "recent_ll": recent_ll[-1] if recent_ll else 0}
        
        # FIX: Easier structure detection
        if hh_pattern or hl_pattern:
            score = 20
            details["structure"] = "BULLISH"
        elif lh_pattern or ll_pattern:
            score = -20
            details["structure"] = "BEARISH"
        else:
            # Check simple trend
            closes = [c[4] for c in ohlcv_4h[-5:]]
            if closes[-1] > closes[0]:
                score = 10
                details["structure"] = "WEAK_BULL"
            elif closes[-1] < closes[0]:
                score = -10
                details["structure"] = "WEAK_BEAR"
            else:
                score = 0
                details["structure"] = "CHOPPY"
        
        return score, details
    
    def _analyze_momentum(self, tf15: List, tf1h: List) -> Tuple[int, Dict]:
        details = {}
        total = 0
        
        if len(tf15) >= 10:  # FIX: 20 থেকে কমিয়ে 10
            closes_15m = [c[4] for c in tf15[-10:]]
            rsi_15m = self._calculate_rsi(closes_15m, 7)  # FIX: 14 থেকে কমিয়ে 7
            rsi_score = (rsi_15m - 50) / 25 * 15  # FIX: Adjusted
            details["rsi_15m"] = round(rsi_15m, 1)
            total += rsi_score
        
        if len(tf15) >= 5:  # FIX: 10 থেকে কমিয়ে 5
            volumes = [c[5] for c in tf15[-5:]]
            avg_vol = sum(volumes[:-1]) / (len(volumes)-1) if len(volumes) > 1 else volumes[0]
            vol_trend = volumes[-1] / avg_vol if avg_vol > 0 else 1
            
            if vol_trend > 1.2:
                vol_score = 8 if rsi_score > 0 else -8
            elif vol_trend > 1.0:
                vol_score = 3 if rsi_score > 0 else -3
            else:
                vol_score = 0
            
            details["volume_ratio"] = round(vol_trend, 2)
            total += vol_score
        
        return max(-20, min(20, int(total))), details  # FIX: Range 25→20
    
    def _analyze_volatility(self, ohlcv: List) -> Tuple[int, Dict]:
        if len(ohlcv) < 7:  # FIX: 14 থেকে কমিয়ে 7
            return 5, {"atr_pct": 0.5, "regime": "DEFAULT"}  # FIX: Default
        
        trs = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        
        atr = sum(trs[-7:]) / 7  # FIX: 14 থেকে কমিয়ে 7
        current_price = ohlcv[-1][4]
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
        
        details = {"atr_pct": round(atr_pct, 2)}
        
        # FIX: Wider acceptable range
        if 0.3 <= atr_pct <= 2.0:  # Was 0.5-1.5
            score = 10
            details["regime"] = "NORMAL"
        elif 2.0 < atr_pct <= 3.0:
            score = 5
            details["regime"] = "ELEVATED"
        elif atr_pct < 0.3:
            score = 3
            details["regime"] = "LOW_VOL"
        elif 3.0 < atr_pct <= 4.0:
            score = -5
            details["regime"] = "HIGH_VOL"
        else:
            score = -8
            details["regime"] = "EXTREME_VOL"
        
        return score, details
    
    def _classify_regime(self, total_score: float) -> Tuple[BTCRegime, int]:
        abs_score = abs(total_score)
        
        # FIX: Higher confidence for same score
        trend_confidence = min(100, int(abs_score * 2.2))  # Was 1.6
        choppy_confidence = min(60, int(30 + abs_score * 1.5))  # Was 45, 25+abs_score
        
        if total_score >= 20:  # Was 25
            confidence = min(100, trend_confidence + 15)
            return BTCRegime.STRONG_BULL, confidence
        elif total_score >= 8:  # Was 10
            return BTCRegime.BULL, trend_confidence
        elif total_score <= -20:  # Was -25
            confidence = min(100, trend_confidence + 15)
            return BTCRegime.STRONG_BEAR, confidence
        elif total_score <= -8:  # Was -10
            return BTCRegime.BEAR, trend_confidence
        else:
            return BTCRegime.CHOPPY, choppy_confidence
    
    def _calculate_strength(self, abs_score: float) -> str:
        if abs_score >= 30:  # Was 40
            return "STRONG"
        elif abs_score >= 15:  # Was 20
            return "MODERATE"
        else:
            return "WEAK"
    
    def _check_consistency(self) -> str:
        if len(self.regime_history) < 2:  # Was 3
            return "STABILIZING"  # Was INSUFFICIENT_DATA
        
        recent = self.regime_history[-2:]  # Was 3
        if len(recent) >= 2 and recent[0] == recent[1]:
            return "CONSISTENT"
        else:
            return "STABILIZING"  # Was CHANGING
    
    def _calculate_rsi(self, closes: List[float], period: int = 7) -> float:  # FIX: Default 14→7
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
    
    def should_trade_alt(self, alt_direction: str, min_confidence: int = 30) -> Tuple[bool, str]:  # FIX: 45→30
        """
        Determine if altcoin trading is allowed based on BTC regime.
        UPDATED: Lowered min_confidence for live market
        """
        if not self._last_analysis:
            return False, "No analysis"
        
        analysis = self._last_analysis
        
        # Enforce min_confidence check
        if analysis.confidence < min_confidence:
            return False, f"Confidence {analysis.confidence}% < required {min_confidence}%"
        
        if not analysis.can_trade:
            return False, analysis.block_reason or "Regime block"
        
        if analysis.trade_mode == "TREND":
            if analysis.regime in [BTCRegime.STRONG_BULL, BTCRegime.BULL] and alt_direction != "LONG":
                return False, f"BTC {analysis.regime.value} but trying SHORT"
            if analysis.regime in [BTCRegime.STRONG_BEAR, BTCRegime.BEAR] and alt_direction != "SHORT":
                return False, f"BTC {analysis.regime.value} but trying LONG"
        
        return True, f"{analysis.trade_mode} | {analysis.regime.value} | Need {analysis.tier_requirement} | ADX>{analysis.adx_threshold}"


# Global instance
btc_detector = BTCRegimeDetector()