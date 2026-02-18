"""
ARUNABHA EXTREME FEAR BOT v1.0
Simplified config - Only essential settings
"""

import os
from typing import List

# ─── Telegram ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("PORT", "8080"))

# ─── Exchange ─────────────────────────────────────────
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")
COINDCX_API_KEY = os.getenv("COINDCX_API_KEY", "")
COINDCX_SECRET = os.getenv("COINDCX_SECRET", "")
PRIMARY_EXCHANGE = os.getenv("PRIMARY_EXCHANGE", "binance")

# ─── Trading Universe ─────────────────────────────────
TRADING_PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "LINK/USDT", "ADA/USDT"]


# ─── Timeframes ───────────────────────────────────────
# 🆕 FIXED: ws_feed.py needs this
TIMEFRAMES = ["5m", "15m", "1h"]  # WebSocket monitors all
TIMEFRAME = "15m"  # Main trading timeframe

# ─── Core Signal Thresholds ───────────────────────────
RSI_PERIOD = 14
RSI_OVERSOLD = 38      # Relaxed for fear market
RSI_OVERBOUGHT = 62
EMA_FAST = 9
EMA_SLOW = 21
VOLUME_MULTIPLIER = 1.0  # Base volume enough

# ─── Risk Management ────────────────────────────────────
ATR_PERIOD = 14
ATR_SL_MULT = 1.5
ATR_TP_MULT = 3.0      # 2x = realistic target
MIN_RR_RATIO = 2.0
LEVERAGE = 15
RISK_PCT = 1.5         # Fixed 1.5% risk per trade

# ─── Extreme Fear Engine ────────────────────────────────
EXTREME_FEAR_RSI = 30          # RSI < 30 = panic
EXTREME_FEAR_VOLUME_MULT = 2.0  # 2x volume spike
BEAR_TRAP_WICK_MULT = 2.0       # Lower wick 2x body
LIQUIDITY_SWEEP_PCT = 0.3       # 0.3% break + reclaim
FUNDING_EXTREME = -0.0005       # -0.05% funding

# ─── Simple Filters (6 only) ───────────────────────────
FILTERS = {
    "session_active": True,      # Volume/volatility check
    "btc_trend_ok": True,        # No conflict with BTC
    "mtf_confirm": True,         # 1h confirms 15m
    "liquidity_zone": True,      # Near support/resistance
    "funding_safe": True,        # Not extreme crowded
    "cooldown_ok": True,         # 30 min per coin
}
MIN_FILTERS_PASS = 4  # 4/6 = 67% enough

# ─── Limits ────────────────────────────────────────────
MAX_SIGNALS_DAY = 3      # Max 3 trades/day (fear market)
MAX_CONCURRENT = 1       # Only 1 active trade
COOLDOWN_MINUTES = 30    # Same coin 30 min wait
FEAR_INDEX_STOP = 75     # >75 fear = stop trading

# ─── Session Times (IST) ──────────────────────────────
LONDON_OPEN_IST = 13     # 13:30 IST
NY_OPEN_IST = 18         # 18:00 IST
ASIA_CLOSE_IST = 9       # 09:00 IST

# ─── Bot Info ───────────────────────────────────────────
BOT_NAME = "ARUNABHA EXTREME FEAR"
BOT_VERSION = "v1.0"

# ─── Fear Index API ────────────────────────────────────
FEAR_GREED_API_URL = "https://api.alternative.me/fng/?limit=1"
