# 🔥 ARUNABHA SURGICAL EXECUTION ENGINE v3.0

Institutional-Grade Crypto Futures Decision Support System  
Designed for disciplined, capital-protected manual trading.

---

## 📌 Overview

ARUNABHA v3.0 একটি **Surgical Execution Engine**  
যা crypto futures market-এ high-quality signal generate করে  
কিন্তু auto-trade করে না।

এটি একটি **Decision Support System** —  
Manual execution ভিত্তিক।

Core Philosophy:

- Capital First
- Discipline Over Frequency
- Regime-Controlled Execution
- No Emotional Trading

---

## 🧠 System Architecture

Execution Order (Non-Negotiable):

1️⃣ BTC Regime Gatekeeper  
2️⃣ Volatility Compression Check  
3️⃣ Structure Confirmation (BOS / CHoCH Mandatory)  
4️⃣ Score Validation  
5️⃣ Risk Manager Approval  
6️⃣ Signal Finalization  

---

## 📂 Core Modules

### 1️⃣ btc_regime_detector.py
- Multi-timeframe EMA stack analysis
- Market structure evaluation
- Momentum & volatility scoring
- Hard override logic
- Confidence <45% → HARD BLOCK
- Regime CHANGING → BLOCK

---

### 2️⃣ extreme_fear_engine.py
- BOS / CHoCH candle close validation
- Strict structure confirmation
- Score discipline enforced
- Choppy mode higher threshold
- Weak structure → BLOCK

---

### 3️⃣ risk_manager.py
Institutional Capital Protection Layer:

- 2 Consecutive SL → Day Lock
- -2% Daily Drawdown → Auto Halt
- 1R → 70% Partial Exit
- +0.5% Move → SL to Break-Even
- ATR > 3% → Trade Block
- ATR 2–3% → Position Reduce 50%

---

### 4️⃣ smart_signal.py
Strict Execution Order Enforcement:

Regime → Volatility → Structure → Score → Risk → Signal

No shortcut allowed.

---

## 🛡 Capital Protection Rules

- Maximum Risk per Trade: config controlled
- No trade without structure confirmation
- No trade in unstable regime
- No trade during extreme volatility
- Overtrading prevention built-in
- Daily lock system active

---

## ⚙️ Configuration Required

Ensure `config.py` contains:

- MIN_RR_RATIO
- ATR_SL_MULT
- ATR_TP_MULT
- RISK_PCT
- LEVERAGE
- MAX_SIGNALS_DAY
- MAX_CONCURRENT
- ENTRY_CONFIRMATION_WAIT

---

## 🚀 How It Works

1. BTC regime analyzed first (Gatekeeper)
2. Market volatility checked
3. Structure validated strictly
4. Score calculated and graded
5. Risk manager approves
6. Telegram signal sent

⚠️ Exchange order is NOT placed automatically.

Manual execution required.

---

## 📊 Expected Behavior

### Strong Trend Day
- 3–6 High quality signals
- 60–70% win probability zone
- Controlled drawdown

### Choppy Day
- 0–3 signals
- Strict filtering
- Reduced position size

### Extreme Volatility
- Mostly blocked
- Capital preserved

---

## ❌ What This Bot Does NOT Do

- Does not auto-trade
- Does not chase breakouts blindly
- Does not ignore regime conditions
- Does not allow revenge trading
- Does not allow unlimited losses

---

## 🔒 Safety Features

- Hard regime override
- Strict structure validation
- Volatility compression
- Consecutive SL lock
- Daily drawdown halt
- Break-even auto management
- Partial profit locking

---

## 🎯 Objective

Create a disciplined institutional-style trading engine  
that survives long-term and protects capital  
instead of gambling for short-term gains.

---

## ⚠️ Disclaimer

This system is for educational and decision-support purposes only.  
Trading involves risk.  
User is responsible for all execution decisions.

---

## 👤 Author

ARUNABHA – Hybrid Manual Trader  
System Version: 3.0 (Surgical Execution Engine)

---

🔥 Trade Less. Trade Smart. Protect Capital.