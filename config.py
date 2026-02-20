"""
ARUNABHA EXTREME FEAR BOT v3.2
Conservative Elite Institutional Configuration
UPDATED FOR LIVE MARKET - OPTION 3 (Balanced Risk)
"""

import os
import logging
from typing import List

logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# TELEGRAM CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("PORT", "8080"))

# ═════════════════════════════════════════════════════════════════════════════
# EXCHANGE CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")
COINDCX_API_KEY = os.getenv("COINDCX_API_KEY", "")
COINDCX_SECRET = os.getenv("COINDCX_SECRET", "")
PRIMARY_EXCHANGE = os.getenv("PRIMARY_EXCHANGE", "binance")

# ═════════════════════════════════════════════════════════════════════════════
# TRADING UNIVERSE - Elite Mode: Focused Quality
# ═════════════════════════════════════════════════════════════════════════════

TRADING_PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAMES = ["5m", "15m", "1h"]
TIMEFRAME = "15m"

# ═════════════════════════════════════════════════════════════════════════════
# ACCOUNT CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", "60000"))  # ₹60,000 for ₹500/day target

# ═════════════════════════════════════════════════════════════════════════════
# CORE SIGNAL THRESHOLDS - OPTION 3 (Balanced)
# ═════════════════════════════════════════════════════════════════════════════

RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 200
VOLUME_MULTIPLIER = 1.1

# ═════════════════════════════════════════════════════════════════════════════
# RISK MANAGEMENT - TIGHTER FOR SAFETY
# ═════════════════════════════════════════════════════════════════════════════

ATR_PERIOD = 14
ATR_SL_MULT = 1.3        # 1.5 → 1.3 (টাইট SL - লোকসান কমাবে)
ATR_TP_MULT = 2.8        # 3.0 → 2.8 (R/R 2.15:1)

MIN_RR_RATIO = 1.8       # 2.0 → 1.8 (আরও ট্রেডের জন্য)
LEVERAGE = 8             # 10 → 8 (কম লিভারেজ = কম রিস্ক)
RISK_PCT = 0.7           # 1.0% → 0.7% (নিরাপদ)

# ═════════════════════════════════════════════════════════════════════════════
# EXTREME FEAR ENGINE - OPTION 3
# ═════════════════════════════════════════════════════════════════════════════

EXTREME_FEAR_RSI = 24
EXTREME_FEAR_VOLUME_MULT = 2.0
BEAR_TRAP_WICK_MULT = 2.0
LIQUIDITY_SWEEP_PCT = 0.3
FUNDING_EXTREME = -0.0005

# OPTION 3: Balanced thresholds
MIN_SCORE_TO_TRADE = 25        # 45 → 25 (আরও ট্রেড)
REQUIRE_EMA200_CONFIRM = True
REQUIRE_STRUCTURE_SHIFT = False  # True → False (নরম)
ENTRY_CONFIRMATION_WAIT = True

# ═════════════════════════════════════════════════════════════════════════════
# SIMPLE FILTERS - OPTION 3
# ═════════════════════════════════════════════════════════════════════════════

FILTERS = {
    "session_active": True,
    "btc_trend_ok": True,
    "mtf_confirm": True,
    "liquidity_zone": True,
    "funding_safe": True,
    "cooldown_ok": True,
    "ema200_confirm": True,
    "structure_shift": False,
}

MIN_FILTERS_PASS = 3           # 4 → 3 (আরও ট্রেড)

# ═════════════════════════════════════════════════════════════════════════════
# TRADE LIMITS - OPTION 3
# ═════════════════════════════════════════════════════════════════════════════

MAX_SIGNALS_DAY = 5            # 4 → 5 (টার্গেট ৫-৬ সিগন্যাল)
MAX_CONCURRENT = 1             # Single exposure only (নিরাপদ)
COOLDOWN_MINUTES = 20          # 30 → 20 (দ্রুত পরবর্তী ট্রেড)

FEAR_INDEX_STOP = 85           # 80 → 85 (greed-এও ট্রেড)

# ═════════════════════════════════════════════════════════════════════════════
# SESSION TIMES (IST)
# ═════════════════════════════════════════════════════════════════════════════

LONDON_OPEN_IST = 13
NY_OPEN_IST = 18
ASIA_CLOSE_IST = 9

ELITE_SESSIONS_ONLY = False    # সব সেশনে ট্রেড

# ═════════════════════════════════════════════════════════════════════════════
# TRADE MANAGEMENT - TIGHTER FOR SAFETY
# ═════════════════════════════════════════════════════════════════════════════

BREAK_EVEN_TRIGGER_PCT = 0.4   # 0.5 → 0.4 (আগেই break-even)
PARTIAL_EXIT_R = 0.8           # 1.0 → 0.8 (আগেই পার্শিয়াল এক্সিট)

MAX_CONSECUTIVE_SL = 2         # 3 → 2 (২টা লোকসানে স্টপ)

# ═════════════════════════════════════════════════════════════════════════════
# BOT IDENTITY
# ═════════════════════════════════════════════════════════════════════════════

BOT_NAME = "ARUNABHA BALANCED ELITE"
BOT_VERSION = "v3.2-Option3"

# ═════════════════════════════════════════════════════════════════════════════
# EXTERNAL APIS
# ═════════════════════════════════════════════════════════════════════════════

FEAR_GREED_API_URL = "https://api.alternative.me/fng/?limit=1"

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

def validate_config():
    """Light validation - won't crash"""
    checks = {
        "MIN_RR_RATIO >= 1.5": MIN_RR_RATIO >= 1.5,
        "RISK_PCT <= 1.0": RISK_PCT <= 1.0,
        "MAX_SIGNALS_DAY <= 6": MAX_SIGNALS_DAY <= 6,
        "LEVERAGE <= 10": LEVERAGE <= 10,
    }
    
    failed = [k for k, v in checks.items() if not v]
    if failed:
        print(f"⚠️ Config warnings: {failed}")
    
    return True

# Auto-validate
validate_config()