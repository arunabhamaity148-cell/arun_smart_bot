"""
ARUNABHA BTC REGIME DETECTOR v3.0
Institutional-grade with strict override enforcement
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


@dataclass
class RegimeAnalysis:
    regime: BTCRegime
    confidence: int
    direction: str
    strength: str
    consistency: str
    can_trade: bool              # 🆕 Pre-computed decision
    trade_mode: str              # 🆕 "TREND", "RANGE", "BLOCK"
    block_reason: Optional[str]  # 🆕 If blocked, why
    details: Dict


class BTCRegimeDetector:
    """
    Institutional-grade regime detection with non-negotiable overrides.
    Executes BEFORE signal scoring - gatekeeper architecture.
    """
    
    # 🆕 STRICT THRESHOLDS (Non-negotiable)
    MIN_CONFIDENCE_HARD = 45      # Issue I.1: <45% = HARD BLOCK
    MIN_CONFIDENCE_CHOPPY = 50    # Issue I.3: CHOPPY needs 50%
    MIN_CONFIDENCE_TREND = 60     # Trend mode preference
    
    def __init__(self):
        self.regime_history: List[BTCRegime] = []
        self.max_history = 10
        self._last_analysis: Optional[RegimeAnalysis] = None
    
    def _calculate_ema(self, values: List[float], period: int) -> float:
        """Proper EMA calculation."""
        if len(values) < period:
            return sum(values) / len(values)
        
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        
        for price in values[period:]:
            ema = (price * k) + (ema * (1 - k))
        
        return ema
    
    def _get_ema_signals(self, ohlcv: List, name: str) -> Dict:
        """True EMA200 calculation."""
        if len(ohlcv) < 200:
            return {"valid": False, "reason": f"Need 200 candles, got {len(ohlcv)}"}
        
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
            "alignment_score": 15 if bullish_stack else -15 if bearish_stack else 0
        }
    
    def analyze(self, ohlcv_15m: List[List[float]], 
                ohlcv_1h: List[List[float]],
                ohlcv_4h: List[List[float]]) -> RegimeAnalysis:
        """
        Full analysis with PRE-COMPUTED trade decision.
        This executes BEFORE any signal scoring - gatekeeper pattern.
        """
        
        # Layer 1-4 analysis
        ema_score, ema_details = self._analyze_ema_structure(ohlcv_15m, ohlcv_1h, ohlcv_4h)
        structure_score, structure_details = self._analyze_market_structure(ohlcv_4h)
        momentum_score, momentum_details = self._analyze_momentum(ohlcv_15m, ohlcv_1h)
        vol_score, vol_details = self._analyze_volatility(ohlcv_15m)
        
        total_score = (
            ema_score * 0.4 +
            structure_score * 0.3 +
            momentum_score * 0.2 +
            vol_score * 0.1
        )
        
        regime, confidence = self._classify_regime(total_score)
        consistency = self._check_consistency()
        
        # 🆕 ISSUE I: STRICT REGIME OVERRIDE (Non-negotiable)
        can_trade, trade_mode, block_reason = self._apply_regime_rules(
            regime, confidence, consistency, vol_details
        )
        
        # Update history only if valid analysis
        self.regime_history.append(regime)
        if len(self.regime_history) > self.max_history:
            self.regime_history.pop(0)
        
        direction = "UP" if total_score > 10 else "DOWN" if total_score < -10 else "SIDEWAYS"
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
            details={
                "total_score": round(total_score, 1),
                "ema": ema_details,
                "structure": structure_details,
                "momentum": momentum_details,
                "volatility": vol_details,
            }
        )
        
        self._last_analysis = analysis
        
        # 🆕 CRITICAL LOGGING
        logger.info(
            "[REGIME GATE] %s | Conf:%d%% | Consistency:%s | Mode:%s | Trade:%s | %s",
            regime.value,
            confidence,
            consistency,
            trade_mode,
            "ALLOW" if can_trade else "BLOCK",
            block_reason if block_reason else "OK"
        )
        
        return analysis
    
    def _apply_regime_rules(self, regime: BTCRegime, confidence: int, 
                           consistency: str, vol_details: Dict) -> Tuple[bool, str, Optional[str]]:
        """
        🆕 ISSUE I: Non-negotiable regime override logic.
        Returns: (can_trade, trade_mode, block_reason)
        """
        
        # I.2: CHANGING = HARD BLOCK
        if consistency == "CHANGING":
            return False, "BLOCK", f"Regime CHANGING (was {self.regime_history[-2].value if len(self.regime_history)>1 else 'unknown'})"
        
        # I.1: Confidence < 45% = HARD BLOCK
        if confidence < self.MIN_CONFIDENCE_HARD:
            return False, "BLOCK", f"Confidence {confidence}% < {self.MIN_CONFIDENCE_HARD}%"
        
        # I.3: CHOPPY mode rules
        if regime == BTCRegime.CHOPPY:
            if confidence < self.MIN_CONFIDENCE_CHOPPY:
                return False, "BLOCK", f"CHOPPY + Low confidence {confidence}%"
            return True, "RANGE", None  # Only range logic allowed
        
        # I.4: STRONG regimes - enforce directional bias
        if regime in [BTCRegime.STRONG_BULL, BTCRegime.STRONG_BEAR]:
            if confidence < self.MIN_CONFIDENCE_TREND:
                return False, "BLOCK", f"STRONG regime but confidence {confidence}% < {self.MIN_CONFIDENCE_TREND}%"
            return True, "TREND", None
        
        # BULL/BEAR normal
        return True, "TREND", None
    
    def _analyze_ema_structure(self, tf15: List, tf1h: List, tf4h: List) -> Tuple[int, Dict]:
        """Multi-timeframe EMA."""
        score = 0
        details = {}
        
        tfs = {
            "15m": self._get_ema_signals(tf15, "15m"),
            "1h": self._get_ema_signals(tf1h, "1h"),
            "4h": self._get_ema_signals(tf4h, "4h")
        }
        
        valid_tfs = {k: v for k, v in tfs.items() if v.get("valid")}
        
        if not valid_tfs:
            return 0, {"error": "No valid EMA data"}
        
        weights = {"4h": 1.5, "1h": 1.0, "15m": 0.5}
        
        for tf_name, tf_data in valid_tfs.items():
            score += tf_data["alignment_score"] * weights[tf_name]
            details[tf_name] = {
                "stack": "BULL" if tf_data["bullish_stack"] else "BEAR" if tf_data["bearish_stack"] else "MIXED",
                "dist_200": round(tf_data["dist_200_pct"], 2)
            }
        
        if all(t.get("bullish_stack") for t in valid_tfs.values()):
            score += 10
            details["alignment"] = "FULL_BULL"
        elif all(t.get("bearish_stack") for t in valid_tfs.values()):
            score -= 10
            details["alignment"] = "FULL_BEAR"
        else:
            details["alignment"] = "MIXED"
        
        return max(-50, min(50, score)), details
    
    def _analyze_market_structure(self, ohlcv_4h: List) -> Tuple[int, Dict]:
        """HH/HL or LH/LL detection."""
        if len(ohlcv_4h) < 30:
            return 0, {"error": "Insufficient data"}
        
        highs = [c[2] for c in ohlcv_4h[-30:]]
        lows = [c[3] for c in ohlcv_4h[-30:]]
        
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(highs)-2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 0, {"structure": "UNCLEAR"}
        
        recent_hh = [h for _, h in swing_highs[-3:]]
        recent_ll = [l for _, l in swing_lows[-3:]]
        
        hh_pattern = recent_hh[-1] > recent_hh[0] if len(recent_hh) >= 2 else False
        hl_pattern = recent_ll[-1] > recent_ll[0] if len(recent_ll) >= 2 else False
        lh_pattern = recent_hh[-1] < recent_hh[0] if len(recent_hh) >= 2 else False
        ll_pattern = recent_ll[-1] < recent_ll[0] if len(recent_ll) >= 2 else False
        
        details = {"recent_hh": recent_hh[-1], "recent_ll": recent_ll[-1]}
        
        if hh_pattern and hl_pattern:
            score = 35
            details["structure"] = "HH_HL"
        elif lh_pattern and ll_pattern:
            score = -35
            details["structure"] = "LH_LL"
        elif hh_pattern or hl_pattern:
            score = 15
            details["structure"] = "WEAK_BULL"
        elif lh_pattern or ll_pattern:
            score = -15
            details["structure"] = "WEAK_BEAR"
        else:
            score = 0
            details["structure"] = "CHOPPY"
        
        return score, details
    
    def _analyze_momentum(self, tf15: List, tf1h: List) -> Tuple[int, Dict]:
        """RSI + Volume."""
        details = {}
        
        if len(tf15) >= 20:
            closes_15m = [c[4] for c in tf15[-20:]]
            rsi_15m = self._calculate_rsi(closes_15m, 14)
            rsi_score = (rsi_15m - 50) / 50 * 25
            details["rsi_15m"] = round(rsi_15m, 1)
        else:
            rsi_score = 0
            details["rsi_15m"] = "N/A"
        
        if len(tf15) >= 10:
            volumes = [c[5] for c in tf15[-10:]]
            vol_trend = volumes[-1] / (sum(volumes[:-1]) / 9)
            
            if vol_trend > 1.5:
                vol_score = 10 if rsi_score > 0 else -10
            elif vol_trend > 1.2:
                vol_score = 5 if rsi_score > 0 else -5
            else:
                vol_score = 0
            
            details["volume_ratio"] = round(vol_trend, 2)
        else:
            vol_score = 0
        
        total = rsi_score + vol_score
        return max(-25, min(25, total)), details
    
    def _analyze_volatility(self, ohlcv: List) -> Tuple[int, Dict]:
        """Balanced ATR scoring."""
        if len(ohlcv) < 14:
            return 0, {"error": "No data", "atr_pct": 0}
        
        trs = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        
        atr = sum(trs[-14:]) / 14
        current_price = ohlcv[-1][4]
        atr_pct = (atr / current_price) * 100
        
        details = {"atr_pct": round(atr_pct, 2)}
        
        if 0.5 <= atr_pct <= 1.5:
            score = 10
            details["regime"] = "NORMAL"
        elif 1.5 < atr_pct <= 2.5:
            score = 5
            details["regime"] = "ELEVATED"
        elif atr_pct < 0.3:
            score = 0
            details["regime"] = "LOW_VOL"
        elif 0.3 <= atr_pct < 0.5:
            score = 3
            details["regime"] = "LOW_ACCEPTABLE"
        elif 2.5 < atr_pct <= 3.5:
            score = -5
            details["regime"] = "HIGH_VOL"
        else:
            score = -10
            details["regime"] = "EXTREME_VOL"
        
        return score, details
    
    def _classify_regime(self, total_score: float) -> Tuple[BTCRegime, int]:
        """Classify regime."""
        abs_score = abs(total_score)
        confidence = min(100, int(abs_score * 1.5))
        
        if total_score >= 25:
            return BTCRegime.STRONG_BULL, confidence
        elif total_score >= 10:
            return BTCRegime.BULL, confidence
        elif total_score <= -25:
            return BTCRegime.STRONG_BEAR, confidence
        elif total_score <= -10:
            return BTCRegime.BEAR, confidence
        else:
            return BTCRegime.CHOPPY, max(0, 50 - int(abs_score * 2))
    
    def _calculate_strength(self, abs_score: float) -> str:
        if abs_score >= 40:
            return "STRONG"
        elif abs_score >= 20:
            return "MODERATE"
        else:
            return "WEAK"
    
    def _check_consistency(self) -> str:
        """Regime consistency check."""
        if len(self.regime_history) < 3:
            return "INSUFFICIENT_DATA"
        
        recent = self.regime_history[-3:]
        if all(r == recent[0] for r in recent):
            return "CONSISTENT"
        elif recent[-1] == recent[-2]:
            return "STABILIZING"
        else:
            return "CHANGING"
    
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Standard RSI."""
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
    
    def should_trade_alt(self, alt_direction: str, min_confidence: int = 60) -> Tuple[bool, str]:
        """
        🆕 Final gate check - uses pre-computed analysis.
        """
        if not self._last_analysis:
            return False, "No analysis"
        
        analysis = self._last_analysis
        
        # Use pre-computed decision
        if not analysis.can_trade:
            return False, analysis.block_reason or "Regime block"
        
        # Direction alignment check
        if analysis.trade_mode == "TREND":
            if analysis.regime in [BTCRegime.STRONG_BULL, BTCRegime.BULL] and alt_direction != "LONG":
                return False, f"BTC {analysis.regime.value} but trying SHORT"
            if analysis.regime in [BTCRegime.STRONG_BEAR, BTCRegime.BEAR] and alt_direction != "SHORT":
                return False, f"BTC {analysis.regime.value} but trying LONG"
        
        return True, f"{analysis.trade_mode} mode | {analysis.regime.value} | {analysis.consistency}"


# Global instance
btc_detector = BTCRegimeDetector()
