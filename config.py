"""
ARUNABHA EXTREME FEAR BOT v3.2
Conservative Elite Institutional Configuration
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
# CORE SIGNAL THRESHOLDS - Elite Strict Mode
# ═════════════════════════════════════════════════════════════════════════════

RSI_PERIOD = 14
RSI_OVERSOLD = 35        # More conservative than 38
RSI_OVERBOUGHT = 65      # More conservative than 62
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 200
VOLUME_MULTIPLIER = 1.2  # Increased from 1.0 for stronger confirmation

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
# EXTREME FEAR ENGINE - Elite Mode
# ═════════════════════════════════════════════════════════════════════════════

EXTREME_FEAR_RSI = 28        # More conservative than 30
EXTREME_FEAR_VOLUME_MULT = 2.5   # Increased from 2.0
BEAR_TRAP_WICK_MULT = 2.5    # Increased from 2.0
LIQUIDITY_SWEEP_PCT = 0.25   # Tighter than 0.3
FUNDING_EXTREME = -0.0003    # More conservative than -0.0005

# Elite Grade Settings - FIX 7: Only A/A+ allowed
MIN_SCORE_TO_TRADE = 55      # Increased from 50
REQUIRE_EMA200_CONFIRM = True
REQUIRE_STRUCTURE_SHIFT = True
ENTRY_CONFIRMATION_WAIT = True

# ═════════════════════════════════════════════════════════════════════════════
# SIMPLE FILTERS - Elite Validation
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

# FIX 4: Strict filter enforcement
MIN_FILTERS_PASS = 6     # All 6 must pass (was 5)

# ═════════════════════════════════════════════════════════════════════════════
# ELITE TRADE LIMITS - Quality Over Quantity
# ═════════════════════════════════════════════════════════════════════════════

MAX_SIGNALS_DAY = 3      # Strict 2-3 high-quality trades per day
MAX_CONCURRENT = 1       # Single exposure only
COOLDOWN_MINUTES = 45    # Increased from 30 for selectivity

# FIX 3: More conservative greed threshold
FEAR_INDEX_STOP = 75     # Block above 75 (was 80)

# ═════════════════════════════════════════════════════════════════════════════
# SESSION TIMES (IST) - Elite: Only Major Sessions
# ═════════════════════════════════════════════════════════════════════════════

LONDON_OPEN_IST = 13
NY_OPEN_IST = 18
ASIA_CLOSE_IST = 9

# Elite: Only trade London/NY overlap for best liquidity
ELITE_SESSIONS_ONLY = True

# ═════════════════════════════════════════════════════════════════════════════
# BREAK-EVEN & TRADE MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

# FIX 9: Configurable break-even trigger
BREAK_EVEN_TRIGGER_PCT = 0.6   # 0.6R for break-even (conservative)
PARTIAL_EXIT_R = 1.0           # 1R partial exit

# FIX 10: Consecutive SL limit
MAX_CONSECUTIVE_SL = 2         # Day lock on 3rd loss

# ═════════════════════════════════════════════════════════════════════════════
# BOT IDENTITY
# ═════════════════════════════════════════════════════════════════════════════

BOT_NAME = "ARUNABHA CONSERVATIVE ELITE"
BOT_VERSION = "v3.2-Institutional"

# ═════════════════════════════════════════════════════════════════════════════
# EXTERNAL APIS
# ═════════════════════════════════════════════════════════════════════════════

FEAR_GREED_API_URL = "https://api.alternative.me/fng/?limit=1"

# ═════════════════════════════════════════════════════════════════════════════
# ELITE MODE VALIDATION
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
        "MIN_FILTERS_PASS >= 5": MIN_FILTERS_PASS >= 5,
        "FEAR_INDEX_STOP <= 80": FEAR_INDEX_STOP <= 80,
    }
    
    failed = [k for k, v in checks.items() if not v]
    
    if failed:
        raise ValueError(f"Elite Mode validation failed: {failed}")
    
    return True

# Auto-validate on import
validate_elite_config()
