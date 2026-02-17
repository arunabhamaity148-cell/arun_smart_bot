"""
Telegram Alerts — ARUNABHA SMART v10.1
Rich signal formatting with SMC + MTF + Funding + VPOC details.
"""

import logging
from typing import Dict, Any, List

from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config
from core.smart_signal import SignalResult
from utils.time_utils import ts_label

logger = logging.getLogger(__name__)


def _esc(text: str) -> str:
    """Escape MarkdownV2 special chars."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def _filter_row(detail: Dict[str, bool]) -> str:
    """Icon badges for all 9 filters."""
    icons = {
        # Original 6
        "session":     "🕐",
        "orderflow":   "📊",
        "liquidation": "💥",
        "btc_trend":   "₿",
        "correlation": "🔗",
        "volatility":  "📈",
        # New v10.1
        "mtf_1h":      "⏱",
        "funding":     "💸",
        "vpoc":        "📦",
    }
    return "  ".join(
        f"{icons.get(k, '•')}{'✅' if v else '❌'}"
        for k, v in detail.items()
    )


def _smc_row(smc: Dict[str, Any]) -> str:
    parts = [
        f"Structure {'✅' if smc.get('structure_ok') else '❌'}",
        f"Discount  {'✅' if smc.get('in_discount') else '❌'}",
        f"OB        {'✅' if smc.get('near_ob') else '❌'}",
        f"FVG       {'✅' if smc.get('in_fvg') else '❌'}",
    ]
    return " | ".join(parts)


def format_signal_message(signal: SignalResult) -> str:
    """Telegram MarkdownV2 signal card — v10.1."""
    dir_emoji = "🟢 LONG" if signal.direction == "LONG" else "🔴 SHORT"
    grade_map = {"A+": "⭐⭐⭐ A\\+", "A": "⭐⭐ A", "B": "⭐ B", "C": "C"}
    grade_str = grade_map.get(signal.quality, signal.quality)

    smc    = signal.smc    or {}
    sizing = signal.sizing or {}

    # SMC details
    smc_score = smc.get("smc_score", 0)
    structure = smc.get("structure", "—")
    fvg       = smc.get("fvg")
    ob        = smc.get("order_block")
    equil     = smc.get("equilibrium", 0)
    swing_hi  = smc.get("swing_high", 0)
    swing_lo  = smc.get("swing_low", 0)

    ob_str  = f"{ob[0]:.4f} — {ob[1]:.4f}"   if ob  else "Not found"
    fvg_str = f"{fvg[0]:.4f} — {fvg[1]:.4f}" if fvg else "Not found"

    # Risk line
    risk_str = ""
    if sizing:
        risk_str = (
            f"💼 Risk: {sizing.get('risk_pct', 0):.1f}%"
            f"  \\(${sizing.get('risk_usd', 0):.0f}\\)"
            f"  \\|  Position: ${sizing.get('position_usd', 0):.0f}"
            f"  \\|  {sizing.get('contracts', 0):.4f} contracts"
        )

    filter_badges = _filter_row(signal.filter_detail)

    # v10.1 extra context lines (only show if data present)
    mtf_line     = f"│ {_esc(signal.mtf_label)}\n"     if getattr(signal, "mtf_label",     "") else ""
    vpoc_line    = f"│ {_esc(signal.vpoc_label)}\n"    if getattr(signal, "vpoc_label",    "") else ""
    funding_line = f"│ {_esc(signal.funding_label)}\n" if getattr(signal, "funding_label", "") else ""

    msg = (
        f"⚡ *ARUNABHA SMART v10\\.1*\n"
        f"\n"
        f"{dir_emoji}  `{_esc(signal.symbol)}`  \\[{signal.timeframe}\\]  {grade_str}\n"
        f"\n"
        f"┌─ *ENTRY PLAN* ───────────────────\n"
        f"│ 📍 Entry      `{signal.entry:.4f}`\n"
        f"│ 🛑 Stop Loss  `{signal.stop_loss:.4f}`\n"
        f"│ 🎯 TP         `{signal.take_profit:.4f}`\n"
        f"│ 📐 R:R        `{signal.rr_ratio:.2f} : 1`\n"
        f"└──────────────────────────────────\n"
        f"\n"
        f"┌─ *TECHNICALS* ───────────────────\n"
        f"│ RSI `{signal.rsi:.1f}`  EMA9 `{signal.ema_fast:.2f}`  EMA21 `{signal.ema_slow:.2f}`\n"
        f"│ Volume `{signal.volume_ratio:.2f}×` avg\n"
        f"└──────────────────────────────────\n"
        f"\n"
        f"┌─ *SMART MONEY* \\({smc_score}/4\\) ─────────\n"
        f"│ Structure `{_esc(structure)}`\n"
        f"│ Swing   Hi `{swing_hi:.4f}`  Lo `{swing_lo:.4f}`\n"
        f"│ Equilib   `{equil:.4f}`\n"
        f"│ Order Block `{_esc(ob_str)}`\n"
        f"│ FVG Zone    `{_esc(fvg_str)}`\n"
        f"└──────────────────────────────────\n"
        f"\n"
        f"┌─ *v10\\.1 CONFLUENCE* ────────────\n"
        f"{mtf_line}"
        f"{vpoc_line}"
        f"{funding_line}"
        f"└──────────────────────────────────\n"
        f"\n"
        f"┌─ *CONTEXT FILTERS* \\({signal.filters_passed}/{signal.filters_total}\\) ──\n"
        f"│ {filter_badges}\n"
        f"└──────────────────────────────────\n"
        f"\n"
        f"{risk_str}\n"
        f"\n"
        f"⏱ {_esc(ts_label())}\n"
        f"🚨 *MANUAL EXECUTION — DO NOT AUTO\\-TRADE*"
    )
    return msg


def format_status_message(stats: Dict[str, Any]) -> str:
    total  = stats.get("total_signals", 0)
    longs  = stats.get("longs", 0)
    shorts = stats.get("shorts", 0)
    date   = _esc(stats.get("date", "—"))
    return (
        f"⚡ *ARUNABHA SMART v10\\.1 — Status*\n\n"
        f"📅 Date: `{date}`\n"
        f"📡 Signals: `{total}/{config.MAX_SIGNALS_DAY}`\n"
        f"🟢 Longs: `{longs}`    🔴 Shorts: `{shorts}`\n"
        f"🔁 Concurrent: `{stats.get('concurrent', 0)}/{config.MAX_CONCURRENT}`\n\n"
        f"🤖 Bot running ✅\n"
        f"🔌 WebSocket: live ✅\n"
        f"📊 MTF \\+ Funding \\+ VPOC: ON ✅\n"
        f"📋 Pairs: `{_esc(', '.join(config.TRADING_PAIRS))}`"
    )


def format_signals_list(signals: List[Dict[str, Any]]) -> str:
    if not signals:
        return "⚡ *ARUNABHA SMART* — Aaj kono signal generate hoyni\\."
    lines = ["⚡ *ARUNABHA SMART v10\\.1 — Today's Signals*\n"]
    for i, s in enumerate(signals, 1):
        d   = "🟢" if s.get("direction") == "LONG" else "🔴"
        sym = _esc(s.get("symbol", "?"))
        t   = _esc(s.get("time", "—"))
        rr  = s.get("rr_ratio", 0.0)
        q   = _esc(s.get("quality", "—"))
        lines.append(f"{i}\\. {d} `{sym}` — {t}  RR=`{rr:.2f}`  Grade=`{q}`")
    return "\n".join(lines)


class TelegramAlerts:

    def __init__(self, state: Dict[str, Any]) -> None:
        self._bot   = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self._state = state

    async def send_signal(self, signal: SignalResult) -> None:
        try:
            await self._bot.send_message(
                chat_id    = config.TELEGRAM_CHAT_ID,
                text       = format_signal_message(signal),
                parse_mode = ParseMode.MARKDOWN_V2,
            )
            logger.info("Alert sent: %s %s [%s]", signal.symbol, signal.direction, signal.quality)
        except Exception as exc:
            logger.error("MarkdownV2 send failed (%s) — trying plain text", exc)
            try:
                plain = (
                    f"ARUNABHA SMART v10.1\n"
                    f"{signal.direction} {signal.symbol} [{signal.timeframe}] Grade={signal.quality}\n"
                    f"Entry: {signal.entry}  SL: {signal.stop_loss}  TP: {signal.take_profit}\n"
                    f"R:R={signal.rr_ratio}  RSI={signal.rsi}  Vol={signal.volume_ratio}x\n"
                    f"SMC Score: {signal.smc.get('smc_score', 0)}/4  "
                    f"Filters: {signal.filters_passed}/{signal.filters_total}\n"
                    f"{getattr(signal, 'mtf_label', '')}  "
                    f"{getattr(signal, 'vpoc_label', '')}  "
                    f"{getattr(signal, 'funding_label', '')}\n"
                    f"MANUAL EXECUTION REQUIRED"
                )
                await self._bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=plain)
            except Exception as exc2:
                logger.error("Plain text fallback also failed: %s", exc2)

    async def send_text(self, text: str) -> None:
        try:
            await self._bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
        except Exception as exc:
            logger.error("send_text failed: %s", exc)

    async def send_startup(self) -> None:
        await self.send_text(
            f"⚡ ARUNABHA SMART v10.1 started!\n"
            f"Exchange: {config.PRIMARY_EXCHANGE.upper()}\n"
            f"Pairs: {', '.join(config.TRADING_PAIRS)}\n"
            f"Mode: WebSocket (no polling) 🔌\n"
            f"Filters: MTF ✓ | Funding Rate ✓ | VPOC ✓\n"
            f"SMC: ON | Anti-overfitting: ON\n"
            f"Max signals: {config.MAX_SIGNALS_DAY}/day\n"
            f"Ready! 🚀"
        )

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            format_status_message(self._state.get("daily_stats", {})),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            format_status_message(self._state.get("daily_stats", {})),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def _cmd_signals(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            format_signals_list(self._state.get("signals_today", [])),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    def build_application(self):
        app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start",   self._cmd_start))
        app.add_handler(CommandHandler("status",  self._cmd_status))
        app.add_handler(CommandHandler("signals", self._cmd_signals))
        return app
