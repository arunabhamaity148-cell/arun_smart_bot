"""
ARUNABHA FINAL v4.0 - ADAPTIVE ENGINE
Changes parameters based on market type
"""

import logging
from typing import Dict, Any, Optional
from config import MARKET_CONFIGS

logger = logging.getLogger(__name__)

class AdaptiveEngine:
    def __init__(self):
        self.current_config = MARKET_CONFIGS["CHOPPY"]
        self.last_market = "CHOPPY"
    
    def update_for_market(self, market_type: str):
        """Update trading parameters based on market"""
        if market_type in MARKET_CONFIGS:
            self.current_config = MARKET_CONFIGS[market_type]
            self.last_market = market_type
            logger.info(f"[ADAPTIVE] Switched to {market_type} mode")
    
    def get_params(self, market_type: Optional[str] = None) -> Dict[str, Any]:
        """Get current parameters"""
        if market_type and market_type in MARKET_CONFIGS:
            return MARKET_CONFIGS[market_type]
        return self.current_config
    
    def should_trade(self, score: int, filters_passed: int, market_type: str) -> tuple[bool, str]:
        """Check if we should trade based on market conditions"""
        config = self.get_params(market_type)
        
        if score < config["min_score"]:
            return False, f"Score {score} < {config['min_score']} for {market_type}"
        
        if filters_passed < config["min_filters"]:
            return False, f"Filters {filters_passed} < {config['min_filters']} for {market_type}"
        
        return True, f"OK for {market_type}"
    
    def get_position_size(self, base_size: float, market_type: str) -> float:
        """Get market-adjusted position size"""
        config = self.get_params(market_type)
        return base_size * config.get("position_size", 1.0)
    
    def get_sl_tp(self, entry: float, atr: float, direction: str, market_type: str) -> Dict[str, float]:
        """Get market-adjusted SL and TP"""
        config = self.get_params(market_type)
        
        if direction == "LONG":
            sl = entry - (atr * config["sl_mult"])
            tp = entry + (atr * config["tp_mult"])
        else:
            sl = entry + (atr * config["sl_mult"])
            tp = entry - (atr * config["tp_mult"])
        
        rr = abs(tp - entry) / abs(entry - sl)
        
        return {
            "stop_loss": sl,
            "take_profit": tp,
            "rr_ratio": rr
        }

adaptive_engine = AdaptiveEngine()