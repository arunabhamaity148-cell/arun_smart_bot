"""
ARUNABHA BTC REGIME DETECTOR v1.0
Multi-timeframe trend + structure + momentum
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
    details: Dict


class BTCRegimeDetector:
    """
    4-layer BTC analysis:
    1. EMA Structure (Trend)
    2. Market Structure (HH/HL or LH/LL)
    3. Momentum (RSI + Volume)
    4. Volatility Regime (ATR)
    """
    
    def __init__(self):
        self.regime_history: List[BTCRegime] = []
        self.max_history = 10
    
    def analyze(self, ohlcv_15m: List[List[float]], 
                ohlcv_1h: List[List[float]],
                ohlcv_4h: List[List[float]]) -> RegimeAnalysis:
        
        # Layer 1: EMA Structure (Weight: 40%)
        ema_score, ema_details = self._analyze_ema_structure(ohlcv_15m, ohlcv_1h, ohlcv_4h)
        
        # Layer 2: Market Structure (Weight: 30%)
        structure_score, structure_details = self._analyze_market_structure(ohlcv_4h)
        
        # Layer 3: Momentum (Weight: 20%)
        momentum_score, momentum_details = self._analyze_momentum(ohlcv_15m, ohlcv_1h)
        
        # Layer 4: Volatility (Weight: 10%)
        vol_score, vol_details = self._analyze_volatility(ohlcv_15m)
        
        # Calculate weighted score (-100 to +100)
        total_score = (
            ema_score * 0.4 +
            structure_score * 0.3 +
            momentum_score * 0.2 +
            vol_score * 0.1
        )
        
        # Determine regime
        regime, confidence = self._classify_regime(total_score, ema_details, structure_details)
        
        # Direction and strength
        direction = "UP" if total_score > 10 else "DOWN" if total_score < -10 else "SIDEWAYS"
        strength = self._calculate_strength(abs(total_score))
        
        # Store history
        self.regime_history.append(regime)
        if len(self.regime_history) > self.max_history:
            self.regime_history.pop(0)
        
        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            direction=direction,
            strength=strength,
            details={
                "total_score": round(total_score, 1),
                "ema": ema_details,
                "structure": structure_details,
                "momentum": momentum_details,
                "volatility": vol_details,
                "regime_consistency": self._check_consistency()
            }
        )
    
    def _analyze_ema_structure(self, tf15: List, tf1h: List, tf4h: List) -> Tuple[int, Dict]:
        score = 0
        details = {}
        
        def get_ema_signals(ohlcv: List, name: str) -> Dict:
            if len(ohlcv) < 50:
                return {"valid": False}
            
            closes = [c[4] for c in ohlcv]
            ema9 = sum(closes[-9:]) / 9
            ema21 = sum(closes[-21:]) / 21
            ema200 = sum(closes[-50:]) / 50
            
            price = closes[-1]
            
            bullish_stack = ema9 > ema21 > ema200
            bearish_stack = ema9 < ema21 < ema200
            
            return {
                "valid": True,
                "bullish_stack": bullish_stack,
                "bearish_stack": bearish_stack,
                "alignment_score": 15 if bullish_stack else -15 if bearish_stack else 0
            }
        
        tfs = {
            "15m": get_ema_signals(tf15, "15m"),
            "1h": get_ema_signals(tf1h, "1h"),
            "4h": get_ema_signals(tf4h, "4h")
        }
        
        valid_tfs = [v for v in tfs.values() if v["valid"]]
        
        if tfs["4h"]["valid"]:
            score += tfs["4h"]["alignment_score"] * 1.5
            details["4h"] = "Bull" if tfs["4h"]["bullish_stack"] else "Bear" if tfs["4h"]["bearish_stack"] else "Mixed"
            
        if tfs["1h"]["valid"]:
            score += tfs["1h"]["alignment_score"] * 1.0
            details["1h"] = "Bull" if tfs["1h"]["bullish_stack"] else "Bear" if tfs["1h"]["bearish_stack"] else "Mixed"
            
        if tfs["15m"]["valid"]:
            score += tfs["15m"]["alignment_score"] * 0.5
            details["15m"] = "Bull" if tfs["15m"]["bullish_stack"] else "Bear" if tfs["15m"]["bearish_stack"] else "Mixed"
        
        # Full alignment bonus
        if all(t.get("bullish_stack") for t in valid_tfs):
            score += 10
            details["alignment"] = "FULL_BULL"
        elif all(t.get("bearish_stack") for t in valid_tfs):
            score -= 10
            details["alignment"] = "FULL_BEAR"
        else:
            details["alignment"] = "MIXED"
        
        score = max(-50, min(50, score))
        return score, details
    
    def _analyze_market_structure(self, ohlcv_4h: List) -> Tuple[int, Dict]:
        if len(ohlcv_4h) < 30:
            return 0, {"error": "No data"}
        
        highs = [c[2] for c in ohlcv_4h[-30:]]
        lows = [c[3] for c in ohlcv_4h[-30:]]
        
        # Find swing points
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
        
        details = {
            "recent_hh": recent_hh[-1] if recent_hh else None,
            "recent_ll": recent_ll[-1] if recent_ll else None,
        }
        
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
        details = {}
        
        # 15m RSI
        if len(tf15) >= 20:
            closes_15m = [c[4] for c in tf15[-20:]]
            rsi_15m = self._calculate_rsi(closes_15m, 14)
            rsi_score = (rsi_15m - 50) / 50 * 25
            details["rsi_15m"] = round(rsi_15m, 1)
        else:
            rsi_score = 0
            details["rsi_15m"] = "N/A"
        
        # Volume trend
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
            details["volume_ratio"] = "N/A"
        
        total_score = rsi_score + vol_score
        total_score = max(-25, min(25, total_score))
        
        return total_score, details
    
    def _analyze_volatility(self, ohlcv: List) -> Tuple[int, Dict]:
        if len(ohlcv) < 14:
            return 0, {"error": "No data"}
        
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
        
        if 0.3 <= atr_pct <= 2.0:
            score = 10
            details["regime"] = "NORMAL"
        elif atr_pct < 0.3:
            score = -10
            details["regime"] = "LOW_VOL"
        elif atr_pct > 3.0:
            score = -5
            details["regime"] = "HIGH_VOL"
        else:
            score = 5
            details["regime"] = "ELEVATED"
        
        return score, details
    
    def _classify_regime(self, total_score: float, ema_details: Dict, structure_details: Dict) -> Tuple[BTCRegime, int]:
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
        if not self.regime_history:
            return False, "No regime data"
        
        current = self.regime_history[-1]
        
        if current == BTCRegime.STRONG_BULL:
            return alt_direction == "LONG", "BTC Strong Bull"
        elif current == BTCRegime.BULL:
            return alt_direction == "LONG", "BTC Bull"
        elif current == BTCRegime.STRONG_BEAR:
            return alt_direction == "SHORT", "BTC Strong Bear"
        elif current == BTCRegime.BEAR:
            return alt_direction == "SHORT", "BTC Bear"
        else:
            return False, "BTC Choppy - No trade"


# Global instance
btc_detector = BTCRegimeDetector()
