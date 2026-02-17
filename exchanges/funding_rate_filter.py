"""
funding_rate_filter.py — ARUNABHA SMART v10.1
═══════════════════════════════════════════════
Funding Rate Filter

Logic:
  Binance perpetual funding rate refreshes every 8 hours.
  Extreme funding = crowded trade → fade the crowd.

  HIGH POSITIVE funding (+0.05%+):
    → Market is crowded LONG → avoid new LONGs, prefer SHORTs
  HIGH NEGATIVE funding (-0.05%+):
    → Market is crowded SHORT → avoid new SHORTs, prefer LONGs

Thresholds:
  NEUTRAL zone:  -0.05% to +0.05%  (funding_rate between -0.0005 and +0.0005)
  WARNING zone:  ±0.05% to ±0.10%  (reduce confidence but allow)
  EXTREME zone:  beyond ±0.10%     (block signal in crowded direction)

REST call: once per symbol per scan (cheap, not frequent like OHLCV).
Result is cached for 8 minutes to avoid repeated calls.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple

import ccxt.async_support as ccxt_async
import config

logger = logging.getLogger(__name__)

# Thresholds (as raw float, e.g. 0.0005 = 0.05%)
FUNDING_NEUTRAL_MAX  =  0.0005   # +0.05%
FUNDING_NEUTRAL_MIN  = -0.0005   # -0.05%
FUNDING_EXTREME_MAX  =  0.0010   # +0.10%
FUNDING_EXTREME_MIN  = -0.0010   # -0.10%

# Cache TTL: 8 minutes (funding rate updates every 8h, checking more often is wasteful)
_CACHE_TTL_SEC = 480


class FundingRateFilter:
    """
    Fetches and caches Binance funding rates.
    Evaluates whether funding conditions permit a trade.
    """

    def __init__(self) -> None:
        # Cache: symbol → (rate: float, fetched_at: float)
        self._cache: Dict[str, Tuple[float, float]] = {}
        self._client: Optional[ccxt_async.binanceusdm] = None

    async def connect(self) -> None:
        """Reuse the existing Binance credentials."""
        if config.PRIMARY_EXCHANGE.lower() != "binance":
            return   # CoinDCX doesn't have perpetual funding
        self._client = ccxt_async.binanceusdm({
            "apiKey":          config.BINANCE_API_KEY,
            "secret":          config.BINANCE_SECRET,
            "enableRateLimit": True,
        })

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    async def get_funding_rate(self, symbol: str) -> float:
        """
        Returns current funding rate for `symbol`.
        Uses in-memory cache (8-min TTL) to avoid excess REST calls.
        Returns 0.0 on any error (neutral — don't block signals on data failure).
        """
        now = time.monotonic()

        # Cache hit
        if symbol in self._cache:
            rate, fetched_at = self._cache[symbol]
            if now - fetched_at < _CACHE_TTL_SEC:
                return rate

        # Cache miss — fetch from REST
        if self._client is None:
            return 0.0

        try:
            info = await self._client.fetch_funding_rate(symbol)
            rate = float(info.get("fundingRate", 0.0))
            self._cache[symbol] = (rate, now)
            logger.debug("Funding rate %s: %.4f%%", symbol, rate * 100)
            return rate
        except Exception as exc:
            logger.warning("Funding rate fetch failed %s: %s", symbol, exc)
            self._cache[symbol] = (0.0, now)   # cache the miss too
            return 0.0

    def evaluate(self, direction: str, rate: float) -> Tuple[bool, str]:
        """
        Returns (passes: bool, reason: str).

        LONG  + HIGH POSITIVE rate → FAIL (crowded long, likely liquidation cascade)
        SHORT + HIGH NEGATIVE rate → FAIL (crowded short, likely short squeeze)
        """
        rate_pct = rate * 100   # convert to % for readability

        if direction == "LONG":
            if rate >= FUNDING_EXTREME_MAX:
                reason = f"Funding={rate_pct:+.3f}% (crowded LONG — skip)"
                logger.info("💸 FUNDING BLOCK [LONG] %s", reason)
                return False, reason
            elif rate >= FUNDING_NEUTRAL_MAX:
                reason = f"Funding={rate_pct:+.3f}% (elevated, allowed)"
                logger.info("💸 FUNDING WARN  [LONG] %s", reason)
                return True, reason   # warning but not block
            else:
                return True, f"Funding={rate_pct:+.3f}% OK"

        else:  # SHORT
            if rate <= FUNDING_EXTREME_MIN:
                reason = f"Funding={rate_pct:+.3f}% (crowded SHORT — skip)"
                logger.info("💸 FUNDING BLOCK [SHORT] %s", reason)
                return False, reason
            elif rate <= FUNDING_NEUTRAL_MIN:
                reason = f"Funding={rate_pct:+.3f}% (elevated, allowed)"
                logger.info("💸 FUNDING WARN  [SHORT] %s", reason)
                return True, reason
            else:
                return True, f"Funding={rate_pct:+.3f}% OK"

    async def passes(self, direction: str, symbol: str) -> Tuple[bool, str]:
        """Convenience: fetch + evaluate in one call."""
        rate = await self.get_funding_rate(symbol)
        return self.evaluate(direction, rate)

    def format_for_alert(self, symbol: str) -> str:
        """Human-readable funding rate for Telegram alerts."""
        if symbol not in self._cache:
            return ""
        rate, _ = self._cache[symbol]
        pct = rate * 100
        if abs(rate) >= FUNDING_EXTREME_MAX:
            icon = "🔴"
        elif abs(rate) >= FUNDING_NEUTRAL_MAX:
            icon = "🟡"
        else:
            icon = "🟢"
        return f"{icon} Funding: {pct:+.3f}%"
