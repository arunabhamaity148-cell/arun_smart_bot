"""
Exchange Manager – unified interface over CCXT.
Handles Binance futures / CoinDCX spot.

v10.1 — WebSocket-aware:
  • fetch_ohlcv() first checks WS cache (zero REST calls during normal ops)
  • REST is used only for seeding on startup and as fallback
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING

import ccxt.async_support as ccxt_async

import config

if TYPE_CHECKING:
    from exchanges.ws_feed import BinanceWSFeed

logger = logging.getLogger(__name__)


class ExchangeManager:
    """
    Thin async wrapper around a single CCXT exchange instance.
    All methods return plain Python dicts / lists so callers stay portable.
    """

    def __init__(self) -> None:
        self._exchange: Optional[ccxt_async.Exchange] = None
        self._ws_feed: Optional["BinanceWSFeed"]      = None   # set by main.py

    def set_ws_feed(self, feed: "BinanceWSFeed") -> None:
        """Attach the WebSocket feed so fetch_ohlcv can use cached data."""
        self._ws_feed = feed

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def connect(self) -> None:
        name = config.PRIMARY_EXCHANGE.lower()
        if name == "binance":
            self._exchange = ccxt_async.binanceusdm({
                "apiKey":          config.BINANCE_API_KEY,
                "secret":          config.BINANCE_SECRET,
                "enableRateLimit": True,
                "options":         {"defaultType": "future"},
            })
        elif name == "coindcx":
            self._exchange = ccxt_async.coindcx({
                "apiKey":          config.COINDCX_API_KEY,
                "secret":          config.COINDCX_SECRET,
                "enableRateLimit": True,
            })
        else:
            raise ValueError(f"Unsupported exchange: {name}")

        try:
            await self._exchange.load_markets()
            logger.info("Connected to %s", name)
        except Exception as exc:
            logger.error("Exchange connection failed: %s", exc)
            raise

    async def close(self) -> None:
        if self._exchange:
            await self._exchange.close()
            logger.info("Exchange connection closed")

    # ── OHLCV — WS-first, REST fallback ──────────────────────────────────

    async def fetch_ohlcv(
        self,
        symbol:    str,
        timeframe: str = "15m",
        limit:     int = 100,
    ) -> List[List[float]]:
        """
        1. Try WebSocket cache (instant, no API calls).
        2. Fall back to REST if cache is empty or feed not attached.
        """
        # ── WebSocket cache path ──────────────────────────────────────────
        if self._ws_feed is not None:
            cached = self._ws_feed.get_ohlcv(symbol, timeframe)
            if cached and len(cached) >= limit // 2:
                # Return the most recent `limit` candles
                return cached[-limit:]
            # Cache not warm yet — fall through to REST

        # ── REST fallback ─────────────────────────────────────────────────
        assert self._exchange, "Not connected"
        try:
            data = await self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            logger.debug("REST fetch %s %s (%d candles)", symbol, timeframe, len(data))
            return data
        except ccxt_async.NetworkError as exc:
            logger.warning("OHLCV network error %s %s: %s", symbol, timeframe, exc)
            raise
        except Exception as exc:
            logger.error("OHLCV error %s %s: %s", symbol, timeframe, exc)
            raise

    # ── Orderbook ─────────────────────────────────────────────────────────

    async def fetch_orderbook(
        self,
        symbol: str,
        limit:  int = 20,
    ) -> Dict[str, Any]:
        """Returns {'bids': [[price, vol], ...], 'asks': [[price, vol], ...]}."""
        assert self._exchange, "Not connected"
        try:
            ob = await self._exchange.fetch_order_book(symbol, limit)
            return {"bids": ob.get("bids", []), "asks": ob.get("asks", [])}
        except Exception as exc:
            logger.warning("Orderbook error %s: %s", symbol, exc)
            return {"bids": [], "asks": []}

    # ── Ticker ────────────────────────────────────────────────────────────

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        assert self._exchange, "Not connected"
        try:
            return await self._exchange.fetch_ticker(symbol)
        except Exception as exc:
            logger.warning("Ticker error %s: %s", symbol, exc)
            return {}

    # ── Multi-symbol helper ───────────────────────────────────────────────

    async def fetch_all_ohlcv(
        self,
        symbols:   List[str],
        timeframe: str = "15m",
        limit:     int = 100,
    ) -> Dict[str, List[List[float]]]:
        """Fetch OHLCV for multiple symbols concurrently."""
        tasks   = {sym: self.fetch_ohlcv(sym, timeframe, limit) for sym in symbols}
        results: Dict[str, List[List[float]]] = {}
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for sym, result in zip(tasks.keys(), gathered):
            if isinstance(result, Exception):
                logger.warning("Skipping %s: %s", sym, result)
                results[sym] = []
            else:
                results[sym] = result
        return results
