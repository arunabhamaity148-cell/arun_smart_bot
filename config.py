"""
ARUNABHA EXTREME FEAR BOT v2.1
Balanced configuration
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
TIMEFRAMES = ["5m", "15m", "1h"]
TIMEFRAME = "15m"

# ─── Core Signal Thresholds ───────────────────────────
RSI_PERIOD = 14
RSI_OVERSOLD = 38
RSI_OVERBOUGHT = 62
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 200
VOLUME_MULTIPLIER = 1.0

# ─── Risk Management ────────────────────────────────────
ATR_PERIOD = 14
ATR_SL_MULT = 1.8
ATR_TP_MULT = 3.6
MIN_RR_RATIO = 2.0
LEVERAGE = 15
RISK_PCT = 1.5

# ─── Extreme Fear Engine ────────────────────────────────
EXTREME_FEAR_RSI = 30
EXTREME_FEAR_VOLUME_MULT = 2.0
BEAR_TRAP_WICK_MULT = 2.0
LIQUIDITY_SWEEP_PCT = 0.3
FUNDING_EXTREME = -0.0005

# 🆕 BALANCED SETTINGS
MIN_SCORE_TO_TRADE = 50
REQUIRE_EMA200_CONFIRM = True
REQUIRE_STRUCTURE_SHIFT = True
ENTRY_CONFIRMATION_WAIT = True

# ─── Simple Filters ───────────────────────────────────
FILTERS = {
    "session_active": True,
    "btc_trend_ok": True,
    "mtf_confirm": True,
    "liquidity_zone": True,
    "funding_safe": True,
    "cooldown_ok": True,
    "ema200_confirm": True,
    "structure_shift": True,
}
MIN_FILTERS_PASS = 5  # 🆕 Reduced from 6

# ─── Limits ────────────────────────────────────────────
MAX_SIGNALS_DAY = 5  # 🆕 Increased from 3
MAX_CONCURRENT = 1
COOLDOWN_MINUTES = 30
FEAR_INDEX_STOP = 80  # 🆕 Greed block threshold

# ─── Session Times (IST) ──────────────────────────────
LONDON_OPEN_IST = 13
NY_OPEN_IST = 18
ASIA_CLOSE_IST = 9

# ─── Bot Info ───────────────────────────────────────────
BOT_NAME = "ARUNABHA EXTREME FEAR"
BOT_VERSION = "v2.1"

# ─── Fear Index API ────────────────────────────────────
FEAR_GREED_API_URL = "https://api.alternative.me/fng/?limit=1"
