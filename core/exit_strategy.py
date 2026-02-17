"""
exit_strategy.py — ARUNABHA SMART v10.2
══════════════════════════════════════════
Adaptive Exit Strategy — live bot integration.

Rules:
  1. Entry হলেই hard SL + hard TP set
  2. 1.0× RR → SL breakeven-এ move করো
  3. 1.5× RR → 50% position close (partial TP)
  4. Partial-এর পর → 0.8× ATR trailing stop চালু
  5. Hard TP = 2.5× RR (বা regime TP mult × ATR)
  6. Hard SL সবসময় active

Telegram alert:
  প্রতিটা stage-এ আলাদা notification পাঠায়।
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ActiveTrade:
    """State of one open trade."""
    symbol:          str
    direction:       str           # "LONG" | "SHORT"
    entry_price:     float
    initial_sl:      float
    take_profit:     float
    atr:             float
    timeframe:       str

    # Mutable state
    current_sl:      float = 0.0
    trail_sl:        float = 0.0
    breakeven_moved: bool  = False
    partial_closed:  bool  = False
    trail_active:    bool  = False
    candles_open:    int   = 0

    def __post_init__(self):
        self.current_sl = self.initial_sl
        self.trail_sl   = self.initial_sl

    @property
    def sl_dist(self) -> float:
        return abs(self.entry_price - self.initial_sl)

    @property
    def tp_dist(self) -> float:
        return abs(self.entry_price - self.take_profit)

    def progress(self, current_price: float) -> float:
        """How many R units of profit currently showing."""
        if self.sl_dist <= 0:
            return 0.0
        if self.direction == "LONG":
            return (current_price - self.entry_price) / self.sl_dist
        else:
            return (self.entry_price - current_price) / self.sl_dist


class ExitManager:
    """
    Manages all open trades and fires exit alerts.

    Usage in main.py scan loop:
        exit_mgr = ExitManager(alerts)
        exit_mgr.open_trade(signal)          # when signal fires
        await exit_mgr.update(exchange)      # call on every candle close
    """

    def __init__(self, alerts=None) -> None:
        self._alerts = alerts
        self._trades: dict = {}   # symbol → ActiveTrade

    def open_trade(self, signal) -> None:
        """Register a new trade from SignalResult."""
        trade = ActiveTrade(
            symbol      = signal.symbol,
            direction   = signal.direction,
            entry_price = signal.entry,
            initial_sl  = signal.stop_loss,
            take_profit = signal.take_profit,
            atr         = signal.smc.get("atr", abs(signal.entry - signal.stop_loss) / 1.5),
            timeframe   = signal.timeframe,
        )
        self._trades[signal.symbol] = trade
        logger.info(
            "📬 Trade opened: %s %s | Entry=%.4f SL=%.4f TP=%.4f",
            signal.symbol, signal.direction,
            signal.entry, signal.stop_loss, signal.take_profit,
        )

    def close_trade(self, symbol: str) -> None:
        """Remove trade from active trades (call from main when SL/TP hit)."""
        self._trades.pop(symbol, None)

    def get_active(self) -> dict:
        return dict(self._trades)

    async def update_trade(
        self,
        trade:     ActiveTrade,
        high:      float,
        low:       float,
        close:     float,
        exchange=  None,
    ) -> Tuple[Optional[str], float]:
        """
        Update one trade with new candle data.
        Returns (exit_reason or None, exit_price).

        exit_reason values:
          "SL"           — stop loss hit
          "TP"           — full take profit hit
          "BREAKEVEN"    — SL moved to breakeven (info only, no exit)
          "PARTIAL_TP"   — 50% closed at 1.5× RR
          "TRAIL_STOP"   — trailing stop hit after partial
        """
        trade.candles_open += 1

        current_price = high if trade.direction == "LONG" else low
        adverse_price = low  if trade.direction == "LONG" else high
        prog          = trade.progress(current_price)

        # ── Hard SL ──────────────────────────────────────────────────────────
        if trade.direction == "LONG" and adverse_price <= trade.current_sl:
            await self._notify("SL", trade, trade.current_sl)
            return "SL", trade.current_sl

        if trade.direction == "SHORT" and adverse_price >= trade.current_sl:
            await self._notify("SL", trade, trade.current_sl)
            return "SL", trade.current_sl

        # ── Hard TP ───────────────────────────────────────────────────────────
        if trade.direction == "LONG" and high >= trade.take_profit:
            await self._notify("TP", trade, trade.take_profit)
            return "TP", trade.take_profit

        if trade.direction == "SHORT" and low <= trade.take_profit:
            await self._notify("TP", trade, trade.take_profit)
            return "TP", trade.take_profit

        # ── Move to Breakeven at 1.0× RR ─────────────────────────────────────
        if prog >= 1.0 and not trade.breakeven_moved:
            trade.current_sl      = trade.entry_price
            trade.breakeven_moved = True
            await self._notify("BREAKEVEN", trade, trade.entry_price)
            logger.info("🔒 BE move %s | Progress=%.2fR", trade.symbol, prog)

        # ── Partial close at 1.5× RR ─────────────────────────────────────────
        if prog >= 1.5 and not trade.partial_closed:
            trade.partial_closed = True
            trade.trail_active   = True

            # Start trail from current price
            if trade.direction == "LONG":
                trade.trail_sl = current_price - trade.atr * 0.8
            else:
                trade.trail_sl = current_price + trade.atr * 0.8
            trade.current_sl = trade.trail_sl

            await self._notify("PARTIAL_TP", trade, current_price)
            return "PARTIAL_TP", current_price

        # ── Trailing stop (after partial close) ───────────────────────────────
        if trade.trail_active:
            if trade.direction == "LONG":
                new_trail = current_price - trade.atr * 0.8
                if new_trail > trade.trail_sl:
                    trade.trail_sl   = new_trail
                    trade.current_sl = new_trail
                    logger.debug("Trail up %s → %.4f", trade.symbol, new_trail)
                if adverse_price <= trade.trail_sl:
                    await self._notify("TRAIL_STOP", trade, trade.trail_sl)
                    return "TRAIL_STOP", trade.trail_sl
            else:
                new_trail = current_price + trade.atr * 0.8
                if new_trail < trade.trail_sl:
                    trade.trail_sl   = new_trail
                    trade.current_sl = new_trail
                    logger.debug("Trail down %s → %.4f", trade.symbol, new_trail)
                if adverse_price >= trade.trail_sl:
                    await self._notify("TRAIL_STOP", trade, trade.trail_sl)
                    return "TRAIL_STOP", trade.trail_sl

        return None, 0.0

    async def _notify(self, reason: str, trade: ActiveTrade, price: float) -> None:
        """Send Telegram notification for exit event."""
        if not self._alerts:
            return

        pnl_pct = 0.0
        if trade.sl_dist > 0:
            if trade.direction == "LONG":
                pnl_pct = (price - trade.entry_price) / trade.entry_price * 100
            else:
                pnl_pct = (trade.entry_price - price) / trade.entry_price * 100

        emoji_map = {
            "SL":         "🔴",
            "TP":         "🟢",
            "PARTIAL_TP": "🟡",
            "TRAIL_STOP": "🟠",
            "BREAKEVEN":  "🔵",
        }
        emoji = emoji_map.get(reason, "⚪")

        if reason == "BREAKEVEN":
            msg = (
                f"{emoji} *BREAKEVEN* — {trade.symbol}\n"
                f"SL moved to entry `{trade.entry_price:.4f}`\n"
                f"Trade protected ✅"
            )
        elif reason == "PARTIAL_TP":
            msg = (
                f"{emoji} *PARTIAL TP* — {trade.symbol} {trade.direction}\n"
                f"50% closed at `{price:.4f}`\n"
                f"P&L so far: `{pnl_pct:+.2f}%`\n"
                f"Trailing stop now active 🔄"
            )
        elif reason == "TRAIL_STOP":
            msg = (
                f"{emoji} *TRAIL STOP* — {trade.symbol} {trade.direction}\n"
                f"Exit at `{price:.4f}`\n"
                f"P&L: `{pnl_pct:+.2f}%` | Open: {trade.candles_open} candles"
            )
        elif reason == "TP":
            msg = (
                f"{emoji} *FULL TP HIT* — {trade.symbol} {trade.direction}\n"
                f"Exit at `{price:.4f}`\n"
                f"P&L: `{pnl_pct:+.2f}%` ✅"
            )
        elif reason == "SL":
            msg = (
                f"{emoji} *STOP LOSS* — {trade.symbol} {trade.direction}\n"
                f"Exit at `{price:.4f}`\n"
                f"P&L: `{pnl_pct:+.2f}%`"
            )
        else:
            msg = f"{emoji} {reason} — {trade.symbol} @ {price:.4f}"

        try:
            await self._alerts.send_text(msg)
        except Exception as exc:
            logger.warning("Exit alert failed: %s", exc)
