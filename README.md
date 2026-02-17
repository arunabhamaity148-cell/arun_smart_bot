# ⚡ ARUNABHA SMART v10.0

> **"Simple robust rules beat complex overfitted models"**

একটি production-grade cryptocurrency trading signal bot যা manual trading-এর জন্য তৈরি। কোনো auto-execution নেই — bot শুধু signal দেয়, সিদ্ধান্ত আপনার।

---

## 🎯 Bot কী করে?

প্রতি ৫ মিনিটে ৬টি crypto pair scan করে এবং যখন সব condition মিলে যায়, তখন Telegram-এ একটি বিস্তারিত signal পাঠায়। Signal-এ থাকে:

- Entry price, Stop Loss, Take Profit
- R:R Ratio (Risk:Reward)
- Smart Money analysis (Order Block, FVG, Market Structure)
- Position size suggestion (কত টাকা লাগাবেন)

---

## 📊 Signal কীভাবে তৈরি হয়?

### ধাপ ১ — Core Rules (Simple & Robust)

```
LONG  সংকেত = RSI < 35  AND EMA9 > EMA21 AND Volume > 1.2× গড়
SHORT সংকেত = RSI > 65  AND EMA9 < EMA21 AND Volume > 1.2× গড়
```

এই তিনটি নিয়ম সবচেয়ে গুরুত্বপূর্ণ। সহজ কিন্তু battle-tested।

### ধাপ ২ — Smart Money Concept (SMC) Layer

| Factor | মানে কী |
|--------|---------|
| **Market Structure** | বাজার কি Higher High/HL (Bullish) নাকি LH/LL (Bearish)? |
| **Order Block** | বড় institution কোন price-এ buy/sell করেছিল? |
| **Fair Value Gap (FVG)** | বাজারে কোনো imbalance zone আছে কি? |
| **Premium/Discount Zone** | Price কি swing range-এর উপরে (Premium) নাকি নিচে (Discount)? |

LONG-এ Discount zone + Bullish OB = strongest entry।
SHORT-এ Premium zone + Bearish OB = strongest entry।

### ধাপ ৩ — Smart Filters (৬টি context filter, ৪টি pass করতে হবে)

| Filter | কী দেখে |
|--------|---------|
| 🕐 **Session** | Market কি active? Volume/volatility দিয়ে judge করে, clock দিয়ে নয় |
| 📊 **Orderflow** | Bid/Ask pressure কি signal-এর দিকে? |
| 💥 **Liquidation** | Price কি কোনো key level-এর কাছে? |
| ₿ **BTC Trend** | Bitcoin কি signal-এর বিরুদ্ধে যাচ্ছে? |
| 🔗 **Correlation** | Altcoin কি BTC থেকে independently move করছে? |
| 📈 **Volatility** | ATR কি trade-এর জন্য যথেষ্ট? |

### ধাপ ৪ — Signal Grade

| Grade | মানে |
|-------|------|
| ⭐⭐⭐ **A+** | সব filter + ৩+ SMC factor → সেরা signal |
| ⭐⭐ **A** | ৫+ filter + ২+ SMC → ভালো signal |
| ⭐ **B** | ৪ filter pass → acceptable signal |
| **C** | কোনোভাবে pass হয়েছে → caution নিন |

---

## 📱 Telegram Signal দেখতে কেমন?

```
⚡ ARUNABHA SMART v10.0

🟢 LONG  ETH/USDT  [15m]  ⭐⭐⭐ A+

┌─ ENTRY PLAN ──────────────────
│ 📍 Entry      3421.5000
│ 🛑 Stop Loss  3381.2000
│ 🎯 TP         3521.8000
│ 📐 R:R        2.49 : 1
└──────────────────────────────────

┌─ TECHNICALS ──────────────────
│ RSI 32.4  EMA9 3418.20  EMA21 3405.60
│ Volume 1.84× avg
└──────────────────────────────────

┌─ SMART MONEY (3/4) ────────
│ Structure BULLISH
│ Swing   Hi 3580.00  Lo 3350.00
│ Equilib   3465.00
│ Order Block 3415.00 — 3425.00
│ FVG Zone    3398.00 — 3410.00
└──────────────────────────────────

┌─ CONTEXT FILTERS (5/6) ─
│ 🕐✅  📊✅  💥✅  ₿✅  🔗✅  📈❌
└──────────────────────────────────

💼 Risk: 1.5%  ($15)  | Position: $2000  | 0.5851 contracts

⏱ 17 Feb 2026  21:45 IST
🚨 MANUAL EXECUTION — DO NOT AUTO-TRADE
```

---

## 🤖 Telegram Commands

| Command | কাজ |
|---------|-----|
| `/start` | Bot status দেখুন |
| `/status` | আজকের signal count |
| `/signals` | আজকের সব signals |

---

## ⚙️ Configuration (config.py)

| Setting | Default | মানে |
|---------|---------|------|
| `RSI_OVERSOLD` | 35 | LONG-এর RSI threshold |
| `RSI_OVERBOUGHT` | 65 | SHORT-এর RSI threshold |
| `ATR_SL_MULT` | 1.5× | Stop Loss = 1.5 × ATR |
| `ATR_TP_MULT` | 2.5× | Take Profit = 2.5 × ATR |
| `MIN_RR_RATIO` | 1.5 | Minimum risk:reward |
| `MIN_FILTERS_PASS` | 4 | ৬টির মধ্যে কতটা pass করতে হবে |
| `MAX_SIGNALS_DAY` | 6 | দিনে সর্বোচ্চ কতটা signal |
| `LEVERAGE` | 15x | Display only, bot trade করে না |
| `RISK_PCT_MIN/MAX` | 1–2% | Position size calculation |

---

## 🚀 Deploy on Railway

### Environment Variables

```bash
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
WEBHOOK_URL=https://your-app.up.railway.app
BINANCE_API_KEY=your_key
BINANCE_SECRET=your_secret
PRIMARY_EXCHANGE=binance
ACCOUNT_SIZE_USD=1000
SCAN_INTERVAL_SEC=300
```

### Steps
1. GitHub-এ push করুন
2. Railway → New Project → GitHub repo
3. Variables set করুন
4. Domain নিন → `WEBHOOK_URL` set করুন
5. `/health` endpoint check করুন

---

## 🛡️ Anti-Overfitting Design

| ❌ নেই | ✅ আছে |
|--------|--------|
| Machine Learning | Fixed simple rules |
| Daily retraining | Dynamic context only |
| Hyper-optimized params | Time-tested thresholds |
| Auto-execution | Human final decision |
| Complex indicators | RSI + EMA + Volume |

---

## 📈 কত marks দেব?

**Current Bot: 7/10**

| Area | Score | কারণ |
|------|-------|------|
| Core Signal Quality | 7/10 | RSI+EMA+Vol solid কিন্তু single-timeframe |
| Anti-overfitting | 9/10 | No ML, fixed rules |
| SMC Integration | 6/10 | Proxy SMC, real OB needs tick data |
| Risk Management | 8/10 | Dynamic sizing, clear SL/TP |
| Infrastructure | 9/10 | Railway, webhook, health check |

---

## 🔮 আরো কী যোগ করলে ভালো হবে?

### Signal Quality বাড়াতে:

1. **Multi-timeframe Confirmation (MTF)**
   - 1h structure + 15m entry + 5m trigger
   - এটা সবচেয়ে বড় upgrade হবে

2. **Volume Profile (VPOC)**
   - High Volume Node থেকে entry নিলে win rate বাড়ে

3. **Funding Rate Filter**
   - Binance funding rate > 0.1% → SHORT avoid করুন
   - ইতিমধ্যে `BinanceClient` এ method আছে

4. **ATR-adaptive RSI Thresholds**
   - High volatility market-এ RSI <30, >70 use করুন
   - Low volatility-তে <38, >62

5. **Open Interest Divergence**
   - Price up + OI down = fake breakout
   - Price down + OI up = real downtrend

6. **Backtesting Module**
   - Historical signal validation
   - Win rate tracking per pair

---

## ⚠️ Disclaimer

এই bot শুধু educational purpose-এ তৈরি। Crypto trading-এ capital loss হতে পারে। Bot-এর signal manual review করুন, auto-execute করবেন না।

---

*ARUNABHA SMART v10.0 — Built with ❤️ for disciplined trading*
