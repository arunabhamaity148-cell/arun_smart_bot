"""
ARUNABHA FINAL v4.0 - MAIN EXECUTION ENGINE
Market Adaptive | Indian Exchange Ready | ₹500/day Target
"""

import asyncio
import logging
import sys
import gc
from datetime import datetime
from aiohttp import web

import config
from core import (
    extreme_fear_engine, SimpleFilters, risk_manager,
    MarketMood, generate_signal, btc_detector
)
from core.market_detector import market_detector
from core.adaptive_engine import adaptive_engine
from alerts.telegram_alerts import TelegramAlerts
from exchanges.exchange_manager import ExchangeManager
from exchanges.ws_feed import BinanceWSFeed
from utils.profit_calculator import profit_calculator
from utils.time_utils import is_sleep_time, ist_now

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("main")

class ArunabhaFinalBot:
    def __init__(self):
        self.exchange = ExchangeManager()
        self.alerts = TelegramAlerts()
        self.filters = SimpleFilters()
        self.risk = risk_manager
        self.mood = MarketMood()
        self.ws = None
        
        self.btc_cache = {"15m": [], "1h": [], "4h": []}
        self._btc_data_ready = False
        self._current_market = "CHOPPY"
        self._trades_today = 0
        self._daily_loss = 0.0
        self._last_health_check = datetime.now()
        self._restart_count = 0
    
    async def start(self):
        """Main start method with error handling"""
        try:
            logger.info("=" * 60)
            logger.info("ARUNABHA FINAL v4.0 - ₹500/DAY TARGET")
            logger.info("=" * 60)
            
            # Connect to exchange
            try:
                await self.exchange.connect()
            except Exception as e:
                logger.error(f"Exchange connection failed: {e}")
                await asyncio.sleep(10)
                await self.start()
                return
            
            # Fetch fear index
            try:
                await self.mood.fetch_fear_index()
            except Exception as e:
                logger.warning(f"Fear index fetch failed: {e}")
            
            # Load BTC data
            if not await self._ensure_btc_data():
                logger.error("BTC data failed - restarting in 30s")
                await asyncio.sleep(30)
                await self.start()
                return
            
            # Start WebSocket
            try:
                self.ws = BinanceWSFeed(on_candle_close=self.on_candle_close)
                self.exchange.set_ws_feed(self.ws)
                await self.ws.seed_from_rest(self.exchange)
                await self.ws.start()
            except Exception as e:
                logger.error(f"WebSocket failed: {e}")
                await asyncio.sleep(10)
                await self.start()
                return
            
            # Send startup alert
            try:
                await self.alerts.send_startup()
            except Exception as e:
                logger.warning(f"Telegram startup failed: {e}")
            
            # Start background tasks
            asyncio.create_task(self._market_monitor())
            asyncio.create_task(self._daily_reset_monitor())
            asyncio.create_task(self._run_health_server())
            asyncio.create_task(self._memory_monitor())
            
            logger.info("Bot running - Manual trading only")
            logger.info(f"Market: {self._current_market} | Trades today: {self._trades_today}")
            
            # Main loop
            while True:
                try:
                    await asyncio.sleep(60)
                    
                    # Update fear index every 15 min
                    if datetime.now().minute % 15 == 0:
                        try:
                            await self.mood.fetch_fear_index()
                        except Exception as e:
                            logger.warning(f"Fear index update failed: {e}")
                    
                    # Update BTC data every 15 min
                    if datetime.now().minute % 15 == 0:
                        try:
                            await self._update_btc_data()
                        except Exception as e:
                            logger.warning(f"BTC update failed: {e}")
                    
                    # Clean memory every 30 min
                    if datetime.now().minute % 30 == 0:
                        gc.collect()
                        logger.debug(f"Memory cleaned - Trades: {self._trades_today}")
                    
                    # Log status every hour
                    if datetime.now().minute == 0:
                        logger.info(f"Status | Market: {self._current_market} | Trades: {self._trades_today}")
                        
                except asyncio.CancelledError:
                    logger.info("Main loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Main loop error: {e}")
                    await asyncio.sleep(5)
                    continue
                    
        except Exception as e:
            logger.error(f"Fatal error in start(): {e}")
            self._restart_count += 1
            
            if self._restart_count < 5:
                logger.info(f"Restarting in 30s (attempt {self._restart_count}/5)")
                await asyncio.sleep(30)
                await self.start()
            else:
                logger.critical("Too many restarts - giving up")
                raise
    
    async def _ensure_btc_data(self):
        """Ensure BTC data is loaded"""
        for attempt in range(3):
            try:
                await self._update_btc_data()
                
                if len(self.btc_cache["15m"]) >= 50:
                    self._btc_data_ready = True
                    
                    # Detect market type
                    market = market_detector.detect(
                        self.btc_cache["15m"],
                        self.btc_cache["1h"]
                    )
                    self._current_market = market.name
                    adaptive_engine.update_for_market(market.name)
                    
                    logger.info(f"BTC Ready | Market: {market.name} | Conf: {market.confidence}%")
                    return True
                else:
                    logger.warning(f"BTC data insufficient: {len(self.btc_cache['15m'])}/50")
                    
            except Exception as e:
                logger.warning(f"BTC seed attempt {attempt+1} failed: {e}")
            
            await asyncio.sleep(5)
        
        return False
    
    async def _update_btc_data(self):
        """Update BTC cache"""
        try:
            self.btc_cache["15m"] = await self.exchange.fetch_ohlcv("BTC/USDT", "15m", 100)
            self.btc_cache["1h"] = await self.exchange.fetch_ohlcv("BTC/USDT", "1h", 50)
            self.btc_cache["4h"] = await self.exchange.fetch_ohlcv("BTC/USDT", "4h", 50)
        except Exception as e:
            logger.error(f"BTC update failed: {e}")
            raise
    
    async def _market_monitor(self):
        """Monitor market type every 15 min"""
        while True:
            try:
                await asyncio.sleep(900)  # 15 min
                
                if self._btc_data_ready:
                    market = market_detector.detect(
                        self.btc_cache["15m"],
                        self.btc_cache["1h"]
                    )
                    self._current_market = market.name
                    adaptive_engine.update_for_market(market.name)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Market monitor error: {e}")
                await asyncio.sleep(60)
    
    async def _daily_reset_monitor(self):
        """Reset daily counters at midnight"""
        while True:
            try:
                await asyncio.sleep(60)
                
                now = ist_now()
                if now.hour == 0 and now.minute == 0:
                    self._trades_today = 0
                    self._daily_loss = 0.0
                    profit_calculator.reset_daily()
                    
                    try:
                        await self.alerts.send_profit_update()
                    except Exception as e:
                        logger.warning(f"Profit update failed: {e}")
                    
                    logger.info("Daily reset complete")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Daily reset error: {e}")
    
    async def _run_health_server(self):
        """Run health check server for Railway"""
        try:
            app = web.Application()
            
            async def health_handler(request):
                self._last_health_check = datetime.now()
                return web.json_response({
                    "status": "ok",
                    "market": self._current_market,
                    "trades_today": self._trades_today,
                    "btc_ready": self._btc_data_ready,
                    "timestamp": datetime.now().isoformat(),
                    "uptime": str(datetime.now() - self._last_health_check)
                })
            
            app.router.add_get('/health', health_handler)
            app.router.add_get('/', health_handler)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', config.WEBHOOK_PORT)
            await site.start()
            
            logger.info(f"Health server running on port {config.WEBHOOK_PORT}")
            
            # Keep the server running
            while True:
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logger.info("Health server stopped")
        except Exception as e:
            logger.error(f"Health server error: {e}")
    
    async def _memory_monitor(self):
        """Monitor memory usage"""
        while True:
            try:
                await asyncio.sleep(300)  # 5 min
                
                import psutil
                process = psutil.Process()
                memory_usage = process.memory_percent()
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                logger.debug(f"Memory: {memory_mb:.1f}MB ({memory_usage:.1f}%)")
                
                if memory_mb > 400:  # If over 400MB
                    logger.warning(f"High memory usage: {memory_mb:.1f}MB - cleaning")
                    gc.collect()
                    
            except ImportError:
                # psutil not installed - skip
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Memory monitor error: {e}")
                await asyncio.sleep(300)
    
    async def on_candle_close(self, symbol: str, tf: str, ohlcv: list):
        """Process candle close"""
        try:
            if tf != "15m":
                return
            
            if not self._btc_data_ready:
                logger.debug(f"Candle ignored - BTC data not ready")
                return
            
            # Check sleep time
            if is_sleep_time():
                return
            
            # Check daily limits
            max_trades = config.MARKET_CONFIGS[self._current_market]["max_trades"]
            if self._trades_today >= max_trades:
                logger.debug(f"Max trades reached: {self._trades_today}/{max_trades}")
                return
            
            if self._daily_loss <= -config.MAX_DAILY_LOSS:
                logger.warning(f"Daily loss limit reached: {self._daily_loss}%")
                return
            
            # Get market-adaptive parameters
            market_config = adaptive_engine.get_params(self._current_market)
            
            # Fetch additional data
            try:
                ohlcv_5m = await self.exchange.fetch_ohlcv(symbol, "5m", 20)
                ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, "1h", 30)
            except Exception as e:
                logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
                return
            
            # Generate signal
            try:
                signal = generate_signal(
                    symbol=symbol,
                    ohlcv_15m=ohlcv,
                    ohlcv_5m=ohlcv_5m,
                    ohlcv_1h=ohlcv_1h,
                    btc_ohlcv_15m=self.btc_cache["15m"],
                    btc_ohlcv_1h=self.btc_cache["1h"],
                    btc_ohlcv_4h=self.btc_cache["4h"],
                    funding_rate=0,
                    fear_index=self.mood.fear_index,
                    account_size=config.ACCOUNT_SIZE,
                    risk_mgr=self.risk,
                    filters=self.filters,
                    engine=extreme_fear_engine,
                    mood=self.mood
                )
            except Exception as e:
                logger.error(f"Signal generation failed for {symbol}: {e}")
                return
            
            if signal:
                # Apply market-adaptive filters
                can_trade, reason = adaptive_engine.should_trade(
                    signal.extreme_fear_score,
                    signal.filters_passed,
                    self._current_market
                )
                
                if can_trade:
                    self._trades_today += 1
                    
                    try:
                        await self.alerts.send_signal(signal, self._current_market)
                        logger.info(f"✅ Signal sent: {symbol} | Market: {self._current_market}")
                    except Exception as e:
                        logger.error(f"Failed to send signal via Telegram: {e}")
                else:
                    logger.info(f"⏸️ Signal filtered: {reason}")
                    
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

async def main():
    """Main entry point with error handling"""
    try:
        bot = ArunabhaFinalBot()
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot exited")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)