"""
ARUNABHA SMART v10.0 — Main Bot
════════════════════════════════
Manual trading signal bot with anti-overfitting design.
Deploys on Railway.app via webhook (no polling).

Architecture:
  • aiohttp web server  — health endpoint + Telegram webhook
  • asyncio scan loop   — scans all pairs every SCAN_INTERVAL_SEC
  • PTB Application     — handles /start /status /signals commands

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
from core.smart_signal       import generate_signal, SignalResult
from exchanges.exchange_manager import ExchangeManager
from utils.time_utils import is_sleep_time, today_ist_str, ts_label

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
    "daily_stats":   _fresh_daily_stats(),
    "signals_today": [],      # list of minimal dicts for /signals command
    "active_signals": set(),  # set of symbols currently in open signal
    "last_scan":     None,
}


# ─── Day-reset helper ─────────────────────────────────────────────────────────

def _maybe_reset_day() -> None:
    """Reset daily counters at IST midnight."""
    today = today_ist_str()
    if STATE["daily_stats"]["date"] != today:
        logger.info("New IST day — resetting daily stats")
        STATE["daily_stats"]   = _fresh_daily_stats()
        STATE["signals_today"] = []


# ─── Scan logic ───────────────────────────────────────────────────────────────

async def scan_once(exchange: ExchangeManager, alerts: TelegramAlerts) -> None:
    """Single scan cycle across all configured pairs."""
    _maybe_reset_day()

    if is_sleep_time():
        logger.info("😴 Sleep hours (IST 1–7 AM) — skipping scan")
        return

    stats = STATE["daily_stats"]

    # Daily cap
    if stats["total_signals"] >= config.MAX_SIGNALS_DAY:
        logger.info("Daily signal cap reached (%d)", config.MAX_SIGNALS_DAY)
        return

    # Concurrent cap
    active: Set[str] = STATE["active_signals"]
    if len(active) >= config.MAX_CONCURRENT:
        logger.info("Concurrent cap reached — active: %s", active)
        return

    logger.info("🔍 Scanning %d pairs…", len(config.TRADING_PAIRS))

    # Fetch BTC data for correlation context
    try:
        btc_ohlcv = await exchange.fetch_ohlcv(config.BTC_PAIR, "15m", config.CANDLE_LOOKBACK)
    except Exception as exc:
        logger.warning("BTC OHLCV fetch failed: %s — continuing without correlation", exc)
        btc_ohlcv = []

    # Process each pair
    for symbol in config.TRADING_PAIRS:
        # Re-check caps inside loop
        if stats["total_signals"] >= config.MAX_SIGNALS_DAY:
            break
        if len(active) >= config.MAX_CONCURRENT:
            break
        if symbol in active:
            logger.debug("%s already has active signal — skipping", symbol)
            continue

        try:
            ohlcv = await exchange.fetch_ohlcv(symbol, "15m", config.CANDLE_LOOKBACK)
            ob    = await exchange.fetch_orderbook(symbol, config.ORDERBOOK_DEPTH)
        except Exception as exc:
            logger.warning("Data fetch failed for %s: %s", symbol, exc)
            continue

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
            continue

        if signal is None:
            continue

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

        await alerts.send_signal(signal)

        # Small delay between alerts
        await asyncio.sleep(1)

    STATE["last_scan"] = datetime.utcnow().isoformat()
    logger.info(
        "Scan complete — signals today: %d/%d  active: %s",
        stats["total_signals"], config.MAX_SIGNALS_DAY, active,
    )


# ─── Background scan loop ─────────────────────────────────────────────────────

async def scan_loop(exchange: ExchangeManager, alerts: TelegramAlerts) -> None:
    """Infinite loop — runs scan_once every SCAN_INTERVAL_SEC seconds."""
    logger.info("Scan loop started (interval=%ds)", config.SCAN_INTERVAL_SEC)
    while True:
        try:
            await scan_once(exchange, alerts)
        except asyncio.CancelledError:
            logger.info("Scan loop cancelled")
            break
        except Exception as exc:
            logger.error("Unhandled error in scan_once: %s", exc, exc_info=True)
        await asyncio.sleep(config.SCAN_INTERVAL_SEC)


# ─── aiohttp web server ───────────────────────────────────────────────────────

async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint for Railway."""
    stats = STATE["daily_stats"]
    return web.json_response({
        "status":       "ok",
        "bot":          f"{config.BOT_NAME} {config.BOT_VERSION}",
        "signals_today": stats["total_signals"],
        "last_scan":    STATE.get("last_scan"),
    })


def make_webhook_handler(ptb_app) -> web.RequestHandler:
    """Factory that creates an aiohttp handler for PTB webhook updates."""
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

    # ── Set up exchange ────────────────────────────────────────────────────
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

    # Set webhook if WEBHOOK_URL is configured (production/Railway)
    if config.WEBHOOK_URL:
        webhook_endpoint = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
        try:
            await ptb_app.bot.set_webhook(webhook_endpoint)
            logger.info("Webhook set to %s", webhook_endpoint)
        except Exception as exc:
            logger.warning("Could not set webhook: %s", exc)

    # ── Start aiohttp server ───────────────────────────────────────────────
    web_app = web.Application()
    web_app.router.add_get(config.HEALTH_PATH,  health_handler)
    web_app.router.add_post(config.WEBHOOK_PATH, make_webhook_handler(ptb_app))

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.WEBHOOK_PORT)
    await site.start()
    logger.info("Web server listening on port %d", config.WEBHOOK_PORT)

    # ── Send startup notification ──────────────────────────────────────────
    try:
        await alerts.send_startup()
    except Exception as exc:
        logger.warning("Startup notification failed: %s", exc)

    # ── Background scan task ───────────────────────────────────────────────
    scan_task = asyncio.create_task(scan_loop(exchange, alerts))

    logger.info("✅ %s %s is running!", config.BOT_NAME, config.BOT_VERSION)

    # Run forever until cancelled
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown signal received")

    # ── Cleanup ────────────────────────────────────────────────────────────
    scan_task.cancel()
    try:
        await scan_task
    except asyncio.CancelledError:
        pass

    await ptb_app.shutdown()
    await exchange.close()
    await runner.cleanup()
    logger.info("Bot shut down cleanly. Goodbye! 👋")


if __name__ == "__main__":
    asyncio.run(main())
