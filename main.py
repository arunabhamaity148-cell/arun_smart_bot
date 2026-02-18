"""
ARUNABHA EXTREME FEAR BOT v2.1
Main entry with BTC multi-timeframe
"""

import asyncio
import logging
import sys
from aiohttp import web
from datetime import datetime

import config
from core import ExtremeFearEngine, SimpleFilters, RiskManager, MarketMood, generate_signal, btc_detector
from alerts.telegram_alerts import TelegramAlerts
from exchanges.exchange_manager import ExchangeManager
from exchanges.ws_feed import BinanceWSFeed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("main")


class ArunabhaBot:
    
    def __init__(self):
        self.exchange = ExchangeManager()
        self.alerts = TelegramAlerts()
        self.engine = ExtremeFearEngine()
        self.filters = SimpleFilters()
        self.risk = RiskManager()
        self.mood = MarketMood()
        self.ws = None
        
        # 🆕 BTC data cache
        self.btc_cache = {
            "15m": [],
            "1h": [],
            "4h": []
        }
        self.last_btc_update = None
        
    async def start(self):
        """Start bot"""
        logger.info("Starting %s %s", config.BOT_NAME, config.BOT_VERSION)
        
        await self.exchange.connect()
        await self.mood.fetch_fear_index()
        
        # 🆕 Pre-fetch BTC data for all timeframes
        await self._update_btc_data()
        
        self.ws = BinanceWSFeed(on_candle_close=self.on_candle_close)
        self.exchange.set_ws_feed(self.ws)
        
        await self.ws.seed_from_rest(self.exchange)
        await self.ws.start()
        
        await self.alerts.send_startup()
        await self.start_web_server()
        
        logger.info("Bot running!")
        
        # Keep alive with periodic BTC update
        while True:
            await asyncio.sleep(60)
            
            # Update fear index every 5 min
            if datetime.now().minute % 5 == 0:
                await self.mood.fetch_fear_index()
            
            # 🆕 Update BTC data every 15 minutes
            if datetime.now().minute % 15 == 0:
                await self._update_btc_data()
                
    async def _update_btc_data(self):
        """🆕 Fetch BTC data for all timeframes"""
        try:
            self.btc_cache["15m"] = await self.exchange.fetch_ohlcv("BTC/USDT", "15m", 100)
            self.btc_cache["1h"] = await self.exchange.fetch_ohlcv("BTC/USDT", "1h", 100)
            self.btc_cache["4h"] = await self.exchange.fetch_ohlcv("BTC/USDT", "4h", 100)
            self.last_btc_update = datetime.now()
            
            # Log current regime
            if self.btc_cache["15m"] and self.btc_cache["1h"] and self.btc_cache["4h"]:
                analysis = btc_detector.analyze(
                    self.btc_cache["15m"],
                    self.btc_cache["1h"],
                    self.btc_cache["4h"]
                )
                logger.info("BTC Regime: %s (Confidence: %d%%)", 
                           analysis.regime.value, analysis.confidence)
        except Exception as exc:
            logger.error("BTC data update failed: %s", exc)
    
    async def on_candle_close(self, symbol: str, timeframe: str, ohlcv: list):
        """Callback on candle close"""
        if timeframe != config.TIMEFRAME:
            return
            
        # Check daily reset
        current_date = datetime.now().strftime("%Y-%m-%d")
        if self.risk.daily_stats["date"] != current_date:
            self.risk.reset_daily()
        
        # 🆕 Ensure BTC data is fresh
        if not self.btc_cache["15m"] or not self.btc_cache["1h"] or not self.btc_cache["4h"]:
            await self._update_btc_data()
        
        try:
            ohlcv_5m = await self.exchange.fetch_ohlcv(symbol, "5m", 50)
            ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, "1h", 50)
            funding = 0
            
            # 🆕 Generate signal with multi-timeframe BTC data
            signal = generate_signal(
                symbol=symbol,
                ohlcv_15m=ohlcv,
                ohlcv_5m=ohlcv_5m,
                ohlcv_1h=ohlcv_1h,
                btc_ohlcv_15m=self.btc_cache["15m"],
                btc_ohlcv_1h=self.btc_cache["1h"],      # 🆕 New
                btc_ohlcv_4h=self.btc_cache["4h"],      # 🆕 New
                funding_rate=funding,
                fear_index=self.mood.fear_index,
                account_size=1000,
                risk_manager=self.risk,
                filters=self.filters,
                engine=self.engine,
                mood=self.mood
            )
            
            if signal:
                await self.alerts.send_signal(signal)
                
        except Exception as exc:
            logger.error("Error processing %s: %s", symbol, exc)
            
    async def start_web_server(self):
        """Health check endpoint"""
        app = web.Application()
        app.router.add_get('/health', self.health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', config.WEBHOOK_PORT)
        await site.start()
        
        logger.info("Web server on port %d", config.WEBHOOK_PORT)
        
    async def health_handler(self, request):
        """Health check with BTC regime"""
        
        # Get current BTC regime if available
        btc_info = "No data"
        if self.btc_cache["15m"] and self.btc_cache["1h"] and self.btc_cache["4h"]:
            try:
                analysis = btc_detector.analyze(
                    self.btc_cache["15m"],
                    self.btc_cache["1h"],
                    self.btc_cache["4h"]
                )
                btc_info = f"{analysis.regime.value} ({analysis.confidence}%)"
            except:
                pass
        
        return web.json_response({
            "status": "ok",
            "bot": f"{config.BOT_NAME} {config.BOT_VERSION}",
            "fear_index": self.mood.fear_index,
            "daily_signals": self.risk.daily_stats["total"],
            "active_trades": len(self.risk.active_trades),
            "btc_regime": btc_info,  # 🆕 New
            "last_btc_update": self.last_btc_update.isoformat() if self.last_btc_update else None
        })


async def main():
    bot = ArunabhaBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
