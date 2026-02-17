"""
CoinDCX-specific helpers.
Optional – only used if PRIMARY_EXCHANGE = coindcx.
"""

import logging
from typing import Dict, Any, Optional

import ccxt.async_support as ccxt_async
import config

logger = logging.getLogger(__name__)


class CoinDCXClient:
    """CoinDCX spot market helper."""

    def __init__(self) -> None:
        self._client: Optional[ccxt_async.coindcx] = None

    async def connect(self) -> None:
        self._client = ccxt_async.coindcx({
            "apiKey": config.COINDCX_API_KEY,
            "secret": config.COINDCX_SECRET,
            "enableRateLimit": True,
        })
        await self._client.load_markets()

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        try:
            return await self._client.fetch_ticker(symbol)
        except Exception as exc:
            logger.debug("CoinDCX ticker error %s: %s", symbol, exc)
            return {}