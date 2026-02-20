"""
ARUNABHA FINAL v4.0 - MAIN EXECUTION ENGINE
Market Adaptive | Indian Exchange Ready | ₹500/day Target
"""

import asyncio
import logging
import sys
from datetime import datetime

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
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
    
    async def start(self):
        logger.info("=" * 60)
        logger.info("ARUNABHA FINAL v4.0 - ₹500/DAY TARGET")
        logger.info("=" * 60)
        
        await self.exchange.connect()
        await self.mood.fetch_fear_index()
        
        if not await self._ensure_btc_data():
            logger.error("BTC data failed")
            return
        
        self.ws = BinanceWSFeed(on_candle_close=self.on_candle_close)
        self.exchange.set_ws_feed(self.ws)
        await self.ws.seed_from_rest(self.exchange)
        await self.ws.start()
        
        await self.alerts.send_startup()
        
        # Background tasks
        asyncio.create_task(self._market_monitor())
        asyncio.create_task(self._daily_reset_monitor())
        
        logger.info("Bot running - Manual trading only")
        
        while True:
            await asyncio.sleep(60)
            
            # Update fear index every 15 min
            if datetime.now().minute % 15 == 0:
                await self.mood.fetch_fear_index()
            
            # Update BTC data every 15 min
            if datetime.now().minute % 15 == 0:
                await self._update_btc_data()
    
    async def _ensure_btc_data(self):
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
            except Exception as e:
                logger.warning(f"BTC seed attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2)
        
        return False
    
    async def _update_btc_data(self):
        self.btc_cache["15m"] = await self.exchange.fetch_ohlcv("BTC/USDT", "15m", 100)
        self.btc_cache["1h"] = await self.exchange.fetch_ohlcv("BTC/USDT", "1h", 50)
        self.btc_cache["4h"] = await self.exchange.fetch_ohlcv("BTC/USDT", "4h", 50)
    
    async def _market_monitor(self):
        """Monitor market type every 15 min"""
        while True:
            await asyncio.sleep(900)  # 15 min
            
            if self._btc_data_ready:
                market = market_detector.detect(
                    self.btc_cache["15m"],
                    self.btc_cache["1h"]
                )
                self._current_market = market.name
                adaptive_engine.update_for_market(market.name)
    
    async def _daily_reset_monitor(self):
        """Reset daily counters at midnight"""
        while True:
            await asyncio.sleep(60)
            now = ist_now()
            if now.hour == 0 and now.minute == 0:
                self._trades_today = 0
                self._daily_loss = 0.0
                profit_calculator.reset_daily()
                await self.alerts.send_profit_update()
                logger.info("Daily reset complete")
    
    async def on_candle_close(self, symbol: str, tf: str, ohlcv: list):
        """Process candle close"""
        if tf != "15m":
            return
        
        if not self._btc_data_ready:
            return
        
        # Check sleep time
        if is_sleep_time():
            return
        
        # Check daily limits
        if self._trades_today >= config.MARKET_CONFIGS[self._current_market]["max_trades"]:
            return
        
        if self._daily_loss <= -config.MAX_DAILY_LOSS:
            logger.warning(f"Daily loss limit reached: {self._daily_loss}%")
            return
        
        # Get market-adaptive parameters
        market_config = adaptive_engine.get_params(self._current_market)
        
        try:
            ohlcv_5m = await self.exchange.fetch_ohlcv(symbol, "5m", 20)
            ohlcv_1h = await self.exchange.fetch_ohlcv(symbol, "1h", 30)
            
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
            
            if signal:
                # Apply market-adaptive filters
                can_trade, reason = adaptive_engine.should_trade(
                    signal.extreme_fear_score,
                    signal.filters_passed,
                    self._current_market
                )
                
                if can_trade:
                    self._trades_today += 1
                    await self.alerts.send_signal(signal, self._current_market)
                    logger.info(f"✅ Signal sent: {symbol} | Market: {self._current_market}")
                else:
                    logger.info(f"⏸️ Signal filtered: {reason}")
                    
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

async def main():
    bot = ArunabhaFinalBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())