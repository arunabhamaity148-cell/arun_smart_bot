"""
vpoc_profile.py — ARUNABHA SMART v10.1
════════════════════════════════════════
Volume Profile & VPOC (Volume Point of Control)

What is VPOC?
  The price level where the most volume traded over a lookback window.
  Price tends to gravitate toward VPOC (magnetic effect) and also
  respect it as strong support/resistance once broken.

How we use it:
  • LONG entry: price near or just above VPOC → strong support floor
  • SHORT entry: price near or just below VPOC → strong resistance ceiling
  • "Near" = within VPOC_TOLERANCE_PCT% of VPOC

High Volume Nodes (HVN):
  Price levels with volume ≥ 70% of VPOC volume.
  Entry near any HVN = high confluence zone.

Low Volume Nodes (LVN):
  Price levels with volume ≤ 30% of VPOC volume.
  Price tends to move fast through LVNs (low resistance).
  Avoid entries in LVN zones.
"""

import logging
from typing import List, Dict, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)

# How close to VPOC/HVN price must be (as % of price)
VPOC_TOLERANCE_PCT = 0.5     # within 0.5%
HVN_THRESHOLD      = 0.70    # ≥70% of VPOC volume = High Volume Node
LVN_THRESHOLD      = 0.30    # ≤30% of VPOC volume = Low Volume Node
PROFILE_BINS       = 50      # number of price buckets for the profile


def build_volume_profile(
    ohlcv: List[List[float]],
    bins: int = PROFILE_BINS,
) -> Dict[str, float]:
    """
    Builds a volume profile from OHLCV data.

    Returns:
        {
          "vpoc":        float,   # price of max volume
          "vah":         float,   # Value Area High (70% of volume above VPOC)
          "val":         float,   # Value Area Low  (70% of volume below VPOC)
          "hvn_levels":  list,    # High Volume Node prices
          "lvn_levels":  list,    # Low Volume Node prices
          "bin_prices":  list,    # price center of each bin
          "bin_volumes": list,    # volume in each bin
        }
    """
    if not ohlcv or len(ohlcv) < 10:
        return _empty_profile()

    arr     = np.array(ohlcv, dtype=float)
    highs   = arr[:, 2]
    lows    = arr[:, 3]
    closes  = arr[:, 4]
    volumes = arr[:, 5]

    price_min = float(np.min(lows))
    price_max = float(np.max(highs))

    if price_max <= price_min:
        return _empty_profile()

    # Build price bins
    bin_edges  = np.linspace(price_min, price_max, bins + 1)
    bin_prices = [(bin_edges[i] + bin_edges[i+1]) / 2 for i in range(bins)]
    bin_vols   = np.zeros(bins)

    # Distribute each candle's volume across the bins it spans
    for i in range(len(ohlcv)):
        lo = lows[i]
        hi = highs[i]
        v  = volumes[i]

        # Find bins this candle spans
        lo_idx = max(0, int((lo - price_min) / (price_max - price_min) * bins))
        hi_idx = min(bins - 1, int((hi - price_min) / (price_max - price_min) * bins))

        span = hi_idx - lo_idx + 1
        if span > 0:
            bin_vols[lo_idx:hi_idx + 1] += v / span

    # VPOC = bin with highest volume
    vpoc_idx = int(np.argmax(bin_vols))
    vpoc     = float(bin_prices[vpoc_idx])
    max_vol  = float(bin_vols[vpoc_idx])

    # HVN / LVN
    hvn_levels = [float(bin_prices[i]) for i in range(bins)
                  if bin_vols[i] >= max_vol * HVN_THRESHOLD]
    lvn_levels = [float(bin_prices[i]) for i in range(bins)
                  if bin_vols[i] <= max_vol * LVN_THRESHOLD]

    # Value Area (70% of total volume centered on VPOC)
    total_vol     = float(np.sum(bin_vols))
    target_vol    = total_vol * 0.70
    va_vol        = float(bin_vols[vpoc_idx])
    lo_ptr, hi_ptr = vpoc_idx, vpoc_idx

    while va_vol < target_vol and (lo_ptr > 0 or hi_ptr < bins - 1):
        add_lo = float(bin_vols[lo_ptr - 1]) if lo_ptr > 0 else 0.0
        add_hi = float(bin_vols[hi_ptr + 1]) if hi_ptr < bins - 1 else 0.0
        if add_lo >= add_hi and lo_ptr > 0:
            lo_ptr -= 1
            va_vol += add_lo
        elif hi_ptr < bins - 1:
            hi_ptr += 1
            va_vol += add_hi
        else:
            break

    vah = float(bin_prices[hi_ptr])
    val = float(bin_prices[lo_ptr])

    logger.debug(
        "Volume Profile: VPOC=%.4f VAH=%.4f VAL=%.4f HVNs=%d LVNs=%d",
        vpoc, vah, val, len(hvn_levels), len(lvn_levels),
    )

    return {
        "vpoc":        vpoc,
        "vah":         vah,
        "val":         val,
        "hvn_levels":  hvn_levels,
        "lvn_levels":  lvn_levels,
        "bin_prices":  [float(p) for p in bin_prices],
        "bin_volumes": [float(v) for v in bin_vols],
    }


def _empty_profile() -> Dict:
    return {
        "vpoc": 0.0, "vah": 0.0, "val": 0.0,
        "hvn_levels": [], "lvn_levels": [],
        "bin_prices": [], "bin_volumes": [],
    }


def near_vpoc(profile: Dict, price: float) -> bool:
    """True if price is within VPOC_TOLERANCE_PCT% of VPOC."""
    vpoc = profile.get("vpoc", 0.0)
    if vpoc <= 0:
        return False
    return abs(price - vpoc) / vpoc * 100 <= VPOC_TOLERANCE_PCT


def near_hvn(profile: Dict, price: float) -> bool:
    """True if price is near any High Volume Node."""
    for hvn in profile.get("hvn_levels", []):
        if hvn > 0 and abs(price - hvn) / hvn * 100 <= VPOC_TOLERANCE_PCT:
            return True
    return False


def in_lvn(profile: Dict, price: float) -> bool:
    """True if price is in a Low Volume Node (avoid entries here)."""
    for lvn in profile.get("lvn_levels", []):
        if lvn > 0 and abs(price - lvn) / lvn * 100 <= VPOC_TOLERANCE_PCT * 0.5:
            return True
    return False


def vpoc_confirms(
    direction: str,
    entry: float,
    profile: Dict,
) -> Tuple[bool, str]:
    """
    Full VPOC confluence check.

    LONG:
      • Entry near VPOC or HVN → strong support → PASS
      • Entry in LVN → no support → FAIL
      • Entry below VAL → outside value area → FAIL

    SHORT:
      • Entry near VPOC or HVN → strong resistance → PASS
      • Entry in LVN → no resistance → FAIL
      • Entry above VAH → outside value area → FAIL

    Returns (passes: bool, reason: str)
    """
    if not profile or profile.get("vpoc", 0) <= 0:
        return True, "No profile data (neutral)"   # don't penalize missing data

    vpoc = profile["vpoc"]
    vah  = profile["vah"]
    val  = profile["val"]

    is_near_vpoc = near_vpoc(profile, entry)
    is_near_hvn  = near_hvn(profile, entry)
    is_in_lvn    = in_lvn(profile, entry)

    if direction == "LONG":
        if is_in_lvn:
            return False, f"LVN zone (no floor) VPOC={vpoc:.4f}"
        if entry < val * 0.998:
            return False, f"Below Value Area Low={val:.4f}"
        if is_near_vpoc or is_near_hvn:
            return True, f"Near HVN/VPOC={vpoc:.4f} ✓"
        return True, f"Inside Value Area [{val:.4f}–{vah:.4f}]"

    else:  # SHORT
        if is_in_lvn:
            return False, f"LVN zone (no ceiling) VPOC={vpoc:.4f}"
        if entry > vah * 1.002:
            return False, f"Above Value Area High={vah:.4f}"
        if is_near_vpoc or is_near_hvn:
            return True, f"Near HVN/VPOC={vpoc:.4f} ✓"
        return True, f"Inside Value Area [{val:.4f}–{vah:.4f}]"


def vpoc_label(profile: Dict, price: float) -> str:
    """Short label for Telegram alerts."""
    vpoc = profile.get("vpoc", 0)
    if vpoc <= 0:
        return ""
    dist_pct = (price - vpoc) / vpoc * 100
    return f"📊 VPOC: {vpoc:.4f} ({dist_pct:+.2f}%)"
