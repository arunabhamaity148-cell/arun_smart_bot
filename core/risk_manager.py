"""
ARUNABHA RISK MANAGER v1.0
Simple SL/TP calculation + trade tracking
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, List
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
    max_holding_minutes: int = 90  # 1.5 hours max


class RiskManager:
    """
    Simple risk management:
    - Fixed 1.5% risk per trade
    - SL/TP based on ATR
    - 90 min max holding
    - Daily limit tracking
    """
    
    def __init__(self):
        self.active_trades: Dict[str, Trade] = {}
        self.daily_stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total": 0,
            "wins": 0,
            "losses": 0,
            "pnl_pct": 0.0
        }
        
    def calculate_position(self,
                         account_size: float,
                         entry: float,
                         stop_loss: float) -> Dict[str, float]:
        """
        Calculate position size based on 1.5% risk
        """
        risk_amount = account_size * (config.RISK_PCT / 100)
        sl_distance = abs(entry - stop_loss)
        sl_distance_pct = sl_distance / entry
        
        if sl_distance_pct == 0:
            return {}
            
        # Position size = Risk / SL%
        position_usd = risk_amount / sl_distance_pct
        
        # Cap at leverage limit
        max_position = account_size * config.LEVERAGE
        position_usd = min(position_usd, max_position)
        
        contracts = position_usd / entry
        
        return {
            "risk_usd": risk_amount,
            "position_usd": position_usd,
            "contracts": contracts,
            "leverage": config.LEVERAGE,
            "sl_distance_pct": sl_distance_pct * 100
        }
    
    def calculate_sl_tp(self,
                       direction: str,
                       entry: float,
                       atr: float) -> Dict[str, float]:
        """
        Calculate SL and TP based on ATR
        """
        if direction == "LONG":
            sl = entry - (atr * config.ATR_SL_MULT)
            tp = entry + (atr * config.ATR_TP_MULT)
        else:
            sl = entry + (atr * config.ATR_SL_MULT)
            tp = entry - (atr * config.ATR_TP_MULT)
            
        rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
        
        return {
            "stop_loss": sl,
            "take_profit": tp,
            "rr_ratio": rr
        }
    
    def can_trade(self, symbol: str) -> bool:
        """
        Check if we can take new trade
        """
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
    
    def open_trade(self, trade: Trade):
        """Track new trade"""
        self.active_trades[trade.symbol] = trade
        self.daily_stats["total"] += 1
        logger.info("Trade opened: %s %s @ %.2f", 
                   trade.symbol, trade.direction, trade.entry)
    
    def close_trade(self, symbol: str, exit_price: float, reason: str):
        """Close trade and update stats"""
        if symbol not in self.active_trades:
            return
            
        trade = self.active_trades.pop(symbol)
        
        # Calculate PnL
        if trade.direction == "LONG":
            pnl_pct = (exit_price - trade.entry) / trade.entry * 100
        else:
            pnl_pct = (trade.entry - exit_price) / trade.entry * 100
            
        self.daily_stats["pnl_pct"] += pnl_pct
        
        if pnl_pct > 0:
            self.daily_stats["wins"] += 1
        else:
            self.daily_stats["losses"] += 1
            
        logger.info("Trade closed: %s @ %.2f | PnL: %.2f%% | Reason: %s",
                   symbol, exit_price, pnl_pct, reason)
        
        return pnl_pct
    
    def check_timeouts(self, current_prices: Dict[str, float]) -> List[str]:
        """
        Check for trades held too long
        """
        timed_out = []
        now = datetime.now()
        
        for symbol, trade in list(self.active_trades.items()):
            held_minutes = (now - trade.timestamp).total_seconds() / 60
            
            if held_minutes > trade.max_holding_minutes:
                # Close at current price
                if symbol in current_prices:
                    self.close_trade(symbol, current_prices[symbol], "TIMEOUT")
                    timed_out.append(symbol)
                    
        return timed_out
    
    def get_stats(self) -> Dict:
        """Return current stats"""
        total_closed = self.daily_stats["wins"] + self.daily_stats["losses"]
        win_rate = (self.daily_stats["wins"] / total_closed * 100) if total_closed > 0 else 0
        
        return {
            **self.daily_stats,
            "active_trades": len(self.active_trades),
            "win_rate": win_rate,
            "symbols_active": list(self.active_trades.keys())
        }
    
    def reset_daily(self):
        """Reset for new day"""
        self.daily_stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total": 0,
            "wins": 0,
            "losses": 0,
            "pnl_pct": 0.0
        }
        self.active_trades.clear()
