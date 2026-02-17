"""
ARUNABHA SMART v10.1 — Main Bot
════════════════════════════════
Manual trading signal bot with anti-overfitting design.
Deploys on Railway.app via webhook (no polling).

Architecture:
  • aiohttp web server      — health endpoint + Telegram webhook
  • BinanceWSFeed           — real-time kline via WebSocket (no REST polling)
  • Candle-close callback   — triggers scan immediately when a candle closes
  • PTB Application         — handles /start /status /signals commands

Run locally:
  python main.py

Required env vars:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WEBHOOK_URL,
  BINANCE_API_KEY, BINANCE_SECRET, PORT
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from aiohttp import web
from telegram import Update

import config
from alerts.telegram_alerts import TelegramAlerts
from core.smart_signal           import generate_signal, SignalResult
from exchanges.exchange_manager  import ExchangeManager
from exchanges.ws_feed           import BinanceWSFeed
from utils.time_utils            import is_sleep_time, today_ist_str, ts_label

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
        "pairs":         [p.replace("/", "") for p in config.TRADING_PAIRS],
    }


STATE: Dict[str, Any] = {
    "daily_stats":    _fresh_daily_stats(),
    "signals_today":  [],       # list of minimal dicts for /signals command
    "active_signals": set(),    # set of symbols currently in open signal
    "last_scan":      None,
}

# Per-symbol scan lock — prevents simultaneous scans of the same symbol
_scan_locks: Dict[str, asyncio.Lock] = {
    sym: asyncio.Lock() for sym in config.TRADING_PAIRS
}


# ─── Day-reset helper ─────────────────────────────────────────────────────────

def _maybe_reset_day() -> None:
    today = today_ist_str()
    if STATE["daily_stats"]["date"] != today:
        logger.info("New IST day — resetting daily stats")
        STATE["daily_stats"]   = _fresh_daily_stats()
        STATE["signals_today"] = []


# ─── Single-pair scan (called on candle close) ────────────────────────────────

async def scan_symbol(
    symbol:    str,
    timeframe: str,
    exchange:  ExchangeManager,
    alerts:    TelegramAlerts,
) -> None:
    """
    Triggered by WebSocket when a candle closes for `symbol`/`timeframe`.
    Evaluates signal conditions and sends alert if triggered.
    """
    _maybe_reset_day()

    if is_sleep_time():
        return

    stats  = STATE["daily_stats"]
    active: Set[str] = STATE["active_signals"]

    # Cap checks
    if stats["total_signals"] >= config.MAX_SIGNALS_DAY:
        return
    if len(active) >= config.MAX_CONCURRENT:
        return
    if symbol in active:
        return

    # One scan at a time per symbol
    lock = _scan_locks.get(symbol)
    if lock is None:
        lock = asyncio.Lock()
        _scan_locks[symbol] = lock

    if lock.locked():
        return   # previous scan still running — skip

    async with lock:
        try:
            # OHLCV comes from WS cache — no REST call needed
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, config.CANDLE_LOOKBACK)
            ob    = await exchange.fetch_orderbook(symbol, config.ORDERBOOK_DEPTH)
        except Exception as exc:
            logger.warning("Data fetch failed for %s: %s", symbol, exc)
            return

        # BTC correlation data (also from WS cache, 15m hardcoded for context)
        try:
            btc_ohlcv = await exchange.fetch_ohlcv(
                config.BTC_PAIR, "15m", config.CANDLE_LOOKBACK
            )
        except Exception:
            btc_ohlcv = []

        try:
            signal: Optional[SignalResult] = generate_signal(
                symbol           = symbol,
                ohlcv            = ohlcv,
                orderbook        = ob,
                btc_ohlcv        = btc_ohlcv,
                account_size_usd = config.ACCOUNT_SIZE_USD,
            )
        except Exception as exc:
            logger.error("Signal generation error %s: %s", symbol, exc, exc_info=True)
            return

        if signal is None:
            return

        # ── Record and alert ───────────────────────────────────────────────
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
        })

        STATE["last_scan"] = datetime.utcnow().isoformat()

        await alerts.send_signal(signal)

        logger.info(
            "✅ Signal sent: %s %s | Total today: %d/%d",
            symbol, signal.direction,
            stats["total_signals"], config.MAX_SIGNALS_DAY,
        )


# ─── WebSocket candle-close callback ─────────────────────────────────────────

def make_candle_callback(exchange: ExchangeManager, alerts: TelegramAlerts):
    """
    Returns the async callback that BinanceWSFeed fires on every candle close.
    Only scans on the timeframes we actually care about.
    """
    SCAN_TIMEFRAMES = {"5m", "15m", "1h"}

    async def on_candle_close(symbol: str, tf: str, ohlcv: list) -> None:
        if tf not in SCAN_TIMEFRAMES:
            return
        # Launch scan as a fire-and-forget task so WS listener isn't blocked
        asyncio.create_task(
            scan_symbol(symbol, tf, exchange, alerts),
            name=f"scan_{symbol}_{tf}",
        )

    return on_candle_close


# ─── aiohttp web server ───────────────────────────────────────────────────────

async def health_handler(request: web.Request) -> web.Response:
    stats = STATE["daily_stats"]
    return web.json_response({
        "status":        "ok",
        "bot":           f"{config.BOT_NAME} {config.BOT_VERSION}",
        "signals_today": stats["total_signals"],
        "last_scan":     STATE.get("last_scan"),
    })


def make_webhook_handler(ptb_app) -> web.RequestHandler:
    async def webhook_handler(request: web.Request) -> web.Response:
        try:
            data   = await request.json()
            update = Update.de_json(data, ptb_app.bot)
            await ptb_app.process_update(update)
        except Exception as exc:
            logger.error("Webhook processing error: %s", exc)
        return web.Response(text="ok")
    return webhook_handler


# ─── Application entry point ──────────────────────────────────────────────────

async def main() -> None:
    # Validate critical config
    if not config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN not set — exiting")
        sys.exit(1)
    if not config.TELEGRAM_CHAT_ID:
        logger.critical("TELEGRAM_CHAT_ID not set — exiting")
        sys.exit(1)

    # ── Set up exchange (REST — used only for seeding & orderbook) ─────────
    exchange = ExchangeManager()
    try:
        await exchange.connect()
    except Exception as exc:
        logger.critical("Exchange connection failed: %s — exiting", exc)
        sys.exit(1)

    # ── Set up Telegram ────────────────────────────────────────────────────
    alerts  = TelegramAlerts(STATE)
    ptb_app = alerts.build_application()
    await ptb_app.initialize()

    if config.WEBHOOK_URL:
        webhook_endpoint = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
        try:
            await ptb_app.bot.set_webhook(webhook_endpoint)
            logger.info("Webhook set to %s", webhook_endpoint)
        except Exception as exc:
            logger.warning("Could not set webhook: %s", exc)

    # ── Set up WebSocket feed ──────────────────────────────────────────────
    ws_feed = BinanceWSFeed(
        on_candle_close=make_candle_callback(exchange, alerts)
    )

    # Attach WS feed to exchange so fetch_ohlcv uses cache
    exchange.set_ws_feed(ws_feed)

    # Pre-fill caches from REST so bot is ready immediately at startup
    await ws_feed.seed_from_rest(exchange)

    # Start the live WebSocket connection
    await ws_feed.start()
    logger.info("🔌 WebSocket feed live — no more polling!")

    # ── Start aiohttp server ───────────────────────────────────────────────
    web_app = web.Application()
    web_app.router.add_get(config.HEALTH_PATH,   health_handler)
    web_app.router.add_post(config.WEBHOOK_PATH, make_webhook_handler(ptb_app))

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.WEBHOOK_PORT)
    await site.start()
    logger.info("Web server listening on port %d", config.WEBHOOK_PORT)

    # ── Startup notification ───────────────────────────────────────────────
    try:
        await alerts.send_startup()
    except Exception as exc:
        logger.warning("Startup notification failed: %s", exc)

    logger.info("✅ %s %s is running! (WebSocket mode)", config.BOT_NAME, config.BOT_VERSION)

    # ── Run forever ────────────────────────────────────────────────────────
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown signal received")

    # ── Cleanup ────────────────────────────────────────────────────────────
    await ws_feed.stop()
    await ptb_app.shutdown()
    await exchange.close()
    await runner.cleanup()
    logger.info("Bot shut down cleanly. Goodbye! 👋")


if __name__ == "__main__":
    asyncio.run(main())
