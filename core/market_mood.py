"""
ARUNABHA MARKET MOOD v1.0
Fear & Greed Index + Session detection
"""

import logging
import aiohttp
from typing import Dict, Any
from datetime import datetime
import pytz

import config

logger = logging.getLogger(__name__)


class MarketMood:
    """
    Track market emotional state
    """
    
    def __init__(self):
        self.fear_index = 50  # Default neutral
        self.last_update = None
        
    async def fetch_fear_index(self) -> int:
        """
        Fetch from alternative.me API
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(config.FEAR_GREED_API_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.fear_index = int(data["data"][0]["value"])
                        self.last_update = datetime.now()
                        logger.info("Fear Index updated: %d", self.fear_index)
                        return self.fear_index
        except Exception as exc:
            logger.warning("Fear index fetch failed: %s", exc)
            
        return self.fear_index  # Return last known
    
    def get_mood(self) -> Dict[str, Any]:
        """
        Interpret fear index
        """
        fi = self.fear_index
        
        if fi < 20:
            mood = "EXTREME_FEAR"
            action = "REDUCE_SIZE_QUICK_PROFIT"
            color = "🔴"
        elif fi < 40:
            mood = "FEAR"
            action = "CAUTIOUS_SCALP"
            color = "🟠"
        elif fi > 75:
            mood = "GREED"
            action = "AVOID_FOMO"
            color = "🟢"
        elif fi > 55:
            mood = "NEUTRAL_BULLISH"
            action = "NORMAL_TRADE"
            color = "🟡"
        else:
            mood = "NEUTRAL"
            action = "STANDARD"
            color = "⚪"
            
        return {
            "index": fi,
            "mood": mood,
            "action": action,
            "emoji": color,
            "should_trade": fi < config.FEAR_INDEX_STOP  # Stop if >75
        }
    
    def is_session_active(self) -> Dict[str, Any]:
        """
        Check if major session is active (London/NY)
        """
        ist = datetime.now(pytz.timezone('Asia/Kolkata'))
        hour = ist.hour
        
        # London: 13:30-17:00 IST
        # NY: 18:00-22:00 IST
        # Asia: 06:00-12:00 IST
        
        sessions = {
            "asia": 6 <= hour < 12,
            "london": 13 <= hour < 17,
            "ny": 17 <= hour < 22
        }
        
        active = [s for s, v in sessions.items() if v]
        
        return {
            "active_sessions": active,
            "is_major": "london" in active or "ny" in active,
            "time_ist": ist.strftime("%H:%M")
        }


async def get_fear_index() -> int:
    """Convenience function"""
    mood = MarketMood()
    return await mood.fetch_fear_index()
