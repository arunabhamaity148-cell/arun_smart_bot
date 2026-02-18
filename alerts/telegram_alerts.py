"""
ARUNABHA TELEGRAM ALERTS v2.0
Using HTML parse mode - no escape issues
"""

import logging
from typing import Dict, Any
from telegram import Bot
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


def escape_html(text: str) -> str:
    """🆕 Escape HTML special characters"""
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


class TelegramAlerts:
    
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        
    async def send_signal(self, signal):
        """Send formatted signal message using HTML"""
        
        emoji = "🟢" if signal.direction == "LONG" else "🔴"
        
        # Escape dynamic content
        symbol_html = escape_html(signal.symbol)
        grade_html = escape_html(signal.extreme_fear_grade)
        
        if signal.confirmation_pending:
            # Pending confirmation message
            message = f"""⏳ <b>ENTRY CONFIRMATION PENDING</b>

{emoji} <b>{signal.direction}</b> {symbol_html}  [{grade_html}]

📍 <b>Entry Zone:</b> <code>{signal.entry:.2f}</code>
🛑 <b>Stop Loss:</b> <code>{signal.stop_loss:.2f}</code>
🎯 <b>Take Profit:</b> <code>{signal.take_profit:.2f}</code>
📐 <b>R:R:</b> <code>{signal.rr_ratio:.2f}</code>

⏳ <b>Waiting for:</b>
• Next candle close above entry
• Small higher low formation
• Max 3 candles wait

🔍 <b>Score:</b> <code>{signal.extreme_fear_score}</code>/100
🔍 <b>Filters:</b> <code>{signal.filters_passed}</code>/8

🧠 <b>Insight:</b>
{escape_html(signal.human_insight)}

⏱ {escape_html(signal.timestamp)}
"""
        else:
            # Confirmed signal message
            logic_text = ", ".join(signal.logic_triggered[:3])
            risk_usd = signal.position_size.get('risk_usd', 0)
            pos_usd = signal.position_size.get('position_usd', 0)
            
            message = f"""⚡ <b>ARUNABHA EXTREME FEAR BOT v2.0</b>

{emoji} <b>{signal.direction}</b> {symbol_html}  [{grade_html}]

┌─ <b>ENTRY PLAN</b> ───────────────
│ 📍 Entry:      <code>{signal.entry:.2f}</code>
│ 🛑 Stop Loss:  <code>{signal.stop_loss:.2f}</code>
│ 🎯 Take Profit: <code>{signal.take_profit:.2f}</code>
│ 📐 R:R:        <code>{signal.rr_ratio:.2f}</code>
└───────────────────────────────

┌─ <b>POSITION</b> ─────────────────
│ Risk: <code>${risk_usd:.2f}</code> USD
│ Size: <code>${pos_usd:.2f}</code> USD
│ Leverage: <code>{config.LEVERAGE}x</code>
└───────────────────────────────

┌─ <b>EXTREME FEAR ENGINE</b> ──────
│ Score: <code>{signal.extreme_fear_score}</code>/100
│ Logic: {escape_html(logic_text)}
└───────────────────────────────

┌─ <b>MARKET CONTEXT</b> ────────────
│ Mood: {escape_html(signal.market_mood)}
│ Session: {escape_html(signal.session_info)}
│ Filters: <code>{signal.filters_passed}</code>/8
└───────────────────────────────

🧠 <b>INSIGHT</b>
{escape_html(signal.human_insight)}

⏱ {escape_html(signal.timestamp)}
🚨 <b>MANUAL EXECUTION REQUIRED</b>
"""
        
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=ParseMode.HTML  # 🆕 Use HTML instead of Markdown
            )
            logger.info("Signal sent to Telegram: %s", signal.symbol)
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            # Fallback: send without parse mode
            try:
                plain_message = f"""ARUNABHA BOT SIGNAL

{signal.direction} {signal.symbol} [{signal.extreme_fear_grade}]

Entry: {signal.entry:.2f}
SL: {signal.stop_loss:.2f}
TP: {signal.take_profit:.2f}
RR: {signal.rr_ratio:.2f}

Score: {signal.extreme_fear_score}/100
Filters: {signal.filters_passed}/8

{signal.human_insight}

{signal.timestamp}
MANUAL EXECUTION REQUIRED"""
                
                await self.bot.send_message(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    text=plain_message,
                    parse_mode=None
                )
                logger.info("Signal sent as plain text (fallback)")
            except Exception as exc2:
                logger.error("Plain text fallback also failed: %s", exc2)
    
    async def send_status(self, stats: Dict[str, Any]):
        """Send daily status"""
        active_symbols = stats.get('symbols_active', [])
        active_str = ', '.join(active_symbols) if active_symbols else 'None'
        
        message = f"""⚡ <b>ARUNABHA EXTREME FEAR BOT v2.0</b>

📊 <b>Daily Stats</b>
Signals: <code>{stats.get('total', 0)}</code>/{config.MAX_SIGNALS_DAY}
Wins: <code>{stats.get('wins', 0)}</code> | Losses: <code>{stats.get('losses', 0)}</code>
PnL: <code>{stats.get('pnl_pct', 0):.2f}</code>%
Win Rate: <code>{stats.get('win_rate', 0):.1f}</code>%

🔥 <b>Active Trades</b>
{escape_html(active_str)}

🧠 <b>Market Mood</b>
Check with /mood command
"""
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            logger.error("Status send failed: %s", exc)
    
    async def send_startup(self):
        """Send startup message"""
        pairs_text = ', '.join(config.TRADING_PAIRS)
        
        message = f"""🚀 <b>{escape_html(config.BOT_NAME)} {escape_html(config.BOT_VERSION)}</b>

✅ Bot started successfully

<b>Configuration:</b>
• Pairs: {escape_html(pairs_text)}
• Timeframe: {escape_html(config.TIMEFRAME)}
• Max Signals: {config.MAX_SIGNALS_DAY}/day
• Risk: {config.RISK_PCT}% per trade
• Cooldown: {config.COOLDOWN_MINUTES} min

<b>Strict Filters Active:</b>
✅ EMA200 Mandatory
✅ Structure Shift Required  
✅ Session Quiet = No Trade
✅ Entry Confirmation Delay
✅ Min Score: {config.MIN_SCORE_TO_TRADE}

Ready! 🔥
"""
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            logger.error("Startup send failed: %s", exc)
