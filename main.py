"""
ARUNABHA EXTREME FEAR BOT v3.2
Conservative Elite Institutional Mode
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
        self.risk = risk_manager
        self.mood = MarketMood()
        self.ws = None
        
        self.btc_cache = {
            "15m": [],
            "1h": [],
            "4h": []
        }
        self.last_btc_update = None
        self._btc_data_ready = False
        
        self._current_date = datetime.now().strftime("%Y-%m-%d")
        self._reset_lock = False  # FIX 11: Prevent double reset
    
    async def start(self):
        """Start Conservative Elite Institutional execution engine."""
        logger.info("=" * 70)
        logger.info("ARUNABHA CONSERVATIVE ELITE INSTITUTIONAL v3.2")
        logger.info("=" * 70)
        logger.info("High-Quality Execution | Capital Protection | 65%+ Win Target")
        
        await self.exchange.connect()
        await self.mood.fetch_fear_index()
        
        await self._ensure_btc_data_loaded()
        
        if not self._btc_data_ready:
            logger.error("❌ CRITICAL: Cannot start without BTC data")
            await self.alerts.send_message("❌ Elite Bot startup failed: BTC data unavailable")
            return
        
        self.ws = BinanceWSFeed(on_candle_close=self.on_candle_close)
        self.exchange.set_ws_feed(self.ws)
        
        await self.ws.seed_from_rest(self.exchange)
        await self.ws.start()
        
        await self.alerts.send_startup()
        await self.start_web_server()
        
        logger.info("Elite Engine running - Conservative Mode Active")
        
        # FIX 11: Only background reset monitor, no candle-based reset
        reset_task = asyncio.create_task(self._daily_reset_monitor())
        
        while True:
            await asyncio.sleep(60)
            
            if datetime.now().minute % 5 == 0:
                await self.mood.fetch_fear_index()
            
            if datetime.now().minute % 15 == 0:
                await self._update_btc_data()
            
            await self._check_active_trades()
    
    # FIX 11: Single source of truth for daily reset
    async def _daily_reset_monitor(self):
        """
        Exclusive daily reset monitor - prevents double reset.
        """
        while True:
            try:
                await asyncio.sleep(60)
                
                current_date = datetime.now().strftime("%Y-%m-%d")
                
                # FIX 11: Lock mechanism prevents double reset
                if current_date != self._current_date and not self._reset_lock:
                    self._reset_lock = True  # Acquire lock
                    
                    logger.info("🌅 ELITE RESET: %s -> %s", self._current_date, current_date)
                    
                    self.risk.reset_daily()
                    self._current_date = current_date
                    self.filters.cooldown_map.clear()
                    
                    await self.alerts.send_message(
                        f"🌅 <b>Elite Daily Reset</b>\n"
                        f"Date: {current_date}\n"
                        f"Conservative Mode | 2-3 Trades/Day Target\n"
                        f"Grade A/A+ Only | Capital Protection ON"
                    )
                    
                    logger.info("✅ Elite reset completed")
                    
                    # Release lock after short delay
                    await asyncio.sleep(5)
                    self._reset_lock = False
                    
            except Exception as exc:
                logger.error("Reset monitor error: %s", exc)
                self._reset_lock = False  # Release on error
                await asyncio.sleep(300)
    
    async def _ensure_btc_data_loaded(self):
        max_retries = 5
        retry_delay = 3
        
        for attempt in range(1, max_retries + 1):
            logger.info(f"[BTC SEED] Attempt {attempt}/{max_retries}...")
            
            try:
                await self._update_btc_data()
                
                has_15m = len(self.btc_cache["15m"]) >= 200
                has_1h = len(self.btc_cache["1h"]) >= 100
                has_4h = len(self.btc_cache["4h"]) >= 100
                
                if has_15m and has_1h and has_4h:
                    self._btc_data_ready = True
                    
                    analysis = btc_detector.analyze(
                        self.btc_cache["15m"],
                        self.btc_cache["1h"],
                        self.btc_cache["4h"]
                    )
                    logger.info("[BTC] ✅ Elite Data Ready | Regime: %s | Conf: %d%%",
                               analysis.regime.value, analysis.confidence)
                    return True
                else:
                    logger.warning(f"[BTC] Partial data - 15m:{len(self.btc_cache['15m'])}/200")
                    
            except Exception as exc:
                logger.error(f"[BTC] Fetch error: {exc}")
            
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
        
        logger.error("❌ [BTC] Failed to load after all retries")
        return False
                
    async def _update_btc_data(self):
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
                logger.info("[BTC] %s | Conf:%d%% | %s",
                           analysis.regime.value, analysis.confidence,
                           "TRADE" if analysis.can_trade else "BLOCK")
        except Exception as exc:
            logger.error("BTC update failed: %s", exc)
            raise
    
    async def _check_active_trades(self):
        if not self.risk.active_trades:
            return
        
        try:
            for symbol in list(self.risk.active_trades.keys()):
                ticker = await self.exchange.fetch_ticker(symbol)
                current_price = ticker.get("last", 0)
                
                action = self.risk.check_trade_management(symbol, current_price)
                
                if action == "PARTIAL_EXIT":
                    logger.info(f"[ELITE] PARTIAL: {symbol} at 1R")
                elif action == "BREAK_EVEN":
                    logger.info(f"[ELITE] BE: {symbol} SL→Entry")
                    
        except Exception as exc:
            logger.error("Trade management error: %s", exc)
    
    async def on_candle_close(self, symbol: str, timeframe: str, ohlcv: list):
        """Process candle - Conservative Elite Mode."""
        if timeframe != config.TIMEFRAME:
            return
        
        # FIX 11: Removed candle-based reset - only background monitor handles this
        
        if not self._btc_data_ready:
            logger.warning(f"[SKIP] {symbol} - BTC data not ready")
            return
        
        if not all(self.btc_cache.values()) or len(self.btc_cache["15m"]) < 50:
            logger.warning(f"[SKIP] {symbol} - Insufficient BTC cache")
            return
        
        try:
            ohlcv_5m = await self.exchange.fetch_ohlcv(symbol, "5m", 50)
            ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, "1h", 50)
            funding = 0
            
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
                account_size=account_size,
                risk_mgr=self.risk,
                filters=self.filters,
                engine=self.engine,
                mood=self.mood
            )
            
            if signal and not signal.confirmation_pending:
                await self.alerts.send_signal(signal)
            elif signal and signal.confirmation_pending:
                logger.info(f"[ELITE PENDING] {symbol}")
                
        except Exception as exc:
            logger.error("Error processing %s: %s", symbol, exc)
    
    async def start_web_server(self):
        app = web.Application()
        app.router.add_get('/health', self.health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', config.WEBHOOK_PORT)
        await site.start()
        
        logger.info("Health server on port %d", config.WEBHOOK_PORT)
    
    async def health_handler(self, request):
        stats = self.risk.get_stats()
        
        btc_info = "No data"
        if self._btc_data_ready:
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
            "status": "elite" if self._btc_data_ready else "degraded",
            "version": "3.2-conservative-elite",
            "mode": "Conservative Institutional",
            "btc_data_ready": self._btc_data_ready,
            "fear_index": self.mood.fear_index,
            "daily_stats": stats,
            "btc_regime": btc_info,
            "day_locked": stats.get("day_locked"),
            "lock_reason": stats.get("lock_reason"),
            "current_date": self._current_date,
            "target": "2-3 high-quality trades/day | 65%+ win rate"
        })


async def main():
    bot = ArunabhaBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
