"""
ARUNABHA v4.0 - SHARED INDICATORS
এক জায়গায় সব ইন্ডিকেটর ক্যালকুলেশন
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def calculate_atr(ohlcv: List[List[float]], period: int = 14) -> float:
    """
    ATR ক্যালকুলেশন - সব জায়গা থেকে এই ফাংশন কল করবে
    """
    if len(ohlcv) < period + 1:
        return 0.0
    
    trs = []
    for i in range(1, len(ohlcv)):
        high = ohlcv[i][2]
        low = ohlcv[i][3]
        prev_close = ohlcv[i-1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    
    return sum(trs[-period:]) / period


def calculate_adx(ohlcv: List[List[float]], period: int = 14) -> float:
    """
    ADX ক্যালকুলেশন - market_detector এবং btc_regime_detector উভয়েই ইউজ করবে
    """
    if len(ohlcv) < period + 1:
        return 20.0
    
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    closes = [c[4] for c in ohlcv]
    
    tr_list = []
    plus_dm = []
    minus_dm = []
    
    for i in range(1, len(ohlcv)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        tr_list.append(tr)
        
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
    
    atr = sum(tr_list[-period:]) / period
    plus_di = (sum(plus_dm[-period:]) / atr) * 100 if atr > 0 else 0
    minus_di = (sum(minus_dm[-period:]) / atr) * 100 if atr > 0 else 0
    
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
    
    return dx


def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """
    RSI ক্যালকুলেশন
    """
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


def calculate_ema(values: List[float], period: int) -> float:
    """
    EMA ক্যালকুলেশন
    """
    if len(values) < period:
        return sum(values) / len(values)
    
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    
    for price in values[period:]:
        ema = (price * k) + (ema * (1 - k))
    
    return ema