"""
Telegram Alerts – ARUNABHA SMART v10.0
Sends formatted signal alerts and responds to Telegram commands.
"""

import logging
from typing import Optional, Dict, Any, List

from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config
from core.smart_signal import SignalResult
from utils.time_utils import ts_label

logger = logging.getLogger(__name__)


# ─── Message formatters ───────────────────────────────────────────────────────

def _filter_badges(detail: Dict[str, bool]) -> str:
    icons = {"session": "🕐", "orderflow": "📊", "liquidation": "💥",
             "btc_trend": "₿", "correlation": "🔗", "volatility": "📈"}
    parts = []
    for k, v in detail.items():
        icon = icons.get(k, "•")
        parts.append(f"{icon}{'✓' if v else '✗'}")
    return "  ".join(parts)


def format_signal_message(signal: SignalResult) -> str:
    """Full-detail signal alert message (MarkdownV2 escaped)."""
    emoji    = "🟢 LONG" if signal.direction == "LONG" else "🔴 SHORT"
    quality_star = {"A+": "⭐⭐⭐", "A": "⭐⭐", "B": "⭐", "C": "•"}.get(signal.quality, "")
    lever    = config.LEVERAGE
    sizing   = signal.sizing

    risk_line = ""
    if sizing:
        risk_line = (
            f"\n💼 *Risk:* {sizing.get('risk_pct', 0):.1f}%  "
            f"(${sizing.get('risk_usd', 0):.0f})  "
            f"| Position: ${sizing.get('position_usd', 0):.0f}  "
            f"| {sizing.get('contracts', 0):.4f} contracts"
        )

    badge_row = _filter_badges(signal.filter_detail)

    lines = [
        f"⚡ *ARUNABHA SMART v10\\.0*",
        f"",
        f"{emoji}  *{signal.symbol}*  \\[{signal.timeframe}\\]  {quality_star}",
        f"",
        f"📍 *Entry:*       `{signal.entry:.4f}`",
        f"🛑 *Stop Loss:*   `{signal.stop_loss:.4f}`",
        f"🎯 *Take Profit:* `{signal.take_profit:.4f}`",
        f"📐 *R:R Ratio:*   `{signal.rr_ratio:.2f}`",
        f"",
        f"📊 *RSI:* `{signal.rsi:.1f}`  "
        f"*EMA9:* `{signal.ema_fast:.4f}`  "
        f"*EMA21:* `{signal.ema_slow:.4f}`",
        f"📦 *Vol Ratio:* `{signal.volume_ratio:.2f}×`",
        f"",
        f"🧠 *Smart Filters:* `{signal.filters_passed}/{signal.filters_total}`",
        f"`{badge_row}`",
        risk_line,
        f"",
        f"🚨 *MANUAL EXECUTION REQUIRED*",
        f"⏱ {ts_label()}",
    ]
    return "\n".join(lines)


def format_status_message(daily_stats: Dict[str, Any]) -> str:
    today     = daily_stats.get("date", "—")
    total     = daily_stats.get("total_signals", 0)
    longs     = daily_stats.get("longs", 0)
    shorts    = daily_stats.get("shorts", 0)
    concurrent = daily_stats.get("concurrent", 0)
    pairs     = daily_stats.get("pairs", [])

    pairs_str = ", ".join(pairs) if pairs else "None"

    lines = [
        f"⚡ *ARUNABHA SMART v10\\.0 \\— Status*",
        f"",
        f"📅 *Date:* {today}",
        f"📡 *Signals today:* {total}/{config.MAX_SIGNALS_DAY}",
        f"🟢 *Longs:* {longs}   🔴 *Shorts:* {shorts}",
        f"🔁 *Concurrent active:* {concurrent}/{config.MAX_CONCURRENT}",
        f"📋 *Pairs scanned:* {pairs_str}",
        f"",
        f"🤖 Bot is running ✅",
    ]
    return "\n".join(lines)


def format_signals_list(signals_today: List[Dict[str, Any]]) -> str:
    if not signals_today:
        return "⚡ *ARUNABHA SMART* — No signals generated today yet\\."

    lines = ["⚡ *ARUNABHA SMART v10\\.0 \\— Today's Signals*", ""]
    for i, s in enumerate(signals_today, 1):
        d    = "🟢" if s.get("direction") == "LONG" else "🔴"
        sym  = s.get("symbol", "?")
        time = s.get("time", "—")
        rr   = s.get("rr_ratio", 0.0)
        q    = s.get("quality", "—")
        lines.append(f"{i}\\. {d} `{sym}` {time} | RR={rr:.2f} | Q={q}")

    return "\n".join(lines)


# ─── Telegram Bot setup ───────────────────────────────────────────────────────

class TelegramAlerts:
    """Handles both outbound alerts and inbound /commands via webhook."""

    def __init__(self, state: Dict[str, Any]) -> None:
        """
        Args:
            state: Shared mutable state dict from main.py containing
                   daily_stats, signals_today, etc.
        """
        self._bot   = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self._state = state
        self._app   = None   # built lazily

    async def send_signal(self, signal: SignalResult) -> None:
        """Send a formatted signal alert to the configured chat."""
        try:
            text = format_signal_message(signal)
            await self._bot.send_message(
                chat_id    = config.TELEGRAM_CHAT_ID,
                text       = text,
                parse_mode = ParseMode.MARKDOWN_V2,
            )
            logger.info("Signal alert sent: %s %s", signal.symbol, signal.direction)
        except Exception as exc:
            logger.error("Failed to send signal alert: %s", exc)

    async def send_text(self, text: str) -> None:
        """Send a plain text notification."""
        try:
            await self._bot.send_message(
                chat_id = config.TELEGRAM_CHAT_ID,
                text    = text,
            )
        except Exception as exc:
            logger.error("Failed to send message: %s", exc)

    async def send_startup(self) -> None:
        await self.send_text(
            f"⚡ ARUNABHA SMART v10.0 started!\n"
            f"Pairs: {', '.join(config.TRADING_PAIRS)}\n"
            f"Scan interval: {config.SCAN_INTERVAL_SEC}s\n"
            f"Max signals/day: {config.MAX_SIGNALS_DAY}\n"
            f"Ready. 🚀"
        )

    # ── Command handlers ──────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        stats  = self._state.get("daily_stats", {})
        text   = format_status_message(stats)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        stats  = self._state.get("daily_stats", {})
        text   = format_status_message(stats)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

    async def _cmd_signals(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        signals = self._state.get("signals_today", [])
        text    = format_signals_list(signals)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

    def build_application(self):
        """Build the PTB Application for webhook use."""
        app = (
            ApplicationBuilder()
            .token(config.TELEGRAM_BOT_TOKEN)
            .build()
        )
        app.add_handler(CommandHandler("start",   self._cmd_start))
        app.add_handler(CommandHandler("status",  self._cmd_status))
        app.add_handler(CommandHandler("signals", self._cmd_signals))
        self._app = app
        return app