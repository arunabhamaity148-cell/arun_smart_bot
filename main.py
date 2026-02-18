"""
ARUNABHA EXTREME FEAR BOT v3.0
Surgical execution engine
"""

import asyncio
import logging
import sys
from aiohttp import web
from datetime import datetime

import config
from core import (
    ExtremeFearEngine, 
    SimpleFilters, 
    RiskManager, 
    MarketMood, 
    generate_signal,
    btc_detector,
    risk_manager
)
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
        self.risk = risk_manager  # Use global instance
        self.mood = MarketMood()
        self.ws = None
        
        self.btc_cache = {
            "15m": [],
            "1h": [],
            "4h": []
        }
        self.last_btc_update = None
        
    async def start(self):
        """Start surgical execution engine."""
        logger.info("=" * 70)
        logger.info("ARUNABHA SURGICAL EXECUTION ENGINE v3.0")
        logger.info("=" * 70)
        logger.info("Institutional-grade discipline initialized")
        
        await self.exchange.connect()
        await self.mood.fetch_fear_index()
        await self._update_btc_data()
        
        self.ws = BinanceWSFeed(on_candle_close=self.on_candle_close)
        self.exchange.set_ws_feed(self.ws)
        
        await self.ws.seed_from_rest(self.exchange)
        await self.ws.start()
        
        await self.alerts.send_startup()
        await self.start_web_server()
        
        logger.info("Engine running - All protections active")
        
        while True:
            await asyncio.sleep(60)
            
            if datetime.now().minute % 5 == 0:
                await self.mood.fetch_fear_index()
            
            if datetime.now().minute % 15 == 0:
                await self._update_btc_data()
            
            # Check trade management every minute
            await self._check_active_trades()
                
    async def _update_btc_data(self):
        """Fetch BTC multi-timeframe data."""
        try:
            self.btc_cache["15m"] = await self.exchange.fetch_ohlcv("BTC/USDT", "15m", 200)  # Need 200 for EMA200
            self.btc_cache["1h"] = await self.exchange.fetch_ohlcv("BTC/USDT", "1h", 100)
            self.btc_cache["4h"] = await self.exchange.fetch_ohlcv("BTC/USDT", "4h", 100)
            self.last_btc_update = datetime.now()
            
            if all(self.btc_cache.values()):
                analysis = btc_detector.analyze(
                    self.btc_cache["15m"],
                    self.btc_cache["1h"],
                    self.btc_cache["4h"]
                )
                logger.info("[BTC] Regime: %s | Mode: %s | Conf: %d%% | Trade: %s",
                           analysis.regime.value, analysis.trade_mode,
                           analysis.confidence, "YES" if analysis.can_trade else "NO")
        except Exception as exc:
            logger.error("BTC update failed: %s", exc)
    
    async def _check_active_trades(self):
        """Check active trades for management (BE, partial, etc.)."""
        if not self.risk.active_trades:
            return
        
        try:
            for symbol in list(self.risk.active_trades.keys()):
                ticker = await self.exchange.fetch_ticker(symbol)
                current_price = ticker.get("last", 0)
                
                action = self.risk.check_trade_management(symbol, current_price)
                
                if action == "PARTIAL_EXIT":
                    await self.alerts.send_message(f"🔒 PARTIAL EXIT: {symbol} at 1R")
                elif action == "BREAK_EVEN":
                    await self.alerts.send_message(f"🛡️ SL → BE: {symbol} at +0.5%")
                elif action in ["SL_HIT", "TP_HIT"]:
                    # These handled by candle close or manual check
                    pass
                    
        except Exception as exc:
            logger.error("Trade management error: %s", exc)
    
    async def on_candle_close(self, symbol: str, timeframe: str, ohlcv: list):
        """Process candle with surgical discipline."""
        if timeframe != config.TIMEFRAME:
            return
        
        # Daily reset
        current_date = datetime.now().strftime("%Y-%m-%d")
        if self.risk.daily_stats["date"] != current_date:
            self.risk.reset_daily()
        
        # Ensure BTC data
        if not all(self.btc_cache.values()):
            await self._update_btc_data()
        
        try:
            # Fetch alt data
            ohlcv_5m = await self.exchange.fetch_ohlcv(symbol, "5m", 50)
            ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, "1h", 50)
            funding = 0
            
            # 🆕 SURGICAL EXECUTION ORDER enforced in generate_signal
            signal = generate_signal(
                symbol=symbol,
                ohlcv_15m=ohlcv,
                ohlcv_5m=ohlcv_5m,
                ohlcv_1h=ohlcv_1h,
                btc_ohlcv_15m=self.btc_cache["15m"],
                btc_ohlcv_1h=self.btc_cache["1h"],
                btc_ohlcv_4h=self.btc_cache["4h"],
                funding_rate=funding,
                fear_index=self.mood.fear_index,
                account_size=1000,
                risk_mgr=self.risk,
                filters=self.filters,
                engine=self.engine,
                mood=self.mood
            )
            
            if signal and not signal.confirmation_pending:
                await self.alerts.send_signal(signal)
            elif signal and signal.confirmation_pending:
                await self.alerts.send_pending_notification(signal)
                
        except Exception as exc:
            logger.error("Error processing %s: %s", symbol, exc)
    
    async def start_web_server(self):
        """Health endpoint."""
        app = web.Application()
        app.router.add_get('/health', self.health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', config.WEBHOOK_PORT)
        await site.start()
        
        logger.info("Health server on port %d", config.WEBHOOK_PORT)
    
    async def health_handler(self, request):
        """Health with full status."""
        stats = self.risk.get_stats()
        
        btc_info = "No data"
        if self.btc_cache["15m"] and self.btc_cache["1h"] and self.btc_cache["4h"]:
            try:
                analysis = btc_detector.analyze(
                    self.btc_cache["15m"],
                    self.btc_cache["1h"],
                    self.btc_cache["4h"]
                )
                btc_info = {
                    "regime": analysis.regime.value,
                    "mode": analysis.trade_mode,
                    "confidence": analysis.confidence,
                    "can_trade": analysis.can_trade
                }
            except:
                pass
        
        return web.json_response({
            "status": "ok",
            "version": "3.0-surgical",
            "fear_index": self.mood.fear_index,
            "daily_stats": stats,
            "btc_regime": btc_info,
            "day_locked": stats.get("day_locked"),
            "lock_reason": stats.get("lock_reason")
        })


async def main():
    bot = ArunabhaBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
