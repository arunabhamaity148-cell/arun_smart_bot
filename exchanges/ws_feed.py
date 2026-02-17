"""
ws_feed.py — ARUNABHA SMART v10.0
════════════════════════════════════
Binance WebSocket kline feed.

• Subscribes to kline streams for all TRADING_PAIRS across required timeframes.
• Maintains an in-memory OHLCV cache (deque of 150 candles per symbol+tf).
• Fires a callback when a candle closes (is_closed == True).
• Replaces polling — zero REST calls during normal operation.

Stream format:
  wss://fstream.binance.com/stream?streams=btcusdt@kline_15m/ethusdt@kline_15m/...
"""

import asyncio
import json
import logging
from collections import deque
from typing import Callable, Coroutine, Dict, List, Optional, Set, Tuple

import aiohttp

import config

logger = logging.getLogger(__name__)

# OHLCV candle: [timestamp_ms, open, high, low, close, volume]
Candle      = List[float]
OHLCVCache  = Dict[Tuple[str, str], deque]          # (symbol, timeframe) → deque[Candle]
ClosedCandle = Tuple[str, str, Candle]              # (symbol, timeframe, candle)

# Binance futures WebSocket base
_WS_BASE = "wss://fstream.binance.com/stream?streams={streams}"

# How many completed candles to keep per (symbol, tf)
_CACHE_SIZE = 150

# Timeframes the bot monitors
_TIMEFRAMES = config.TIMEFRAMES   # ["5m", "15m", "1h"]

# Reconnect delay on error
_RECONNECT_DELAY_SEC = 5


def _symbol_to_stream(symbol: str, tf: str) -> str:
    """'BTC/USDT', '15m' → 'btcusdt@kline_15m'"""
    return symbol.replace("/", "").lower() + f"@kline_{tf}"


def _stream_to_key(stream: str) -> Tuple[str, str]:
    """'btcusdt@kline_15m' → ('BTC/USDT', '15m')"""
    base, rest = stream.split("@kline_")
    # rebuild symbol with slash (e.g. btcusdt → BTC/USDT)
    # We keep a reverse-lookup built at init time instead
    raise NotImplementedError("use _StreamRegistry")


class _StreamRegistry:
    """Bidirectional mapping: stream_name ↔ (symbol, tf)"""

    def __init__(self, symbols: List[str], timeframes: List[str]) -> None:
        self._s2k: Dict[str, Tuple[str, str]] = {}
        self._k2s: Dict[Tuple[str, str], str] = {}
        for sym in symbols:
            for tf in timeframes:
                stream = _symbol_to_stream(sym, tf)
                key    = (sym, tf)
                self._s2k[stream] = key
                self._k2s[key]    = stream

    def stream_names(self) -> List[str]:
        return list(self._s2k.keys())

    def key(self, stream_name: str) -> Optional[Tuple[str, str]]:
        return self._s2k.get(stream_name)

    def stream(self, symbol: str, tf: str) -> Optional[str]:
        return self._k2s.get((symbol, tf))


class BinanceWSFeed:
    """
    Maintains live OHLCV caches for all pairs × timeframes.

    Usage:
        feed = BinanceWSFeed(on_candle_close=my_callback)
        await feed.start()          # starts background task
        ohlcv = feed.get_ohlcv("BTC/USDT", "15m")
        await feed.stop()

    on_candle_close(symbol, timeframe, ohlcv_cache) is called every time
    a candle closes so the scan loop can react immediately.
    """

    def __init__(
        self,
        on_candle_close: Optional[Callable[[str, str, List[Candle]], Coroutine]] = None,
    ) -> None:
        self._on_close      = on_candle_close
        self._registry      = _StreamRegistry(config.TRADING_PAIRS, _TIMEFRAMES)
        self._cache: OHLCVCache = {
            (sym, tf): deque(maxlen=_CACHE_SIZE)
            for sym in config.TRADING_PAIRS
            for tf  in _TIMEFRAMES
        }
        self._live: Dict[Tuple[str, str], Candle] = {}  # current (open) candle
        self._task: Optional[asyncio.Task]         = None
        self._stop_event                           = asyncio.Event()

        # Track which (sym, tf) combos have been seeded with REST data
        self._seeded: Set[Tuple[str, str]] = set()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_ohlcv(self, symbol: str, tf: str) -> List[Candle]:
        """
        Returns list of closed candles (oldest first), optionally with
        the current live (open) candle appended.
        """
        key    = (symbol, tf)
        closed = list(self._cache.get(key, []))
        live   = self._live.get(key)
        if live:
            closed.append(live)
        return closed

    def is_ready(self, symbol: str, tf: str, min_candles: int = 50) -> bool:
        """True once enough candles have accumulated."""
        return len(self._cache.get((symbol, tf), [])) >= min_candles

    async def seed_from_rest(self, exchange) -> None:
        """
        Pre-fill caches using REST OHLCV before WebSocket data arrives.
        Called once at startup with the ExchangeManager.
        Runs in parallel for all (symbol, tf) combinations.
        """
        logger.info("🌱 Seeding OHLCV cache from REST…")
        tasks = []
        for sym in config.TRADING_PAIRS:
            for tf in _TIMEFRAMES:
                tasks.append(self._seed_one(exchange, sym, tf))
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("🌱 Seeding complete — %d streams ready", len(self._seeded))

    async def _seed_one(self, exchange, symbol: str, tf: str) -> None:
        try:
            candles = await exchange.fetch_ohlcv(symbol, tf, limit=_CACHE_SIZE)
            if candles:
                cache = self._cache[(symbol, tf)]
                for c in candles:
                    cache.append(c)
                self._seeded.add((symbol, tf))
                logger.debug("Seeded %s %s with %d candles", symbol, tf, len(candles))
        except Exception as exc:
            logger.warning("Seed failed %s %s: %s", symbol, tf, exc)

    async def start(self) -> None:
        """Launch the WebSocket listener as a background task."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_forever(), name="ws_feed")
        logger.info("WebSocket feed started (%d streams)", len(self._registry.stream_names()))

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("WebSocket feed stopped")

    # ── Internal WebSocket loop ───────────────────────────────────────────────

    async def _run_forever(self) -> None:
        """Reconnect loop — restarts on any connection error."""
        while not self._stop_event.is_set():
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("WS disconnected: %s — reconnecting in %ds",
                               exc, _RECONNECT_DELAY_SEC)
                await asyncio.sleep(_RECONNECT_DELAY_SEC)

    async def _connect_and_listen(self) -> None:
        streams   = "/".join(self._registry.stream_names())
        url       = _WS_BASE.format(streams=streams)

        timeout   = aiohttp.ClientTimeout(total=None, sock_read=30)
        connector = aiohttp.TCPConnector(ssl=True)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.ws_connect(
                url,
                heartbeat=20,           # send ping every 20 s
                receive_timeout=60,     # raise if no data for 60 s
            ) as ws:
                logger.info("✅ WS connected: %s", url[:80] + "…")
                async for msg in ws:
                    if self._stop_event.is_set():
                        break
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_message(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSED,
                                      aiohttp.WSMsgType.ERROR):
                        logger.warning("WS closed/error: %s", msg)
                        break

    async def _handle_message(self, raw: str) -> None:
        try:
            outer = json.loads(raw)
        except json.JSONDecodeError:
            return

        # Combined stream format: {"stream": "btcusdt@kline_15m", "data": {...}}
        stream_name = outer.get("stream", "")
        data        = outer.get("data", outer)   # fallback for single-stream format

        key = self._registry.key(stream_name)
        if key is None:
            return

        k = data.get("k") or data.get("K")
        if k is None:
            return

        symbol, tf = key
        candle: Candle = [
            float(k["t"]),   # open time ms
            float(k["o"]),   # open
            float(k["h"]),   # high
            float(k["l"]),   # low
            float(k["c"]),   # close
            float(k["v"]),   # volume
        ]

        # Update live (current open) candle
        self._live[key] = candle

        is_closed = bool(k.get("x", False))
        if is_closed:
            # Push closed candle into cache
            self._cache[key].append(candle)
            del self._live[key]

            logger.debug("Candle closed %s %s close=%.4f", symbol, tf, candle[4])

            # Fire callback
            if self._on_close:
                ohlcv_snapshot = list(self._cache[key])
                try:
                    await self._on_close(symbol, tf, ohlcv_snapshot)
                except Exception as exc:
                    logger.error("on_candle_close error %s %s: %s", symbol, tf, exc,
                                 exc_info=True)
