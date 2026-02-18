"""
ARUNABHA RISK MANAGER v3.0
Institutional capital protection with hard locks
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple  # 🆕 ADDED Tuple import
from datetime import datetime

import config

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    size_usd: float
    timestamp: datetime
    max_holding_minutes: int = 90
    # 🆕 Tracking fields
    partial_exited: bool = False
    be_triggered: bool = False
    sl_count_toward_lock: bool = True  # Count this trade for day lock


class RiskManager:
    """
    Institutional-grade risk management with hard locks.
    Issue V: Capital protection layer.
    """
    
    # 🆕 ISSUE V: HARD LOCK THRESHOLDS
    MAX_CONSECUTIVE_SL = 2
    MAX_DAILY_DRAWDOWN_PCT = -2.0
    PARTIAL_EXIT_R = 1.0
    BREAK_EVEN_TRIGGER_PCT = 0.5
    
    def __init__(self):
        self.active_trades: Dict[str, Trade] = {}
        self.daily_stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total": 0,
            "wins": 0,
            "losses": 0,
            "pnl_pct": 0.0,
            "consecutive_sl": 0,  # 🆕 Track consecutive SL
            "day_locked": False,   # 🆕 Day lock flag
            "lock_reason": None
        }
        self.trade_history: List[Dict] = []  # 🆕 For tracking
    
    def check_day_lock(self) -> Tuple[bool, Optional[str]]:
        """
        🆕 ISSUE V: Check if day is locked before trading.
        Returns: (is_locked, reason)
        """
        # Check existing lock
        if self.daily_stats["day_locked"]:
            return True, self.daily_stats["lock_reason"]
        
        # Check drawdown lock
        if self.daily_stats["pnl_pct"] <= self.MAX_DAILY_DRAWDOWN_PCT:
            self.daily_stats["day_locked"] = True
            self.daily_stats["lock_reason"] = f"Drawdown {self.daily_stats['pnl_pct']:.2f}% <= {self.MAX_DAILY_DRAWDOWN_PCT}%"
            logger.error("[RISK LOCK] Day locked: %s", self.daily_stats["lock_reason"])
            return True, self.daily_stats["lock_reason"]
        
        # Check consecutive SL lock
        if self.daily_stats["consecutive_sl"] >= self.MAX_CONSECUTIVE_SL:
            self.daily_stats["day_locked"] = True
            self.daily_stats["lock_reason"] = f"{self.daily_stats['consecutive_sl']} consecutive SL"
            logger.error("[RISK LOCK] Day locked: %s", self.daily_stats["lock_reason"])
            return True, self.daily_stats["lock_reason"]
        
        return False, None
    
    def can_trade(self, symbol: str) -> bool:
        """
        🆕 Enhanced with day lock check.
        """
        # Check day lock first (Issue V)
        is_locked, reason = self.check_day_lock()
        if is_locked:
            logger.warning("[RISK] Trade blocked: Day locked - %s", reason)
            return False
        
        # Daily limit
        if self.daily_stats["total"] >= config.MAX_SIGNALS_DAY:
            logger.info("Daily limit reached: %d/%d", 
                       self.daily_stats["total"], config.MAX_SIGNALS_DAY)
            return False
            
        # Concurrent limit
        if len(self.active_trades) >= config.MAX_CONCURRENT:
            logger.info("Max concurrent: %d/%d", 
                       len(self.active_trades), config.MAX_CONCURRENT)
            return False
            
        # Already active on this symbol
        if symbol in self.active_trades:
            return False
            
        return True
    
    def calculate_position(self,
                         account_size: float,
                         entry: float,
                         stop_loss: float,
                         atr_pct: float = 1.0) -> Dict[str, float]:
        """
        🆕 ISSUE IV: Volatility-adjusted position sizing.
        """
        risk_amount = account_size * (config.RISK_PCT / 100)
        sl_distance = abs(entry - stop_loss)
        sl_distance_pct = sl_distance / entry
        
        if sl_distance_pct == 0:
            return {}
        
        # Base position
        position_usd = risk_amount / sl_distance_pct
        
        # 🆕 ISSUE IV: Volatility compression
        # ATR > 3% → BLOCK (return empty = block)
        if atr_pct > 3.0:
            logger.warning("[RISK] Position blocked: ATR %.2f%% > 3%%", atr_pct)
            return {"blocked": True, "reason": f"ATR {atr_pct:.2f}% too high"}
        
        # ATR 2-3% → Reduce 50%
        if 2.0 <= atr_pct <= 3.0:
            position_usd *= 0.5
            logger.info("[RISK] Position reduced 50%%: ATR %.2f%%", atr_pct)
        
        # ATR < 0.4% → Avoid (reduce 30%)
        if atr_pct < 0.4:
            position_usd *= 0.7
            logger.info("[RISK] Position reduced 30%%: ATR %.2f%% low", atr_pct)
        
        # Cap at leverage limit
        max_position = account_size * config.LEVERAGE
        position_usd = min(position_usd, max_position)
        
        contracts = position_usd / entry
        
        return {
            "risk_usd": risk_amount,
            "position_usd": position_usd,
            "contracts": contracts,
            "leverage": config.LEVERAGE,
            "sl_distance_pct": sl_distance_pct * 100,
            "atr_pct": atr_pct,
            "vol_adjusted": True
        }
    
    def calculate_sl_tp(self,
                       direction: str,
                       entry: float,
                       atr: float,
                       trade_mode: str = "TREND") -> Dict[str, float]:
        """
        🆕 ISSUE IV: Choppy mode TP compression.
        """
        if direction == "LONG":
            sl = entry - (atr * config.ATR_SL_MULT)
            tp = entry + (atr * config.ATR_TP_MULT)
        else:
            sl = entry + (atr * config.ATR_SL_MULT)
            tp = entry - (atr * config.ATR_TP_MULT)
        
        # 🆕 ISSUE IV: Choppy mode → compress TP to 0.6-1.1%
        if trade_mode == "CHOPPY":
            # Override TP for choppy mode
            if direction == "LONG":
                tp = entry * 1.008  # 0.8% target
            else:
                tp = entry * 0.992  # 0.8% target
            
            # Tighter SL in choppy
            sl_distance = abs(entry - sl)
            sl = entry - (sl_distance * 0.8) if direction == "LONG" else entry + (sl_distance * 0.8)
            
            logger.info("[RISK] CHOPPY mode: TP compressed to %.2f, SL tightened", tp)
        
        rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
        
        return {
            "stop_loss": sl,
            "take_profit": tp,
            "rr_ratio": rr,
            "mode": trade_mode
        }
    
    def open_trade(self, trade: Trade):
        """Track new trade."""
        if trade.symbol in self.active_trades:
            logger.warning("Trade already exists for %s", trade.symbol)
            return False
        
        # Check day lock
        is_locked, reason = self.check_day_lock()
        if is_locked:
            logger.error("Cannot open trade: Day locked - %s", reason)
            return False
        
        self.active_trades[trade.symbol] = trade
        self.daily_stats["total"] += 1
        
        logger.info("[RISK] Trade opened: %s %s @ %.2f | SL:%.2f | TP:%.2f",
                   trade.symbol, trade.direction, trade.entry, 
                   trade.stop_loss, trade.take_profit)
        
        return True
    
    def check_trade_management(self, symbol: str, current_price: float) -> Optional[str]:
        """
        🆕 ISSUE V: Active trade management.
        Returns action: "PARTIAL_EXIT", "BREAK_EVEN", "SL_HIT", "TP_HIT", None
        """
        if symbol not in self.active_trades:
            return None
        
        trade = self.active_trades[symbol]
        
        # Calculate current R
        if trade.direction == "LONG":
            r_distance = trade.entry - trade.stop_loss
            current_r = (current_price - trade.entry) / r_distance if r_distance != 0 else 0
        else:
            r_distance = trade.stop_loss - trade.entry
            current_r = (trade.entry - current_price) / r_distance if r_distance != 0 else 0
        
        # 🆕 1R → 70% partial exit mandatory
        if current_r >= 1.0 and not trade.partial_exited:
            trade.partial_exited = True
            logger.info("[RISK] PARTIAL_EXIT: %s at %.2fR (%.2f)", symbol, current_r, current_price)
            return "PARTIAL_EXIT"
        
        # 🆕 +0.5% → SL to break-even
        if current_r >= 0.5 and not trade.be_triggered:
            trade.be_triggered = True
            # Move SL to entry (break-even)
            trade.stop_loss = trade.entry
            logger.info("[RISK] BREAK_EVEN: %s SL moved to entry @ %.2f", symbol, current_price)
            return "BREAK_EVEN"
        
        # Check SL/TP
        if trade.direction == "LONG":
            if current_price <= trade.stop_loss:
                return "SL_HIT"
            if current_price >= trade.take_profit:
                return "TP_HIT"
        else:
            if current_price >= trade.stop_loss:
                return "SL_HIT"
            if current_price <= trade.take_profit:
                return "TP_HIT"
        
        return None
    
    def close_trade(self, symbol: str, exit_price: float, reason: str):
        """Close trade with PnL tracking."""
        if symbol not in self.active_trades:
            return None
        
        trade = self.active_trades.pop(symbol)
        
        # Calculate PnL
        if trade.direction == "LONG":
            pnl_pct = (exit_price - trade.entry) / trade.entry * 100
        else:
            pnl_pct = (trade.entry - exit_price) / trade.entry * 100
        
        self.daily_stats["pnl_pct"] += pnl_pct
        
        # 🆕 Track consecutive SL (Issue V)
        if pnl_pct < 0 and trade.sl_count_toward_lock:
            self.daily_stats["consecutive_sl"] += 1
            logger.warning("[RISK] SL #%d: %s @ %.2f%%", 
                        self.daily_stats["consecutive_sl"], symbol, pnl_pct)
        else:
            # Reset consecutive SL on win
            if pnl_pct > 0:
                if self.daily_stats["consecutive_sl"] > 0:
                    logger.info("[RISK] Consecutive SL reset after win")
                self.daily_stats["consecutive_sl"] = 0
        
        if pnl_pct > 0:
            self.daily_stats["wins"] += 1
        else:
            self.daily_stats["losses"] += 1
        
        # Record in history
        self.trade_history.append({
            "symbol": symbol,
            "direction": trade.direction,
            "entry": trade.entry,
            "exit": exit_price,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info("[RISK] Trade closed: %s @ %.2f | PnL: %.2f%% | Reason: %s",
                   symbol, exit_price, pnl_pct, reason)
        
        # 🆕 Check if day should lock after this trade
        self.check_day_lock()
        
        return pnl_pct
    
    def check_timeouts(self, current_prices: Dict[str, float]) -> List[str]:
        """Check for trades held too long."""
        timed_out = []
        now = datetime.now()
        
        for symbol, trade in list(self.active_trades.items()):
            held_minutes = (now - trade.timestamp).total_seconds() / 60
            
            if held_minutes > trade.max_holding_minutes:
                if symbol in current_prices:
                    self.close_trade(symbol, current_prices[symbol], "TIMEOUT")
                    timed_out.append(symbol)
        
        return timed_out
    
    def get_stats(self) -> Dict:
        """Return current stats with lock status."""
        total_closed = self.daily_stats["wins"] + self.daily_stats["losses"]
        win_rate = (self.daily_stats["wins"] / total_closed * 100) if total_closed > 0 else 0
        
        return {
            **self.daily_stats,
            "active_trades": len(self.active_trades),
            "win_rate": win_rate,
            "symbols_active": list(self.active_trades.keys()),
            "day_locked": self.daily_stats["day_locked"],
            "lock_reason": self.daily_stats["lock_reason"]
        }
    
    def reset_daily(self):
        """Reset for new day."""
        self.daily_stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total": 0,
            "wins": 0,
            "losses": 0,
            "pnl_pct": 0.0,
            "consecutive_sl": 0,
            "day_locked": False,
            "lock_reason": None
        }
        self.active_trades.clear()
        self.trade_history.clear()
        logger.info("[RISK] Daily reset complete")


# Global instance
risk_manager = RiskManager()
