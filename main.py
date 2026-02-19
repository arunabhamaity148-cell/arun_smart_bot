"""
ARUNABHA EXTREME FEAR BOT v3.1
Surgical execution engine with auto daily reset
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
    risk_manager  # Global instance
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
        self._btc_data_ready = False
        
        # FIX 3: Track current date for auto reset
        self._current_date = datetime.now().strftime("%Y-%m-%d")
    
    async def start(self):
        """Start surgical execution engine."""
        logger.info("=" * 70)
        logger.info("ARUNABHA SURGICAL EXECUTION ENGINE v3.1")
        logger.info("=" * 70)
        logger.info("Institutional-grade discipline initialized")
        
        await self.exchange.connect()
        await self.mood.fetch_fear_index()
        
        # Ensure BTC data is fully loaded BEFORE starting WebSocket
        await self._ensure_btc_data_loaded()
        
        if not self._btc_data_ready:
            logger.error("❌ CRITICAL: Cannot start without BTC data")
            await self.alerts.send_message("❌ Bot startup failed: BTC data unavailable")
            return
        
        self.ws = BinanceWSFeed(on_candle_close=self.on_candle_close)
        self.exchange.set_ws_feed(self.ws)
        
        await self.ws.seed_from_rest(self.exchange)
        await self.ws.start()
        
        await self.alerts.send_startup()
        await self.start_web_server()
        
        logger.info("Engine running - All protections active")
        
        # FIX 3: Start background task for daily reset check
        reset_task = asyncio.create_task(self._daily_reset_monitor())
        
        while True:
            await asyncio.sleep(60)
            
            if datetime.now().minute % 5 == 0:
                await self.mood.fetch_fear_index()
            
            if datetime.now().minute % 15 == 0:
                await self._update_btc_data()
            
            await self._check_active_trades()
    
    # FIX 3: New method to monitor and trigger daily reset
    async def _daily_reset_monitor(self):
        """
        Background task that checks for date change and triggers daily reset.
        Runs every minute to ensure reset happens at midnight.
        """
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_date = datetime.now().strftime("%Y-%m-%d")
                
                if current_date != self._current_date:
                    logger.info("🌅 DATE CHANGE DETECTED: %s -> %s", self._current_date, current_date)
                    
                    # Perform daily reset
                    self.risk.reset_daily()
                    self._current_date = current_date
                    
                    # Reset cooldowns in filters
                    self.filters.cooldown_map.clear()
                    
                    # Send notification
                    await self.alerts.send_message(
                        f"🌅 <b>Daily Reset Complete</b>\n"
                        f"Date: {current_date}\n"
                        f"All counters reset. Ready for new trading day."
                    )
                    
                    logger.info("✅ Daily reset completed for %s", current_date)
                    
            except Exception as exc:
                logger.error("Error in daily reset monitor: %s", exc)
                await asyncio.sleep(300)  # Wait 5 minutes on error before retry
    
    async def _ensure_btc_data_loaded(self):
        """
        Ensure BTC data is loaded with retries before starting WS
        """
        max_retries = 5
        retry_delay = 3  # seconds
        
        for attempt in range(1, max_retries + 1):
            logger.info(f"[BTC SEED] Attempt {attempt}/{max_retries}...")
            
            try:
                await self._update_btc_data()
                
                # Check if all timeframes have sufficient data
                has_15m = len(self.btc_cache["15m"]) >= 200
                has_1h = len(self.btc_cache["1h"]) >= 100
                has_4h = len(self.btc_cache["4h"]) >= 100
                
                if has_15m and has_1h and has_4h:
                    self._btc_data_ready = True
                    
                    # Log regime analysis
                    analysis = btc_detector.analyze(
                        self.btc_cache["15m"],
                        self.btc_cache["1h"],
                        self.btc_cache["4h"]
                    )
                    logger.info("[BTC] ✅ Data ready | Regime: %s | Mode: %s | Conf: %d%%",
                               analysis.regime.value, analysis.trade_mode,
                               analysis.confidence)
                    return True
                else:
                    logger.warning(f"[BTC] Partial data - 15m:{len(self.btc_cache['15m'])}/200, "
                                 f"1h:{len(self.btc_cache['1h'])}/100, "
                                 f"4h:{len(self.btc_cache['4h'])}/100")
                    
            except Exception as exc:
                logger.error(f"[BTC] Fetch error: {exc}")
            
            if attempt < max_retries:
                logger.info(f"[BTC] Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
        
        logger.error("❌ [BTC] Failed to load after all retries")
        return False
                
    async def _update_btc_data(self):
        """Fetch BTC multi-timeframe data."""
        try:
            self.btc_cache["15m"] = await self.exchange.fetch_ohlcv("BTC/USDT", "15m", 200)
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
            raise  # Re-raise to trigger retry logic
    
    async def _check_active_trades(self):
        """Check active trades for management."""
        if not self.risk.active_trades:
            return
        
        try:
            for symbol in list(self.risk.active_trades.keys()):
                ticker = await self.exchange.fetch_ticker(symbol)
                current_price = ticker.get("last", 0)
                
                action = self.risk.check_trade_management(symbol, current_price)
                
                if action == "PARTIAL_EXIT":
                    logger.info(f"[MANAGE] PARTIAL EXIT: {symbol} at 1R")
                elif action == "BREAK_EVEN":
                    logger.info(f"[MANAGE] SL → BE: {symbol} at +0.5%")
                    
        except Exception as exc:
            logger.error("Trade management error: %s", exc)
    
    async def on_candle_close(self, symbol: str, timeframe: str, ohlcv: list):
        """Process candle with surgical discipline."""
        if timeframe != config.TIMEFRAME:
            return
        
        # FIX 3: Check for date change on every candle
        current_date = datetime.now().strftime("%Y-%m-%d")
        if current_date != self._current_date:
            logger.info("🌅 Date change detected in candle handler, triggering reset...")
            # Reset will be handled by _daily_reset_monitor, but we can force it here too
            self.risk.reset_daily()
            self._current_date = current_date
        
        # Guard: Skip if BTC data not ready
        if not self._btc_data_ready:
            logger.warning(f"[SKIP] {symbol} - BTC data not ready")
            return
        
        # Guard: Check BTC cache validity
        if not all(self.btc_cache.values()) or len(self.btc_cache["15m"]) < 50:
            logger.warning(f"[SKIP] {symbol} - Insufficient BTC cache")
            return
        
        try:
            ohlcv_5m = await self.exchange.fetch_ohlcv(symbol, "5m", 50)
            ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, "1h", 50)
            funding = 0
            
            # FIX: Get account_size from config instead of hardcoded
            account_size = getattr(config, 'DEFAULT_ACCOUNT_SIZE', 1000)
            
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
                account_size=account_size,  # Use config value
                risk_mgr=self.risk,
                filters=self.filters,
                engine=self.engine,
                mood=self.mood
            )
            
            if signal and not signal.confirmation_pending:
                await self.alerts.send_signal(signal)
            elif signal and signal.confirmation_pending:
                logger.info(f"[PENDING] {symbol} waiting confirmation")
                
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
        if self._btc_data_ready and self.btc_cache["15m"] and self.btc_cache["1h"] and self.btc_cache["4h"]:
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
            "status": "ok" if self._btc_data_ready else "degraded",
            "version": "3.1-surgical",
            "btc_data_ready": self._btc_data_ready,
            "fear_index": self.mood.fear_index,
            "daily_stats": stats,
            "btc_regime": btc_info,
            "day_locked": stats.get("day_locked"),
            "lock_reason": stats.get("lock_reason"),
            "current_date": self._current_date  # FIX 3: Show current tracked date
        })


async def main():
    bot = ArunabhaBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
