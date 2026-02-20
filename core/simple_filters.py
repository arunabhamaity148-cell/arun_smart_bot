"""
ARUNABHA SIMPLE FILTERS v2.4
Balanced filtering - UPDATED FOR LIVE MARKET
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta

import config
from .btc_regime_detector import btc_detector, BTCRegime

logger = logging.getLogger(__name__)


class SimpleFilters:
   """
   6 balanced filters - UPDATED: Lowered thresholds for live trading
   """
   
   def __init__(self):
       self.cooldown_map = {}
       self.btc_min_confidence = 30  # 🆕 45 থেকে কমিয়ে 30
       
   def evaluate(self,
                direction: str,
                ohlcv_15m: List[List[float]],
                ohlcv_1h: List[List[float]],
                btc_ohlcv_15m: List[List[float]],
                btc_ohlcv_1h: List[List[float]],
                btc_ohlcv_4h: List[List[float]],
                funding_rate: float,
                symbol: str,
                ema200_passed: bool = False) -> Tuple[int, int, Dict[str, Any], bool]:
       """
       Return: (passed, total, details, mandatory_pass)
       UPDATED: More lenient mandatory requirements
       """
       results = {}
       
       # 1. Session Active
       session_ok, session_msg = self._check_session_strict(ohlcv_15m)
       results["session"] = {
           "pass": session_ok,
           "weight": 3,
           "msg": session_msg
       }
       
       # 2. BTC Regime Detection
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
       
       # Calculate
       passed = sum(1 for r in results.values() if r["pass"])
       total = len(results)
       
       # UPDATED: Mandatory now requires at least 2 of 3 (session, btc, mtf)
       mandatory_count = sum([session_ok, btc_ok, mtf_ok])
       mandatory_pass = mandatory_count >= 2  # Was: session_ok and btc_ok and mtf_ok
       
       logger.info(
           "Filters %s: %d/%d | Mandatory: %s (%d/3) | BTC:%s",
           symbol, passed, total, "✅" if mandatory_pass else "❌", 
           mandatory_count, "✅" if btc_ok else "❌"
       )
       
       return passed, total, results, mandatory_pass
   
   def _check_btc_regime(self, direction: str, 
                         btc_15m: List, 
                         btc_1h: List, 
                         btc_4h: List) -> Tuple[bool, str]:
       """
       BTC Regime Detection with lower confidence requirement
       """
       if not btc_15m or len(btc_15m) < 50:  # 200 থেকে কমিয়ে 50
           return True, "⚠️ Limited BTC data - allowing"  # Block না করে allow
       
       analysis = btc_detector.analyze(btc_15m, btc_1h, btc_4h)
       
       can_trade, reason = btc_detector.should_trade_alt(
           direction, 
           min_confidence=self.btc_min_confidence
       )
       
       regime_name = analysis.regime.value.replace("_", " ").upper()
       confidence = analysis.confidence
       consistency = analysis.consistency
       
       if can_trade:
           return True, f"✅ BTC {regime_name} ({confidence}%, {consistency}) - {reason}"
       else:
           # UPDATED: Even if can_trade false, allow if confidence > 20
           if confidence >= 20:
               return True, f"⚠️ BTC {regime_name} ({confidence}%) - allowing anyway"
           return False, f"❌ BTC {regime_name} ({confidence}%, {consistency}) - {reason}"
   
   def _check_session_strict(self, ohlcv: List[List[float]]) -> Tuple[bool, str]:
       """Volume and volatility check - UPDATED: More lenient"""
       if len(ohlcv) < 5:  # 10 থেকে কমিয়ে 5
           return True, "No data - allowing"
           
       volumes = [c[5] for c in ohlcv[-5:]]  # 10 থেকে কমিয়ে 5
       avg_vol = sum(volumes[:-1]) / (len(volumes)-1) if len(volumes) > 1 else volumes[0]
       last_vol = volumes[-1]
       
       atr = self._calculate_atr(ohlcv[-5:])  # 10 থেকে কমিয়ে 5
       current_price = ohlcv[-1][4]
       atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
       
       # UPDATED: More lenient thresholds
       volume_ok = last_vol > avg_vol * 0.5  # 0.8 থেকে কমিয়ে 0.5
       atr_ok = atr_pct > 0.2  # 0.3 থেকে কমিয়ে 0.2
       
       if volume_ok and atr_ok:
           return True, f"✅ Active: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
       elif volume_ok or atr_ok:
           return True, f"⚠️ Partial: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
       else:
           return False, f"❌ Quiet: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
   
   def _check_mtf(self, direction: str, ohlcv_1h: List[List[float]]) -> bool:
       """1h timeframe confirms - UPDATED: More lenient"""
       if not ohlcv_1h or len(ohlcv_1h) < 10:  # 21 থেকে কমিয়ে 10
           return True
           
       closes = [c[4] for c in ohlcv_1h[-10:]]  # 21 থেকে কমিয়ে 10
       ema5 = sum(closes[-5:]) / 5  # 9 থেকে কমিয়ে 5
       ema10 = sum(closes[-10:]) / 10  # 21 থেকে কমিয়ে 10
       
       h1_bullish = ema5 > ema10
       
       # Check simple trend as fallback
       price_trend = closes[-1] > closes[0]
       
       if direction == "LONG":
           return h1_bullish or price_trend
       else:
           return (not h1_bullish) or (not price_trend)
   
   def _check_liquidity(self, direction: str, ohlcv: List[List[float]]) -> bool:
       """Near support/resistance - UPDATED: Wider range"""
       if len(ohlcv) < 10:  # 20 থেকে কমিয়ে 10
           return True
           
       current = ohlcv[-1][4]
       highs = [c[2] for c in ohlcv[-10:]]
       lows = [c[3] for c in ohlcv[-10:]]
       
       recent_high = max(highs)
       recent_low = min(lows)
       range_size = recent_high - recent_low
       
       # UPDATED: Wider zone (30% instead of 20%)
       near_support = current < recent_low + range_size * 0.3
       near_resistance = current > recent_high - range_size * 0.3
       
       if direction == "LONG":
           return near_support
       else:
           return near_resistance
   
   def _check_funding(self, direction: str, funding_rate: float) -> bool:
       """Not extreme funding - UPDATED: More lenient"""
       # UPDATED: Higher thresholds
       extreme_long = funding_rate > 0.002  # 0.001 থেকে বাড়িয়ে 0.002
       extreme_short = funding_rate < -0.002  # -0.001 থেকে কমিয়ে -0.002
       
       if direction == "LONG" and extreme_long:
           return False
       if direction == "SHORT" and extreme_short:
           return False
           
       return True
   
   def _check_cooldown(self, symbol: str) -> bool:
       """30 min cooldown - keeping as is"""
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