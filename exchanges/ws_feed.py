"""
ws_feed.py - ARUNABHA EXTREME FEAR BOT
WebSocket feed - Compatible with on_candle_close callback
"""

import asyncio
import json
import logging
from collections import deque
from typing import Callable, Coroutine, Dict, List, Optional, Tuple

import aiohttp
import config

logger = logging.getLogger(__name__)

_TIMEFRAMES = config.TIMEFRAMES
_CACHE_SIZE = 100


def _symbol_to_stream(symbol: str, tf: str) -> str:
    """'BTC/USDT', '15m' → 'btcusdt@kline_15m'"""
    return symbol.replace("/", "").lower() + f"@kline_{tf}"


class _StreamRegistry:
    """Bidirectional mapping: stream_name ↔ (symbol, tf)"""
    
    def __init__(self, symbols: List[str], timeframes: List[str]):
        self._s2k: Dict[str, Tuple[str, str]] = {}
        self._k2s: Dict[Tuple[str, str], str] = {}
        
        for sym in symbols:
            for tf in timeframes:
                stream = _symbol_to_stream(sym, tf)
                key = (sym, tf)
                self._s2k[stream] = key
                self._k2s[key] = stream
    
    def stream_names(self) -> List[str]:
        return list(self._s2k.keys())
    
    def key(self, stream_name: str) -> Optional[Tuple[str, str]]:
        return self._s2k.get(stream_name)
    
    def stream(self, symbol: str, tf: str) -> Optional[str]:
        return self._k2s.get((symbol, tf))


class BinanceWSFeed:
    """
    WebSocket feed with on_candle_close callback
    """
    
    def __init__(
        self,
        on_candle_close: Optional[Callable[[str, str, List[List[float]]], Coroutine]] = None
    ):
        self.on_candle_close = on_candle_close  # 🆕 CORRECT parameter name
        self._registry = _StreamRegistry(config.TRADING_PAIRS, _TIMEFRAMES)
        
        # Cache: (symbol, tf) -> deque of candles
        self._cache: Dict[Tuple[str, str], deque] = {
            (sym, tf): deque(maxlen=_CACHE_SIZE)
            for sym in config.TRADING_PAIRS
            for tf in _TIMEFRAMES
        }
        
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    def get_ohlcv(self, symbol: str, tf: str) -> List[List[float]]:
        """Get cached OHLCV"""
        return list(self._cache.get((symbol, tf), []))
    
    async def seed_from_rest(self, exchange):
        """Pre-fill cache from REST API"""
        logger.info("🌱 Seeding cache from REST...")
        
        for sym in config.TRADING_PAIRS:
            for tf in _TIMEFRAMES:
                try:
                    candles = await exchange.fetch_ohlcv(sym, tf, _CACHE_SIZE)
                    if candles:
                        self._cache[(sym, tf)].extend(candles)
                        logger.debug(f"Seeded {sym} {tf}: {len(candles)} candles")
                except Exception as exc:
                    logger.warning(f"Seed failed {sym} {tf}: {exc}")
        
        logger.info("🌱 Seeding complete")
    
    async def start(self):
        """Start WebSocket connection"""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_forever())
        logger.info("🔌 WebSocket started")
    
    async def stop(self):
        """Stop WebSocket"""
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🔌 WebSocket stopped")
    
    async def _run_forever(self):
        """Reconnect loop"""
        while not self._stop_event.is_set():
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"WS error: {exc} - reconnecting in 5s...")
                await asyncio.sleep(5)
    
    async def _connect_and_listen(self):
        """Connect and listen to streams"""
        streams = "/".join(self._registry.stream_names())
        url = f"wss://fstream.binance.com/stream?streams={streams}"
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                url,
                heartbeat=20,
                receive_timeout=60
            ) as ws:
                logger.info(f"✅ WS connected")
                
                async for msg in ws:
                    if self._stop_event.is_set():
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_message(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        logger.warning("WS closed/error")
                        break
    
    async def _handle_message(self, raw: str):
        """Handle incoming message"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        
        # Get stream info
        stream_name = data.get("stream", "")
        payload = data.get("data", data)
        
        key = self._registry.key(stream_name)
        if not key:
            return
        
        symbol, tf = key
        
        # Parse kline
        k = payload.get("k", {})
        if not k:
            return
        
        candle = [
            k["t"],  # timestamp
            float(k["o"]),  # open
            float(k["h"]),  # high
            float(k["l"]),  # low
            float(k["c"]),  # close
            float(k["v"]),  # volume
        ]
        
        is_closed = k.get("x", False)
        
        # Update live candle or add to cache
        if is_closed:
            self._cache[key].append(candle)
            logger.debug(f"Closed candle: {symbol} {tf} @ {candle[4]}")
            
            # 🆕 FIXED: Call on_candle_close with correct signature
            if self.on_candle_close:
                try:
                    await self.on_candle_close(symbol, tf, list(self._cache[key]))
                except Exception as exc:
                    logger.error(f"Callback error: {exc}")
