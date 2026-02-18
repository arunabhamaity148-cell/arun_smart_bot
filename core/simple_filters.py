"""
ARUNABHA SIMPLE FILTERS v1.0
Only 6 essential filters - 4 pass needed
"""

import logging
from typing import Dict, List, Any, Tuple
import numpy as np

import config

logger = logging.getLogger(__name__)


class SimpleFilters:
    """
    6 filters only:
    1. Session active (volume + volatility)
    2. BTC trend OK (no conflict)
    3. MTF confirm (1h agrees)
    4. Liquidity zone (near S/R)
    5. Funding safe (not extreme)
    6. Cooldown OK (30 min wait)
    """
    
    def __init__(self):
        self.cooldown_map = {}  # symbol -> last_signal_time
        
    def evaluate(self,
                 direction: str,
                 ohlcv_15m: List[List[float]],
                 ohlcv_1h: List[List[float]],
                 btc_ohlcv_15m: List[List[float]],
                 funding_rate: float,
                 symbol: str) -> Tuple[int, int, Dict[str, Any]]:
        """
        Return: (passed, total, details)
        """
        results = {}
        
        # 1. Session Active (weight: 2)
        session_ok = self._check_session(ohlcv_15m)
        results["session"] = {
            "pass": session_ok,
            "weight": 2,
            "msg": "Active" if session_ok else "Quiet"
        }
        
        # 2. BTC Trend OK (weight: 2)
        btc_ok = self._check_btc_trend(direction, btc_ohlcv_15m)
        results["btc_trend"] = {
            "pass": btc_ok,
            "weight": 2,
            "msg": "Aligned" if btc_ok else "Conflict"
        }
        
        # 3. MTF Confirm (weight: 2)
        mtf_ok = self._check_mtf(direction, ohlcv_1h)
        results["mtf"] = {
            "pass": mtf_ok,
            "weight": 2,
            "msg": "Confirmed" if mtf_ok else "Conflict"
        }
        
        # 4. Liquidity Zone (weight: 1)
        liq_ok = self._check_liquidity(direction, ohlcv_15m)
        results["liquidity"] = {
            "pass": liq_ok,
            "weight": 1,
            "msg": "Near zone" if liq_ok else "Mid range"
        }
        
        # 5. Funding Safe (weight: 1)
        fund_ok = self._check_funding(direction, funding_rate)
        results["funding"] = {
            "pass": fund_ok,
            "weight": 1,
            "msg": "Safe" if fund_ok else "Extreme"
        }
        
        # 6. Cooldown OK (weight: 1) - Gatekeeper
        cool_ok = self._check_cooldown(symbol)
        results["cooldown"] = {
            "pass": cool_ok,
            "weight": 1,
            "msg": "Ready" if cool_ok else "Waiting"
        }
        
        # Calculate
        passed = sum(1 for r in results.values() if r["pass"])
        total = len(results)
        
        logger.info(
            "Filters %s: %d/6 | Session:%s BTC:%s MTF:%s Liq:%s Fund:%s Cool:%s",
            symbol, passed,
            results["session"]["msg"],
            results["btc_trend"]["msg"],
            results["mtf"]["msg"],
            results["liquidity"]["msg"],
            results["funding"]["msg"],
            results["cooldown"]["msg"]
        )
        
        return passed, total, results
    
    def _check_session(self, ohlcv: List[List[float]]) -> bool:
        """Volume and volatility sufficient"""
        if len(ohlcv) < 10:
            return True  # Default pass
            
        volumes = [c[5] for c in ohlcv[-10:]]
        avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
        last_vol = volumes[-1]
        
        # ATR calculation
        atr = self._calculate_atr(ohlcv[-10:])
        current_price = ohlcv[-1][4]
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
        
        # Active if volume OK and ATR > 0.2%
        return last_vol > avg_vol * 0.8 and atr_pct > 0.2
    
    def _check_btc_trend(self, direction: str, btc_ohlcv: List[List[float]]) -> bool:
        """BTC not conflicting with our trade"""
        if not btc_ohlcv or len(btc_ohlcv) < 21:
            return True  # Neutral
            
        closes = [c[4] for c in btc_ohlcv[-21:]]
        ema9 = sum(closes[-9:]) / 9
        ema21 = sum(closes[-21:]) / 21
        
        btc_bullish = ema9 > ema21
        
        if direction == "LONG":
            return btc_bullish or not btc_bullish  # Allow neutral
        else:
            return not btc_bullish or btc_bullish  # Allow neutral
        
        return True
    
    def _check_mtf(self, direction: str, ohlcv_1h: List[List[float]]) -> bool:
        """1h timeframe confirms 15m signal"""
        if not ohlcv_1h or len(ohlcv_1h) < 21:
            return True  # No data = neutral
            
        closes = [c[4] for c in ohlcv_1h[-21:]]
        ema9 = sum(closes[-9:]) / 9
        ema21 = sum(closes[-21:]) / 21
        
        h1_bullish = ema9 > ema21
        
        if direction == "LONG":
            return h1_bullish
        else:
            return not h1_bullish
    
    def _check_liquidity(self, direction: str, ohlcv: List[List[float]]) -> bool:
        """Near support (long) or resistance (short)"""
        if len(ohlcv) < 20:
            return True
            
        current = ohlcv[-1][4]
        highs = [c[2] for c in ohlcv[-20:]]
        lows = [c[3] for c in ohlcv[-20:]]
        
        recent_high = max(highs)
        recent_low = min(lows)
        
        # Near support (bottom 20% of range)
        near_support = current < recent_low + (recent_high - recent_low) * 0.2
        
        # Near resistance (top 20% of range)
        near_resistance = current > recent_high - (recent_high - recent_low) * 0.2
        
        if direction == "LONG":
            return near_support
        else:
            return near_resistance
    
    def _check_funding(self, direction: str, funding_rate: float) -> bool:
        """Not entering crowded trade"""
        extreme_long = funding_rate > 0.001  # +0.1%
        extreme_short = funding_rate < -0.001  # -0.1%
        
        if direction == "LONG" and extreme_long:
            return False  # Crowded long
        if direction == "SHORT" and extreme_short:
            return False  # Crowded short
            
        return True
    
    def _check_cooldown(self, symbol: str) -> bool:
        """30 min per coin cooldown"""
        from datetime import datetime, timedelta
        
        if symbol not in self.cooldown_map:
            return True
            
        last_time = self.cooldown_map[symbol]
        if datetime.now() - last_time < timedelta(minutes=config.COOLDOWN_MINUTES):
            return False
            
        return True
    
    def update_cooldown(self, symbol: str):
        """Call when signal taken"""
        from datetime import datetime
        self.cooldown_map[symbol] = datetime.now()
    
    def _calculate_atr(self, ohlcv: List[List[float]]) -> float:
        """Simple ATR"""
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
