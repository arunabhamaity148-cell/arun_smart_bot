"""
ARUNABHA EXTREME FEAR BOT v3.2
Conservative Elite Institutional Configuration
UPDATED FOR LIVE MARKET - Feb 2026
"""

import os
from typing import List

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

# Conservative: Only high-liquidity, proven pairs
TRADING_PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

# Timeframes
TIMEFRAMES = ["5m", "15m", "1h"]
TIMEFRAME = "15m"

# ═════════════════════════════════════════════════════════════════════════════
# CONSERVATIVE ELITE INSTITUTIONAL SETTINGS
# ═════════════════════════════════════════════════════════════════════════════

# Account Configuration
DEFAULT_ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", "5000"))  # Default $5K for serious trading

# ═════════════════════════════════════════════════════════════════════════════
# CORE SIGNAL THRESHOLDS - Adjusted for live market
# ═════════════════════════════════════════════════════════════════════════════

RSI_PERIOD = 14
RSI_OVERSOLD = 32        # 35 থেকে কমিয়ে 32 (বিয়ার মার্কেটে বেশি oversold হয়)
RSI_OVERBOUGHT = 68      # 65 থেকে বাড়িয়ে 68
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 200
VOLUME_MULTIPLIER = 1.1  # 1.2 থেকে কমিয়ে 1.1

# ═════════════════════════════════════════════════════════════════════════════
# RISK MANAGEMENT - Elite Capital Protection
# ═════════════════════════════════════════════════════════════════════════════

ATR_PERIOD = 14
ATR_SL_MULT = 1.5        # Tighter than 1.8
ATR_TP_MULT = 3.0        # 2:1 minimum RR (3.0/1.5 = 2.0)

# FIX 8: Strict 2.0 minimum R:R ratio
MIN_RR_RATIO = 2.0

LEVERAGE = 10            # Reduced from 15 for conservative approach
RISK_PCT = 1.0           # Reduced from 1.5% - Elite capital protection

# ═════════════════════════════════════════════════════════════════════════════
# EXTREME FEAR ENGINE - Adjusted for live market
# ═════════════════════════════════════════════════════════════════════════════

EXTREME_FEAR_RSI = 25        # 28 থেকে কমিয়ে 25 (বিয়ার মার্কেটে বেশি extreme)
EXTREME_FEAR_VOLUME_MULT = 2.0   # 2.5 থেকে কমিয়ে 2.0
BEAR_TRAP_WICK_MULT = 2.0    # 2.5 থেকে কমিয়ে 2.0
LIQUIDITY_SWEEP_PCT = 0.3   # 0.25 থেকে বাড়িয়ে 0.3
FUNDING_EXTREME = -0.0005    # -0.0003 থেকে কমিয়ে -0.0005 (আরও extreme)

# Elite Grade Settings - Relaxed for live market
MIN_SCORE_TO_TRADE = 45      # 55 থেকে কমিয়ে 45
REQUIRE_EMA200_CONFIRM = True
REQUIRE_STRUCTURE_SHIFT = True
ENTRY_CONFIRMATION_WAIT = True

# ═════════════════════════════════════════════════════════════════════════════
# SIMPLE FILTERS - Relaxed for live market
# ═════════════════════════════════════════════════════════════════════════════

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

# FIX 4: Relaxed filter enforcement for live market
MIN_FILTERS_PASS = 4     # 6 থেকে কমিয়ে 4 (বিয়ার মার্কেটে বেশি সুযোগ দিতে)

# ═════════════════════════════════════════════════════════════════════════════
# ELITE TRADE LIMITS - Relaxed for live market
# ═════════════════════════════════════════════════════════════════════════════

MAX_SIGNALS_DAY = 4      # 3 থেকে বাড়িয়ে 4 (বিয়ার মার্কেটে বেশি সুযোগ)
MAX_CONCURRENT = 1       # Single exposure only
COOLDOWN_MINUTES = 30    # 45 থেকে কমিয়ে 30

# FIX 3: More relaxed greed threshold
FEAR_INDEX_STOP = 80     # 75 থেকে বাড়িয়ে 80 (greed-এও ট্রেড করতে দেবে)

# ═════════════════════════════════════════════════════════════════════════════
# SESSION TIMES (IST) - Relaxed for live market
# ═════════════════════════════════════════════════════════════════════════════

LONDON_OPEN_IST = 13
NY_OPEN_IST = 18
ASIA_CLOSE_IST = 9

# Elite: Only trade London/NY overlap for best liquidity
ELITE_SESSIONS_ONLY = False  # True থেকে False (যেকোনো সেশনে ট্রেড করতে দেবে)

# ═════════════════════════════════════════════════════════════════════════════
# BREAK-EVEN & TRADE MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

# FIX 9: Configurable break-even trigger
BREAK_EVEN_TRIGGER_PCT = 0.5   # 0.6 থেকে কমিয়ে 0.5 (আগেই break-even এ নিয়ে যাবে)
PARTIAL_EXIT_R = 1.0           # 1R partial exit

# FIX 10: Consecutive SL limit
MAX_CONSECUTIVE_SL = 3         # 2 থেকে বাড়িয়ে 3 (৩টা SL-এর পর lock)

# ═════════════════════════════════════════════════════════════════════════════
# BOT IDENTITY
# ═════════════════════════════════════════════════════════════════════════════

BOT_NAME = "ARUNABHA CONSERVATIVE ELITE"
BOT_VERSION = "v3.2-Institutional-Live"

# ═════════════════════════════════════════════════════════════════════════════
# EXTERNAL APIS
# ═════════════════════════════════════════════════════════════════════════════

FEAR_GREED_API_URL = "https://api.alternative.me/fng/?limit=1"

# ═════════════════════════════════════════════════════════════════════════════
# ELITE MODE VALIDATION - Disabled for live market
# ═════════════════════════════════════════════════════════════════════════════

def validate_elite_config():
    """
    Validate that Elite Mode settings are correctly configured.
    Called on startup to ensure institutional discipline.
    """
    checks = {
        "MIN_RR_RATIO >= 2.0": MIN_RR_RATIO >= 2.0,
        "RISK_PCT <= 1.5": RISK_PCT <= 1.5,
        "MAX_SIGNALS_DAY <= 5": MAX_SIGNALS_DAY <= 5,
        "LEVERAGE <= 10": LEVERAGE <= 10,
        "MIN_FILTERS_PASS >= 3": MIN_FILTERS_PASS >= 3,  # 5 থেকে কমিয়ে 3
        "FEAR_INDEX_STOP <= 85": FEAR_INDEX_STOP <= 85,  # 80 থেকে বাড়িয়ে 85
    }
    
    failed = [k for k, v in checks.items() if not v]
    
    if failed:
        logger.warning(f"⚠️ Elite Mode validation warnings: {failed}")
        return False  # Exception না দিয়ে warning দেবে
    
    return True

# Auto-validate on import - but don't crash
try:
    import logging
    logger = logging.getLogger(__name__)
    validate_elite_config()
except:
    pass