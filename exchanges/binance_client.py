"""
Binance-specific helpers (futures, funding rate, open interest).
Optional – only used if PRIMARY_EXCHANGE = binance.
"""

import logging
from typing import Dict, Any, Optional

import ccxt.async_support as ccxt_async
import config

logger = logging.getLogger(__name__)


class BinanceClient:
    """Extended Binance futures data – open interest, funding rate."""

    def __init__(self) -> None:
        self._client: Optional[ccxt_async.binanceusdm] = None

    async def connect(self) -> None:
        self._client = ccxt_async.binanceusdm({
            "apiKey": config.BINANCE_API_KEY,
            "secret": config.BINANCE_SECRET,
            "enableRateLimit": True,
        })
        await self._client.load_markets()

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    async def get_funding_rate(self, symbol: str) -> float:
        """Returns current funding rate as float (0.0001 = 0.01%)."""
        try:
            info = await self._client.fetch_funding_rate(symbol)
            return float(info.get("fundingRate", 0.0))
        except Exception as exc:
            logger.debug("Funding rate error %s: %s", symbol, exc)
            return 0.0

    async def get_open_interest(self, symbol: str) -> Dict[str, Any]:
        """Returns open interest dict with 'openInterestAmount'."""
        try:
            return await self._client.fetch_open_interest(symbol)
        except Exception as exc:
            logger.debug("Open interest error %s: %s", symbol, exc)
            return {}