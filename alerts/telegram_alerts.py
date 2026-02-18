"""
ARUNABHA TELEGRAM ALERTS v1.0
Human-style messages with insight
"""

import logging
from typing import Dict, Any
from telegram import Bot
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


class TelegramAlerts:
    
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        
    async def send_signal(self, signal):
        """Send formatted signal message"""
        
        emoji = "🟢" if signal.direction == "LONG" else "🔴"
        
        message = f"""
{emoji} **{signal.direction} {signal.symbol}** | Grade: **{signal.extreme_fear_grade}**

┌─ **ENTRY PLAN** ─────────────────
│ Entry: `{signal.entry:.2f}`
│ Stop Loss: `{signal.stop_loss:.2f}`
│ Take Profit: `{signal.take_profit:.2f}`
│ R:R: `{signal.rr_ratio:.2f}`
└────────────────────────────────────

┌─ **POSITION** ───────────────────
│ Risk: `{signal.position_size.get('risk_usd', 0):.2f}` USD
│ Size: `{signal.position_size.get('position_usd', 0):.2f}` USD
│ Leverage: `{signal.position_size.get('leverage', 15)}x`
└────────────────────────────────────

┌─ **EXTREME FEAR ENGINE** ────────
│ Score: `{signal.extreme_fear_score}/100`
│ Logic: {', '.join(signal.logic_triggered[:3])}
└────────────────────────────────────

┌─ **MARKET CONTEXT** ─────────────
│ Mood: {signal.market_mood}
│ Session: {signal.session_info}
│ Filters: `{signal.filters_passed}/6`
└────────────────────────────────────

🧠 **HUMAN INSIGHT**
{signal.human_insight}

⏱ {signal.timestamp}
🚨 **MANUAL EXECUTION REQUIRED**
"""
        
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info("Signal sent to Telegram: %s", signal.symbol)
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
    
    async def send_status(self, stats: Dict[str, Any]):
        """Send daily status"""
        message = f"""
⚡ **ARUNABHA EXTREME FEAR BOT**

📊 **Daily Stats**
Signals: `{stats.get('total', 0)}/{config.MAX_SIGNALS_DAY}`
Wins: `{stats.get('wins', 0)}` | Losses: `{stats.get('losses', 0)}`
PnL: `{stats.get('pnl_pct', 0):.2f}%`
Win Rate: `{stats.get('win_rate', 0):.1f}%`

🔥 **Active Trades**
{', '.join(stats.get('symbols_active', [])) if stats.get('symbols_active') else 'None'}

🧠 **Market Mood**
Check with /mood command
"""
        await self.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def send_startup(self):
        """Send startup message"""
        message = f"""
🚀 **{config.BOT_NAME} {config.BOT_VERSION}**

✅ Bot started successfully

**Configuration:**
- Pairs: {', '.join(config.TRADING_PAIRS)}
- Timeframe: {config.TIMEFRAME}
- Max Signals: {config.MAX_SIGNALS_DAY}/day
- Risk: {config.RISK_PCT}% per trade
- Cooldown: {config.COOLDOWN_MINUTES} min

**Extreme Fear Engine:**
- 10 logic active
- Need 40+ score to trade
- 6 filters, 4 pass needed

Ready! 🔥
"""
        await self.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN
        )
