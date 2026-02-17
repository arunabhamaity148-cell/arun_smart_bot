"""
ARUNABHA SMART v10.0 - Configuration
All settings in one place. Override via environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import List


# ─── Telegram ──────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL", "")           # e.g. https://your-app.railway.app
WEBHOOK_PORT       = int(os.getenv("PORT", "8080"))
WEBHOOK_PATH       = "/webhook"
HEALTH_PATH        = "/health"

# ─── Exchange API Keys ──────────────────────────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET     = os.getenv("BINANCE_SECRET", "")
COINDCX_API_KEY    = os.getenv("COINDCX_API_KEY", "")
COINDCX_SECRET     = os.getenv("COINDCX_SECRET", "")
PRIMARY_EXCHANGE   = os.getenv("PRIMARY_EXCHANGE", "binance")   # binance | coindcx

# ─── Trading Universe ───────────────────────────────────────────────────────
TRADING_PAIRS: List[str] = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "LINK/USDT",
    "ADA/USDT",
]
BTC_PAIR = "BTC/USDT"   # Reference pair for correlation

# ─── Signal Parameters (Simple robust rules) ───────────────────────────────
RSI_PERIOD       = 14
RSI_OVERSOLD     = 35       # LONG  threshold
RSI_OVERBOUGHT   = 65       # SHORT threshold
EMA_FAST         = 9
EMA_SLOW         = 21
VOLUME_MULTIPLIER = 1.2     # Minimum volume vs average
ATR_PERIOD       = 14
ATR_SL_MULT      = 1.5      # Stop-loss = 1.5x ATR
ATR_TP_MULT      = 2.5      # Take-profit = 2.5x ATR
MIN_RR_RATIO     = 1.5      # Minimum risk:reward

# ─── Timeframes ─────────────────────────────────────────────────────────────
TIMEFRAMES = ["5m", "15m", "1h"]
DEFAULT_TF = "15m"

# ─── Smart Filters ──────────────────────────────────────────────────────────
MIN_FILTERS_PASS = 4        # At least 4 out of 6 context filters must pass
ORDERBOOK_DEPTH  = 20       # Levels to fetch for bid/ask pressure

# ─── Risk Management ────────────────────────────────────────────────────────
LEVERAGE          = 15
RISK_PCT_MIN      = 1.0     # Min risk % per trade
RISK_PCT_MAX      = 2.0     # Max risk % per trade
ACCOUNT_SIZE_USD  = float(os.getenv("ACCOUNT_SIZE_USD", "1000"))

# ─── Signal Limits ──────────────────────────────────────────────────────────
MAX_SIGNALS_DAY   = 6
MAX_CONCURRENT    = 2

# ─── Sleep Schedule (IST = UTC+5:30) ───────────────────────────────────────
# IST 1 AM  = UTC 19:30 previous day
# IST 7 AM  = UTC 01:30
SLEEP_START_UTC_H = 19
SLEEP_START_UTC_M = 30
SLEEP_END_UTC_H   = 1
SLEEP_END_UTC_M   = 30

# ─── Scan Interval ──────────────────────────────────────────────────────────
SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "300"))   # 5 minutes

# ─── Lookback windows ───────────────────────────────────────────────────────
CANDLE_LOOKBACK       = 100    # Candles to fetch per pair
CORRELATION_LOOKBACK  = 20     # Bars for BTC correlation
VOLUME_LOOKBACK       = 20     # Bars for average volume
LIQ_LOOKBACK          = 50     # Bars to build liquidation map
ATR_WINDOW            = 14

# ─── Volatility thresholds (for timeframe selection) ───────────────────────
LOW_VOL_ATR_PCT   = 0.3     # ATR/price < 0.3% → use 5m
MED_VOL_ATR_PCT   = 0.8     # ATR/price 0.3–0.8% → use 15m
                             # ATR/price > 0.8%  → use 1h

# ─── Correlation thresholds ─────────────────────────────────────────────────
CORR_DIVERGENCE_THRESHOLD = 0.4    # |corr| < 0.4 → alt diverging from BTC
CORR_STRONG_AGREEMENT     = 0.7    # corr > 0.7  → strong BTC agreement

# ─── Orderflow thresholds ───────────────────────────────────────────────────
OB_PRESSURE_THRESHOLD = 0.60       # bid_vol/(bid+ask) > 0.60 → bullish pressure

# ─── Liquidation cluster thresholds ─────────────────────────────────────────
LIQ_ZONE_PCT   = 0.5               # ±0.5% band around price counts as near cluster

# ─── Bot metadata ───────────────────────────────────────────────────────────
BOT_NAME    = "ARUNABHA SMART"
BOT_VERSION = "v10.0"
BOT_EMOJI   = "⚡"