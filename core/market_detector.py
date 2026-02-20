"""
ARUNABHA FINAL v4.0 - MARKET TYPE DETECTOR
Detects Trending/Choppy/High Vol markets automatically
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

from utils.indicators import calculate_adx, calculate_atr

logger = logging.getLogger(__name__)

@dataclass
class MarketType:
    name: str  # TRENDING, CHOPPY, HIGH_VOL
    confidence: int
    adx: float
    atr_pct: float
    reason: str

class MarketDetector:
    def __init__(self):
        self.history: List[str] = []
        self.last_market = "CHOPPY"
    
    def detect(self, btc_15m: List[List[float]], btc_1h: List[List[float]]) -> MarketType:
        """Detect current market type"""
        
        # Calculate ADX for trend strength (using shared indicator)
        adx = calculate_adx(btc_15m)
        
        # Calculate ATR for volatility (using shared indicator)
        atr_pct = self._calculate_atr_pct(btc_1h)
        
        # Check volatility first
        if atr_pct > 3.0:
            market = "HIGH_VOL"
            conf = min(100, int(atr_pct * 20))
            reason = f"ATR {atr_pct:.1f}% > 3%"
        elif adx > 25:
            market = "TRENDING"
            conf = min(100, int(adx * 2.5))
            reason = f"ADX {adx:.1f} > 25"
        else:
            market = "CHOPPY"
            conf = max(30, int(100 - adx * 2))
            reason = f"ADX {adx:.1f} between 15-25"
        
        self.history.append(market)
        if len(self.history) > 5:
            self.history.pop(0)
        
        # Check consistency
        if len(self.history) >= 3:
            if all(m == market for m in self.history[-3:]):
                conf = min(100, conf + 20)
        
        self.last_market = market
        
        logger.info(f"[MARKET] {market} | Conf:{conf}% | ADX:{adx:.1f} | ATR:{atr_pct:.1f}% | {reason}")
        
        return MarketType(
            name=market,
            confidence=conf,
            adx=adx,
            atr_pct=atr_pct,
            reason=reason
        )
    
    def _calculate_atr_pct(self, ohlcv: List[List[float]], period: int = 14) -> float:
        """Calculate ATR as percentage"""
        if len(ohlcv) < period:
            return 1.0
        
        atr = calculate_atr(ohlcv, period)
        current_price = ohlcv[-1][4]
        
        return (atr / current_price) * 100 if current_price > 0 else 1.0

market_detector = MarketDetector()