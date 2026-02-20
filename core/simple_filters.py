"""
ARUNABHA SIMPLE FILTERS v2.4
Balanced filtering - UPDATED: OPTION 3
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta

import config
from .btc_regime_detector import btc_detector, BTCRegime

logger = logging.getLogger(__name__)


class SimpleFilters:
   """
   6 balanced filters - OPTION 3: More lenient
   """
   
   def __init__(self):
       self.cooldown_map = {}
       self.btc_min_confidence = 25  # 30 → 25
       
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
       
       # OPTION 3: Mandatory now requires at least 1 of 3 (session, btc, mtf)
       mandatory_count = sum([session_ok, btc_ok, mtf_ok])
       mandatory_pass = mandatory_count >= 1  # 2 → 1
       
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
       BTC Regime Detection - OPTION 3
       """
       if not btc_15m or len(btc_15m) < 30:  # 50 → 30
           return True, "⚠️ Limited BTC data - allowing"
       
       analysis = btc_detector.analyze(btc_15m, btc_1h, btc_4h)
       
       can_trade, reason = btc_detector.should_trade_alt(
           direction, 
           min_confidence=self.btc_min_confidence
       )
       
       regime_name = analysis.regime.value.replace("_", " ").upper()
       confidence = analysis.confidence
       
       if can_trade or confidence >= 20:  # 20+ confidence থাকলে অ্যালাউ
           return True, f"✅ BTC {regime_name} ({confidence}%)"
       else:
           return False, f"❌ BTC {regime_name} ({confidence}%) - {reason}"
   
   def _check_session_strict(self, ohlcv: List[List[float]]) -> Tuple[bool, str]:
       """Volume and volatility check - OPTION 3: More lenient"""
       if len(ohlcv) < 3:
           return True, "No data - allowing"
           
       volumes = [c[5] for c in ohlcv[-5:]]
       avg_vol = sum(volumes[:-1]) / (len(volumes)-1) if len(volumes) > 1 else volumes[0]
       last_vol = volumes[-1]
       
       atr = self._calculate_atr(ohlcv[-5:])
       current_price = ohlcv[-1][4]
       atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
       
       # OPTION 3: Very lenient thresholds
       volume_ok = last_vol > avg_vol * 0.3  # 0.5 → 0.3
       atr_ok = atr_pct > 0.15  # 0.2 → 0.15
       
       if volume_ok or atr_ok:
           return True, f"✅ Active: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
       else:
           return False, f"❌ Quiet: Vol {last_vol/avg_vol:.1f}x, ATR {atr_pct:.2f}%"
   
   def _check_mtf(self, direction: str, ohlcv_1h: List[List[float]]) -> bool:
       """1h timeframe confirms - OPTION 3: Very lenient"""
       if not ohlcv_1h or len(ohlcv_1h) < 5:
           return True
           
       closes = [c[4] for c in ohlcv_1h[-5:]]
       ema3 = sum(closes[-3:]) / 3
       ema5 = sum(closes[-5:]) / 5
       
       h1_bullish = ema3 > ema5
       price_trend = closes[-1] > closes[0]
       
       if direction == "LONG":
           return h1_bullish or price_trend
       else:
           return (not h1_bullish) or (not price_trend)
   
   def _check_liquidity(self, direction: str, ohlcv: List[List[float]]) -> bool:
       """Near support/resistance - OPTION 3: Wider range"""
       if len(ohlcv) < 5:
           return True
           
       current = ohlcv[-1][4]
       highs = [c[2] for c in ohlcv[-10:]]
       lows = [c[3] for c in ohlcv[-10:]]
       
       recent_high = max(highs)
       recent_low = min(lows)
       range_size = recent_high - recent_low
       
       # OPTION 3: 40% zone
       near_support = current < recent_low + range_size * 0.4
       near_resistance = current > recent_high - range_size * 0.4
       
       if direction == "LONG":
           return near_support
       else:
           return near_resistance
   
   def _check_funding(self, direction: str, funding_rate: float) -> bool:
       """Not extreme funding - OPTION 3: Very lenient"""
       extreme_long = funding_rate > 0.003  # 0.002 → 0.003
       extreme_short = funding_rate < -0.003  # -0.002 → -0.003
       
       if direction == "LONG" and extreme_long:
           return False
       if direction == "SHORT" and extreme_short:
           return False
           
       return True
   
   def _check_cooldown(self, symbol: str) -> bool:
       """Cooldown check"""
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