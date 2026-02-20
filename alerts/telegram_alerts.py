"""
ARUNABHA FINAL v4.0 - HUMAN STYLE TELEGRAM ALERTS
Natural language, emojis, Indian style messages
"""

import logging
from typing import Dict, Any, Optional
from telegram import Bot
from telegram.constants import ParseMode
import config
from utils.profit_calculator import profit_calculator

logger = logging.getLogger(__name__)

class TelegramAlerts:
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.last_signal = None
    
    async def send_signal(self, signal, market_type: str):
        """Send human-style signal message"""
        
        if signal.direction == "LONG":
            emoji = "🟢🟢🟢"
            trend = "🚀 UPTREND"
        else:
            emoji = "🔴🔴🔴"
            trend = "📉 DOWNTREND"
        
        # Market type emoji
        market_emoji = {
            "TRENDING": "📈",
            "CHOPPY": "〰️",
            "HIGH_VOL": "⚡"
        }.get(market_type, "📊")
        
        # Human style message
        message = f"""
{emoji} *আজব ব্যবসা* {emoji}

👉 *পেয়ার:* `{signal.symbol}`
👉 *দিক:* {trend}
👉 *গ্রেড:* {signal.extreme_fear_grade} (স্কোর: {signal.extreme_fear_score})

💵 *এন্ট্রি জোন:* `₹{signal.entry:,.2f}`
🛑 *স্টপ লস:* `₹{signal.stop_loss:,.2f}`
🎯 *টার্গেট:* `₹{signal.take_profit:,.2f}`
📊 *R:R রেশিও:* `{signal.rr_ratio:.2f}`

📌 *মার্কেট কন্ডিশন:* {market_emoji} {market_type}
🧠 *লজিক:* {', '.join(signal.logic_triggered[:2])}

💡 *ভাইজ বলছি:*
{signal.human_insight}

⏰ {signal.timestamp.split('T')[0]} {signal.timestamp.split('T')[1][:5]}

👉 *CoinDCX/Delta-এ ম্যানুয়াল ট্রেড করুন*
🎯 *টার্গেট ₹৫০০-৭০০/দিন*
"""
        
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"✅ Signal sent: {signal.symbol}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")
    
    async def send_profit_update(self):
        """Send daily profit update with TDS/GST calculation"""
        summary = profit_calculator.get_daily_summary()
        
        if summary["total_trades"] == 0:
            return
        
        if summary["target_achieved"]:
            mood = "🥳🎉🍾"
            target_text = "★ টার্গেট অর্জিত! ★"
        else:
            mood = "🤔"
            target_text = "আগামীকাল দেখা যাবে"
        
        message = f"""
{mood} *আজকের পাটিগণিত* {mood}

📊 *ট্রেড রিপোর্ট*
────────────────
মোট ট্রেড: {summary['total_trades']} টি
জিতেছি: {summary['wins']} টি
হেরেছি: {summary['losses']} টি
উইন রেট: {summary['win_rate']}%

💰 *টাকা-পয়সা*
────────────────
গ্রস P&L: ₹{summary['gross_pnl']}
TDS কাটা: ₹{summary['total_tds']}
GST কাটা: ₹{summary['total_gst']}
ব্রোকারেজ: ₹{summary['total_brokerage']}
────────────────
*নেট প্রফিট: ₹{summary['net_pnl']}*

{target_text}

🎯 টার্গেট: ₹৫০০/দিন
🏦 ক্যাপিটাল: ₹{config.ACCOUNT_SIZE}
⚡ লিভারেজ: {config.MAX_LEVERAGE}x

🤝 কাল আবার দেখা হবে!
"""
        
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Profit update error: {e}")
    
    async def send_startup(self):
        """Send startup message in human style"""
        message = f"""
🌅 *নমস্কার বস!*

*ARUNABHA FINAL v4.0* অনলাইনে এসে গেছে

📊 *আজকের সেটিংস*
────────────────
ক্যাপিটাল: ₹{config.ACCOUNT_SIZE}
রিস্ক/ট্রেড: {config.RISK_PER_TRADE}%
টার্গেট: ₹৫০০-৭০০/দিন
লিভারেজ: {config.MAX_LEVERAGE}x

🎯 *সিগন্যাল পাবেন যখন:*
• মার্কেট ট্রেন্ডিং/চপি বুঝে
• স্কোর ২০-৩০ এর মধ্যে
• ফিল্টার পাস করলে

🤖 *বট বলছে:* "ভাই, আমি শুধু বলব, ট্রেড আপনি করবেন"

📈 *বেস্ট টাইম:* 
• লন্ডন ওপেন (১-৩টা)
• NY ওপেন (৬-৮টা)
• এশিয়া ওপেন (৭-৯টা)

🚀 শুরু করা যাক!
"""
        
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Startup error: {e}")