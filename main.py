"""
ARUNABHA SMART v10.2 — Main Bot
════════════════════════════════
Adaptive strategy bot — market regime auto-detection + exit management.

Architecture:
  • aiohttp web server        — health + Telegram webhook
  • BinanceWSFeed             — real-time kline via WebSocket (no polling)
  • FundingRateFilter         — async, 8-min cache
  • Market Regime Detector    — auto-switches strategy per regime
  • ExitManager               — trailing stop + partial TP alerts
  • Candle-close callback     — scans + updates exits on every candle close

Regimes:
  📈 TRENDING     → RSI 35/65, full position, SL 1.5×ATR, TP 2.5×ATR
  ↔️  RANGING      → RSI 30/70, 0.7× position, SL 1.2×ATR, TP 1.8×ATR
  😱 EXTREME_FEAR → RSI 25/75, 0.5× position, SL 2.0×ATR, TP 3.5×ATR

Exit Rules:
  1× RR  → SL breakeven-এ move
  1.5× RR → 50% partial close + trailing stop চালু
  2.5× RR → Full TP (বা regime TP mult × ATR)
  Always  → Hard SL

Required env vars:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEBHOOK_URL,
  BINANCE_API_KEY, BINANCE_SECRET, PORT
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Set

from aiohttp import web
from telegram import Update

import config
from alerts.telegram_alerts        import TelegramAlerts
from core.smart_signal             import generate_signal, SignalResult
from core.exit_strategy            import ExitManager
from exchanges.exchange_manager    import ExchangeManager
from exchanges.ws_feed             import BinanceWSFeed
from exchanges.funding_rate_filter import FundingRateFilter
from utils.time_utils              import is_sleep_time, today_ist_str, ts_label

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream = sys.stdout,
)
logger = logging.getLogger("arunabha")


# ─── Shared state ─────────────────────────────────────────────────────────────

def _fresh_daily_stats() -> Dict[str, Any]:
    return {
        "date":          today_ist_str(),
        "total_signals": 0,
        "longs":         0,
        "shorts":        0,
        "concurrent":    0,
        "regime":        "UNKNOWN",
        "pairs":         [p.replace("/", "") for p in config.TRADING_PAIRS],
    }


STATE: Dict[str, Any] = {
    "daily_stats":    _fresh_daily_stats(),
    "signals_today":  [],
    "active_signals": set(),
    "last_scan":      None,
    "current_regime": "UNKNOWN",
}

_scan_locks: Dict[str, asyncio.Lock] = {
    sym: asyncio.Lock() for sym in config.TRADING_PAIRS
}


def _maybe_reset_day() -> None:
    today = today_ist_str()
    if STATE["daily_stats"]["date"] != today:
        logger.info("New IST day — resetting daily stats")
        STATE["daily_stats"]   = _fresh_daily_stats()
        STATE["signals_today"] = []


# ─── Exit update (runs on every candle close for active trades) ───────────────

async def update_exits(
    symbol:   str,
    tf:       str,
    exchange: ExchangeManager,
    exit_mgr: ExitManager,
) -> None:
    """
    For every active trade, check if SL/TP/Trail has been hit
    on the latest closed candle. Fires Telegram alerts automatically.
    """
    active_trades = exit_mgr.get_active()
    if symbol not in active_trades:
        return

    trade = active_trades[symbol]

    # Only update on the timeframe the trade was entered on
    if tf != trade.timeframe:
        return

    try:
        recent = await exchange.fetch_ohlcv(symbol, tf, limit=3)
        if not recent:
            return
        last_candle = recent[-1]
        high  = float(last_candle[2])
        low   = float(last_candle[3])
        close = float(last_candle[4])
    except Exception as exc:
        logger.warning("Exit update fetch failed %s: %s", symbol, exc)
        return

    reason, price = await exit_mgr.update_trade(trade, high, low, close)

    if reason in ("SL", "TP", "TRAIL_STOP"):
        # Trade closed — remove from active signals
        STATE["active_signals"].discard(symbol)
        exit_mgr.close_trade(symbol)
        logger.info(
            "🏁 Trade closed %s | Reason=%s Price=%.4f",
            symbol, reason, price,
        )
    elif reason == "PARTIAL_TP":
        logger.info(
            "🟡 Partial TP %s @ %.4f | Trail active",
            symbol, price,
        )


# ─── Single-pair signal scan ──────────────────────────────────────────────────

async def scan_symbol(
    symbol:   str,
    timeframe: str,
    exchange:  ExchangeManager,
    alerts:    TelegramAlerts,
    funding:   FundingRateFilter,
    exit_mgr:  ExitManager,
) -> None:
    """
    Triggered on every candle close.
    1. Updates open trade exits first
    2. Then looks for new signal if slot available
    """
    _maybe_reset_day()

    if is_sleep_time():
        return

    # ── Step 1: Update exits for this symbol ─────────────────────────────────
    await update_exits(symbol, timeframe, exchange, exit_mgr)

    # ── Step 2: Check if we can take a new signal ─────────────────────────────
    stats  = STATE["daily_stats"]
    active: Set[str] = STATE["active_signals"]

    if stats["total_signals"] >= config.MAX_SIGNALS_DAY:
        return
    if len(active) >= config.MAX_CONCURRENT:
        return
    if symbol in active:
        return

    lock = _scan_locks.setdefault(symbol, asyncio.Lock())
    if lock.locked():
        return

    async with lock:
        # ── Fetch data (all from WS cache — zero REST for OHLCV) ─────────────
        try:
            ohlcv    = await exchange.fetch_ohlcv(symbol, timeframe, config.CANDLE_LOOKBACK)
            ohlcv_1h = await exchange.fetch_ohlcv(symbol, "1h",       config.CANDLE_LOOKBACK)
            ob       = await exchange.fetch_orderbook(symbol, config.ORDERBOOK_DEPTH)
        except Exception as exc:
            logger.warning("Data fetch failed %s: %s", symbol, exc)
            return

        # BTC context (15m correlation, 1h regime)
        try:
            btc_ohlcv    = await exchange.fetch_ohlcv(config.BTC_PAIR, "15m", config.CANDLE_LOOKBACK)
            btc_ohlcv_1h = await exchange.fetch_ohlcv(config.BTC_PAIR, "1h",  config.CANDLE_LOOKBACK)
        except Exception:
            btc_ohlcv    = []
            btc_ohlcv_1h = []

        # ── Funding rate (REST, cached 8 min) ─────────────────────────────────
        btc_funding      = await funding.get_funding_rate(config.BTC_PAIR)
        funding_long_ok,  fl = await funding.passes(symbol=symbol, direction="LONG")
        funding_short_ok, fs = await funding.passes(symbol=symbol, direction="SHORT")

        # ── Signal pipeline ───────────────────────────────────────────────────
        try:
            signal: Optional[SignalResult] = generate_signal(
                symbol            = symbol,
                ohlcv             = ohlcv,
                orderbook         = ob,
                btc_ohlcv         = btc_ohlcv,
                account_size_usd  = config.ACCOUNT_SIZE_USD,
                ohlcv_1h          = ohlcv_1h,
                funding_long_ok   = funding_long_ok,
                funding_short_ok  = funding_short_ok,
                funding_long_lbl  = fl,
                funding_short_lbl = fs,
                btc_funding_rate  = btc_funding,
                btc_ohlcv_1h      = btc_ohlcv_1h,
            )
        except Exception as exc:
            logger.error("Signal error %s: %s", symbol, exc, exc_info=True)
            return

        # Update regime in STATE (shown in /status)
        if signal:
            STATE["current_regime"]        = signal.regime
            STATE["daily_stats"]["regime"] = signal.regime

        if signal is None:
            return

        # ── Record signal ─────────────────────────────────────────────────────
        stats["total_signals"] += 1
        if signal.direction == "LONG":
            stats["longs"] += 1
        else:
            stats["shorts"] += 1
        stats["concurrent"] = len(active) + 1

        active.add(symbol)
        STATE["signals_today"].append({
            "symbol":    symbol,
            "direction": signal.direction,
            "time":      ts_label(),
            "rr_ratio":  signal.rr_ratio,
            "quality":   signal.quality,
            "regime":    signal.regime,
        })
        STATE["last_scan"] = datetime.utcnow().isoformat()

        # ── Send entry alert ──────────────────────────────────────────────────
        await alerts.send_signal(signal)

        # ── Register trade with ExitManager ──────────────────────────────────
        exit_mgr.open_trade(signal)

        logger.info(
            "✅ Signal: %s %s [%s] Grade=%s Regime=%s | Today: %d/%d",
            symbol, signal.direction, signal.timeframe,
            signal.quality, signal.regime,
            stats["total_signals"], config.MAX_SIGNALS_DAY,
        )


# ─── WebSocket candle-close callback ─────────────────────────────────────────

def make_candle_callback(
    exchange: ExchangeManager,
    alerts:   TelegramAlerts,
    funding:  FundingRateFilter,
    exit_mgr: ExitManager,
):
    SCAN_TIMEFRAMES = {"5m", "15m", "1h"}

    async def on_candle_close(symbol: str, tf: str, ohlcv: list) -> None:
        if tf not in SCAN_TIMEFRAMES:
            return
        asyncio.create_task(
            scan_symbol(symbol, tf, exchange, alerts, funding, exit_mgr),
            name=f"scan_{symbol}_{tf}",
        )

    return on_candle_close


# ─── aiohttp handlers ────────────────────────────────────────────────────────

async def health_handler(request: web.Request) -> web.Response:
    stats = STATE["daily_stats"]
    active_trades = len(STATE["active_signals"])
    return web.json_response({
        "status":         "ok",
        "bot":            f"{config.BOT_NAME} {config.BOT_VERSION}",
        "signals_today":  stats["total_signals"],
        "active_trades":  active_trades,
        "regime":         STATE.get("current_regime", "UNKNOWN"),
        "last_scan":      STATE.get("last_scan"),
    })


def make_webhook_handler(ptb_app):
    async def webhook_handler(request: web.Request) -> web.Response:
        try:
            data   = await request.json()
            update = Update.de_json(data, ptb_app.bot)
            await ptb_app.process_update(update)
        except Exception as exc:
            logger.error("Webhook error: %s", exc)
        return web.Response(text="ok")
    return webhook_handler


# ─── Entry point ─────────────────────────────────────────────────────────────

async def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)
    if not config.TELEGRAM_CHAT_ID:
        logger.critical("TELEGRAM_CHAT_ID not set")
        sys.exit(1)

    # ── Exchange ──────────────────────────────────────────────────────────────
    exchange = ExchangeManager()
    try:
        await exchange.connect()
    except Exception as exc:
        logger.critical("Exchange failed: %s", exc)
        sys.exit(1)

    # ── Funding rate filter ────────────────────────────────────────────────────
    funding = FundingRateFilter()
    await funding.connect()
    logger.info("💸 Funding rate filter ready")

    # ── Telegram ──────────────────────────────────────────────────────────────
    alerts  = TelegramAlerts(STATE)
    ptb_app = alerts.build_application()
    await ptb_app.initialize()

    if config.WEBHOOK_URL:
        try:
            await ptb_app.bot.set_webhook(f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}")
            logger.info("Webhook set to %s%s", config.WEBHOOK_URL, config.WEBHOOK_PATH)
        except Exception as exc:
            logger.warning("Webhook failed: %s", exc)

    # ── Exit Manager ──────────────────────────────────────────────────────────
    exit_mgr = ExitManager(alerts)
    logger.info("🏁 Exit manager ready (Trailing stop + Partial TP)")

    # ── WebSocket feed ────────────────────────────────────────────────────────
    ws_feed = BinanceWSFeed(
        on_candle_close=make_candle_callback(exchange, alerts, funding, exit_mgr)
    )
    exchange.set_ws_feed(ws_feed)
    await ws_feed.seed_from_rest(exchange)
    await ws_feed.start()
    logger.info("🔌 WebSocket live — 18 streams active")

    # ── Web server ────────────────────────────────────────────────────────────
    web_app = web.Application()
    web_app.router.add_get(config.HEALTH_PATH,   health_handler)
    web_app.router.add_post(config.WEBHOOK_PATH, make_webhook_handler(ptb_app))

    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.WEBHOOK_PORT).start()
    logger.info("Web server on port %d", config.WEBHOOK_PORT)

    # ── Startup notification ──────────────────────────────────────────────────
    try:
        await alerts.send_startup()
    except Exception as exc:
        logger.warning("Startup msg failed: %s", exc)

    logger.info(
        "✅ %s %s running! "
        "(WebSocket + MTF + Funding + VPOC + Regime + ExitManager)",
        config.BOT_NAME, config.BOT_VERSION,
    )

    # ── Run forever ───────────────────────────────────────────────────────────
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown signal received")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    await ws_feed.stop()
    await funding.close()
    await ptb_app.shutdown()
    await exchange.close()
    await runner.cleanup()
    logger.info("Bot shut down cleanly. Goodbye! 👋")


if __name__ == "__main__":
    asyncio.run(main())
