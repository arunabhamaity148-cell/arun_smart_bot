"""
ARUNABHA SIMPLE FILTERS v2.0
Strict filters: 8 filters, 6 pass needed
Session quiet = BLOCK
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
import pytz

import config

logger = logging.getLogger(__name__)


class SimpleFilters:
    """
    8 strict filters:
    1. Session active (MANDATORY - quiet = no trade)
    2. BTC trend OK
    3. MTF confirm
    4. Liquidity zone
    5. Funding safe
    6. Cooldown OK
    7. EMA200 confirm (MANDATORY)
    8. Structure shift (MANDATORY)
    """
    
    def __init__(self):
        self.cooldown_map = {}
        
    def evaluate(self,
                 direction: str,
                 ohlcv_15m: List[List[float]],
                 ohlcv_1h: List[List[float]],
                 btc_ohlcv_15m: List[List[float]],
                 funding_rate: float,
                 symbol: str,
                 ema200_passed: bool = False,
                 structure_passed: bool = False) -> Tuple[int, int, Dict[str, Any], bool]:
        """
        Return: (passed, total, details, mandatory_pass)
        """
        results = {}
        
        # 1. 🆕 STRICT: Session Active (MANDATORY)
        session_ok, session_msg = self._check_session_strict(ohlcv_15m)
        results["session"] = {
            "pass": session_ok,
            "weight": 3,
            "msg": session_msg
        }
        
        # 2. BTC Trend OK
        btc_ok = self._check_btc_trend(direction, btc_ohlcv_15m)
        results["btc_trend"] = {
            "pass": btc_ok,
            "weight": 2,
            "msg": "Aligned" if btc_ok else "Conflict"
        }
        
        # 3. MTF Confirm
        mtf_ok = self._check_mtf(direction, ohlcv_1h)
        results["mtf"] = {
            "pass": mtf_ok,
            "weight": 2,
            "msg": "Confirmed" if mtf_ok else "Conflict"
        }
        
        # 4. Liquidity Zone
        liq_ok = self._check_liquidity(direction, ohlcv_15m)
        results["liquidity"] = {
            "pass": liq_ok,
            "weight": 1,
            "msg": "Near zone" if liq_ok else "Mid range"
        }
        
        # 5. Funding Safe
        fund_ok = self._check_funding(direction, funding_rate)
        results["funding"] = {
            "pass": fund_ok,
            "weight": 1,
            "msg": "Safe" if fund_ok else "Extreme"
        }
        
        # 6. Cooldown OK
        cool_ok = self._check_cooldown(symbol)
        results["cooldown"] = {
            "pass": cool_ok,
            "weight": 1,
            "msg": "Ready" if cool_ok else "Waiting"
        }
        
        # 7. 🆕 EMA200 Confirm (MANDATORY)
        results["ema200"] = {
            "pass": ema200_passed,
            "weight": 3,
            "msg": "Confirmed" if ema200_passed else "Failed"
        }
        
        # 8. 🆕 Structure Shift (MANDATORY)
        results["structure"] = {
            "pass": structure_passed,
            "weight": 3,
            "msg": "Confirmed" if structure_passed else "Failed"
        }
        
        # Calculate
        passed = sum(1 for r in results.values() if r["pass"])
        total = len(results)
        
        # 🆕 STRICT: Must pass Session, EMA200, Structure
        mandatory_pass = session_ok and ema200_passed and structure_passed
        
        logger.info(
            "Filters %s: %d/%d | Mandatory: %s | Session:%s EMA200:%s Structure:%s",
            symbol, passed, total, mandatory_pass,
            results["session"]["msg"],
            results["ema200"]["msg"],
            results["structure"]["msg"]
        )
        
        return passed, total, results, mandatory_pass
    
    def _check_session_strict(self, ohlcv: List[List[float]]) -> Tuple[bool, str]:
        """🆕 STRICT: Volume and volatility MUST be sufficient"""
        if len(ohlcv) < 10:
            return False, "No data"
            
        volumes = [c[5] for c in ohlcv[-10:]]
        avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
        last_vol = volumes[-1]
        
        # ATR calculation
        atr = self._calculate_atr(ohlcv[-10:])
        current_price = ohlcv[-1][4]
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
        
        # 🆕 STRICT: Both volume AND ATR must be good
        volume_ok = last_vol > avg_vol * 0.8
        atr_ok = atr_pct > 0.3  # Increased from 0.2%
        
        if not volume_ok and not atr_ok:
            return False, f"❌ QUIET: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
        elif not volume_ok:
            return False, f"❌ Low Volume: {last_vol/avg_vol:.1f}x"
        elif not atr_ok:
            return False, f"❌ Low Volatility: ATR {atr_pct:.2f}%"
        
        return True, f"✅ Active: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
    
    def _check_btc_trend(self, direction: str, btc_ohlcv: List[List[float]]) -> bool:
        """BTC not conflicting with our trade"""
        if not btc_ohlcv or len(btc_ohlcv) < 21:
            return True
            
        closes = [c[4] for c in btc_ohlcv[-21:]]
        ema9 = sum(closes[-9:]) / 9
        ema21 = sum(closes[-21:]) / 21
        
        btc_bullish = ema9 > ema21
        
        if direction == "LONG":
            return btc_bullish or not btc_bullish
        else:
            return not btc_bullish or btc_bullish
        
        return True
    
    def _check_mtf(self, direction: str, ohlcv_1h: List[List[float]]) -> bool:
        """1h timeframe confirms 15m signal"""
        if not ohlcv_1h or len(ohlcv_1h) < 21:
            return True
            
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
        
        near_support = current < recent_low + (recent_high - recent_low) * 0.2
        near_resistance = current > recent_high - (recent_high - recent_low) * 0.2
        
        if direction == "LONG":
            return near_support
        else:
            return near_resistance
    
    def _check_funding(self, direction: str, funding_rate: float) -> bool:
        """Not entering crowded trade"""
        extreme_long = funding_rate > 0.001
        extreme_short = funding_rate < -0.001
        
        if direction == "LONG" and extreme_long:
            return False
        if direction == "SHORT" and extreme_short:
            return False
            
        return True
    
    def _check_cooldown(self, symbol: str) -> bool:
        """30 min per coin cooldown"""
        if symbol not in self.cooldown_map:
            return True
            
        last_time = self.cooldown_map[symbol]
        if datetime.now() - last_time < timedelta(minutes=config.COOLDOWN_MINUTES):
            return False
            
        return True
    
    def update_cooldown(self, symbol: str):
        """Call when signal taken"""
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
