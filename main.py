"""
ARUNABHA EXTREME FEAR BOT v1.0
Main entry point
"""

import asyncio
import logging
import sys
from aiohttp import web
from datetime import datetime

import config
from core import ExtremeFearEngine, SimpleFilters, RiskManager, MarketMood, generate_signal
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
        
    async def start(self):
        """Start bot"""
        logger.info("Starting %s %s", config.BOT_NAME, config.BOT_VERSION)
        
        # Connect exchange
        await self.exchange.connect()
        
        # Fetch initial fear index
        await self.mood.fetch_fear_index()
        
        # Setup WebSocket
        self.ws = BinanceWSFeed(on_candle=self.on_candle)
        self.exchange.set_ws_feed(self.ws)
        
        # Seed data
        await self.ws.seed_from_rest(self.exchange)
        
        # Start WebSocket
        await self.ws.start()
        
        # Send startup
        await self.alerts.send_startup()
        
        # Start web server
        await self.start_web_server()
        
        logger.info("Bot running!")
        
        # Keep alive
        while True:
            await asyncio.sleep(60)
            
            # Update fear index every 5 min
            if datetime.now().minute % 5 == 0:
                await self.mood.fetch_fear_index()
                
            # Check trade timeouts
            # (Implementation needed with price fetch)
            
    async def on_candle(self, symbol: str, timeframe: str, ohlcv: list):
        """Callback on new candle"""
        if timeframe != config.TIMEFRAME:
            return  # Only trade 15m
            
        # Check daily reset
        current_date = datetime.now().strftime("%Y-%m-%d")
        if self.risk.daily_stats["date"] != current_date:
            self.risk.reset_daily()
            
        # Fetch all data
        try:
            ohlcv_5m = await self.exchange.fetch_ohlcv(symbol, "5m", 50)
            ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, "1h", 50)
            btc_15m = await self.exchange.fetch_ohlcv(config.TRADING_PAIRS[0], "15m", 50)
            funding = 0  # Fetch from exchange if available
            
            # Generate signal
            signal = generate_signal(
                symbol=symbol,
                ohlcv_15m=ohlcv,
                ohlcv_5m=ohlcv_5m,
                ohlcv_1h=ohlcv_1h,
                btc_ohlcv_15m=btc_15m,
                funding_rate=funding,
                fear_index=self.mood.fear_index,
                account_size=1000,  # From config or env
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
        """Health check"""
        return web.json_response({
            "status": "ok",
            "bot": f"{config.BOT_NAME} {config.BOT_VERSION}",
            "fear_index": self.mood.fear_index,
            "daily_signals": self.risk.daily_stats["total"],
            "active_trades": len(self.risk.active_trades)
        })


async def main():
    bot = ArunabhaBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
