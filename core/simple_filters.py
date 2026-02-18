"""
ARUNABHA SIMPLE FILTERS v2.2
Updated to pass min_confidence to regime detector
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta

import config
from .btc_regime_detector import btc_detector, BTCRegime

logger = logging.getLogger(__name__)


class SimpleFilters:
    """
    8 strict filters with proper BTC alignment
    """
    
    def __init__(self):
        self.cooldown_map = {}
        self.btc_min_confidence = 60  # 🆕 Configurable threshold
        
    def evaluate(self,
                 direction: str,
                 ohlcv_15m: List[List[float]],
                 ohlcv_1h: List[List[float]],
                 btc_ohlcv_15m: List[List[float]],
                 btc_ohlcv_1h: List[List[float]],
                 btc_ohlcv_4h: List[List[float]],
                 funding_rate: float,
                 symbol: str,
                 ema200_passed: bool = False,
                 structure_passed: bool = False) -> Tuple[int, int, Dict[str, Any], bool]:
        """
        Return: (passed, total, details, mandatory_pass)
        """
        results = {}
        
        # 1. Session Active
        session_ok, session_msg = self._check_session_strict(ohlcv_15m)
        results["session"] = {
            "pass": session_ok,
            "weight": 3,
            "msg": session_msg
        }
        
        # 2. 🆕 ADVANCED BTC Regime Detection with confidence
        btc_ok, btc_msg = self._check_btc_regime(direction, btc_ohlcv_15m, btc_ohlcv_1h, btc_ohlcv_4h)
        results["btc_trend"] = {
            "pass": btc_ok,
            "weight": 3,
            "msg": btc_msg
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
        
        # 7. EMA200 Confirm
        results["ema200"] = {
            "pass": ema200_passed,
            "weight": 3,
            "msg": "Confirmed" if ema200_passed else "Failed"
        }
        
        # 8. Structure Shift
        results["structure"] = {
            "pass": structure_passed,
            "weight": 3,
            "msg": "Confirmed" if structure_passed else "Failed"
        }
        
        # Calculate
        passed = sum(1 for r in results.values() if r["pass"])
        total = len(results)
        
        # STRICT: Must pass Session, BTC, EMA200, Structure
        mandatory_pass = session_ok and btc_ok and ema200_passed and structure_passed
        
        logger.info(
            "Filters %s: %d/%d | Mandatory: %s | BTC:%s",
            symbol, passed, total, mandatory_pass,
            "✅" if btc_ok else "❌"
        )
        
        return passed, total, results, mandatory_pass
    
    def _check_btc_regime(self, direction: str, 
                          btc_15m: List, 
                          btc_1h: List, 
                          btc_4h: List) -> Tuple[bool, str]:
        """
        🆕 ADVANCED: Use BTC Regime Detector with confidence enforcement
        """
        if not btc_15m or len(btc_15m) < 200:  # 🆕 Need 200 for true EMA200
            return False, "No BTC data (need 200 candles)"
        
        # Analyze regime
        analysis = btc_detector.analyze(btc_15m, btc_1h, btc_4h)
        
        # 🆕 Pass min_confidence from config or self
        can_trade, reason = btc_detector.should_trade_alt(
            direction, 
            min_confidence=self.btc_min_confidence
        )
        
        # Build detailed message
        regime_name = analysis.regime.value.replace("_", " ").upper()
        confidence = analysis.confidence
        consistency = analysis.consistency
        
        if can_trade:
            return True, f"✅ BTC {regime_name} ({confidence}%, {consistency}) - {reason}"
        else:
            return False, f"❌ BTC {regime_name} ({confidence}%, {consistency}) - {reason}"
    
    def _check_session_strict(self, ohlcv: List[List[float]]) -> Tuple[bool, str]:
        """Volume and volatility check"""
        if len(ohlcv) < 10:
            return False, "No data"
            
        volumes = [c[5] for c in ohlcv[-10:]]
        avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
        last_vol = volumes[-1]
        
        atr = self._calculate_atr(ohlcv[-10:])
        current_price = ohlcv[-1][4]
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
        
        volume_ok = last_vol > avg_vol * 0.8
        atr_ok = atr_pct > 0.3
        
        if not volume_ok and not atr_ok:
            return False, f"❌ QUIET: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
        elif not volume_ok:
            return False, f"❌ Low Volume: {last_vol/avg_vol:.1f}x"
        elif not atr_ok:
            return False, f"❌ Low Volatility: ATR {atr_pct:.2f}%"
        
        return True, f"✅ Active: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
    
    def _check_mtf(self, direction: str, ohlcv_1h: List[List[float]]) -> bool:
        """1h timeframe confirms"""
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
        """Near support/resistance"""
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
        """Not extreme funding"""
        extreme_long = funding_rate > 0.001
        extreme_short = funding_rate < -0.001
        
        if direction == "LONG" and extreme_long:
            return False
        if direction == "SHORT" and extreme_short:
            return False
            
        return True
    
    def _check_cooldown(self, symbol: str) -> bool:
        """30 min cooldown"""
        if symbol not in self.cooldown_map:
            return True
            
        last_time = self.cooldown_map[symbol]
        if datetime.now() - last_time < timedelta(minutes=config.COOLDOWN_MINUTES):
            return False
            
        return True
    
    def update_cooldown(self, symbol: str):
        self.cooldown_map[symbol] = datetime.now()
    
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
